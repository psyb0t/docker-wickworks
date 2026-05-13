"""Stochastic Oscillator indicator."""

import pandas as pd
import pandas_ta as ta


def add(df: pd.DataFrame, k: int = 14, d: int = 3, smooth_k: int = 3) -> pd.DataFrame:
    """Add Stochastic K and D columns to the DataFrame."""
    stoch = ta.stoch(df["high"], df["low"], df["close"], k=k, d=d, smooth_k=smooth_k)
    return pd.concat([df, stoch], axis=1)
