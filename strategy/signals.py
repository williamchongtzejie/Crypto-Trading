import logging
from pathlib import Path

import pandas as pd
import yaml

from strategy.indicators import pivot_reversal, macd

logger = logging.getLogger(__name__)


def _load_config():
    path = Path(__file__).parent.parent / "config" / "config.yaml"
    with open(path) as f:
        return yaml.safe_load(f)


def generate_signal(df: pd.DataFrame) -> dict:
    """
    Compute Pivot Reversal + MACD and emit a combined signal for the latest bar.

    Combined logic (from paper):
      LONG  = Pivot BULL confirmed AND macd_line > signal_line
      SHORT = Pivot BEAR confirmed AND macd_line < signal_line
      HOLD  = conflicting or no pivot

    Returns a signal dict for the most recently confirmed bar.
    The last y bars of pivot data are excluded to avoid look-ahead.
    """
    cfg = _load_config()
    px = cfg["pivot"]["x"]
    py = cfg["pivot"]["y"]
    mf = cfg["macd"]["fast"]
    ms = cfg["macd"]["slow"]
    mg = cfg["macd"]["signal"]

    pivots = pivot_reversal(df, x=px, y=py)
    macd_df = macd(df, fast=mf, slow=ms, signal=mg)

    # The last confirmed bar is index -(py+1) to avoid look-ahead from y future bars
    confirmed_idx = -(py + 1)
    bar = df.iloc[confirmed_idx]
    pivot_val = pivots.iloc[confirmed_idx]
    macd_row = macd_df.iloc[confirmed_idx]
    ts = df.index[confirmed_idx]

    macd_bullish = macd_row["macd_line"] > macd_row["signal_line"]
    macd_bearish = macd_row["macd_line"] < macd_row["signal_line"]

    if pivot_val == "BULL" and macd_bullish:
        sig = "LONG"
    elif pivot_val == "BEAR" and macd_bearish:
        sig = "SHORT"
    else:
        sig = "HOLD"

    # Stop-loss: for LONG place below the swing low; for SHORT above the swing high
    stop_price = None
    if sig == "LONG":
        stop_price = float(bar["low"])
    elif sig == "SHORT":
        stop_price = float(bar["high"])

    result = {
        "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "signal": sig,
        "pivot": pivot_val,
        "pivot_price": float(bar["close"]),
        "stop_price": stop_price,
        "macd_line": float(macd_row["macd_line"]),
        "signal_line": float(macd_row["signal_line"]),
        "histogram": float(macd_row["histogram"]),
    }
    logger.info("Signal generated: %s at %s", sig, result["timestamp"])
    return result
