"""Volume analysis: SMA, ratio, OBV."""

import pandas as pd
import pandas_ta as ta

from ._helpers import vol_col

# Approximate seconds per timeframe
_TF_SECONDS = {
    "M1": 60,
    "M5": 300,
    "M15": 900,
    "M30": 1800,
    "H1": 3600,
    "H4": 14400,
    "D1": 86400,
    "W1": 604800,
}

# Vol SMA length per timeframe — target ~2 weeks of bars
_TF_VOL_LENGTH = {
    "M1": 200,
    "M5": 100,
    "M15": 60,
    "M30": 50,
    "H1": 50,
    "H4": 50,
    "D1": 200,
    "W1": 52,
}


def _infer_tf(df: pd.DataFrame) -> str | None:
    """Infer timeframe from median bar interval in seconds."""
    if "time" not in df.columns or len(df) < 2:
        return None
    times = df["time"].dropna().astype(int)
    median_secs = int(times.diff().dropna().median())
    best, best_diff = None, float("inf")
    for tf, secs in _TF_SECONDS.items():
        diff = abs(median_secs - secs)
        if diff < best_diff:
            best, best_diff = tf, diff
    return best


def add(df: pd.DataFrame, length: int = 0) -> pd.DataFrame:
    """Add volume SMA, ratio, percentile rank, and OBV columns.

    *length* controls the rolling window. If 0 (default), it is chosen
    based on the inferred timeframe (~2 weeks of bars).

    Columns added:
        vol_sma    — rolling SMA of volume
        vol_ratio  — current volume / vol_sma  (kept for compatibility)
        vol_pct    — rolling percentile rank 0-100 over the same window;
                     use this for spike/dryup detection instead of vol_ratio
        obv        — on-balance volume
    """
    vol = vol_col(df)
    if length == 0:
        tf = _infer_tf(df)
        length = _TF_VOL_LENGTH.get(tf or "", 20)
    df["vol_sma"] = ta.sma(df[vol], length=length)
    df["vol_ratio"] = df[vol] / df["vol_sma"]
    df["vol_sma_21"] = ta.sma(df[vol], length=21)
    df["vol_sma_50"] = ta.sma(df[vol], length=50)
    # Percentile rank: where does this bar sit in its rolling window (0-100)
    df["vol_pct"] = (
        df[vol].rolling(length, min_periods=max(5, length // 2)).rank(pct=True).mul(100)
    )
    obv = ta.obv(df["close"], df[vol])
    if obv is not None:
        df["obv"] = obv
    return df
