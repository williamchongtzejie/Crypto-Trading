from dash import html, dcc, dash_table
import dash_bootstrap_components as dbc


def layout():
    return html.Div([
        # Open position card
        dbc.Row([
            dbc.Col(dbc.Card([
                dbc.CardHeader("Current Open Position"),
                dbc.CardBody(id="open-position-body", children=[
                    html.P("No open position.", className="text-muted text-center mt-3"),
                ])
            ]), width=12),
        ], className="mb-4"),

        # Trade history
        dbc.Row([
            dbc.Col(dbc.Card([
                dbc.CardHeader([
                    "Trade History",
                    dbc.Button("Export CSV", id="btn-export", size="sm", color="secondary", className="float-end"),
                    dcc.Download(id="download-trades"),
                ]),
                dbc.CardBody(
                    dash_table.DataTable(
                        id="table-trades",
                        columns=[
                            {"name": "ID", "id": "id"},
                            {"name": "Side", "id": "side"},
                            {"name": "Size (BTC)", "id": "size", "type": "numeric", "format": {"specifier": ".6f"}},
                            {"name": "Fill Price", "id": "fill_price", "type": "numeric", "format": {"specifier": ",.2f"}},
                            {"name": "Exit Price", "id": "exit_price", "type": "numeric", "format": {"specifier": ",.2f"}},
                            {"name": "Stop Price", "id": "stop_price", "type": "numeric", "format": {"specifier": ",.2f"}},
                            {"name": "PnL ($)", "id": "pnl", "type": "numeric", "format": {"specifier": "+,.2f"}},
                            {"name": "Opened", "id": "filled_at"},
                            {"name": "Closed", "id": "closed_at"},
                        ],
                        style_table={"overflowX": "auto"},
                        style_cell={"backgroundColor": "#1e2130", "color": "#cdd6f4", "fontSize": 13, "textAlign": "center"},
                        style_header={"backgroundColor": "#313244", "fontWeight": "bold"},
                        style_data_conditional=[
                            {"if": {"filter_query": "{pnl} > 0"}, "color": "#a6e3a1"},
                            {"if": {"filter_query": "{pnl} < 0"}, "color": "#f38ba8"},
                        ],
                        sort_action="native",
                        filter_action="native",
                        page_size=20,
                    )
                )
            ]), width=12),
        ]),
    ])
