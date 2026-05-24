from dash import html, dcc
import dash_bootstrap_components as dbc


def layout():
    return html.Div([
        # Metric cards row
        dbc.Row([
            dbc.Col(dbc.Card([
                dbc.CardBody([
                    html.P("Net Profit", className="card-title text-muted mb-1", style={"fontSize": "0.85rem"}),
                    html.H4(id="metric-net-profit", children="$0.00", className="mb-0 text-success"),
                ])
            ], className="h-100"), width=2),

            dbc.Col(dbc.Card([
                dbc.CardBody([
                    html.P("Max Drawdown", className="card-title text-muted mb-1", style={"fontSize": "0.85rem"}),
                    html.H4(id="metric-mdd", children="0.00%", className="mb-0 text-danger"),
                ])
            ], className="h-100"), width=2),

            dbc.Col(dbc.Card([
                dbc.CardBody([
                    html.P("Profit Factor", className="card-title text-muted mb-1", style={"fontSize": "0.85rem"}),
                    html.H4(id="metric-pf", children="0.00", className="mb-0 text-info"),
                ])
            ], className="h-100"), width=2),

            dbc.Col(dbc.Card([
                dbc.CardBody([
                    html.P("Win Rate", className="card-title text-muted mb-1", style={"fontSize": "0.85rem"}),
                    html.H4(id="metric-win-rate", children="0.00%", className="mb-0 text-warning"),
                ])
            ], className="h-100"), width=2),

            dbc.Col(dbc.Card([
                dbc.CardBody([
                    html.P("Total Trades", className="card-title text-muted mb-1", style={"fontSize": "0.85rem"}),
                    html.H4(id="metric-total-trades", children="0", className="mb-0"),
                ])
            ], className="h-100"), width=2),

            dbc.Col(dbc.Card([
                dbc.CardBody([
                    html.P("Portfolio Value", className="card-title text-muted mb-1", style={"fontSize": "0.85rem"}),
                    html.H4(id="metric-equity", children="$100,000.00", className="mb-0"),
                ])
            ], className="h-100"), width=2),
        ], className="mb-4 g-3"),

        # Equity curve
        dbc.Row([
            dbc.Col(dbc.Card([
                dbc.CardBody(dcc.Graph(id="chart-equity", config={"displayModeBar": False}))
            ]), width=8),
            dbc.Col(dbc.Card([
                dbc.CardBody(dcc.Graph(id="chart-drawdown", config={"displayModeBar": False}))
            ]), width=4),
        ], className="mb-4"),

        # Monthly heatmap
        dbc.Row([
            dbc.Col(dbc.Card([
                dbc.CardBody(dcc.Graph(id="chart-monthly", config={"displayModeBar": False}))
            ]), width=12),
        ]),
    ])
