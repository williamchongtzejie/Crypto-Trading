from pathlib import Path

import pandas as pd
import numpy as np
import yaml


def _load_config():
    path = Path(__file__).parent.parent / "config" / "config.yaml"
    with open(path) as f:
        return yaml.safe_load(f)


def equity_curve(trades: list[dict], starting_capital: float | None = None) -> pd.Series:
    """Build cumulative equity series from closed trades."""
    if starting_capital is None:
        cfg = _load_config()
        starting_capital = cfg["trading"]["starting_capital"]

    if not trades:
        return pd.Series([starting_capital], name="equity")

    df = pd.DataFrame(trades)
    df = df[df["pnl"].notna()].copy()
    df["closed_at"] = pd.to_datetime(df["closed_at"])
    df = df.sort_values("closed_at")
    df["equity"] = starting_capital + df["pnl"].cumsum()
    return df.set_index("closed_at")["equity"]


def drawdown_series(eq: pd.Series) -> pd.Series:
    """Rolling drawdown from peak (as a negative fraction)."""
    peak = eq.cummax()
    return (eq - peak) / peak


def compute_metrics(trades: list[dict], starting_capital: float | None = None) -> dict:
    """
    Compute performance metrics matching the paper:
      NP  = Net Profit ($)
      MDD = Maximum Drawdown (% and $)
      PF  = Profit Factor
      PP  = Percentage Profitable (win rate)
    """
    if starting_capital is None:
        cfg = _load_config()
        starting_capital = cfg["trading"]["starting_capital"]

    closed = [t for t in trades if t.get("pnl") is not None]
    if not closed:
        return {
            "net_profit": 0.0,
            "mdd_pct": 0.0,
            "mdd_dollar": 0.0,
            "profit_factor": 0.0,
            "win_rate": 0.0,
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
        }

    pnls = [t["pnl"] for t in closed]
    net_profit = sum(pnls)

    winners = [p for p in pnls if p > 0]
    losers = [p for p in pnls if p <= 0]
    gross_profit = sum(winners)
    gross_loss = abs(sum(losers))

    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")
    win_rate = len(winners) / len(pnls) * 100

    eq = equity_curve(closed, starting_capital)
    dd = drawdown_series(eq)
    mdd_pct = float(abs(dd.min())) * 100 if len(dd) > 0 else 0.0
    mdd_dollar = float(abs((eq - eq.cummax()).min())) if len(eq) > 0 else 0.0

    return {
        "net_profit": round(net_profit, 2),
        "mdd_pct": round(mdd_pct, 2),
        "mdd_dollar": round(mdd_dollar, 2),
        "profit_factor": round(profit_factor, 2),
        "win_rate": round(win_rate, 2),
        "total_trades": len(closed),
        "winning_trades": len(winners),
        "losing_trades": len(losers),
    }
