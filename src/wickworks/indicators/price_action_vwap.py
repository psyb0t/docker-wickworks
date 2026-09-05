"""Volume-Weighted Average Price indicator."""

import pandas as pd
import pandas_ta as ta


def add(df: pd.DataFrame) -> pd.DataFrame:
    """Add VWAP column to the DataFrame."""
    df_idx = df.set_index(pd.to_datetime(df["time"], unit="s"))
    df["vwap"] = ta.vwap(df_idx["high"], df_idx["low"], df_idx["close"], df_idx["volume"]).values
    return df
