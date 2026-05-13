"""Donchian Channels indicator."""

import pandas as pd
import pandas_ta as ta


def add(df: pd.DataFrame, length: int = 20) -> pd.DataFrame:
    """Add Donchian Channel columns to the DataFrame."""
    donchian = ta.donchian(
        df["high"], df["low"], lower_length=length, upper_length=length
    )
    if donchian is not None:
        return pd.concat([df, donchian], axis=1)
    return df
