"""
Trading bot entry point.
Runs daily at UTC 00:05 (5 minutes after daily candle close).
Reads bot_control.status from SQLite to honour Start/Stop/Pause from dashboard.
"""
import logging
import sys
import time
from pathlib import Path

import pandas as pd
import yaml
# APScheduler removed — using a lightweight while-loop scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("trading.log"),
    ],
)
logger = logging.getLogger("main")


def load_config():
    with open(Path(__file__).parent / "config" / "config.yaml") as f:
        return yaml.safe_load(f)


def run_once():
    """Execute one full trading cycle."""
    from data.fetcher import BinanceFetcher
    from data.processor import clean_ohlcv
    from data import database as db
    from strategy.signals import generate_signal
    from execution.paper_engine import PaperEngine

    cfg = load_config()
    fetcher = BinanceFetcher()
    engine = PaperEngine()

    # 1. Fetch and store latest candles
    rows = fetcher.fetch_historical(limit=200)
    from data.processor import to_ohlcv_rows
    db.upsert_candles(rows)

    # 2. Load candles into DataFrame
    candle_rows = db.get_candles(cfg["trading"]["symbol"], cfg["trading"]["interval"], limit=200)
    if len(candle_rows) < 50:
        logger.warning("Not enough candles (%d) to compute indicators", len(candle_rows))
        return

    df = pd.DataFrame(candle_rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.set_index("timestamp").sort_index()

    # 3. Generate signal
    signal = generate_signal(df)
    db.insert_signal(signal)

    # 4. Execute on current bar
    current_bar = df.iloc[-1]
    engine.process_bar(signal, current_bar)


def main():
    """
    Run the bot on a daily schedule (blocking loop).
    Fires at UTC 00:05 every day. Checks every 30 seconds so it never
    misses the target minute and responds quickly to Stop/Pause from dashboard.
    """
    from datetime import datetime, timezone
    from data.database import init_db, get_bot_status

    logger.info("Initialising database…")
    init_db()
    logger.info("Bot started. Fires daily at UTC 00:05. Press Ctrl+C to stop.")

    last_run_date = None

    try:
        while True:
            now = datetime.now(tz=timezone.utc)

            # Fire at 00:05 UTC, once per day
            if now.hour == 0 and now.minute == 5 and now.date() != last_run_date:
                status = get_bot_status()
                if status == "RUNNING":
                    logger.info("=== Daily cycle starting ===")
                    try:
                        run_once()
                        last_run_date = now.date()
                    except Exception as e:
                        logger.exception("Error during daily cycle: %s", e)
                elif status == "PAUSED":
                    logger.info("Bot is PAUSED — skipping today's cycle")
                    last_run_date = now.date()
                else:
                    logger.info("Bot is STOPPED — skipping today's cycle")
                    last_run_date = now.date()

            time.sleep(30)

    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")


if __name__ == "__main__":
    main()
