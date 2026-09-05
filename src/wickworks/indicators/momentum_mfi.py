"""Money Flow Index indicator."""

import pandas as pd
import pandas_ta as ta


def add(df: pd.DataFrame, length: int = 14) -> pd.DataFrame:
    """Add MFI column to the DataFrame."""
    df["mfi"] = ta.mfi(
        df["high"],
        df["low"],
        df["close"],
        df["volume"],
        length=length,
    )
    return df
