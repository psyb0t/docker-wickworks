"""Money Flow Index indicator."""

import pandas as pd
import pandas_ta as ta

from ._helpers import vol_col


def add(df: pd.DataFrame, length: int = 14) -> pd.DataFrame:
    """Add MFI column to the DataFrame."""
    vol = vol_col(df)
    df["mfi"] = ta.mfi(df["high"], df["low"], df["close"], df[vol], length=length)
    return df
