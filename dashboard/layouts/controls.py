from pathlib import Path

import yaml
from dash import html, dcc
import dash_bootstrap_components as dbc


def _load_config():
    path = Path(__file__).parent.parent.parent / "config" / "config.yaml"
    with open(path) as f:
        return yaml.safe_load(f)


def layout():
    cfg = _load_config()
    t = cfg["trading"]
    p = cfg["pivot"]
    m = cfg["macd"]

    return html.Div([
        dbc.Row([
            # Bot control panel
            dbc.Col(dbc.Card([
                dbc.CardHeader("Bot Control"),
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col(html.Div([
                            html.Small("Status", className="text-muted"),
                            html.Div(id="bot-status-badge", className="mt-1"),
                        ]), width=4),
                        dbc.Col(html.Div([
                            dbc.Button("Start", id="btn-start", color="success", className="me-2 mb-2", n_clicks=0),
                            dbc.Button("Pause", id="btn-pause", color="warning", className="me-2 mb-2", n_clicks=0),
                            dbc.Button("Stop", id="btn-stop", color="danger", className="mb-2", n_clicks=0),
                        ]), width=8),
                    ]),
                    html.Hr(),
                    html.Div([
                        html.Small("Manual Trigger", className="text-muted d-block mb-2"),
                        dbc.Button(
                            "▶  Run Cycle Now",
                            id="btn-run-now",
                            color="primary",
                            n_clicks=0,
                            className="w-100",
                        ),
                        html.Div(id="run-now-feedback", className="mt-2 small"),
                    ]),
                    html.Div(id="control-feedback", className="mt-2 text-muted small"),
                ])
            ]), width=5),

            # Config summary
            dbc.Col(dbc.Card([
                dbc.CardHeader("Active Configuration"),
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            html.Small("Symbol", className="text-muted d-block"), html.Strong(t["symbol"]),
                            html.Small("Interval", className="text-muted d-block mt-2"), html.Strong(t["interval"]),
                            html.Small("Capital", className="text-muted d-block mt-2"), html.Strong(f"${t['starting_capital']:,.0f}"),
                        ], width=4),
                        dbc.Col([
                            html.Small("Risk / Trade", className="text-muted d-block"), html.Strong(f"{t['risk_per_trade']*100:.0f}%"),
                            html.Small("Max Drawdown", className="text-muted d-block mt-2"), html.Strong(f"{t['max_drawdown_limit']*100:.0f}%"),
                            html.Small("Daily Loss Limit", className="text-muted d-block mt-2"), html.Strong(f"{t['max_daily_loss']*100:.0f}%"),
                        ], width=4),
                        dbc.Col([
                            html.Small("Pivot X / Y", className="text-muted d-block"), html.Strong(f"{p['x']} / {p['y']}"),
                            html.Small("MACD Fast/Slow/Signal", className="text-muted d-block mt-2"),
                            html.Strong(f"{m['fast']} / {m['slow']} / {m['signal']}"),
                        ], width=4),
                    ])
                ])
            ]), width=7),
        ], className="mb-4"),

        # Circuit breaker status
        dbc.Row([
            dbc.Col(dbc.Card([
                dbc.CardHeader("Risk Monitor"),
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            html.Small("Portfolio Drawdown", className="text-muted"),
                            dbc.Progress(id="gauge-dd", value=0, max=100, color="danger", className="mt-1", style={"height": "22px"}),
                            html.Small(id="gauge-dd-label", className="text-muted"),
                        ], width=6),
                        dbc.Col([
                            html.Small("Daily Loss", className="text-muted"),
                            dbc.Progress(id="gauge-daily", value=0, max=100, color="warning", className="mt-1", style={"height": "22px"}),
                            html.Small(id="gauge-daily-label", className="text-muted"),
                        ], width=6),
                    ])
                ])
            ]), width=12),
        ]),
    ])
