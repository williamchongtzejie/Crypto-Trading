# BTC/USDT Algorithmic Trading System

A paper-trading system for Bitcoin built on strategies from the research paper *"Optimizing Algorithmic Strategies for Trading Bitcoin"* (Gil Cohen, 2020). The system combines a **Pivot Reversal** primary signal with **MACD** confirmation, runs on daily Binance data, and is fully monitored through a Dash web dashboard with live WebSocket price feed and historical backtesting.

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
│   └── config.yaml               # All parameters (API keys, risk limits, strategy params)
├── data/
│   ├── fetcher.py                # Binance REST API — fetches daily OHLCV
│   ├── processor.py              # Data cleaning and validation
│   ├── database.py               # SQLite schema and CRUD (shared by bot + dashboard)
│   └── ws_feed.py                # Binance WebSocket feed (live price + candle)
├── strategy/
│   ├── indicators.py             # Pivot Reversal, MACD, RSI calculations
│   └── signals.py                # Combined signal generator
├── risk/
│   └── manager.py                # Position sizing, stop-loss, circuit breakers
├── orders/
│   └── manager.py                # Order lifecycle: PENDING → FILLED → CLOSED
├── execution/
│   ├── paper_engine.py           # Paper trading fill simulator (fills at next open)
│   └── binance_engine.py         # Live Binance stub (drop-in when ready)
├── analysis/
│   ├── metrics.py                # NP, MDD, Profit Factor, Win Rate
│   ├── reporter.py               # Plotly charts (equity curve, drawdown, heatmap)
│   └── backtest.py               # Walk-forward backtesting engine (18 metrics)
├── dashboard/
│   ├── app.py                    # Dash entry point → http://localhost:8050
│   ├── layouts/
│   │   ├── live_chart.py         # Live Chart tab
│   │   ├── backtest.py           # Backtest tab
│   │   ├── overview.py           # Overview tab
│   │   ├── signals.py            # Signals tab
│   │   ├── positions.py          # Positions tab
│   │   └── controls.py           # Controls tab
│   ├── callbacks/
│   │   ├── live.py               # Live chart + WebSocket callbacks
│   │   ├── backtest_cb.py        # Backtest run + results callbacks
│   │   ├── charts.py             # Overview chart callbacks
│   │   ├── tables.py             # Trade/signal table callbacks
│   │   └── bot_control.py        # Start/Stop/Pause + Run Now callbacks
│   └── assets/style.css          # Dark theme styling
├── main.py                       # Bot scheduler (daily UTC 00:05)
└── requirements.txt
```

---

## The 6 Frameworks

### 1. Data Pipeline
- Fetches daily BTC/USDT OHLCV from Binance REST API (no API key needed for market data)
- Validates completeness: no missing candles, no zero volume, no invalid OHLC
- Stores to SQLite via idempotent upsert — safe to re-run without duplicates
- **WebSocket feed** (`data/ws_feed.py`) streams live price and the current building candle continuously in a background thread — no polling
- Runs daily bot cycle at UTC 00:05 (5 minutes after candle close)

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
- **Paper Engine:** Fills at next day's open price. Checks intraday low/high for stop-loss hits. Includes 0.1% Binance taker fee in all PnL calculations.
- **Bot/Dashboard decoupling:** Both processes share only the SQLite database. The dashboard writes `bot_control.status`; the bot reads it on every cycle.
- **Live switch:** Replace `PaperEngine` with `BinanceEngine` in `main.py` when ready.

### 6. Post-Trade Analysis
- Metrics matching the paper: Net Profit, Max Drawdown ($ and %), Profit Factor, Win Rate
- Benchmark: strategy equity curve vs BTC buy-and-hold
- Exports: Plotly equity curve, drawdown chart, monthly PnL heatmap, CSV trade log

---

## Dashboard

Six tabs at **http://localhost:8050**, with a 5-second live refresh and 60-second analytics refresh.

### Live Chart
Real-time market data via Binance WebSocket — no REST polling.
- **Live price strip** — BTC/USDT price, 24h change (green/red), 24h high/low, volume, last update time. Updates on every trade from Binance.
- **Candlestick chart** — last 30/60/90/180 daily bars with green/red candles. ▲ Bull pivot and ▼ Bear pivot markers overlaid directly on price bars. Today's live building candle highlighted in blue.
- **MACD sub-panel** — histogram (green/red bars), MACD line vs Signal line for the selected range.
- **Signal card** — current LONG / SHORT / HOLD with raw indicator values.
- **Connection indicator** — 🟢 green dot when WebSocket is live, 🔴 red on reconnect.

### Backtest
Full historical backtest on Binance data from **2017-08-17 to present** (~8 years).
- **Parameter controls** — date range picker, Pivot X/Y, MACD fast/slow/signal, starting capital, risk %
- **▶ Run Backtest** button — fetches and caches data, runs simulation, displays results instantly on re-runs
- **18 performance metrics** across two rows:

| Paper Metrics | Risk-Adjusted | Trade Statistics |
|---|---|---|
| Net Profit | Sharpe Ratio | Total / Win / Loss trades |
| Max Drawdown (% + $) | Sortino Ratio | Turnover (trades/yr) |
| Profit Factor | Calmar Ratio | Avg Holding Period |
| Win Rate | CAGR | Avg Win / Avg Loss |
| vs Buy & Hold | Recovery Factor | Best / Worst Trade |
| | Expectancy / trade | |

- **Equity curve** vs BTC buy-and-hold, **Drawdown chart**, **Monthly PnL heatmap**
- **Trade log** — every simulated trade with entry/exit/stop/PnL/duration/exit reason, filterable, sortable, with CSV export

### Overview
- Metric cards: Net Profit, MDD, Profit Factor, Win Rate, # Trades, Portfolio Value
- Equity curve vs buy-and-hold, drawdown chart, monthly PnL heatmap (live paper trading data)

### Signals
- Latest signal card with pivot and MACD values
- MACD history chart
- Recent signals table (last 50)

### Positions
- Current open position card (entry, stop, size)
- Full trade history table with CSV export

### Controls
- **Start / Pause / Stop** bot buttons — writes directly to SQLite `bot_control` table
- **▶ Run Cycle Now** — triggers an immediate full trading cycle without waiting for UTC 00:05
- Configuration summary panel
- Portfolio drawdown and daily loss progress bars

---

## How to Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure

Edit `config/config.yaml`. For paper trading, Binance API keys are **not required** — all market data is public.

```yaml
binance:
  api_key: ""       # leave blank for paper trading
  api_secret: ""
```

### 3. Open two terminal tabs (Cmd + T for a new tab on Mac)

**Terminal 1 — Trading Bot**
```bash
cd "path/to/Strategy"
python3 main.py
```
The bot initialises the database, then waits. It fires a full trading cycle every day at **UTC 00:05** (midnight UTC, 08:05 SGT).

**Terminal 2 — Dashboard**
```bash
cd "path/to/Strategy"
python3 dashboard/app.py
```
The dashboard starts the Binance WebSocket feed automatically and opens at:
```
http://localhost:8050
```

### 4. Start the bot from the dashboard

1. Open **http://localhost:8050** in your browser
2. Click the **Controls** tab
3. Click **Start** — the status badge turns green
4. To run a cycle immediately without waiting for UTC 00:05, click **▶ Run Cycle Now**

### 5. Run a backtest

1. Click the **Backtest** tab
2. Select a date range, adjust parameters if desired, click **▶ Run Backtest**
3. Results appear within a few seconds — data is cached so re-runs with different params are instant

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

dashboard:
  host: "127.0.0.1"
  port: 8050
  refresh_interval_ms: 60000  # analytics tabs
  # live chart refreshes separately every 5 seconds via WebSocket
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
