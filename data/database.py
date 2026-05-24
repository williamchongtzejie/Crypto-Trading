import sqlite3
from contextlib import contextmanager
from pathlib import Path
import yaml


def load_config():
    config_path = Path(__file__).parent.parent / "config" / "config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def get_db_path():
    cfg = load_config()
    base = Path(__file__).parent.parent
    return str(base / cfg["database"]["path"])


@contextmanager
def get_conn():
    conn = sqlite3.connect(get_db_path(), detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS ohlcv (
                timestamp  TEXT PRIMARY KEY,
                symbol     TEXT NOT NULL,
                interval   TEXT NOT NULL,
                open       REAL NOT NULL,
                high       REAL NOT NULL,
                low        REAL NOT NULL,
                close      REAL NOT NULL,
                volume     REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS signals (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   TEXT NOT NULL,
                signal      TEXT NOT NULL,
                pivot       TEXT,
                pivot_price REAL,
                stop_price  REAL,
                macd_line   REAL,
                signal_line REAL,
                histogram   REAL
            );

            CREATE TABLE IF NOT EXISTS orders (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol       TEXT NOT NULL,
                side         TEXT NOT NULL,
                status       TEXT NOT NULL DEFAULT 'PENDING',
                size         REAL NOT NULL,
                entry_price  REAL,
                stop_price   REAL,
                fill_price   REAL,
                exit_price   REAL,
                submitted_at TEXT,
                filled_at    TEXT,
                closed_at    TEXT,
                pnl          REAL
            );

            CREATE TABLE IF NOT EXISTS bot_control (
                id         INTEGER PRIMARY KEY CHECK (id = 1),
                status     TEXT NOT NULL DEFAULT 'STOPPED',
                updated_at TEXT
            );

            INSERT OR IGNORE INTO bot_control (id, status, updated_at)
            VALUES (1, 'STOPPED', datetime('now'));
        """)


def upsert_candles(rows: list[dict]):
    if not rows:
        return
    with get_conn() as conn:
        conn.executemany(
            """INSERT INTO ohlcv (timestamp, symbol, interval, open, high, low, close, volume)
               VALUES (:timestamp, :symbol, :interval, :open, :high, :low, :close, :volume)
               ON CONFLICT(timestamp) DO UPDATE SET
                   open=excluded.open, high=excluded.high, low=excluded.low,
                   close=excluded.close, volume=excluded.volume""",
            rows,
        )


def get_candles(symbol: str, interval: str, limit: int = 500) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT * FROM ohlcv
               WHERE symbol=? AND interval=?
               ORDER BY timestamp DESC LIMIT ?""",
            (symbol, interval, limit),
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


def insert_signal(record: dict):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO signals
               (timestamp, signal, pivot, pivot_price, stop_price, macd_line, signal_line, histogram)
               VALUES (:timestamp, :signal, :pivot, :pivot_price, :stop_price,
                       :macd_line, :signal_line, :histogram)""",
            record,
        )


def get_bot_status() -> str:
    with get_conn() as conn:
        row = conn.execute("SELECT status FROM bot_control WHERE id=1").fetchone()
    return row["status"] if row else "STOPPED"


def set_bot_status(status: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE bot_control SET status=?, updated_at=datetime('now') WHERE id=1",
            (status,),
        )


def get_recent_signals(limit: int = 20) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM signals ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_all_trades() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM orders WHERE status='CLOSED' ORDER BY closed_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def get_open_position() -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM orders WHERE status='FILLED' ORDER BY filled_at DESC LIMIT 1"
        ).fetchone()
    return dict(row) if row else None
