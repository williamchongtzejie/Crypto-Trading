"""
Walk-forward backtesting engine for Pivot Reversal + MACD strategy.

Simulation rules (matching the paper):
  - Signal computed on bar i (using closed data, no look-ahead)
  - Entry fills at bar i+1 open price
  - Stop-loss checked intrabar: if day's low (LONG) or high (SHORT) breaches stop → fill at stop
  - One position at a time
  - Position flips on opposing signal (exit at open, enter at same open)
  - Fees: 0.1% taker per fill (Binance spot)
"""

import numpy as np
import pandas as pd

from strategy.indicators import pivot_reversal, macd as compute_macd


FEE_RATE = 0.001   # 0.1% Binance taker fee per side


# ------------------------------------------------------------------ #
#  Historical data fetcher (paginated)                                #
# ------------------------------------------------------------------ #

def fetch_historical_ohlcv(symbol: str = "BTCUSDT", interval: str = "1d") -> pd.DataFrame:
    """
    Pull all available daily OHLCV from Binance via paginated REST.
    Binance daily data goes back to 2017-08-17 for BTCUSDT.
    Returns a clean DataFrame indexed by UTC timestamp.
    """
    import json, urllib.request
    from datetime import datetime, timezone

    all_rows = []
    start_ms = int(datetime(2017, 8, 17, tzinfo=timezone.utc).timestamp() * 1000)
    base_url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit=1000"

    while True:
        url = f"{base_url}&startTime={start_ms}"
        with urllib.request.urlopen(url, timeout=15) as r:
            batch = json.loads(r.read())
        if not batch:
            break

        for k in batch:
            all_rows.append({
                "timestamp": pd.Timestamp(k[0], unit="ms", tz="UTC"),
                "open":   float(k[1]),
                "high":   float(k[2]),
                "low":    float(k[3]),
                "close":  float(k[4]),
                "volume": float(k[5]),
            })

        # Advance start to the bar after the last one received
        last_open_ms = batch[-1][0]
        start_ms = last_open_ms + 86_400_000  # +1 day in ms

        if len(batch) < 1000:
            break  # reached the end

    df = pd.DataFrame(all_rows).set_index("timestamp").sort_index()
    df = df[~df.index.duplicated()]
    return df


# ------------------------------------------------------------------ #
#  Core backtest engine                                               #
# ------------------------------------------------------------------ #

def run_backtest(
    df: pd.DataFrame,
    pivot_x: int = 4,
    pivot_y: int = 1,
    macd_fast: int = 13,
    macd_slow: int = 26,
    macd_signal: int = 10,
    starting_capital: float = 100_000,
    risk_per_trade: float = 0.01,
) -> dict:
    """
    Run a full backtest and return a results dict containing:
      - trades: list of closed trade dicts
      - equity: pd.Series of daily portfolio value
      - metrics: dict of performance metrics
      - df: the enriched OHLCV DataFrame with signals
    """
    # --- Compute indicators ---
    pivots  = pivot_reversal(df, x=pivot_x, y=pivot_y)
    macd_df = compute_macd(df, fast=macd_fast, slow=macd_slow, signal=macd_signal)

    # --- Generate signals bar by bar (no look-ahead) ---
    # Signal for bar i is emitted at bar i; entry fills at bar i+1 open
    signals = []
    for i in range(len(df)):
        if i < macd_slow + macd_signal + pivot_x:
            signals.append("HOLD")
            continue
        pivot_val   = pivots.iloc[i]
        macd_bull   = macd_df["macd_line"].iloc[i] > macd_df["signal_line"].iloc[i]
        macd_bear   = macd_df["macd_line"].iloc[i] < macd_df["signal_line"].iloc[i]

        if pivot_val == "BULL" and macd_bull:
            signals.append("LONG")
        elif pivot_val == "BEAR" and macd_bear:
            signals.append("SHORT")
        else:
            signals.append("HOLD")

    df = df.copy()
    df["signal"]      = signals
    df["macd_line"]   = macd_df["macd_line"]
    df["signal_line"] = macd_df["signal_line"]
    df["pivot"]       = pivots

    # --- Simulate trades ---
    trades      = []
    equity_vals = []
    capital     = starting_capital
    peak_equity = starting_capital

    position = None   # dict: {side, entry_price, stop_price, size, entry_date, entry_bar}

    for i in range(1, len(df)):
        bar        = df.iloc[i]
        prev_sig   = df["signal"].iloc[i - 1]
        prev_bar   = df.iloc[i - 1]
        date       = df.index[i]

        # --- Check stop-loss on existing position ---
        if position is not None:
            stop    = position["stop_price"]
            side    = position["side"]
            stop_hit = (side == "LONG"  and bar["low"]  <= stop) or \
                       (side == "SHORT" and bar["high"] >= stop)

            if stop_hit:
                exit_price = stop
                pnl = _calc_pnl(position, exit_price)
                capital += pnl
                trades.append(_close_trade(position, exit_price, date, pnl, "stop"))
                position = None

        # --- Open / flip position based on yesterday's signal ---
        if prev_sig in ("LONG", "SHORT"):
            if position is not None:
                if position["side"] == prev_sig:
                    pass   # same direction — hold
                else:
                    # Flip: close existing, open new
                    exit_price = bar["open"]
                    pnl = _calc_pnl(position, exit_price)
                    capital += pnl
                    trades.append(_close_trade(position, exit_price, date, pnl, "signal_flip"))
                    position = None
                    position = _open_trade(prev_sig, bar, date, capital, risk_per_trade, prev_bar)
            else:
                position = _open_trade(prev_sig, bar, date, capital, risk_per_trade, prev_bar)

        elif prev_sig == "HOLD" and position is not None:
            pass   # hold existing position through HOLD bars

        peak_equity = max(peak_equity, capital)
        equity_vals.append(capital)

    # Close any open position at the last bar's close
    if position is not None:
        last_bar   = df.iloc[-1]
        exit_price = last_bar["close"]
        pnl        = _calc_pnl(position, exit_price)
        capital   += pnl
        trades.append(_close_trade(position, exit_price, df.index[-1], pnl, "end"))

    equity = pd.Series(equity_vals, index=df.index[1:], name="equity")
    metrics = compute_backtest_metrics(trades, equity, starting_capital, df)

    return {
        "trades":  trades,
        "equity":  equity,
        "metrics": metrics,
        "df":      df,
    }


def _open_trade(side, bar, date, capital, risk_pct, prev_bar):
    entry_price = bar["open"]
    stop_price  = prev_bar["low"] if side == "LONG" else prev_bar["high"]
    price_risk  = abs(entry_price - stop_price)
    if price_risk < 1:
        return None
    risk_amount = capital * risk_pct
    size        = risk_amount / price_risk
    return {
        "side":        side,
        "entry_price": entry_price,
        "stop_price":  stop_price,
        "size":        size,
        "entry_date":  date,
    }


def _calc_pnl(position, exit_price):
    side  = position["side"]
    entry = position["entry_price"]
    size  = position["size"]
    gross = (exit_price - entry) * size if side == "LONG" else (entry - exit_price) * size
    # Deduct fees on both entry and exit notional
    fees  = (entry * size + exit_price * size) * FEE_RATE
    return gross - fees


def _close_trade(position, exit_price, exit_date, pnl, exit_reason):
    duration = (exit_date - position["entry_date"]).days
    return {
        "side":        position["side"],
        "entry_price": position["entry_price"],
        "exit_price":  exit_price,
        "stop_price":  position["stop_price"],
        "size":        position["size"],
        "entry_date":  position["entry_date"].strftime("%Y-%m-%d"),
        "exit_date":   exit_date.strftime("%Y-%m-%d"),
        "duration":    duration,
        "pnl":         round(pnl, 2),
        "exit_reason": exit_reason,
    }


# ------------------------------------------------------------------ #
#  Metrics computation                                                #
# ------------------------------------------------------------------ #

def compute_backtest_metrics(
    trades: list[dict],
    equity: pd.Series,
    starting_capital: float,
    df: pd.DataFrame,
) -> dict:
    if not trades:
        return {}

    pnls    = [t["pnl"] for t in trades]
    winners = [p for p in pnls if p > 0]
    losers  = [p for p in pnls if p <= 0]

    net_profit   = sum(pnls)
    gross_profit = sum(winners)
    gross_loss   = abs(sum(losers))

    # --- Paper metrics ---
    win_rate      = len(winners) / len(pnls) * 100 if pnls else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    # Max drawdown
    peak       = equity.cummax()
    drawdown   = (equity - peak) / peak
    mdd_pct    = abs(drawdown.min()) * 100
    mdd_dollar = abs((equity - peak).min())

    # --- Additional metrics ---
    # Daily returns from equity curve
    daily_ret = equity.pct_change().dropna()

    # Sharpe ratio (annualised, risk-free = 0)
    sharpe = (daily_ret.mean() / daily_ret.std() * np.sqrt(252)) if daily_ret.std() > 0 else 0

    # Sortino ratio (annualised, penalises only downside)
    downside = daily_ret[daily_ret < 0].std()
    sortino  = (daily_ret.mean() / downside * np.sqrt(252)) if downside > 0 else 0

    # CAGR
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    cagr  = ((equity.iloc[-1] / starting_capital) ** (1 / years) - 1) * 100 if years > 0 else 0

    # Calmar ratio = CAGR / max drawdown %
    calmar = (cagr / mdd_pct) if mdd_pct > 0 else 0

    # Recovery factor = net profit / max drawdown $
    recovery_factor = net_profit / mdd_dollar if mdd_dollar > 0 else 0

    # Turnover = trades per year
    turnover = len(trades) / years if years > 0 else 0

    # Expectancy = avg expected $ per trade
    expectancy = net_profit / len(trades) if trades else 0

    # Avg win / avg loss
    avg_win  = np.mean(winners) if winners else 0
    avg_loss = np.mean(losers)  if losers  else 0

    # Best / worst trade
    best_trade  = max(pnls) if pnls else 0
    worst_trade = min(pnls) if pnls else 0

    # Avg holding period
    durations   = [t["duration"] for t in trades]
    avg_duration = np.mean(durations) if durations else 0

    # Buy & hold benchmark
    bh_return    = (df["close"].iloc[-1] / df["close"].iloc[0] - 1) * 100
    bh_cagr      = ((df["close"].iloc[-1] / df["close"].iloc[0]) ** (1 / years) - 1) * 100 if years > 0 else 0

    return {
        # Paper metrics
        "net_profit":       round(net_profit, 2),
        "mdd_pct":          round(mdd_pct, 2),
        "mdd_dollar":       round(mdd_dollar, 2),
        "profit_factor":    round(profit_factor, 2),
        "win_rate":         round(win_rate, 2),
        # Risk-adjusted
        "sharpe":           round(sharpe, 3),
        "sortino":          round(sortino, 3),
        "calmar":           round(calmar, 3),
        "cagr":             round(cagr, 2),
        "recovery_factor":  round(recovery_factor, 2),
        # Trade stats
        "total_trades":     len(trades),
        "winning_trades":   len(winners),
        "losing_trades":    len(losers),
        "turnover":         round(turnover, 1),
        "expectancy":       round(expectancy, 2),
        "avg_win":          round(avg_win, 2),
        "avg_loss":         round(avg_loss, 2),
        "best_trade":       round(best_trade, 2),
        "worst_trade":      round(worst_trade, 2),
        "avg_duration":     round(avg_duration, 1),
        # Benchmark
        "bh_return":        round(bh_return, 2),
        "bh_cagr":          round(bh_cagr, 2),
        "years":            round(years, 1),
    }
