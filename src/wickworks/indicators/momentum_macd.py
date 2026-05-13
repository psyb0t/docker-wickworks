"""MACD indicator."""

import pandas as pd
import pandas_ta as ta


def add(
    df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9
) -> pd.DataFrame:
    """Add MACD line, signal, and histogram columns to the DataFrame."""
    macd = ta.macd(df["close"], fast=fast, slow=slow, signal=signal)
    return pd.concat([df, macd], axis=1)
