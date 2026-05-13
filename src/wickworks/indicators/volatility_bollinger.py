"""Bollinger Bands indicator."""

import pandas as pd
import pandas_ta as ta


def add(df: pd.DataFrame, length: int = 20, std: float = 2.0) -> pd.DataFrame:
    """Add Bollinger Bands columns to the DataFrame."""
    bbands = ta.bbands(df["close"], length=length, std=float(std))  # type: ignore[arg-type]
    return pd.concat([df, bbands], axis=1)
