import logging
from datetime import datetime, timezone

from data.database import get_conn, get_open_position

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class OrderManager:
    def submit_order(
        self,
        symbol: str,
        side: str,
        size: float,
        entry_price: float,
        stop_price: float,
    ) -> int:
        """Insert a PENDING order and return its id."""
        with get_conn() as conn:
            cur = conn.execute(
                """INSERT INTO orders
                   (symbol, side, status, size, entry_price, stop_price, submitted_at)
                   VALUES (?, ?, 'PENDING', ?, ?, ?, ?)""",
                (symbol, side, size, entry_price, stop_price, _now()),
            )
            order_id = cur.lastrowid
        logger.info("Order %d submitted: %s %s %.6f @ %.2f stop=%.2f",
                    order_id, side, symbol, size, entry_price, stop_price)
        return order_id

    def fill_order(self, order_id: int, fill_price: float):
        """Move order from PENDING to FILLED."""
        with get_conn() as conn:
            conn.execute(
                """UPDATE orders
                   SET status='FILLED', fill_price=?, filled_at=?
                   WHERE id=? AND status='PENDING'""",
                (fill_price, _now(), order_id),
            )
        logger.info("Order %d filled @ %.2f", order_id, fill_price)

    def close_position(self, order_id: int, exit_price: float) -> float:
        """Close a FILLED order, compute and store PnL. Returns realized PnL."""
        with get_conn() as conn:
            row = conn.execute(
                "SELECT side, size, fill_price FROM orders WHERE id=?", (order_id,)
            ).fetchone()
            if not row:
                raise ValueError(f"Order {order_id} not found")

            side, size, fill_price = row["side"], row["size"], row["fill_price"]
            if side == "LONG":
                pnl = (exit_price - fill_price) * size
            else:
                pnl = (fill_price - exit_price) * size

            conn.execute(
                """UPDATE orders
                   SET status='CLOSED', exit_price=?, closed_at=?, pnl=?
                   WHERE id=?""",
                (exit_price, _now(), pnl, order_id),
            )
        logger.info("Order %d closed @ %.2f | PnL: $%.2f", order_id, exit_price, pnl)
        return pnl

    def cancel_order(self, order_id: int):
        with get_conn() as conn:
            conn.execute(
                "UPDATE orders SET status='CANCELLED' WHERE id=? AND status='PENDING'",
                (order_id,),
            )
        logger.info("Order %d cancelled", order_id)

    def get_open_position(self) -> dict | None:
        return get_open_position()
