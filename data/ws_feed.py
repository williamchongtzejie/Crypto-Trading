"""
WebSocket feed for live BTC/USDT market data from Binance.

Follows the course pattern from:
  - week_05/9_async_websocket_ans.py  (websockets.connect + async for)
  - week_06/6_strategy_gateway_ans.py (background thread + asyncio event loop)

Subscribes to two combined Binance spot streams:
  - btcusdt@ticker   : real-time price, 24h stats
  - btcusdt@kline_1d : current daily candle building in real-time

Runs in a daemon background thread so it does not block the main process.
Dashboard callbacks read from the shared STORE dict — always up-to-date.
"""

import asyncio
import json
import logging
import threading
from datetime import datetime, timezone

import websockets

logger = logging.getLogger(__name__)

# Combined Binance spot stream URL (two streams in one connection)
_STREAM_URL = (
    "wss://stream.binance.com:9443/stream"
    "?streams=btcusdt@ticker/btcusdt@kline_1d"
)

# Shared in-memory store — read by dashboard callbacks
STORE: dict = {
    "price":        None,
    "change_pct":   None,
    "high_24h":     None,
    "low_24h":      None,
    "volume_24h":   None,
    "candle": {
        "open":   None,
        "high":   None,
        "low":    None,
        "close":  None,
        "volume": None,
        "closed": False,
    },
    "updated_at": None,
    "connected":  False,
}

_thread: threading.Thread | None = None
_loop:   asyncio.AbstractEventLoop | None = None


# ------------------------------------------------------------------ #
#  Message handlers                                                   #
# ------------------------------------------------------------------ #

def _handle_ticker(data: dict) -> None:
    """Parse 24hr ticker event (stream: btcusdt@ticker)."""
    STORE["price"]      = float(data["c"])   # current price
    STORE["change_pct"] = float(data["P"])   # 24h % change
    STORE["high_24h"]   = float(data["h"])
    STORE["low_24h"]    = float(data["l"])
    STORE["volume_24h"] = float(data["v"])   # base asset volume (BTC)
    STORE["updated_at"] = datetime.now(tz=timezone.utc).strftime("%H:%M:%S UTC")


def _handle_kline(data: dict) -> None:
    """Parse kline/candlestick event (stream: btcusdt@kline_1d)."""
    k = data["k"]
    STORE["candle"] = {
        "open":   float(k["o"]),
        "high":   float(k["h"]),
        "low":    float(k["l"]),
        "close":  float(k["c"]),
        "volume": float(k["v"]),
        "closed": bool(k["x"]),   # True = candle closed (new bar started)
    }


# ------------------------------------------------------------------ #
#  Async WebSocket loop (course pattern: websockets.connect)          #
# ------------------------------------------------------------------ #

async def _listen_forever() -> None:
    """
    Maintain a persistent WebSocket connection with automatic reconnection.
    Mirrors the while True / try-except / asyncio.sleep(3) pattern from
    week_06/6_strategy_gateway_ans.py.
    """
    logger.info("WebSocket feed starting → %s", _STREAM_URL)

    while True:
        try:
            async with websockets.connect(_STREAM_URL, ping_interval=20) as ws:
                STORE["connected"] = True
                logger.info("WebSocket connected to Binance spot streams")

                async for raw in ws:
                    envelope = json.loads(raw)
                    stream   = envelope.get("stream", "")
                    data     = envelope.get("data", {})

                    if "ticker" in stream:
                        _handle_ticker(data)
                    elif "kline" in stream:
                        _handle_kline(data)

        except Exception:
            STORE["connected"] = False
            logger.warning("WebSocket disconnected — reconnecting in 3 s…", exc_info=True)
            await asyncio.sleep(3)


# ------------------------------------------------------------------ #
#  Public API                                                         #
# ------------------------------------------------------------------ #

def start() -> None:
    """
    Start the WebSocket feed in a background daemon thread.
    Follows the threading pattern from week_06/6_strategy_gateway_ans.py:
        loop = asyncio.new_event_loop()
        Thread(target=loop.run_forever, daemon=True).start()
    Safe to call multiple times — only starts once.
    """
    global _thread, _loop

    if _thread and _thread.is_alive():
        logger.debug("WebSocket feed already running")
        return

    _loop = asyncio.new_event_loop()

    def _run():
        asyncio.set_event_loop(_loop)
        _loop.run_until_complete(_listen_forever())

    _thread = threading.Thread(target=_run, name="WS-Feed", daemon=True)
    _thread.start()
    logger.info("WebSocket feed thread started")


def is_connected() -> bool:
    return bool(STORE.get("connected"))
