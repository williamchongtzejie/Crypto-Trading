from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

from analysis.metrics import equity_curve, drawdown_series, compute_metrics


def build_equity_figure(
    trades: list[dict],
    starting_capital: float,
    btc_prices: pd.Series | None = None,
) -> go.Figure:
    """Interactive equity curve vs BTC buy-and-hold."""
    eq = equity_curve(trades, starting_capital)

    fig = go.Figure()
    if len(eq) > 0:
        fig.add_trace(go.Scatter(
            x=eq.index, y=eq.values,
            name="Strategy",
            line=dict(color="#00b09b", width=2),
        ))

    if btc_prices is not None and len(btc_prices) > 0:
        btc_norm = starting_capital * (btc_prices / btc_prices.iloc[0])
        fig.add_trace(go.Scatter(
            x=btc_prices.index, y=btc_norm.values,
            name="BTC Buy & Hold",
            line=dict(color="#f7b731", width=2, dash="dash"),
        ))

    fig.update_layout(
        title="Equity Curve",
        xaxis_title="Date",
        yaxis_title="Portfolio Value ($)",
        template="plotly_dark",
        legend=dict(x=0, y=1),
        margin=dict(l=40, r=20, t=40, b=40),
    )
    return fig


def build_drawdown_figure(trades: list[dict], starting_capital: float) -> go.Figure:
    """Drawdown over time."""
    eq = equity_curve(trades, starting_capital)
    fig = go.Figure()
    if len(eq) > 0:
        dd = drawdown_series(eq) * 100
        fig.add_trace(go.Scatter(
            x=dd.index, y=dd.values,
            fill="tozeroy",
            name="Drawdown %",
            line=dict(color="#eb3b5a"),
        ))
    fig.update_layout(
        title="Drawdown",
        xaxis_title="Date",
        yaxis_title="Drawdown (%)",
        template="plotly_dark",
        margin=dict(l=40, r=20, t=40, b=40),
    )
    return fig


def build_monthly_heatmap(trades: list[dict]) -> go.Figure:
    """Monthly PnL heatmap."""
    if not trades:
        return go.Figure()

    df = pd.DataFrame(trades)
    df = df[df["pnl"].notna()].copy()
    if df.empty:
        return go.Figure()

    df["closed_at"] = pd.to_datetime(df["closed_at"])
    df["year"] = df["closed_at"].dt.year
    df["month"] = df["closed_at"].dt.month
    pivot = df.groupby(["year", "month"])["pnl"].sum().unstack(fill_value=0)

    month_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    cols = [month_labels[m - 1] for m in pivot.columns]

    fig = px.imshow(
        pivot.values,
        x=cols,
        y=[str(y) for y in pivot.index],
        color_continuous_scale="RdYlGn",
        color_continuous_midpoint=0,
        text_auto=".0f",
        title="Monthly PnL ($)",
    )
    fig.update_layout(template="plotly_dark", margin=dict(l=40, r=20, t=40, b=40))
    return fig


def export_trade_log(trades: list[dict], path: str = "trade_log.csv"):
    df = pd.DataFrame(trades)
    df.to_csv(path, index=False)
    return path
