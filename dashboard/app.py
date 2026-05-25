"""
Dashboard entry point.
Run: python dashboard/app.py
Opens at http://localhost:8050
"""
import sys
from pathlib import Path

# Ensure project root is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
from dash import Dash, html, dcc
import dash_bootstrap_components as dbc

from data.database import init_db
import data.ws_feed as ws_feed
from dashboard.layouts import overview, signals, positions, controls, live_chart, backtest
from dashboard.callbacks import charts, tables, bot_control, live, backtest_cb


def load_config():
    with open(Path(__file__).parent.parent / "config" / "config.yaml") as f:
        return yaml.safe_load(f)


app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.CYBORG],
    suppress_callback_exceptions=True,
)
app.title = "BTC Trading Dashboard"

cfg = load_config()
refresh_ms = cfg["dashboard"]["refresh_interval_ms"]

app.layout = dbc.Container(
    fluid=True,
    children=[
        # Header
        dbc.Row([
            dbc.Col(html.H3("BTC/USDT Algorithmic Trading Dashboard", className="my-3 text-white"), width=10),
            dbc.Col(html.Div(id="header-status", className="my-3 text-end"), width=2),
        ], className="border-bottom border-secondary mb-3"),

        # Tabs
        dbc.Tabs(
            id="main-tabs",
            active_tab="tab-live",
            children=[
                dbc.Tab(label="Live Chart",  tab_id="tab-live",      children=live_chart.layout()),
                dbc.Tab(label="Backtest",    tab_id="tab-backtest",  children=backtest.layout()),
                dbc.Tab(label="Overview",    tab_id="tab-overview",  children=overview.layout()),
                dbc.Tab(label="Signals",     tab_id="tab-signals",   children=signals.layout()),
                dbc.Tab(label="Positions",   tab_id="tab-positions", children=positions.layout()),
                dbc.Tab(label="Controls",    tab_id="tab-controls",  children=controls.layout()),
            ],
        ),

        # 60-second refresh for analytics tabs
        dcc.Interval(id="refresh", interval=refresh_ms, n_intervals=0),
        # 5-second refresh for live price + candle
        dcc.Interval(id="live-refresh", interval=5000, n_intervals=0),
    ],
    style={"minHeight": "100vh"},
)

# Register all callbacks
charts.register(app)
tables.register(app)
bot_control.register(app)
live.register(app)
backtest_cb.register(app)


if __name__ == "__main__":
    init_db()
    ws_feed.start()   # start WebSocket feed in background thread
    host = cfg["dashboard"]["host"]
    port = cfg["dashboard"]["port"]
    print(f"Dashboard running at http://{host}:{port}")
    app.run(host=host, port=port, debug=False)
