from dash import html, dcc, dash_table
import dash_bootstrap_components as dbc


def _metric_card(title, id_, color="white"):
    return dbc.Col(dbc.Card([
        dbc.CardBody([
            html.P(title, className="text-muted mb-1", style={"fontSize": "0.78rem"}),
            html.H5(id=id_, children="—", className=f"mb-0 text-{color}"),
        ])
    ], className="h-100"), width=2)


def layout():
    return html.Div([

        # ── Controls row ────────────────────────────────────────────────
        dbc.Row([
            dbc.Col(dbc.Card([
                dbc.CardHeader("Backtest Parameters"),
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            html.Label("Date Range", className="text-muted small"),
                            dcc.DatePickerRange(
                                id="bt-date-range",
                                min_date_allowed="2017-08-17",
                                start_date="2020-01-01",
                                end_date="2026-01-01",
                                display_format="YYYY-MM-DD",
                                className="w-100",
                            ),
                        ], width=4),
                        dbc.Col([
                            html.Label("Pivot X / Y", className="text-muted small"),
                            dbc.Row([
                                dbc.Col(dbc.Input(id="bt-pivot-x", type="number", value=4, min=1, max=20, step=1), width=6),
                                dbc.Col(dbc.Input(id="bt-pivot-y", type="number", value=1, min=1, max=10, step=1), width=6),
                            ]),
                        ], width=2),
                        dbc.Col([
                            html.Label("MACD Fast / Slow / Signal", className="text-muted small"),
                            dbc.Row([
                                dbc.Col(dbc.Input(id="bt-macd-fast",   type="number", value=13, min=2,  max=50, step=1), width=4),
                                dbc.Col(dbc.Input(id="bt-macd-slow",   type="number", value=26, min=5,  max=100,step=1), width=4),
                                dbc.Col(dbc.Input(id="bt-macd-signal", type="number", value=10, min=2,  max=50, step=1), width=4),
                            ]),
                        ], width=3),
                        dbc.Col([
                            html.Label("Capital ($)", className="text-muted small"),
                            dbc.Input(id="bt-capital", type="number", value=100000, step=1000),
                        ], width=1),
                        dbc.Col([
                            html.Label("Risk %", className="text-muted small"),
                            dbc.Input(id="bt-risk", type="number", value=1.0, min=0.1, max=10, step=0.1),
                        ], width=1),
                        dbc.Col([
                            html.Br(),
                            dbc.Button("▶  Run Backtest", id="bt-run", color="primary", className="w-100"),
                        ], width=1),
                    ], align="end"),
                ]),
            ]), width=12),
        ], className="mb-3"),

        # ── Status / spinner ────────────────────────────────────────────
        dbc.Row([
            dbc.Col(html.Div(id="bt-status", className="text-muted small text-center"), width=12),
        ], className="mb-2"),

        # ── Metric cards (paper metrics) ────────────────────────────────
        dbc.Row([
            dbc.Col(html.P("Paper Metrics", className="text-muted small mb-1"), width=12),
        ]),
        dbc.Row([
            _metric_card("Net Profit",     "bt-net-profit",    "success"),
            _metric_card("Max Drawdown",   "bt-mdd",           "danger"),
            _metric_card("Profit Factor",  "bt-pf",            "info"),
            _metric_card("Win Rate",       "bt-win-rate",      "warning"),
            _metric_card("Total Trades",   "bt-trades",        "white"),
            _metric_card("vs Buy & Hold",  "bt-vs-bh",         "white"),
        ], className="mb-3 g-2"),

        # ── Metric cards (additional) ────────────────────────────────────
        dbc.Row([
            dbc.Col(html.P("Risk-Adjusted & Trade Metrics", className="text-muted small mb-1"), width=12),
        ]),
        dbc.Row([
            _metric_card("Sharpe Ratio",    "bt-sharpe",         "info"),
            _metric_card("Sortino Ratio",   "bt-sortino",        "info"),
            _metric_card("Calmar Ratio",    "bt-calmar",         "info"),
            _metric_card("CAGR",            "bt-cagr",           "success"),
            _metric_card("Expectancy / Trade", "bt-expectancy",  "white"),
            _metric_card("Recovery Factor", "bt-recovery",       "white"),
        ], className="mb-3 g-2"),
        dbc.Row([
            _metric_card("Turnover (trades/yr)", "bt-turnover",  "white"),
            _metric_card("Avg Hold (days)",  "bt-duration",      "white"),
            _metric_card("Avg Win",          "bt-avg-win",       "success"),
            _metric_card("Avg Loss",         "bt-avg-loss",      "danger"),
            _metric_card("Best Trade",       "bt-best",          "success"),
            _metric_card("Worst Trade",      "bt-worst",         "danger"),
        ], className="mb-4 g-2"),

        # ── Charts ──────────────────────────────────────────────────────
        dbc.Row([
            dbc.Col(dbc.Card([
                dbc.CardHeader("Equity Curve vs Buy & Hold"),
                dbc.CardBody(dcc.Graph(id="bt-chart-equity", config={"displayModeBar": False}, style={"height": "320px"})),
            ]), width=8),
            dbc.Col(dbc.Card([
                dbc.CardHeader("Drawdown"),
                dbc.CardBody(dcc.Graph(id="bt-chart-dd", config={"displayModeBar": False}, style={"height": "320px"})),
            ]), width=4),
        ], className="mb-3"),

        dbc.Row([
            dbc.Col(dbc.Card([
                dbc.CardHeader("Monthly PnL Heatmap"),
                dbc.CardBody(dcc.Graph(id="bt-chart-monthly", config={"displayModeBar": False}, style={"height": "280px"})),
            ]), width=12),
        ], className="mb-3"),

        # ── Trade log ───────────────────────────────────────────────────
        dbc.Row([
            dbc.Col(dbc.Card([
                dbc.CardHeader([
                    "Trade Log",
                    dbc.Button("Export CSV", id="bt-export", size="sm", color="secondary", className="float-end"),
                    dcc.Download(id="bt-download"),
                ]),
                dbc.CardBody(
                    dash_table.DataTable(
                        id="bt-trade-table",
                        columns=[
                            {"name": "Side",        "id": "side"},
                            {"name": "Entry Date",  "id": "entry_date"},
                            {"name": "Exit Date",   "id": "exit_date"},
                            {"name": "Entry $",     "id": "entry_price", "type": "numeric", "format": {"specifier": ",.2f"}},
                            {"name": "Exit $",      "id": "exit_price",  "type": "numeric", "format": {"specifier": ",.2f"}},
                            {"name": "Stop $",      "id": "stop_price",  "type": "numeric", "format": {"specifier": ",.2f"}},
                            {"name": "Size (BTC)",  "id": "size",        "type": "numeric", "format": {"specifier": ".5f"}},
                            {"name": "PnL ($)",     "id": "pnl",         "type": "numeric", "format": {"specifier": "+,.2f"}},
                            {"name": "Duration",    "id": "duration"},
                            {"name": "Exit Reason", "id": "exit_reason"},
                        ],
                        style_table={"overflowX": "auto"},
                        style_cell={"backgroundColor": "#1e2130", "color": "#cdd6f4",
                                    "fontSize": 12, "textAlign": "center"},
                        style_header={"backgroundColor": "#313244", "fontWeight": "bold"},
                        style_data_conditional=[
                            {"if": {"filter_query": "{pnl} > 0"}, "color": "#a6e3a1"},
                            {"if": {"filter_query": "{pnl} < 0"}, "color": "#f38ba8"},
                        ],
                        sort_action="native",
                        filter_action="native",
                        page_size=15,
                    )
                ),
            ]), width=12),
        ]),

        # Hidden store for backtest results
        dcc.Store(id="bt-results-store"),
    ])
