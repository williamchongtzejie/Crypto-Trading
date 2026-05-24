import logging

import pandas as pd

logger = logging.getLogger(__name__)


def clean_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """Validate and clean a raw OHLCV DataFrame."""
    before = len(df)
    df = df.dropna(subset=["open", "high", "low", "close", "volume"])
    df = df[df["volume"] > 0]
    df = df[df["high"] >= df["low"]]
    df = df[df["close"] > 0]
    after = len(df)
    if before != after:
        logger.warning("Dropped %d invalid rows during cleaning", before - after)
    return df.sort_index()


def to_ohlcv_rows(df: pd.DataFrame) -> list[dict]:
    """Convert a cleaned DataFrame back to a list of dicts for DB insertion."""
    rows = []
    for ts, row in df.iterrows():
        rows.append({
            "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "symbol": row.get("symbol", "BTCUSDT"),
            "interval": row.get("interval", "1d"),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": float(row["volume"]),
        })
    return rows
