"""Shared helpers for indicator modules."""

import pandas as pd


def vol_col(df: pd.DataFrame) -> str:
    """Return the volume column name present in the DataFrame."""
    if "tick_volume" in df.columns:
        return "tick_volume"
    return "volume"
