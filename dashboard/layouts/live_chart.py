from dash import html, dcc
import dash_bootstrap_components as dbc


def layout():
    return html.Div([
        # Live price strip
        dbc.Row([
            dbc.Col(dbc.Card([
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            html.Span("BTC/USDT  ", className="text-muted small"),
                            html.Span(id="live-price", children="—", style={"fontSize": "1.6rem", "fontWeight": "700"}),
                            html.Span(id="live-change", children="", className="ms-3 fs-6"),
                        ], width=5),
                        dbc.Col([
                            html.Small("24h High", className="text-muted d-block"), html.Span(id="live-high"),
                        ], width=2),
                        dbc.Col([
                            html.Small("24h Low", className="text-muted d-block"), html.Span(id="live-low"),
                        ], width=2),
                        dbc.Col([
                            html.Small("24h Volume", className="text-muted d-block"), html.Span(id="live-volume"),
                        ], width=2),
                        dbc.Col([
                            html.Small("Last update", className="text-muted d-block"),
                            html.Small(id="live-timestamp", className="text-muted"),
                        ], width=1),
                    ], align="center"),
                ], className="py-2"),
            ], className="border-0", style={"background": "linear-gradient(90deg,#1e2130,#2a2d3e)"})),
        ], className="mb-3"),

        # Candlestick + MACD chart
        dbc.Row([
            dbc.Col(dbc.Card([
                dbc.CardHeader([
                    "BTC/USDT — Daily Candlestick",
                    dbc.ButtonGroup([
                        dbc.Button("30D",  id="range-30",  size="sm", color="secondary", outline=True, n_clicks=0, className="ms-2"),
                        dbc.Button("60D",  id="range-60",  size="sm", color="secondary", outline=True, n_clicks=0),
                        dbc.Button("90D",  id="range-90",  size="sm", color="primary",   outline=False, n_clicks=0),
                        dbc.Button("180D", id="range-180", size="sm", color="secondary", outline=True, n_clicks=0),
                    ], className="float-end"),
                ]),
                dbc.CardBody(
                    dcc.Graph(
                        id="chart-candle",
                        config={"displayModeBar": True, "scrollZoom": True},
                        style={"height": "520px"},
                    )
                ),
            ]), width=12),
        ], className="mb-3"),

        # MACD panel
        dbc.Row([
            dbc.Col(dbc.Card([
                dbc.CardHeader("MACD  (13 / 26 / 10)"),
                dbc.CardBody(
                    dcc.Graph(
                        id="chart-macd-panel",
                        config={"displayModeBar": False},
                        style={"height": "220px"},
                    )
                ),
            ]), width=8),

            dbc.Col(dbc.Card([
                dbc.CardHeader("Current Signal"),
                dbc.CardBody([
                    html.H2(id="live-signal", children="—", className="text-center mt-2"),
                    html.Hr(),
                    dbc.Row([
                        dbc.Col([html.Small("Pivot",        className="text-muted d-block"), html.Span(id="live-pivot")],       width=6),
                        dbc.Col([html.Small("MACD Line",    className="text-muted d-block"), html.Span(id="live-macd-val")],    width=6),
                    ], className="text-center mb-2"),
                    dbc.Row([
                        dbc.Col([html.Small("Signal Line",  className="text-muted d-block"), html.Span(id="live-sig-val")],    width=6),
                        dbc.Col([html.Small("Histogram",    className="text-muted d-block"), html.Span(id="live-hist-val")],   width=6),
                    ], className="text-center"),
                ]),
            ]), width=4),
        ]),
    ])
