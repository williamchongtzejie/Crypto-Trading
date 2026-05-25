import sys
import json
import threading
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from dash import Input, Output, State, dcc
import dash_bootstrap_components as dbc

from analysis.backtest import fetch_historical_ohlcv, run_backtest

# Cache so re-renders don't re-fetch from Binance
_cache: dict = {}


def register(app):

    @app.callback(
        Output("bt-results-store", "data"),
        Output("bt-status",        "children"),
        Input("bt-run",            "n_clicks"),
        State("bt-date-range",     "start_date"),
        State("bt-date-range",     "end_date"),
        State("bt-pivot-x",        "value"),
        State("bt-pivot-y",        "value"),
        State("bt-macd-fast",      "value"),
        State("bt-macd-slow",      "value"),
        State("bt-macd-signal",    "value"),
        State("bt-capital",        "value"),
        State("bt-risk",           "value"),
        prevent_initial_call=True,
    )
    def run(n, start_date, end_date, px, py, mf, ms, mg, capital, risk):
        try:
            # Fetch / use cached OHLCV
            if "df" not in _cache:
                df_full = fetch_historical_ohlcv()
                _cache["df"] = df_full
            else:
                df_full = _cache["df"]

            # Slice to selected date range
            df = df_full.loc[start_date:end_date].copy()
            if len(df) < 60:
                return None, dbc.Alert("Not enough data in selected range (minimum 60 bars).", color="warning")

            result = run_backtest(
                df,
                pivot_x=int(px or 4),
                pivot_y=int(py or 1),
                macd_fast=int(mf or 13),
                macd_slow=int(ms or 26),
                macd_signal=int(mg or 10),
                starting_capital=float(capital or 100_000),
                risk_per_trade=float(risk or 1) / 100,
            )

            m = result["metrics"]
            if not m:
                return None, dbc.Alert("No trades generated in this period.", color="warning")

            # Serialise equity series and trades for the Store
            payload = {
                "metrics": m,
                "trades":  result["trades"],
                "equity":  result["equity"].reset_index().rename(columns={"timestamp": "date", "equity": "val"}).to_dict("records"),
                "close":   df_full.loc[start_date:end_date, "close"].reset_index().rename(columns={"timestamp": "date", "close": "val"}).to_dict("records"),
            }
            status = dbc.Alert(
                f"Backtest complete — {m['total_trades']} trades over {m['years']:.1f} years  |  CAGR {m['cagr']:.1f}%  |  Sharpe {m['sharpe']:.2f}",
                color="success", className="py-1",
            )
            return json.dumps(payload, default=str), status

        except Exception as e:
            return None, dbc.Alert(f"Error: {e}", color="danger")

    # ── Populate metric cards ────────────────────────────────────────────
    @app.callback(
        Output("bt-net-profit",  "children"),
        Output("bt-mdd",         "children"),
        Output("bt-pf",          "children"),
        Output("bt-win-rate",    "children"),
        Output("bt-trades",      "children"),
        Output("bt-vs-bh",       "children"),
        Output("bt-sharpe",      "children"),
        Output("bt-sortino",     "children"),
        Output("bt-calmar",      "children"),
        Output("bt-cagr",        "children"),
        Output("bt-expectancy",  "children"),
        Output("bt-recovery",    "children"),
        Output("bt-turnover",    "children"),
        Output("bt-duration",    "children"),
        Output("bt-avg-win",     "children"),
        Output("bt-avg-loss",    "children"),
        Output("bt-best",        "children"),
        Output("bt-worst",       "children"),
        Input("bt-results-store", "data"),
        prevent_initial_call=True,
    )
    def update_metrics(raw):
        if not raw:
            return ["—"] * 18
        m = json.loads(raw)["metrics"]
        np_val = m["net_profit"]
        bh_diff = np_val - (m.get("bh_return", 0) / 100 * 100_000)
        return [
            f"${np_val:+,.0f}",
            f"{m['mdd_pct']:.2f}%  (${m['mdd_dollar']:,.0f})",
            f"{m['profit_factor']:.2f}",
            f"{m['win_rate']:.1f}%  ({m['winning_trades']}/{m['total_trades']})",
            str(m["total_trades"]),
            f"BH: {m['bh_return']:+.1f}%  /  {m['bh_cagr']:+.1f}% CAGR",
            f"{m['sharpe']:.3f}",
            f"{m['sortino']:.3f}",
            f"{m['calmar']:.3f}",
            f"{m['cagr']:+.2f}%",
            f"${m['expectancy']:+,.2f}",
            f"{m['recovery_factor']:.2f}×",
            f"{m['turnover']:.1f} / yr",
            f"{m['avg_duration']:.1f} days",
            f"${m['avg_win']:,.2f}",
            f"${m['avg_loss']:,.2f}",
            f"${m['best_trade']:+,.2f}",
            f"${m['worst_trade']:+,.2f}",
        ]

    # ── Equity chart ─────────────────────────────────────────────────────
    @app.callback(
        Output("bt-chart-equity", "figure"),
        Input("bt-results-store", "data"),
        prevent_initial_call=True,
    )
    def equity_chart(raw):
        if not raw:
            return go.Figure()
        data = json.loads(raw)
        eq  = pd.DataFrame(data["equity"])
        bh  = pd.DataFrame(data["close"])
        m   = data["metrics"]

        eq["date"] = pd.to_datetime(eq["date"])
        bh["date"] = pd.to_datetime(bh["date"])
        starting   = eq["val"].iloc[0]
        bh_norm    = starting * bh["val"] / bh["val"].iloc[0]

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=eq["date"], y=eq["val"],   name="Strategy",     line=dict(color="#a6e3a1", width=2)))
        fig.add_trace(go.Scatter(x=bh["date"], y=bh_norm,     name="Buy & Hold",   line=dict(color="#f9e2af", width=2, dash="dash")))
        fig.update_layout(
            template="plotly_dark", paper_bgcolor="#1e2130", plot_bgcolor="#1e2130",
            margin=dict(l=10, r=10, t=10, b=10),
            legend=dict(orientation="h", y=1.02, x=0),
            hovermode="x unified",
            yaxis=dict(tickprefix="$", showgrid=True, gridcolor="#2a2d3e"),
            xaxis=dict(showgrid=True, gridcolor="#2a2d3e"),
        )
        return fig

    # ── Drawdown chart ───────────────────────────────────────────────────
    @app.callback(
        Output("bt-chart-dd", "figure"),
        Input("bt-results-store", "data"),
        prevent_initial_call=True,
    )
    def dd_chart(raw):
        if not raw:
            return go.Figure()
        eq  = pd.DataFrame(json.loads(raw)["equity"])
        eq["date"] = pd.to_datetime(eq["date"])
        eq = eq.set_index("date")["val"]
        dd = ((eq - eq.cummax()) / eq.cummax() * 100)

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=dd.index, y=dd.values, fill="tozeroy",
                                  name="Drawdown %", line=dict(color="#f38ba8", width=1)))
        fig.update_layout(
            template="plotly_dark", paper_bgcolor="#1e2130", plot_bgcolor="#1e2130",
            margin=dict(l=10, r=10, t=10, b=10),
            yaxis=dict(ticksuffix="%", showgrid=True, gridcolor="#2a2d3e"),
            xaxis=dict(showgrid=True, gridcolor="#2a2d3e"),
            hovermode="x unified",
        )
        return fig

    # ── Monthly heatmap ──────────────────────────────────────────────────
    @app.callback(
        Output("bt-chart-monthly", "figure"),
        Input("bt-results-store",  "data"),
        prevent_initial_call=True,
    )
    def monthly_chart(raw):
        if not raw:
            return go.Figure()
        trades = json.loads(raw)["trades"]
        if not trades:
            return go.Figure()
        df = pd.DataFrame(trades)
        df["exit_date"] = pd.to_datetime(df["exit_date"])
        df["year"]  = df["exit_date"].dt.year
        df["month"] = df["exit_date"].dt.month
        pivot = df.groupby(["year", "month"])["pnl"].sum().unstack(fill_value=0)
        month_labels = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
        cols = [month_labels[m - 1] for m in pivot.columns]
        fig = px.imshow(pivot.values, x=cols, y=[str(y) for y in pivot.index],
                        color_continuous_scale="RdYlGn", color_continuous_midpoint=0,
                        text_auto=".0f")
        fig.update_layout(template="plotly_dark", paper_bgcolor="#1e2130",
                          margin=dict(l=10, r=10, t=10, b=10))
        return fig

    # ── Trade table ──────────────────────────────────────────────────────
    @app.callback(
        Output("bt-trade-table", "data"),
        Input("bt-results-store", "data"),
        prevent_initial_call=True,
    )
    def trade_table(raw):
        if not raw:
            return []
        return json.loads(raw)["trades"]

    # ── CSV export ───────────────────────────────────────────────────────
    @app.callback(
        Output("bt-download", "data"),
        Input("bt-export",    "n_clicks"),
        State("bt-results-store", "data"),
        prevent_initial_call=True,
    )
    def export(n, raw):
        if not raw:
            return None
        trades = json.loads(raw)["trades"]
        df = pd.DataFrame(trades)
        return dcc.send_data_frame(df.to_csv, "backtest_trades.csv", index=False)
