"""
Live chart callbacks — reads from the WebSocket feed (data/ws_feed.py)
instead of polling Binance REST on every interval.

WebSocket pattern follows the course scripts:
  - week_05/9_async_websocket_ans.py  (websockets.connect + async for)
  - week_06/6_strategy_gateway_ans.py (background thread event loop)

The STORE dict in ws_feed.py is updated continuously by the background
WebSocket thread. Callbacks here just read the latest snapshot.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import json
import urllib.request

import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State

import data.ws_feed as ws_feed
from data.database import get_recent_signals
from strategy.indicators import macd as compute_macd


_DARK = dict(template="plotly_dark", paper_bgcolor="#1e2130", plot_bgcolor="#1e2130")


def _empty_fig():
    fig = go.Figure()
    fig.update_layout(**_DARK, margin=dict(l=10, r=10, t=10, b=10))
    return fig


def _fetch_candles(limit: int = 60, interval: str = "1m") -> pd.DataFrame:
    """Fetch recent OHLCV from Binance REST for the given interval."""
    url = f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval={interval}&limit={limit}"
    with urllib.request.urlopen(url, timeout=8) as r:
        data = json.loads(r.read())
    rows = [{
        "timestamp": pd.Timestamp(k[0], unit="ms", tz="UTC"),
        "open":   float(k[1]),
        "high":   float(k[2]),
        "low":    float(k[3]),
        "close":  float(k[4]),
        "volume": float(k[5]),
    } for k in data]
    df = pd.DataFrame(rows).set_index("timestamp")
    return df


def _load_config():
    import yaml
    with open(Path(__file__).parent.parent.parent / "config" / "config.yaml") as f:
        return yaml.safe_load(f)


def register(app):
    cfg = _load_config()

    # ------------------------------------------------------------------ #
    #  Persist selected interval in dcc.Store                             #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("selected-interval",  "data"),
        Output("interval-1m",        "color"),
        Output("interval-1m",        "outline"),
        Output("interval-5m",        "color"),
        Output("interval-5m",        "outline"),
        Input("interval-1m",         "n_clicks"),
        Input("interval-5m",         "n_clicks"),
        State("selected-interval",   "data"),
        prevent_initial_call=True,
    )
    def set_interval(n1m, n5m, current):
        from dash import ctx
        chosen = "5m" if ctx.triggered_id == "interval-5m" else "1m"
        if chosen == "5m":
            return "5m", "secondary", True,  "primary", False
        return "1m", "primary", False, "secondary", True

    # ------------------------------------------------------------------ #
    #  Live price header — reads from WebSocket STORE                     #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("live-price",     "children"),
        Output("live-price",     "style"),
        Output("live-change",    "children"),
        Output("live-change",    "style"),
        Output("live-high",      "children"),
        Output("live-low",       "children"),
        Output("live-volume",    "children"),
        Output("live-timestamp", "children"),
        Input("live-refresh",    "n_intervals"),
    )
    def update_ticker(_):
        s = ws_feed.STORE
        price  = s.get("price")
        change = s.get("change_pct")

        if price is None:
            dash_style = {"fontSize": "1.6rem", "fontWeight": "700", "color": "#585b70"}
            status = "Connecting…" if not ws_feed.is_connected() else "—"
            return status, dash_style, "", {}, "—", "—", "—", "—"

        price_color = "#a6e3a1" if change >= 0 else "#f38ba8"
        change_str  = f"{'▲' if change >= 0 else '▼'} {abs(change):.2f}%"

        return (
            f"${price:,.2f}",
            {"fontSize": "1.6rem", "fontWeight": "700", "color": price_color},
            change_str,
            {"color": price_color, "fontWeight": "600"},
            f"${s.get('high_24h', 0):,.2f}",
            f"${s.get('low_24h', 0):,.2f}",
            f"{s.get('volume_24h', 0):,.0f} BTC",
            s.get("updated_at") or "—",
        )

    # ------------------------------------------------------------------ #
    #  Candlestick — REST fetch + live WS candle appended               #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("chart-candle",       "figure"),
        Output("chart-title",        "children"),
        Input("live-refresh",        "n_intervals"),
        Input("interval-1m",         "n_clicks"),
        Input("interval-5m",         "n_clicks"),
        Input("range-1h",            "n_clicks"),
        Input("range-4h",            "n_clicks"),
        Input("range-8h",            "n_clicks"),
        Input("range-1d",            "n_clicks"),
        State("selected-interval",   "data"),
    )
    def update_candles(_, i1m, i5m, r1h, r4h, r8h, r1d, stored_interval):
        from dash import ctx

        # Use the interval button that was just clicked, or fall back to stored state
        if ctx.triggered_id == "interval-1m":
            interval = "1m"
        elif ctx.triggered_id == "interval-5m":
            interval = "5m"
        else:
            interval = stored_interval or "1m"

        # Bars per range for each interval
        range_map = {
            "1m": {"range-1h": 60,  "range-4h": 240, "range-8h": 480,  "range-1d": 1440},
            "5m": {"range-1h": 12,  "range-4h": 48,  "range-8h": 96,   "range-1d": 288},
        }
        limit = range_map[interval].get(ctx.triggered_id, range_map[interval]["range-1h"])

        chart_title = f"BTC/USDT — {interval} Candlestick"

        try:
            df = _fetch_candles(limit=min(limit + 1, 1000), interval=interval)
        except Exception:
            return _empty_fig(), chart_title

        if df.empty:
            return _empty_fig(), chart_title

        # Replace or append the current live candle from WebSocket
        ws_key = "candle_5m" if interval == "5m" else "candle_1m"
        live_candle = ws_feed.STORE.get(ws_key, {})
        freq = "5min" if interval == "5m" else "min"
        if live_candle.get("close") is not None:
            now_floored = pd.Timestamp.now(tz="UTC").floor(freq)
            live_row = pd.DataFrame([{
                "open":   live_candle["open"],
                "high":   live_candle["high"],
                "low":    live_candle["low"],
                "close":  live_candle["close"],
                "volume": live_candle["volume"],
            }], index=[now_floored])
            if now_floored in df.index:
                df.loc[now_floored] = live_row.iloc[0]
            else:
                df = pd.concat([df, live_row])

        df = df.tail(limit)

        # Open position levels for reference lines
        from data.database import get_open_position
        open_pos = get_open_position()

        fig = go.Figure()

        # Candlestick
        fig.add_trace(go.Candlestick(
            x=df.index,
            open=df["open"], high=df["high"],
            low=df["low"],   close=df["close"],
            name="BTC/USDT",
            increasing_line_color="#a6e3a1",
            decreasing_line_color="#f38ba8",
            increasing_fillcolor="#a6e3a1",
            decreasing_fillcolor="#f38ba8",
        ))

        # Volume as bar trace on secondary y-axis
        vol_colors = ["#a6e3a161" if c >= o else "#f38ba861"
                      for o, c in zip(df["open"], df["close"])]
        fig.add_trace(go.Bar(
            x=df.index, y=df["volume"],
            name="Volume", marker_color=vol_colors,
            yaxis="y2", showlegend=False,
        ))

        # Entry and stop lines if there's an open position
        if open_pos:
            entry = open_pos.get("fill_price")
            stop  = open_pos.get("stop_price")
            side  = open_pos.get("side", "")
            if entry:
                fig.add_hline(y=entry, line_color="#89b4fa", line_dash="dash", line_width=1,
                              annotation_text=f"Entry ${entry:,.0f}", annotation_position="right",
                              annotation_font_color="#89b4fa")
            if stop:
                fig.add_hline(y=stop, line_color="#f38ba8", line_dash="dot", line_width=1,
                              annotation_text=f"Stop ${stop:,.0f}", annotation_position="right",
                              annotation_font_color="#f38ba8")

        # Highlight the most recent (live) bar
        if len(df):
            last_ts = df.index[-1]
            fig.add_vrect(
                x0=last_ts, x1=last_ts,
                fillcolor="#89b4fa", opacity=0.12,
                layer="below", line_width=1, line_color="#89b4fa",
                annotation_text="Live", annotation_position="top left",
                annotation_font_color="#89b4fa", annotation_font_size=10,
            )

        conn_dot = "🟢" if ws_feed.is_connected() else "🔴"
        fig.update_layout(
            title=dict(text=f"{conn_dot} BTC/USDT — {interval}", font=dict(size=12, color="#a6adc8")),
            template="plotly_dark",
            paper_bgcolor="#1e2130",
            plot_bgcolor="#1e2130",
            xaxis_rangeslider_visible=False,
            margin=dict(l=10, r=10, t=36, b=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
            hovermode="x unified",
            yaxis=dict(showgrid=True, gridcolor="#2a2d3e", tickprefix="$", domain=[0.25, 1]),
            yaxis2=dict(showgrid=False, domain=[0, 0.22], showticklabels=False),
            xaxis=dict(showgrid=True, gridcolor="#2a2d3e", showspikes=True),
        )
        return fig, chart_title

    # ------------------------------------------------------------------ #
    #  MACD sub-panel (computed on selected interval bars)                #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("chart-macd-panel",   "figure"),
        Input("live-refresh",        "n_intervals"),
        Input("interval-1m",         "n_clicks"),
        Input("interval-5m",         "n_clicks"),
        Input("range-1h",            "n_clicks"),
        Input("range-4h",            "n_clicks"),
        Input("range-8h",            "n_clicks"),
        Input("range-1d",            "n_clicks"),
        State("selected-interval",   "data"),
    )
    def update_macd_panel(_, i1m, i5m, r1h, r4h, r8h, r1d, stored_interval):
        from dash import ctx

        if ctx.triggered_id == "interval-1m":
            interval = "1m"
        elif ctx.triggered_id == "interval-5m":
            interval = "5m"
        else:
            interval = stored_interval or "1m"

        range_map = {
            "1m": {"range-1h": 60,  "range-4h": 240, "range-8h": 480,  "range-1d": 1440},
            "5m": {"range-1h": 12,  "range-4h": 48,  "range-8h": 96,   "range-1d": 288},
        }
        limit = range_map[interval].get(ctx.triggered_id, range_map[interval]["range-1h"])

        try:
            # Fetch extra bars so MACD has enough history to warm up
            df = _fetch_candles(limit=min(limit + 60, 1000), interval=interval)
        except Exception:
            return _empty_fig()

        if df.empty:
            return _empty_fig()

        mf, ms, mg = cfg["macd"]["fast"], cfg["macd"]["slow"], cfg["macd"]["signal"]
        macd_df = compute_macd(df, fast=mf, slow=ms, signal=mg).tail(limit)

        colors = ["#a6e3a1" if v >= 0 else "#f38ba8" for v in macd_df["histogram"]]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=macd_df.index, y=macd_df["histogram"],
            name="Histogram", marker_color=colors, opacity=0.7,
        ))
        fig.add_trace(go.Scatter(
            x=macd_df.index, y=macd_df["macd_line"],
            name="MACD", line=dict(color="#89b4fa", width=1.5),
        ))
        fig.add_trace(go.Scatter(
            x=macd_df.index, y=macd_df["signal_line"],
            name="Signal", line=dict(color="#f38ba8", width=1.5, dash="dot"),
        ))
        fig.add_hline(y=0, line_color="#585b70", line_width=1)
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="#1e2130",
            plot_bgcolor="#1e2130",
            margin=dict(l=10, r=10, t=10, b=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.01, x=0),
            hovermode="x unified",
            xaxis=dict(showgrid=True, gridcolor="#2a2d3e"),
            yaxis=dict(showgrid=True, gridcolor="#2a2d3e"),
        )
        return fig

    # ------------------------------------------------------------------ #
    #  Signal card                                                         #
    # ------------------------------------------------------------------ #
    @app.callback(
        Output("live-signal",   "children"),
        Output("live-signal",   "style"),
        Output("live-pivot",    "children"),
        Output("live-macd-val", "children"),
        Output("live-sig-val",  "children"),
        Output("live-hist-val", "children"),
        Input("live-refresh",   "n_intervals"),
    )
    def update_live_signal(_):
        sigs = get_recent_signals(1)
        if not sigs:
            return "—", {}, "—", "—", "—", "—"
        s = sigs[0]
        color = {"LONG": "#a6e3a1", "SHORT": "#f38ba8", "HOLD": "#f9e2af"}.get(s["signal"], "#cdd6f4")
        return (
            s["signal"],
            {"color": color, "fontWeight": "700", "fontSize": "2rem"},
            s.get("pivot") or "None",
            f"{s.get('macd_line', 0):.2f}",
            f"{s.get('signal_line', 0):.2f}",
            f"{s.get('histogram', 0):.2f}",
        )
