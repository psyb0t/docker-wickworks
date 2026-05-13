"""Average True Range indicator."""

import pandas as pd
import pandas_ta as ta


def add(df: pd.DataFrame, length: int = 14) -> pd.DataFrame:
    """Add ATR column to the DataFrame."""
    df["atr"] = ta.atr(df["high"], df["low"], df["close"], length=length)
    return df
