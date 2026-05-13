"""Average Directional Index (ADX) with DI+/DI-."""

import pandas as pd
import pandas_ta as ta


def add(df: pd.DataFrame, length: int = 14) -> pd.DataFrame:
    """Add ADX, DI+, and DI- columns to the DataFrame."""
    adx = ta.adx(df["high"], df["low"], df["close"], length=length)
    return pd.concat([df, adx], axis=1)
