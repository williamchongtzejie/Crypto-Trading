import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dash import Input, Output
import plotly.graph_objects as go

from data.database import get_all_trades, get_recent_signals
from analysis.metrics import compute_metrics, equity_curve
from analysis.reporter import build_equity_figure, build_drawdown_figure, build_monthly_heatmap


def register(app):
    cfg = _get_config()
    capital = cfg["trading"]["starting_capital"]

    @app.callback(
        Output("metric-net-profit", "children"),
        Output("metric-mdd", "children"),
        Output("metric-pf", "children"),
        Output("metric-win-rate", "children"),
        Output("metric-total-trades", "children"),
        Output("metric-equity", "children"),
        Input("refresh", "n_intervals"),
    )
    def update_metrics(_):
        trades = get_all_trades()
        m = compute_metrics(trades, capital)
        eq_val = capital + m["net_profit"]
        color_np = "text-success" if m["net_profit"] >= 0 else "text-danger"
        return (
            f"${m['net_profit']:+,.2f}",
            f"{m['mdd_pct']:.2f}%",
            f"{m['profit_factor']:.2f}",
            f"{m['win_rate']:.1f}%",
            str(m["total_trades"]),
            f"${eq_val:,.2f}",
        )

    @app.callback(
        Output("chart-equity", "figure"),
        Input("refresh", "n_intervals"),
    )
    def update_equity(_):
        trades = get_all_trades()
        return build_equity_figure(trades, capital)

    @app.callback(
        Output("chart-drawdown", "figure"),
        Input("refresh", "n_intervals"),
    )
    def update_drawdown(_):
        trades = get_all_trades()
        return build_drawdown_figure(trades, capital)

    @app.callback(
        Output("chart-monthly", "figure"),
        Input("refresh", "n_intervals"),
    )
    def update_monthly(_):
        trades = get_all_trades()
        return build_monthly_heatmap(trades)

    @app.callback(
        Output("chart-macd", "figure"),
        Input("refresh", "n_intervals"),
    )
    def update_macd_chart(_):
        signals = get_recent_signals(50)
        if not signals:
            return go.Figure()
        import pandas as pd
        df = pd.DataFrame(signals)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("timestamp")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df["timestamp"], y=df["macd_line"], name="MACD", line=dict(color="#89b4fa")))
        fig.add_trace(go.Scatter(x=df["timestamp"], y=df["signal_line"], name="Signal", line=dict(color="#f38ba8")))
        fig.add_bar(x=df["timestamp"], y=df["histogram"], name="Histogram", marker_color="#a6e3a1")
        fig.update_layout(template="plotly_dark", title="MACD History", margin=dict(l=40, r=20, t=40, b=40))
        return fig


def _get_config():
    import yaml
    path = Path(__file__).parent.parent.parent / "config" / "config.yaml"
    with open(path) as f:
        return yaml.safe_load(f)
