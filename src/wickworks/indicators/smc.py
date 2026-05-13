"""Smart Money Concepts via smartmoneyconcepts library."""

import numpy as np
import pandas as pd

from ._helpers import vol_col


def add(df: pd.DataFrame, swing_length: int = 15) -> pd.DataFrame:
    """Add SMC columns: swing H/L, OB, FVG, BOS/CHoCH."""
    from smartmoneyconcepts.smc import smc

    vol = vol_col(df)
    ohlc = df[["open", "high", "low", "close"]].copy()
    ohlc["volume"] = df[vol].values

    swing = smc.swing_highs_lows(ohlc, swing_length=swing_length)
    df["swing_type"] = swing["HighLow"].fillna(0).astype(int)
    df["swing_level"] = swing["Level"]

    obs = smc.ob(ohlc, swing, close_mitigation=False)
    df["ob_type"] = obs["OB"].fillna(0).astype(int)
    df["ob_top"] = obs["Top"]
    df["ob_bottom"] = obs["Bottom"]
    ob_type_arr = df["ob_type"].values
    ob_mit_arr = obs["MitigatedIndex"].values.copy()
    for i in range(1, len(ob_mit_arr)):
        if ob_type_arr[i] != 0 and ob_mit_arr[i] == 0:
            ob_mit_arr[i] = np.nan
    df["ob_mitigated"] = ob_mit_arr

    fvgs = smc.fvg(ohlc, join_consecutive=False)
    df["fvg_type"] = fvgs["FVG"].fillna(0).astype(int)
    df["fvg_top"] = fvgs["Top"]
    df["fvg_bottom"] = fvgs["Bottom"]
    fvg_type_arr = df["fvg_type"].values
    fvg_mit_arr = fvgs["MitigatedIndex"].values.copy()
    for i in range(1, len(fvg_mit_arr)):
        if fvg_type_arr[i] != 0 and fvg_mit_arr[i] == 0:
            fvg_mit_arr[i] = np.nan
    df["fvg_mitigated"] = fvg_mit_arr

    bosc = smc.bos_choch(ohlc, swing, close_break=True)
    df["bos"] = bosc["BOS"].fillna(0).astype(int)
    df["choch"] = bosc["CHOCH"].fillna(0).astype(int)
    df["bos_choch_level"] = bosc["Level"]
    df["bos_choch_broken_idx"] = bosc["BrokenIndex"]

    return df
