from dash import html, dcc, dash_table
import dash_bootstrap_components as dbc


def layout():
    return html.Div([
        dbc.Row([
            # Current signal card
            dbc.Col(dbc.Card([
                dbc.CardHeader("Latest Signal"),
                dbc.CardBody([
                    html.H3(id="sig-current", children="—", className="text-center mb-3"),
                    dbc.Row([
                        dbc.Col([html.Small("Pivot", className="text-muted"), html.Div(id="sig-pivot")], width=4),
                        dbc.Col([html.Small("MACD Line", className="text-muted"), html.Div(id="sig-macd-line")], width=4),
                        dbc.Col([html.Small("Signal Line", className="text-muted"), html.Div(id="sig-signal-line")], width=4),
                    ], className="text-center"),
                    html.Hr(),
                    html.Small(id="sig-timestamp", className="text-muted"),
                ])
            ]), width=4),

            # MACD indicator values
            dbc.Col(dbc.Card([
                dbc.CardHeader("MACD Values"),
                dbc.CardBody(dcc.Graph(id="chart-macd", config={"displayModeBar": False}))
            ]), width=8),
        ], className="mb-4"),

        # Signal history table
        dbc.Row([
            dbc.Col(dbc.Card([
                dbc.CardHeader("Recent Signals"),
                dbc.CardBody(
                    dash_table.DataTable(
                        id="table-signals",
                        columns=[
                            {"name": "Timestamp", "id": "timestamp"},
                            {"name": "Signal", "id": "signal"},
                            {"name": "Pivot", "id": "pivot"},
                            {"name": "Stop Price", "id": "stop_price", "type": "numeric", "format": {"specifier": ",.2f"}},
                            {"name": "MACD Line", "id": "macd_line", "type": "numeric", "format": {"specifier": ".2f"}},
                            {"name": "Signal Line", "id": "signal_line", "type": "numeric", "format": {"specifier": ".2f"}},
                            {"name": "Histogram", "id": "histogram", "type": "numeric", "format": {"specifier": ".2f"}},
                        ],
                        style_table={"overflowX": "auto"},
                        style_cell={"backgroundColor": "#1e2130", "color": "#cdd6f4", "fontSize": 13, "textAlign": "center"},
                        style_header={"backgroundColor": "#313244", "fontWeight": "bold"},
                        style_data_conditional=[
                            {"if": {"filter_query": '{signal} = "LONG"'}, "color": "#a6e3a1"},
                            {"if": {"filter_query": '{signal} = "SHORT"'}, "color": "#f38ba8"},
                        ],
                        page_size=15,
                    )
                )
            ]), width=12),
        ]),
    ])
