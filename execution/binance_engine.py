"""
Stub for live Binance execution — drop-in replacement for PaperEngine.
Wire up when paper trading is validated.
"""
import logging

logger = logging.getLogger(__name__)


class BinanceEngine:
    """Live order execution via Binance API. Not yet implemented."""

    def process_bar(self, signal: dict, bar):
        raise NotImplementedError(
            "BinanceEngine is a stub. Validate with PaperEngine first."
        )
