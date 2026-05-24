import pandas as pd
import numpy as np


def pivot_reversal(df: pd.DataFrame, x: int = 4, y: int = 1) -> pd.Series:
    """
    Identify swing highs (BEAR pivots) and swing lows (BULL pivots).

    A BULL pivot at bar i: df['low'][i] is the minimum of the window [i-x, i+y].
    A BEAR pivot at bar i: df['high'][i] is the maximum of the window [i-x, i+y].

    Returns a Series of 'BULL', 'BEAR', or None.
    Note: last y bars will be NaN (future bars not yet available — no look-ahead).
    """
    n = len(df)
    pivots = pd.Series([None] * n, index=df.index, dtype=object)

    for i in range(x, n - y):
        window_low = df["low"].iloc[i - x: i + y + 1]
        window_high = df["high"].iloc[i - x: i + y + 1]

        if df["low"].iloc[i] == window_low.min():
            pivots.iloc[i] = "BULL"
        elif df["high"].iloc[i] == window_high.max():
            pivots.iloc[i] = "BEAR"

    return pivots


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def macd(
    df: pd.DataFrame, fast: int = 13, slow: int = 26, signal: int = 10
) -> pd.DataFrame:
    """
    Compute MACD indicator (Setup 18 from paper: fast=13, slow=26, signal=10).

    Returns DataFrame with columns: macd_line, signal_line, histogram.
    """
    fast_ema = ema(df["close"], fast)
    slow_ema = ema(df["close"], slow)
    macd_line = fast_ema - slow_ema
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line

    return pd.DataFrame(
        {"macd_line": macd_line, "signal_line": signal_line, "histogram": histogram},
        index=df.index,
    )


def rsi(df: pd.DataFrame, period: int = 13) -> pd.Series:
    """RSI with period=13 (Setup 16 from paper)."""
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))
