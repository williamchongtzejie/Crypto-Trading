import time
import logging
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

logger = logging.getLogger(__name__)


def _load_config():
    path = Path(__file__).parent.parent / "config" / "config.yaml"
    with open(path) as f:
        return yaml.safe_load(f)


class BinanceFetcher:
    """Fetches OHLCV data from Binance via ccxt (no API key needed for public endpoints)."""

    BASE_URL = "https://api.binance.com/api/v3/klines"

    def __init__(self):
        self.cfg = _load_config()
        self.symbol = self.cfg["trading"]["symbol"]
        self.interval = self.cfg["trading"]["interval"]

    def fetch_historical(
        self,
        symbol: str | None = None,
        interval: str | None = None,
        start: str | None = None,
        limit: int = 500,
    ) -> list[dict]:
        """
        Fetch klines from Binance REST API.
        Returns list of dicts with OHLCV fields.
        """
        import urllib.request
        import json

        sym = symbol or self.symbol
        itv = interval or self.interval
        url = f"{self.BASE_URL}?symbol={sym}&interval={itv}&limit={limit}"
        if start:
            ts = int(datetime.fromisoformat(start).replace(tzinfo=timezone.utc).timestamp() * 1000)
            url += f"&startTime={ts}"

        logger.info("Fetching %s %s from Binance (limit=%d)", sym, itv, limit)
        with urllib.request.urlopen(url, timeout=30) as resp:
            raw = json.loads(resp.read())

        rows = []
        for k in raw:
            rows.append({
                "timestamp": datetime.fromtimestamp(k[0] / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "symbol": sym,
                "interval": itv,
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4]),
                "volume": float(k[5]),
            })
        return rows

    def fetch_latest_closed_candle(self) -> dict | None:
        """Fetch the most recently closed daily candle."""
        rows = self.fetch_historical(limit=2)
        # rows[-1] is the still-open candle; rows[-2] is the last closed one
        if len(rows) >= 2:
            return rows[-2]
        return None

    def to_dataframe(self, rows: list[dict]) -> pd.DataFrame:
        df = pd.DataFrame(rows)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.set_index("timestamp").sort_index()
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)
        return df
