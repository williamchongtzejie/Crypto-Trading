# BTC/USDT Algorithmic Trading System

A paper-trading system for Bitcoin built on strategies from the research paper *"Optimizing Algorithmic Strategies for Trading Bitcoin"* (Gil Cohen, 2020). The system combines a **Pivot Reversal** primary signal with **MACD** confirmation, runs on daily Binance data, and is fully monitored through a Dash web dashboard.

---

## Strategy Foundation

Based on Cohen (2020), which tested RSI, MACD, and Pivot Reversal strategies on BTC daily data (2013–2018) using Particle Swarm Optimization (PSO).

| Strategy | Setup | Net Profit | Max Drawdown | Profit Factor | Win Rate |
|---|---|---|---|---|---|
| Pivot Reversal | X=4, Y=1 | $23,575 | 1.22% | 7.39 | 50.68% |
| MACD | Fast=13, Slow=26, Signal=10 | $20,207 | 2.67% | 2.74 | 49.57% |
| RSI | Period=13, OS=30, OB=70 | $2,727 | 2.18% | 1.53 | 61.54% |

### Combined Signal Logic

| Condition | Signal |
|---|---|
| Pivot BULL + MACD line > Signal line | **LONG** |
| Pivot BEAR + MACD line < Signal line | **SHORT** |
| Conflicting or no pivot | **HOLD** |

---

## System Architecture

```
strategy/
├── config/
│   └── config.yaml           # All parameters (API keys, risk limits, strategy params)
├── data/
│   ├── fetcher.py            # Binance REST API — fetches daily OHLCV
│   ├── processor.py          # Data cleaning and validation
│   └── database.py           # SQLite schema and CRUD (shared by bot + dashboard)
├── strategy/
│   ├── indicators.py         # Pivot Reversal, MACD, RSI calculations
│   └── signals.py            # Combined signal generator
├── risk/
│   └── manager.py            # Position sizing, stop-loss, circuit breakers
├── orders/
│   └── manager.py            # Order lifecycle: PENDING → FILLED → CLOSED
├── execution/
│   ├── paper_engine.py       # Paper trading fill simulator (fills at next open)
│   └── binance_engine.py     # Live Binance stub (drop-in when ready)
├── analysis/
│   ├── metrics.py            # NP, MDD, Profit Factor, Win Rate
│   └── reporter.py           # Plotly charts (equity curve, drawdown, heatmap)
├── dashboard/
│   ├── app.py                # Dash entry point → http://localhost:8050
│   ├── layouts/              # Overview, Signals, Positions, Controls tabs
│   ├── callbacks/            # Chart, table, and bot control callbacks
│   └── assets/style.css      # Dark theme styling
├── main.py                   # Bot scheduler (APScheduler, daily UTC 00:05)
└── requirements.txt
```

---

## The 6 Frameworks

### 1. Data Pipeline
- Fetches daily BTC/USDT OHLCV from Binance REST API (no API key needed for market data)
- Validates completeness: no missing candles, no zero volume, no invalid OHLC
- Stores to SQLite via idempotent upsert — safe to re-run without duplicates
- Runs daily at UTC 00:05 (5 minutes after candle close)

### 2. Strategy & Signal Generation
- **Pivot Reversal (X=4, Y=1):** Identifies swing highs (BEAR) and swing lows (BULL) over a `[i-4, i+1]` window. Signal confirmed only on closed bars — no look-ahead.
- **MACD (13, 26, 10):** EMA-based momentum filter. Only takes Pivot signals when MACD direction agrees.
- Output: `{signal, pivot, stop_price, macd_line, signal_line, histogram, timestamp}`

### 3. Risk Management
- **Position sizing:** Risk 1% of capital ($1,000) per trade. Size = $1,000 / |entry − stop|
- **Stop-loss:** Placed at the opposite pivot level (swing low for LONG, swing high for SHORT)
- **Circuit breakers:**
  - Portfolio drawdown ≥ 10% → bot stops permanently (until manually restarted)
  - Daily loss ≥ 2% → bot pauses until next day
- Max 1 open position at a time

### 4. Order Management
- SQLite-backed order book with full lifecycle tracking
- States: `PENDING → FILLED → CLOSED` (or `CANCELLED`)
- Tracks: entry price, stop price, fill price, exit price, realized PnL, timestamps

### 5. Execution
- **Paper Engine:** Fills at next day's open price. Checks intraday low/high for stop-loss hits.
- **Bot/Dashboard decoupling:** Both processes share only the SQLite database. The dashboard writes `bot_control.status`; the bot reads it on every cycle.
- **Live switch:** Replace `PaperEngine` with `BinanceEngine` in `main.py` when ready.

### 6. Post-Trade Analysis
- Metrics matching the paper: Net Profit, Max Drawdown ($ and %), Profit Factor, Win Rate
- Benchmark: strategy equity curve vs BTC buy-and-hold
- Exports: Plotly equity curve, drawdown chart, monthly PnL heatmap, CSV trade log

---

## Dashboard (Dash by Plotly)

Four tabs, auto-refreshes every 60 seconds:

| Tab | Contents |
|---|---|
| **Overview** | Metric cards (NP, MDD, PF, Win Rate, # Trades, Portfolio Value), equity curve vs buy-and-hold, drawdown chart, monthly PnL heatmap |
| **Signals** | Latest signal card, MACD chart history, recent signals table |
| **Positions** | Current open position, full trade history table with CSV export |
| **Controls** | Start / Pause / Stop buttons, config summary, drawdown & daily loss gauges |

---

## Quick Start

### Install dependencies
```bash
pip install -r requirements.txt
```

### Configure
Edit `config/config.yaml`. For paper trading, API keys are optional (public market data only).

### Run
```bash
# Terminal 1 — trading bot (executes daily at UTC 00:05)
python3 main.py

# Terminal 2 — dashboard
python3 dashboard/app.py
# → http://localhost:8050
```

Then open the dashboard, go to the **Controls** tab, and click **Start**.

---

## Configuration Reference

```yaml
trading:
  symbol: "BTCUSDT"
  interval: "1d"
  starting_capital: 100000    # Paper trading capital ($)
  risk_per_trade: 0.01        # 1% risk per trade
  max_drawdown_limit: 0.10    # 10% portfolio drawdown → full stop
  max_daily_loss: 0.02        # 2% daily loss → pause

pivot:
  x: 4    # First bar lookback (Setup 5, best in paper)
  y: 1    # Second bar lookback

macd:
  fast: 13     # Setup 18, best in paper
  slow: 26
  signal: 10
```

---

## Going Live

1. Add your Binance API key and secret to `config/config.yaml`
2. In `main.py`, replace `PaperEngine` with `BinanceEngine`
3. Implement order placement in `execution/binance_engine.py` using `python-binance`
4. Run on a server with a stable connection (e.g., AWS EC2, Raspberry Pi)

---

## References

Cohen, G. (2020). *Optimizing Algorithmic Trading Strategies for Bitcoin Using Particle Swarm Optimization.* Applied Economics Letters.

Wilder, J.W. (1978). *New Concepts in Technical Trading Systems.*

Appel, G. (1979). *The Moving Average Convergence-Divergence Method.*
