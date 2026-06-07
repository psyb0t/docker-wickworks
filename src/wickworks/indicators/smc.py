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

    # Run smc.ob twice so we can tell wick-traversal mitigation apart from
    # close-cross mitigation. The smartmoneyconcepts lib emits one OB per
    # detection bar regardless of close_mitigation; it only changes which
    # later bars get tagged as "mitigated". The OB top/bottom/type/origin
    # bar are identical between the two passes, so we keep them from the
    # wick run (the lib's historical default) and only extract the
    # MitigatedIndex column from each pass to derive the two flags.
    #
    # ob_mitigated (NaN where still live, bar idx where mitigated by wick)
    # is preserved for callers (quanthex scoring, _order_blocks in smc.py)
    # that filter on the loose criterion. The new ob_mitigated_close mirror
    # exposes the stricter criterion so the FE indicator can hide OBs that
    # a close has already taken out — what most SMC traders read as
    # "mitigated by eye".
    obs_wick = smc.ob(ohlc, swing, close_mitigation=False)
    obs_close = smc.ob(ohlc, swing, close_mitigation=True)

    df["ob_type"] = obs_wick["OB"].fillna(0).astype(int)
    df["ob_top"] = obs_wick["Top"]
    df["ob_bottom"] = obs_wick["Bottom"]
    ob_type_arr = df["ob_type"].values

    # Wick-criterion: an OB is mitigated when a later bar's wick fully
    # traverses the zone. Looser than close-cross; this is the legacy
    # filter behavior.
    ob_mit_wick_arr = obs_wick["MitigatedIndex"].values.copy()
    for i in range(1, len(ob_mit_wick_arr)):
        if ob_type_arr[i] != 0 and ob_mit_wick_arr[i] == 0:
            ob_mit_wick_arr[i] = np.nan
    df["ob_mitigated"] = ob_mit_wick_arr

    # Close-criterion: stricter — an OB is mitigated as soon as a later
    # bar's CLOSE crosses into/through the zone, not just its wick.
    ob_mit_close_arr = obs_close["MitigatedIndex"].values.copy()
    for i in range(1, len(ob_mit_close_arr)):
        if ob_type_arr[i] != 0 and ob_mit_close_arr[i] == 0:
            ob_mit_close_arr[i] = np.nan
    df["ob_mitigated_close"] = ob_mit_close_arr

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
