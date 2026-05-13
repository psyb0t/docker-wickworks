"""Divergence detection primitives.

Raw divergence + divergence-trend detection over indicator columns. No
direction scoring, no confluence interpretation — that's the caller's job.
"""

import pandas as pd

from ._helpers import find_col
from .div_trend import detect_div_trends
from .divergences import find_divergences

__all__ = [
    "detect_all_divergences",
    "detect_div_trends",
    "find_divergences",
]


# Fixed-name indicator columns to check for divergences.
_DIV_INDICATORS: list[tuple[str, str]] = [
    ("rsi", "RSI"),
    ("mfi", "MFI"),
]
# Prefix-matched columns (pandas_ta appends parameters to the name).
_DIV_STOCH_PREFIX = "STOCHk_"
_DIV_MACDH_PREFIX = "MACDh_"


def detect_all_divergences(df: pd.DataFrame) -> list[dict]:
    """Return structured divergence dicts for all tracked indicators.

    Each dict contains:
        indicator   – column name
        label       – human-readable label (RSI / MFI / Stochastic)
        type        – "bearish" or "bullish"
        idx1/idx2   – bar indices in df (absolute, not relative to tail)
        time1/time2 – Unix timestamps at those bars
        price1/price2 – price high/low at each pivot
        ind1/ind2   – indicator value at each pivot
    """
    results: list[dict] = []
    times = df["time"].tolist() if "time" in df.columns else [None] * len(df)

    cols: list[tuple[str, str]] = list(_DIV_INDICATORS)
    stoch_col = find_col(df, _DIV_STOCH_PREFIX)
    if stoch_col:
        cols.append((stoch_col, "Stochastic"))
    macdh_col = find_col(df, _DIV_MACDH_PREFIX)
    if macdh_col:
        cols.append((macdh_col, "MACD"))

    for col, label in cols:
        if col == macdh_col:
            divs_for_col = find_divergences(df, col, n=len(df), min_ind_diff_pct=0.05)
        else:
            divs_for_col = find_divergences(df, col, n=len(df))
        for div in divs_for_col:
            i1, i2 = div["idx1"], div["idx2"]
            results.append(
                {
                    "indicator": col,
                    "label": label,
                    "type": div["type"],
                    "idx1": i1,
                    "idx2": i2,
                    "time1": times[i1] if i1 < len(times) else None,
                    "time2": times[i2] if i2 < len(times) else None,
                    "price1": div["price1"],
                    "price2": div["price2"],
                    "ind1": div["ind1"],
                    "ind2": div["ind2"],
                }
            )

    return results
