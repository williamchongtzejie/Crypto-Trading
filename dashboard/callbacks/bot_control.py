import sys
import threading
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dash import Input, Output, State
import dash_bootstrap_components as dbc

from data.database import get_bot_status, set_bot_status
from analysis.metrics import compute_metrics, equity_curve
from data.database import get_all_trades


def register(app):
    cfg = _get_config()
    capital = cfg["trading"]["starting_capital"]
    max_dd = cfg["trading"]["max_drawdown_limit"]
    max_daily = cfg["trading"]["max_daily_loss"]

    @app.callback(
        Output("bot-status-badge", "children"),
        Output("control-feedback", "children"),
        Input("btn-start", "n_clicks"),
        Input("btn-pause", "n_clicks"),
        Input("btn-stop", "n_clicks"),
        Input("refresh", "n_intervals"),
        prevent_initial_call=False,
    )
    def handle_control(start, pause, stop, _refresh):
        from dash import ctx
        triggered = ctx.triggered_id

        if triggered == "btn-start":
            set_bot_status("RUNNING")
            feedback = "Bot started."
        elif triggered == "btn-pause":
            set_bot_status("PAUSED")
            feedback = "Bot paused until next day."
        elif triggered == "btn-stop":
            set_bot_status("STOPPED")
            feedback = "Bot stopped."
        else:
            feedback = ""

        status = get_bot_status()
        color = {"RUNNING": "success", "PAUSED": "warning", "STOPPED": "danger"}.get(status, "secondary")
        badge = dbc.Badge(status, color=color, className="fs-6 px-3 py-2")
        return badge, feedback

    @app.callback(
        Output("gauge-dd", "value"),
        Output("gauge-dd-label", "children"),
        Output("gauge-daily", "value"),
        Output("gauge-daily-label", "children"),
        Input("refresh", "n_intervals"),
    )
    def update_risk_gauges(_):
        trades = get_all_trades()
        m = compute_metrics(trades, capital)
        dd_pct = m["mdd_pct"]
        dd_limit_pct = max_dd * 100
        dd_bar = min(dd_pct / dd_limit_pct * 100, 100) if dd_limit_pct > 0 else 0

        # Daily loss: approximate from last day's trades
        import pandas as pd
        daily_pnl = 0.0
        if trades:
            df = pd.DataFrame(trades)
            df["closed_at"] = pd.to_datetime(df["closed_at"])
            today = pd.Timestamp.utcnow().date()
            today_trades = df[df["closed_at"].dt.date == today]
            daily_pnl = float(today_trades["pnl"].sum()) if not today_trades.empty else 0.0

        daily_loss_pct = abs(min(daily_pnl, 0)) / capital * 100 if capital > 0 else 0
        daily_limit_pct = max_daily * 100
        daily_bar = min(daily_loss_pct / daily_limit_pct * 100, 100) if daily_limit_pct > 0 else 0

        return (
            dd_bar,
            f"{dd_pct:.2f}% of {dd_limit_pct:.0f}% limit",
            daily_bar,
            f"{daily_loss_pct:.2f}% of {daily_limit_pct:.0f}% limit",
        )


    @app.callback(
        Output("run-now-feedback", "children"),
        Input("btn-run-now", "n_clicks"),
        prevent_initial_call=True,
    )
    def run_now(n_clicks):
        from main import run_once
        status = get_bot_status()
        if status != "RUNNING":
            return dbc.Alert("Bot must be RUNNING to trigger a cycle. Click Start first.", color="warning", className="py-1 mb-0")
        def _run():
            try:
                run_once()
            except Exception as e:
                pass
        threading.Thread(target=_run, daemon=True).start()
        return dbc.Alert("Cycle triggered — check the Signals and Positions tabs in ~5 seconds.", color="success", className="py-1 mb-0")


def _get_config():
    import yaml
    path = Path(__file__).parent.parent.parent / "config" / "config.yaml"
    with open(path) as f:
        return yaml.safe_load(f)
