"""Swing-based divergence detection between price and indicators.

Approach (inspired by AutoTrader method=1):
  - Find local peaks and troughs in the indicator.
  - Compare only ADJACENT swings (each to its immediate predecessor).
  - A bearish divergence is: price makes a Higher High, indicator makes a Lower High.
  - A bullish divergence is: price makes a Lower Low, indicator makes a Higher Low.
  - A trendline check rejects pairs where an intervening bar breaks the line
    between the two pivot prices.
  - max_bars caps the distance between the two pivots so divergences can't
    silently span the entire chart.
  - min_swing_ratio filters noise: the smaller leg of a swing (move-in vs
    move-out) must be at least this fraction of the larger leg.  A trough of
    95 between peaks of 100 and 150 has legs 5 and 55; ratio 0.09 < 0.2 so
    it is rejected as a real swing.
"""

import numpy as np
import pandas as pd


def _indicator_peaks(
    values: np.ndarray,
    left: int = 5,
    right: int = 5,
    min_swing_ratio: float = 0.2,
) -> tuple[list, list]:
    """Find local peaks/troughs in a 1D array.

    A peak at index i requires values[i] >= all values in [i-left, i) and (i, i+right].
    A trough requires values[i] <= those windows.

    min_swing_ratio: the smaller leg (move-in vs move-out) must be at least
    this fraction of the larger leg.  Filters out shallow noise swings.
    """
    n = len(values)
    peaks, troughs = [], []
    for i in range(left, n - right):
        if np.isnan(values[i]):
            continue
        win_l = values[i - left : i]
        win_r = values[i + 1 : i + right + 1]
        if np.any(np.isnan(win_l)) or np.any(np.isnan(win_r)):
            continue

        if values[i] >= np.max(win_l) and values[i] >= np.max(win_r):
            move_in = values[i] - np.min(win_l)
            move_out = values[i] - np.min(win_r)
            larger = max(move_in, move_out)
            if larger > 0 and min(move_in, move_out) >= min_swing_ratio * larger:
                peaks.append(i)

        if values[i] <= np.min(win_l) and values[i] <= np.min(win_r):
            move_in = np.max(win_l) - values[i]
            move_out = np.max(win_r) - values[i]
            larger = max(move_in, move_out)
            if larger > 0 and min(move_in, move_out) >= min_swing_ratio * larger:
                troughs.append(i)

    return peaks, troughs


def _trendline_broken(arr: np.ndarray, i1: int, i2: int, above: bool) -> bool:
    """Return True if any value between i1 and i2 breaks the trendline.

    above=True  → any arr[i1+1:i2] > line  (used for bearish: highs above line)
    above=False → any arr[i1+1:i2] < line  (used for bullish: lows below line)
    """
    span = i2 - i1
    if span <= 2:
        return False
    xs = np.arange(1, span)
    p1, p2 = arr[i1], arr[i2]
    line = p1 + (p2 - p1) * xs / span
    segment = arr[i1 + 1 : i2]
    return bool(np.any(segment > line) if above else np.any(segment < line))


def _price_at(price_arr: np.ndarray, i: int, bearish: bool) -> float:
    """Return price at i with ±1 bar tolerance.

    bearish=True → take the max high in [i-1, i+1] (best high near the swing).
    bearish=False → take the min low in [i-1, i+1] (best low near the swing).
    """
    lo = max(0, i - 1)
    hi = min(len(price_arr) - 1, i + 1)
    window = price_arr[lo : hi + 1]
    return float(np.max(window) if bearish else np.min(window))


def _scan_pairs(
    ind_vals: np.ndarray,
    price_arr: np.ndarray,
    swings: list,
    offset: int,
    indicator_col: str,
    div_type: str,
    max_bars: int,
    min_ind_diff_pct: float,
) -> dict | None:
    """Scan adjacent swing pairs from most-recent backwards, return first valid divergence.

    div_type: "bearish" (peaks) or "bullish" (troughs).
    For bearish: indicator LH + price HH.
    For bullish: indicator HL + price LL.
    Price comparison uses ±1 bar tolerance so a 1-bar lag/lead between the
    indicator swing and the price extreme doesn't kill a valid divergence.
    min_ind_diff_pct: |ind2 - ind1| must be >= this fraction of the full
    indicator range in the window — filters zero-line noise (e.g. MACD hist).
    """
    bearish = div_type == "bearish"
    ind_range = float(np.nanmax(ind_vals) - np.nanmin(ind_vals))
    min_ind_diff = min_ind_diff_pct * ind_range if ind_range > 0 else 0.0

    for k in range(len(swings) - 1, 0, -1):
        i2, i1 = swings[k], swings[k - 1]
        if i2 - i1 > max_bars:
            continue
        v1, v2 = ind_vals[i1], ind_vals[i2]
        if abs(v2 - v1) < min_ind_diff:
            continue
        p1 = _price_at(price_arr, i1, bearish)
        p2 = _price_at(price_arr, i2, bearish)

        if bearish:
            # indicator LH (v2 < v1) + price HH (p2 > p1)
            if v2 >= v1 or p2 <= p1:
                continue
            if _trendline_broken(price_arr, i1, i2, above=True):
                continue
        else:
            # indicator HL (v2 > v1) + price LL (p2 < p1)
            if v2 <= v1 or p2 >= p1:
                continue
            if _trendline_broken(price_arr, i1, i2, above=False):
                continue

        return {
            "type": div_type,
            "indicator": indicator_col,
            "idx1": offset + i1,
            "idx2": offset + i2,
            "price1": p1,
            "price2": p2,
            "ind1": v1,
            "ind2": v2,
        }
    return None


def _find_divs(
    ind_vals: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    offset: int,
    indicator_col: str,
    swing_len: int,
    max_bars: int,
    min_swing_ratio: float,
    min_ind_diff_pct: float,
) -> list[dict]:
    peaks, troughs = _indicator_peaks(
        ind_vals, left=swing_len, right=swing_len, min_swing_ratio=min_swing_ratio
    )
    results = []

    if len(peaks) >= 2:
        div = _scan_pairs(
            ind_vals,
            highs,
            peaks,
            offset,
            indicator_col,
            "bearish",
            max_bars,
            min_ind_diff_pct,
        )
        if div:
            results.append(div)

    if len(troughs) >= 2:
        div = _scan_pairs(
            ind_vals,
            lows,
            troughs,
            offset,
            indicator_col,
            "bullish",
            max_bars,
            min_ind_diff_pct,
        )
        if div:
            results.append(div)

    return results


def find_divergences(
    df: pd.DataFrame,
    indicator_col: str,
    n: int = 60,
    swing_len: int = 5,
    max_bars: int = 40,
    min_swing_ratio: float = 0.2,
    min_ind_diff_pct: float = 0.0,
) -> list[dict]:
    """Find the most recent bearish and/or bullish divergence.

    Compares only adjacent indicator swings (each pivot to its immediate
    predecessor), capped at max_bars apart.  Falls back to swing_len=3 if
    no divergence is found with the primary length.

    min_swing_ratio: minimum ratio of the smaller swing leg to the larger.
    Filters out shallow noise swings (e.g. 5-point dip between 100 and 150).

    min_ind_diff_pct: |ind2 - ind1| must be >= this fraction of the full
    indicator range in the window.  Filters zero-line noise on MACD histogram
    where both pivots sit near zero and the "divergence" is meaningless.

    Returns at most one bearish + one bullish divergence (0–2 total).
    """
    if indicator_col not in df.columns or len(df) < 20:
        return []

    recent = df.tail(n).copy()
    offset = len(df) - len(recent)
    ind_vals = recent[indicator_col].values.astype(float)
    highs = recent["high"].values.astype(float)
    lows = recent["low"].values.astype(float)

    for sl in [swing_len, 3]:
        results = _find_divs(
            ind_vals,
            highs,
            lows,
            offset,
            indicator_col,
            sl,
            max_bars,
            min_swing_ratio,
            min_ind_diff_pct,
        )
        if results:
            return results
    return []
