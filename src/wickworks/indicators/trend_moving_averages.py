"""Moving average indicators: EMA-21, SMA-50/100/200."""

import pandas as pd
import pandas_ta as ta


def add(df: pd.DataFrame, lengths: list[int] | None = None) -> pd.DataFrame:
    """Add EMA-21 and SMA columns to the DataFrame."""
    if lengths is None:
        lengths = [50, 100, 200]
    df["ema_21"] = ta.ema(df["close"], length=21)
    for length in lengths:
        df[f"sma_{length}"] = ta.sma(df["close"], length=length)
    return df
