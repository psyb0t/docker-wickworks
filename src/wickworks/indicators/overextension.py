"""Overextension detection: per-bar metrics measuring how far/fast price moved.

Columns added:
    oext_ema21_atr   -- distance from EMA21 in ATR multiples (signed: + = above)
    oext_sma50_atr   -- distance from SMA50 in ATR multiples (signed)
    oext_swing_leg   -- current swing leg size in ATR multiples (unsigned)
    oext_consec      -- consecutive same-direction candles (signed: + bullish, - bearish)
    oext_vol_exhaust -- volume exhaustion score (0.0-1.0, higher = more exhausted)
    oext_score       -- composite overextension score 0-100 per bar
    oext_direction   -- "bullish" (overextended UP) / "bearish" (overextended DOWN) / ""
"""

import numpy as np
import pandas as pd

_DEFAULTS_NAN = [
    "oext_ema21_atr",
    "oext_sma50_atr",
    "oext_swing_leg",
    "oext_vol_exhaust",
    "oext_score",
]
_DEFAULTS_ZERO = ["oext_consec"]
_DEFAULTS_EMPTY = ["oext_direction"]


def add(df: pd.DataFrame) -> pd.DataFrame:
    """Add overextension metric columns to the DataFrame."""
    if "atr" not in df.columns or len(df) < 20:
        for col in _DEFAULTS_NAN:
            df[col] = np.nan
        for col in _DEFAULTS_ZERO:
            df[col] = 0
        for col in _DEFAULTS_EMPTY:
            df[col] = ""
        return df

    _ma_distance_atr(df)
    _swing_leg_atr(df)
    _consecutive_candles(df)
    _volume_exhaustion(df)
    _composite_score(df)
    return df


def _ma_distance_atr(df: pd.DataFrame) -> None:
    """Add oext_ema21_atr and oext_sma50_atr columns."""
    atr = df["atr"]
    safe_atr = atr.replace(0, np.nan)

    if "ema_21" in df.columns:
        df["oext_ema21_atr"] = (df["close"] - df["ema_21"]) / safe_atr
    else:
        df["oext_ema21_atr"] = np.nan

    if "sma_50" in df.columns:
        df["oext_sma50_atr"] = (df["close"] - df["sma_50"]) / safe_atr
    else:
        df["oext_sma50_atr"] = np.nan


def _swing_leg_atr(df: pd.DataFrame) -> None:
    """Add oext_swing_leg: distance from last swing point in ATR multiples."""
    n = len(df)
    result = np.full(n, np.nan)

    swing_type = df["swing_type"].values if "swing_type" in df.columns else np.zeros(n)
    swing_level = (
        df["swing_level"].values if "swing_level" in df.columns else np.full(n, np.nan)
    )
    close = df["close"].values
    atr = df["atr"].values

    last_swing = np.nan

    for i in range(n):
        if swing_type[i] != 0 and not np.isnan(swing_level[i]):
            last_swing = swing_level[i]

        if np.isnan(last_swing) or np.isnan(atr[i]) or atr[i] <= 0:
            continue

        result[i] = abs(close[i] - last_swing) / atr[i]

    df["oext_swing_leg"] = result


def _consecutive_candles(df: pd.DataFrame) -> None:
    """Add oext_consec: consecutive same-direction candles (signed)."""
    direction = np.sign(df["close"].values - df["open"].values)
    n = len(df)
    consec = np.zeros(n, dtype=int)

    for i in range(1, n):
        if direction[i] == 0:
            consec[i] = 0
            continue

        if direction[i] == direction[i - 1] and consec[i - 1] != 0:
            consec[i] = consec[i - 1] + (1 if direction[i] > 0 else -1)
            continue

        consec[i] = int(direction[i])

    df["oext_consec"] = consec


def _volume_exhaustion(df: pd.DataFrame) -> None:
    """Add oext_vol_exhaust: 0.0-1.0 score of volume declining during move."""
    n = len(df)
    result = np.zeros(n)
    window = 5

    if "vol_sma_21" not in df.columns:
        df["oext_vol_exhaust"] = result
        return

    vol_col = "tick_volume" if "tick_volume" in df.columns else "volume"
    vol = df[vol_col].values
    vol_sma = df["vol_sma_21"].values
    close = df["close"].values

    # Vectorized: count bars where vol < vol_sma in rolling window
    valid_sma = ~np.isnan(vol_sma) & (vol_sma > 0)
    below = ((vol < vol_sma) & valid_sma).astype(float)
    rolling_count = pd.Series(below).rolling(window, min_periods=window).sum().values

    # Only apply where price actually moved over the window
    shifted_close = np.empty(n)
    shifted_close[:window] = close[:window]
    shifted_close[window:] = close[:-window]
    price_moved = np.abs(close - shifted_close) >= 1e-10
    price_moved[:window] = False

    mask = price_moved & ~np.isnan(rolling_count)
    result[mask] = np.minimum(rolling_count[mask] / window, 1.0)

    df["oext_vol_exhaust"] = result


def _composite_score(df: pd.DataFrame) -> None:
    """Add oext_score (0-100) and oext_direction columns."""
    n = len(df)
    score = np.zeros(n)

    # Factor 1: EMA21 distance (20 pts, full at 4 ATR)
    if "oext_ema21_atr" in df.columns:
        vals = df["oext_ema21_atr"].abs().fillna(0).values
        score += np.minimum(vals / 4.0, 1.0) * 20

    # Factor 2: Swing leg (20 pts, full at 8 ATR)
    if "oext_swing_leg" in df.columns:
        vals = df["oext_swing_leg"].fillna(0).values
        score += np.minimum(vals / 8.0, 1.0) * 20

    # Factor 3: SMA50 distance (15 pts, full at 6 ATR)
    if "oext_sma50_atr" in df.columns:
        vals = df["oext_sma50_atr"].abs().fillna(0).values
        score += np.minimum(vals / 6.0, 1.0) * 15

    # Factor 4: Consecutive candles (15 pts, full at 7)
    if "oext_consec" in df.columns:
        vals = np.abs(df["oext_consec"].values).astype(float)
        score += np.minimum(vals / 7.0, 1.0) * 15

    # Factor 5: RSI extreme (10 pts)
    if "rsi" in df.columns:
        rsi = df["rsi"].fillna(50).values
        score += np.minimum(np.abs(rsi - 50) / 50.0, 1.0) * 10

    # Factor 6: BB %B extreme (8 pts, only outside bands)
    bbp_col = next((c for c in df.columns if c.startswith("BBP_")), None)
    if bbp_col:
        bbp = df[bbp_col].fillna(0.5).values
        bbp_excess = np.maximum(np.abs(bbp - 0.5) - 0.5, 0) / 0.5
        score += np.minimum(bbp_excess, 1.0) * 8

    # Factor 7: Stochastic extreme (7 pts)
    stoch_col = next((c for c in df.columns if c.startswith("STOCHk_")), None)
    if stoch_col:
        k = df[stoch_col].fillna(50).values
        score += np.minimum(np.abs(k - 50) / 50.0, 1.0) * 7

    # Factor 8: Volume exhaustion (5 pts)
    if "oext_vol_exhaust" in df.columns:
        score += df["oext_vol_exhaust"].fillna(0).values * 5

    df["oext_score"] = np.round(np.clip(score, 0, 100), 1)

    # Direction: sign of EMA21 distance when score is meaningful
    direction = pd.Series("", index=df.index, dtype=object)
    if "oext_ema21_atr" in df.columns:
        ema_dist = df["oext_ema21_atr"].fillna(0)
        direction.loc[(df["oext_score"] >= 30) & (ema_dist > 0)] = "bullish"
        direction.loc[(df["oext_score"] >= 30) & (ema_dist < 0)] = "bearish"
    df["oext_direction"] = direction
