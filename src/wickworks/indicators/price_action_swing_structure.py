"""Swing structure classification: HH/LH/HL/LL using SMC swing_highs_lows(7).

Adds pre-computed swing data with swing_length=7 (tighter than the SMC
indicator which uses swing_length=15) plus Higher High / Lower High /
Higher Low / Lower Low classification used by the breakout signal.

Columns added:
    sw7_hl     — 1 (swing high), -1 (swing low), 0 (neither)
    sw7_level  — price level at each swing, NaN elsewhere
    sw7_high_struct — 1.0 (HH) or -1.0 (LH) at each swing-high bar, NaN elsewhere
    sw7_low_struct  — 1.0 (HL) or -1.0 (LL) at each swing-low bar, NaN elsewhere
"""

import numpy as np
import pandas as pd


def add(df: pd.DataFrame, swing_length: int = 7) -> pd.DataFrame:
    """Classify swing highs/lows as HH/LH and HL/LL."""
    from smartmoneyconcepts.smc import smc as _smc

    n = len(df)
    nan_col = [float("nan")] * n

    if n < swing_length * 2 + 5:
        df["sw7_hl"] = 0
        df["sw7_level"] = nan_col
        df["sw7_high_struct"] = nan_col
        df["sw7_low_struct"] = nan_col
        return df

    ohlc = df[["open", "high", "low", "close"]].copy()
    ohlc["volume"] = df["volume"].values

    sw = _smc.swing_highs_lows(ohlc, swing_length=swing_length)
    sw.iloc[:swing_length] = np.nan
    sw.iloc[-swing_length:] = np.nan
    sw_hl = sw["HighLow"].fillna(0).astype(int)
    sw_level = sw["Level"]

    df["sw7_hl"] = sw_hl.values
    df["sw7_level"] = sw_level.values

    high_struct = np.full(n, float("nan"))
    low_struct = np.full(n, float("nan"))

    prev_high_level: float | None = None
    prev_low_level: float | None = None

    sw_hl_arr = sw_hl.values
    sw_level_arr = sw_level.values

    for i in range(n):
        t = int(sw_hl_arr[i])
        lvl_val = sw_level_arr[i]
        if np.isnan(lvl_val):
            continue
        lvl = float(lvl_val)

        if t == 1:
            if prev_high_level is not None:
                high_struct[i] = 1.0 if lvl > prev_high_level else -1.0
            prev_high_level = lvl
        elif t == -1:
            if prev_low_level is not None:
                low_struct[i] = 1.0 if lvl > prev_low_level else -1.0
            prev_low_level = lvl

    df["sw7_high_struct"] = high_struct
    df["sw7_low_struct"] = low_struct

    return df
