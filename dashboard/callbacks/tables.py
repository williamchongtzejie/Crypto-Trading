import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
from dash import Input, Output, html, dcc
import dash_bootstrap_components as dbc

from data.database import get_all_trades, get_recent_signals, get_open_position
from analysis.reporter import export_trade_log


def register(app):
    @app.callback(
        Output("table-trades", "data"),
        Input("refresh", "n_intervals"),
    )
    def update_trade_table(_):
        return get_all_trades()

    @app.callback(
        Output("table-signals", "data"),
        Input("refresh", "n_intervals"),
    )
    def update_signal_table(_):
        return get_recent_signals(50)

    @app.callback(
        Output("sig-current", "children"),
        Output("sig-current", "className"),
        Output("sig-pivot", "children"),
        Output("sig-macd-line", "children"),
        Output("sig-signal-line", "children"),
        Output("sig-timestamp", "children"),
        Input("refresh", "n_intervals"),
    )
    def update_signal_card(_):
        signals = get_recent_signals(1)
        if not signals:
            return "—", "text-center mb-3 text-muted", "—", "—", "—", ""
        s = signals[0]
        color = {
            "LONG": "text-center mb-3 text-success",
            "SHORT": "text-center mb-3 text-danger",
            "HOLD": "text-center mb-3 text-warning",
        }.get(s["signal"], "text-center mb-3 text-muted")
        return (
            s["signal"],
            color,
            s.get("pivot") or "—",
            f"{s.get('macd_line', 0):.2f}",
            f"{s.get('signal_line', 0):.2f}",
            f"As of {s.get('timestamp', '')}",
        )

    @app.callback(
        Output("open-position-body", "children"),
        Input("refresh", "n_intervals"),
    )
    def update_open_position(_):
        pos = get_open_position()
        if not pos:
            return html.P("No open position.", className="text-muted text-center mt-3")
        side_color = "success" if pos["side"] == "LONG" else "danger"
        return dbc.Row([
            dbc.Col([html.Small("Side", className="text-muted"), html.H5(dbc.Badge(pos["side"], color=side_color))], width=2),
            dbc.Col([html.Small("Size (BTC)", className="text-muted"), html.H5(f"{pos['size']:.6f}")], width=2),
            dbc.Col([html.Small("Entry Price", className="text-muted"), html.H5(f"${pos['fill_price']:,.2f}")], width=2),
            dbc.Col([html.Small("Stop Price", className="text-muted"), html.H5(f"${pos['stop_price']:,.2f}")], width=2),
            dbc.Col([html.Small("Opened", className="text-muted"), html.H5(pos.get("filled_at", "—"))], width=4),
        ])

    @app.callback(
        Output("download-trades", "data"),
        Input("btn-export", "n_clicks"),
        prevent_initial_call=True,
    )
    def export_trades(n):
        trades = get_all_trades()
        if not trades:
            return None
        df = pd.DataFrame(trades)
        return dcc.send_data_frame(df.to_csv, "trade_log.csv", index=False)
