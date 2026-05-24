import logging
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


def _load_config():
    path = Path(__file__).parent.parent / "config" / "config.yaml"
    with open(path) as f:
        return yaml.safe_load(f)


def calculate_position_size(capital: float, entry_price: float, stop_price: float) -> float:
    """
    Size a position so the maximum loss equals 1% of capital.

    position_size (BTC) = risk_amount / |entry - stop|
    """
    cfg = _load_config()
    risk_pct = cfg["trading"]["risk_per_trade"]
    risk_amount = capital * risk_pct

    price_risk = abs(entry_price - stop_price)
    if price_risk <= 0:
        logger.warning("Invalid price risk (entry=%.2f, stop=%.2f) — skipping", entry_price, stop_price)
        return 0.0

    size = risk_amount / price_risk
    logger.info(
        "Position size: %.6f BTC | risk $%.2f on $%.2f entry with $%.2f stop",
        size, risk_amount, entry_price, stop_price,
    )
    return size


def check_circuit_breakers(
    peak_equity: float,
    current_equity: float,
    daily_start_equity: float,
    capital: float,
) -> tuple[bool, str]:
    """
    Return (should_stop, reason).

    Rules:
      - Max portfolio drawdown: 10%  → full stop (status=STOPPED)
      - Max daily loss: 2%           → daily pause (status=PAUSED)
    """
    cfg = _load_config()
    max_dd = cfg["trading"]["max_drawdown_limit"]
    max_daily = cfg["trading"]["max_daily_loss"]

    portfolio_dd = (peak_equity - current_equity) / peak_equity if peak_equity > 0 else 0
    daily_loss = (daily_start_equity - current_equity) / capital if capital > 0 else 0

    if portfolio_dd >= max_dd:
        reason = f"Max drawdown breached: {portfolio_dd:.1%} >= {max_dd:.1%}"
        logger.warning(reason)
        return True, "STOPPED"

    if daily_loss >= max_daily:
        reason = f"Daily loss limit hit: {daily_loss:.1%} >= {max_daily:.1%}"
        logger.warning(reason)
        return True, "PAUSED"

    return False, ""


def compute_equity(starting_capital: float, trades: list[dict]) -> float:
    """Sum starting capital with all closed trade PnLs."""
    realized = sum(t["pnl"] for t in trades if t.get("pnl") is not None)
    return starting_capital + realized
