"""Shared helpers for signal detection modules."""

import pandas as pd

from .divergences import find_divergences


def safe_float(val) -> float | None:
    """Convert val to float, returning None for NaN/Inf/unconvertible."""
    try:
        f = float(val)
        return (
            None if (f != f or f == float("inf") or f == float("-inf")) else round(f, 6)
        )
    except (TypeError, ValueError):
        return None


def find_col(df: pd.DataFrame, prefix: str) -> str | None:
    """Find first column starting with prefix (handles pandas_ta suffix variations)."""
    for c in df.columns:
        if c.startswith(prefix):
            return c
    return None


def ma_touched(candle: pd.Series, ma_val: float) -> bool:
    """Check if a candle's range includes the MA value."""
    if pd.isna(ma_val):
        return False
    return candle["low"] <= ma_val <= candle["high"]


def divergence_signals(
    df: pd.DataFrame, col: str, label: str, signals: list[str]
) -> None:
    """Append bearish/bullish divergence strings for an indicator column."""
    for div in find_divergences(df, col):
        if div["type"] == "bearish":
            signals.append(
                f"Bearish {label} divergence "
                f"(price {div['price1']:.5g}\u2192{div['price2']:.5g} up, "
                f"{label} {div['ind1']:.0f}\u2192{div['ind2']:.0f} down)"
            )
        else:
            signals.append(
                f"Bullish {label} divergence "
                f"(price {div['price1']:.5g}\u2192{div['price2']:.5g} down, "
                f"{label} {div['ind1']:.0f}\u2192{div['ind2']:.0f} up)"
            )


def detect_line_cross(
    df: pd.DataFrame, col1: str, col2: str, lookback: int
) -> tuple[str, int] | None:
    """Scan recent bars for col1 crossing col2.

    Returns ("above", bars_ago) or ("below", bars_ago), or None if no cross found.
    """
    for i in range(-min(lookback, len(df) - 1), 0):
        cur = df.iloc[i]
        prv = df.iloc[i - 1]
        if not (pd.notna(cur.get(col1)) and pd.notna(prv.get(col1))):
            continue
        if not (pd.notna(cur.get(col2)) and pd.notna(prv.get(col2))):
            continue
        if prv[col1] <= prv[col2] and cur[col1] > cur[col2]:
            return ("above", abs(i))
        if prv[col1] >= prv[col2] and cur[col1] < cur[col2]:
            return ("below", abs(i))
    return None
