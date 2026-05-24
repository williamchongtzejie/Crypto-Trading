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
from dashboard.layouts import overview, signals, positions, controls
from dashboard.callbacks import charts, tables, bot_control


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
            active_tab="tab-overview",
            children=[
                dbc.Tab(label="Overview", tab_id="tab-overview", children=overview.layout()),
                dbc.Tab(label="Signals", tab_id="tab-signals", children=signals.layout()),
                dbc.Tab(label="Positions", tab_id="tab-positions", children=positions.layout()),
                dbc.Tab(label="Controls", tab_id="tab-controls", children=controls.layout()),
            ],
        ),

        # Global auto-refresh interval
        dcc.Interval(id="refresh", interval=refresh_ms, n_intervals=0),
    ],
    style={"minHeight": "100vh"},
)

# Register all callbacks
charts.register(app)
tables.register(app)
bot_control.register(app)


if __name__ == "__main__":
    init_db()
    host = cfg["dashboard"]["host"]
    port = cfg["dashboard"]["port"]
    print(f"Dashboard running at http://{host}:{port}")
    app.run(host=host, port=port, debug=False)
