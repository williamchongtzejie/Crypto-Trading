# Trading System — Improvement Roadmap

Comparing our current implementation against the professional **Trading Architecture - Key Components** diagram, this document identifies the gaps and proposes concrete improvements across all six frameworks plus cross-cutting infrastructure.

---

## Framework 1 — Market Data

### Current State
- Single source: Binance REST API (daily OHLCV bars only)
- No real-time feed; polling once per day at UTC 00:05

### Improvements

#### 1.1 Real-Time WebSocket Feed
Replace the daily REST poll with a persistent Binance WebSocket stream. Subscribe to the `kline` channel and process each bar as it closes — enabling faster reaction and intraday monitoring even on a daily strategy.

```python
# execution/websocket_feed.py
# Subscribe to wss://stream.binance.com:9443/ws/btcusdt@kline_1d
# On kline.x == True (bar closed) → trigger run_once()
```

#### 1.2 Alternative & Sentiment Data
The architecture diagram includes *News / Alternative Data* as a first-class market data source. Add:

| Source | What It Adds |
|---|---|
| **Crypto Fear & Greed Index** (Alternative.me API) | Market sentiment filter — avoid longs in Extreme Fear |
| **Glassnode / CryptoQuant** | On-chain metrics: hash rate, exchange netflow, active addresses |
| **Twitter/Reddit sentiment** | NLP-scored social sentiment as a secondary signal filter |

#### 1.3 Order Book Snapshots
The diagram references *Order Book Snapshots* in the Market Data Store. Capture Binance L2 depth snapshots at bar close to measure bid-ask spread, liquidity, and market depth — inputs for smarter execution and slippage estimation.

#### 1.4 Multi-Source Redundancy
Add a fallback data source (e.g., CoinGecko or Kraken) in case Binance REST is unavailable. The `BinanceFetcher` could implement a source-switching pattern with automatic failover.

---

## Framework 2 — Strategy & Signal Generation

### Current State
- Two indicators: Pivot Reversal (primary) + MACD (confirmation)
- Parameters fixed from the paper (no live re-optimisation)
- Single asset (BTC), single timeframe (daily)

### Improvements

#### 2.1 PSO Parameter Optimiser (from the paper)
The paper's core contribution is **Particle Swarm Optimization** of strategy parameters — but we hard-coded the best-known values. Implement the actual PSO loop to periodically re-optimise on recent data using a rolling window.

```
strategy/optimizer.py
  - PSO class: particles, velocity update, pbest/gbest tracking
  - Fitness function: weighted utility U = Σ wᵢ · ln(F(Xᵢ))
  - Runs monthly on trailing 6-month window
  - Writes updated params back to config.yaml
```

#### 2.2 Machine Learning Signal Layer
Add an ML model as a third confirmation filter, sitting between signal generation and execution:

| Model | Input Features | Output |
|---|---|---|
| **LSTM** | Last 60 days OHLCV + MACD + RSI | Probability of up/down move next day |
| **Random Forest** | Technical indicators + on-chain metrics | Signal direction classification |
| **XGBoost** | All of the above + sentiment score | Confidence score 0–1 |

Only take a trade if pivot + MACD + ML model all agree.

#### 2.3 Multi-Timeframe Confirmation
Add 4-hour bars as an entry-timing layer. The daily bar sets direction; the 4H bar triggers the precise entry:

```
Daily signal = LONG (Pivot BULL + MACD bullish)
  → Wait for 4H MACD crossover to confirm
  → Enter on the next 4H bar open
```

This reduces false entries from noisy daily opens.

#### 2.4 RSI Filter
The paper found RSI underperformed standalone, but it can serve as an **extreme filter**:
- Suppress LONG entries when RSI (13) > 75 (overbought)
- Suppress SHORT entries when RSI (13) < 25 (oversold)

#### 2.5 Multi-Asset Portfolio Construction
Extend beyond BTC to a small crypto portfolio (ETH, BNB, SOL). The diagram's *Portfolio Construction & Optimizer* block includes position sizing, optimization, and constraints across assets. Add:

```
strategy/portfolio.py
  - Per-asset signal generation (same Pivot + MACD logic)
  - Portfolio-level position sizing (equal risk contribution)
  - Correlation check: don't open correlated longs simultaneously
```

---

## Framework 3 — Risk Management

### Current State
- Fixed 1% position sizing
- Stop-loss at opposite pivot level
- Two circuit breakers: 10% portfolio drawdown + 2% daily loss

### Improvements

#### 3.1 Value at Risk (VaR) & Stressed VaR
The architecture shows a *Real-Time Risk Engine* with VaR/SVaR. Add:

```python
# risk/var.py
def historical_var(returns: pd.Series, confidence: float = 0.95) -> float:
    """95% 1-day VaR using historical simulation."""
    return float(np.percentile(returns, (1 - confidence) * 100))

def stressed_var(returns: pd.Series, stress_window: str = "2018") -> float:
    """SVaR using worst historical period."""
    ...
```

Report VaR on the dashboard and use it to cap position sizes.

#### 3.2 Stress Testing & What-If Analysis
Simulate the portfolio against historical shock scenarios:
- BTC -30% in one day (March 2020 COVID crash)
- BTC -80% drawdown (2018 bear market)
- Flash crash with stop-loss gap-through

Show stress test results in the dashboard's Controls tab.

#### 3.3 Kelly Criterion Position Sizing
Replace fixed 1% risk with **fractional Kelly** sizing, calculated dynamically from rolling win rate and average win/loss:

```python
def kelly_fraction(win_rate: float, avg_win: float, avg_loss: float, fraction: float = 0.5) -> float:
    """Half-Kelly for conservatism."""
    b = avg_win / avg_loss
    k = (b * win_rate - (1 - win_rate)) / b
    return max(0, k * fraction)
```

#### 3.4 Notional Exposure & Concentration Limits
Cap total notional exposure (position size × price) as a percentage of capital. For multi-asset: cap single-asset concentration at 40% of portfolio.

#### 3.5 Order Throttle
Prevent signal storms from opening too many trades in a short window:
- Max 1 trade per day (already enforced)
- If the bot restarts mid-day, check if a trade was already taken today before acting

---

## Framework 4 — Order Management

### Current State
- Simple lifecycle: PENDING → FILLED → CLOSED
- No amend/cancel, no partial fills, no routing

### Improvements

#### 4.1 Amend & Cancel
Allow stop-loss price to be trailed as the position moves in favour:

```python
def trail_stop(order_id: int, new_stop: float):
    """Move stop-loss to lock in profit as price rises."""
    # Only move stop in the direction of the trade
    # LONG: new_stop > current_stop
    # SHORT: new_stop < current_stop
```

Expose a **Trail Stop** button on the dashboard Positions tab.

#### 4.2 Partial Fill Simulation
In paper trading, model partial fills for large positions relative to market volume:

```python
# If position_value > 0.5% of 24h volume → simulate 2-bar partial fill
```

#### 4.3 Take-Profit Orders
Add an optional take-profit level alongside every stop-loss:
- Fixed R:R ratio (e.g., 2:1 — take profit at 2× the risk distance)
- Or at the next opposing pivot level

Track TP orders in the `orders` table with a `tp_price` column.

---

## Framework 5 — Execution

### Current State
- Paper engine fills at next-day open (optimistic)
- Live engine is a stub
- No slippage or market impact modelling

### Improvements

#### 5.1 Realistic Slippage Model
The paper fills at exactly the open price, but real execution has slippage. Model it in the paper engine:

```python
# paper_engine.py
def _apply_slippage(price: float, side: str, volume_24h: float, size_usd: float) -> float:
    """Estimate market impact based on order size vs daily volume."""
    participation_rate = size_usd / volume_24h
    slippage_bps = participation_rate * 10  # simple linear model
    direction = 1 if side == "LONG" else -1
    return price * (1 + direction * slippage_bps / 10000)
```

#### 5.2 TWAP / VWAP Execution (Live)
For the live `BinanceEngine`, split large orders into time-weighted slices to reduce market impact:

```
execution/algorithms/
  twap.py   — split order into N equal time slices
  vwap.py   — weight slices by expected volume profile
```

#### 5.3 Transaction Cost Accounting
Track Binance maker/taker fees (0.1% spot, 0.02%/0.05% futures) on every paper fill and include them in PnL calculations. Currently we assume zero fees.

```python
FEE_RATE = 0.001  # 10 bps taker fee
pnl_after_fees = gross_pnl - (entry_value + exit_value) * FEE_RATE
```

#### 5.4 Live BinanceEngine Implementation
Complete `execution/binance_engine.py` using `python-binance`:
- Market orders for entries/exits
- API rate limit handling with exponential backoff
- Order confirmation loop (poll until FILLED)
- Store exchange order IDs alongside internal order IDs

---

## Framework 6 — Post-Trade Analysis

### Current State
- Net Profit, MDD, Profit Factor, Win Rate (matching the paper)
- Equity curve vs buy-and-hold
- Monthly PnL heatmap

### Improvements

#### 6.1 Unrealised PnL (Mark-to-Market)
The diagram includes *Mark-to-Market* as a key post-trade component. Track floating PnL for open positions using the latest close price, displayed live on the dashboard:

```python
def mark_to_market(open_pos: dict, current_price: float) -> float:
    if open_pos["side"] == "LONG":
        return (current_price - open_pos["fill_price"]) * open_pos["size"]
    return (open_pos["fill_price"] - current_price) * open_pos["size"]
```

#### 6.2 PnL Attribution
Break down returns by:
- **Signal source:** how much came from Pivot vs MACD confirmation
- **Time of year:** seasonal patterns in BTC returns
- **Trade duration:** short vs long holding periods

#### 6.3 Walk-Forward Backtesting
Replace the static backtest with a proper **walk-forward** validation:
- In-sample: optimise parameters on 18-month window
- Out-of-sample: trade the next 6-month window
- Roll forward and repeat

This prevents overfitting to a single historical period.

#### 6.4 Sharpe & Sortino Ratios
Add standard risk-adjusted return metrics missing from the paper:

```python
def sharpe(returns: pd.Series, risk_free: float = 0.0) -> float:
    excess = returns - risk_free / 252
    return excess.mean() / excess.std() * (252 ** 0.5)

def sortino(returns: pd.Series, risk_free: float = 0.0) -> float:
    excess = returns - risk_free / 252
    downside = excess[excess < 0].std()
    return excess.mean() / downside * (252 ** 0.5)
```

#### 6.5 Regulatory & Audit Reporting
Export a full audit trail (every signal, order, fill, and config change with timestamps) to CSV monthly. Required if this ever becomes investor-facing.

---

## Cross-Cutting Infrastructure

The diagram's bottom layer — **Cross-Cutting Infrastructure & Services** — is almost entirely absent from our current system.

### CI.1 Alerting System
Send notifications when important events occur:

| Event | Channel |
|---|---|
| New LONG / SHORT signal | Telegram bot or email |
| Stop-loss triggered | Telegram (urgent) |
| Circuit breaker tripped | Email + Telegram |
| Daily PnL summary | Email at UTC 06:00 |

```python
# infra/notifier.py
# Telegram: python-telegram-bot
# Email: smtplib
```

### CI.2 Audit Trail & Replay
Log every state change (signal, order, fill, config change) to a separate `audit_log` table with microsecond timestamps. Support *replay* mode: re-run any historical day from the audit log to reproduce exact system state for debugging.

### CI.3 Feature Flags
Add a `features` table in SQLite to toggle capabilities without redeploying:

| Flag | Purpose |
|---|---|
| `ml_filter_enabled` | Enable/disable ML confirmation layer |
| `multi_asset_enabled` | Trade ETH/BNB alongside BTC |
| `trailing_stop_enabled` | Activate dynamic stop trailing |
| `live_trading_enabled` | Switch from paper to live execution |

Expose these as toggles on the dashboard Controls tab.

### CI.4 Security
- **Encrypt API keys** at rest using `cryptography.fernet` — never store plaintext keys in `config.yaml`
- **Dashboard authentication** — add HTTP Basic Auth or token-based login to the Dash app before exposing it on any non-localhost interface
- **Environment variables** — load secrets from `.env` via `python-dotenv`, never commit them

### CI.5 Database Backup & Recovery
SQLite has no built-in replication. Add a daily backup job:

```python
# infra/backup.py
import shutil
shutil.copy("trading.db", f"backups/trading_{date}.db")
# Optionally sync to S3 / Google Drive
```

### CI.6 Health Monitoring
Add a heartbeat endpoint that the dashboard can poll:

```python
# A lightweight Flask or FastAPI health check
GET /health → {"status": "ok", "last_cycle": "2026-05-25T00:05:00Z", "bot_status": "RUNNING"}
```

Alert via Telegram if the heartbeat goes stale (bot has crashed).

### CI.7 Time Synchronisation
The diagram calls out NTP/PTP clock synchronisation. For daily bars this is low priority, but for intraday strategies ensure the host clock is NTP-synced to avoid timestamp misalignment with Binance server time:

```bash
# Verify system clock offset vs Binance server time
GET https://api.binance.com/api/v3/time
```

---

## Priority Summary

| Priority | Improvement | Effort | Impact |
|---|---|---|---|
| High | **Transaction cost accounting** (fees in PnL) | Low | High |
| High | **Mark-to-market unrealised PnL** | Low | High |
| High | **Alerting (Telegram/email)** | Low | High |
| High | **Realistic slippage model** | Medium | High |
| High | **PSO parameter re-optimiser** | Medium | High |
| Medium | **Walk-forward backtesting** | Medium | High |
| Medium | **VaR / Stressed VaR** | Medium | Medium |
| Medium | **Trailing stop-loss** | Medium | Medium |
| Medium | **Fear & Greed / sentiment filter** | Low | Medium |
| Medium | **API key encryption + dashboard auth** | Medium | High |
| Medium | **Database backup** | Low | Medium |
| Low | **ML signal layer (LSTM/RF)** | High | High |
| Low | **Multi-asset portfolio** | High | Medium |
| Low | **TWAP/VWAP execution** | High | Medium |
| Low | **Live BinanceEngine** | Medium | High |
