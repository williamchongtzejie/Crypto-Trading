import logging
from pathlib import Path

import pandas as pd
import yaml

from orders.manager import OrderManager
from risk.manager import calculate_position_size, check_circuit_breakers, compute_equity
from data.database import get_all_trades, get_bot_status, set_bot_status

logger = logging.getLogger(__name__)


def _load_config():
    path = Path(__file__).parent.parent / "config" / "config.yaml"
    with open(path) as f:
        return yaml.safe_load(f)


class PaperEngine:
    """
    Simulates order fills on daily bars.

    Fill rule: entry fills at the next bar's open price.
    Stop-loss check: if day's low (LONG) or high (SHORT) breaches the stop,
    the stop fills at the stop price.
    """

    def __init__(self):
        self.cfg = _load_config()
        self.orders = OrderManager()
        self.starting_capital = self.cfg["trading"]["starting_capital"]
        self.symbol = self.cfg["trading"]["symbol"]
        self._peak_equity = self.starting_capital
        self._daily_start_equity = self.starting_capital

    def _current_equity(self) -> float:
        trades = get_all_trades()
        return compute_equity(self.starting_capital, trades)

    def process_bar(self, signal: dict, bar: pd.Series):
        """
        Called once per completed daily bar.

        bar must have: open, high, low, close as floats, index=timestamp.
        signal is the output of signals.generate_signal().
        """
        if get_bot_status() != "RUNNING":
            logger.info("Bot is not RUNNING — skipping bar")
            return

        equity = self._current_equity()
        self._peak_equity = max(self._peak_equity, equity)

        tripped, new_status = check_circuit_breakers(
            self._peak_equity, equity, self._daily_start_equity, self.starting_capital
        )
        if tripped:
            set_bot_status(new_status)
            logger.warning("Circuit breaker tripped → %s", new_status)
            return

        open_pos = self.orders.get_open_position()

        # --- Check if existing position hit stop-loss ---
        if open_pos:
            order_id = open_pos["id"]
            side = open_pos["side"]
            stop = open_pos["stop_price"]
            fill = open_pos["fill_price"]

            stop_hit = (side == "LONG" and bar["low"] <= stop) or \
                       (side == "SHORT" and bar["high"] >= stop)

            if stop_hit:
                self.orders.close_position(order_id, stop)
                logger.info("Stop-loss triggered on order %d", order_id)
                open_pos = None

        # --- Open new position if no position and signal is directional ---
        if not open_pos and signal["signal"] in ("LONG", "SHORT"):
            entry_price = float(bar["open"])
            stop_price = signal["stop_price"]

            if stop_price is None or abs(entry_price - stop_price) < 1:
                logger.warning("Stop price too close to entry — skipping")
                return

            size = calculate_position_size(equity, entry_price, stop_price)
            if size <= 0:
                return

            order_id = self.orders.submit_order(
                self.symbol, signal["signal"], size, entry_price, stop_price
            )
            self.orders.fill_order(order_id, entry_price)

        # --- Close position if signal flips ---
        elif open_pos and signal["signal"] not in ("HOLD", open_pos["side"]):
            self.orders.close_position(open_pos["id"], float(bar["open"]))

        self._daily_start_equity = self._current_equity()
