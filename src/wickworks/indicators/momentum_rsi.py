"""Relative Strength Index indicator."""

import pandas as pd
import pandas_ta as ta


def add(df: pd.DataFrame, length: int = 14) -> pd.DataFrame:
    """Add RSI column to the DataFrame."""
    df["rsi"] = ta.rsi(df["close"], length=length)
    return df
