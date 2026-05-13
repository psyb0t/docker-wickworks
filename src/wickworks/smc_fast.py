"""
Drop-in numba-accelerated replacements for the hot inner loops of the
smartmoneyconcepts library.

Call ``patch()`` once at import time to monkeypatch the ``smc`` class with
JIT-compiled versions of ``ob``, ``fvg``, ``bos_choch``, and
``swing_highs_lows``.
"""

import numpy as np
import pandas as pd
from numba import njit

# ---------------------------------------------------------------------------
# swing_highs_lows — dedup while-loop converted to njit
# ---------------------------------------------------------------------------


@njit(cache=True)
def _swing_dedup(swing_arr, highs, lows):
    """Remove consecutive same-direction swings (keep strongest)."""
    while True:
        positions = np.flatnonzero(~np.isnan(swing_arr))
        if len(positions) < 2:
            break

        changed = False
        i = 0
        while i < len(positions) - 1:
            p0 = positions[i]
            p1 = positions[i + 1]
            s0 = swing_arr[p0]
            s1 = swing_arr[p1]

            if s0 == 1.0 and s1 == 1.0:
                if highs[p0] < highs[p1]:
                    swing_arr[p0] = np.nan
                else:
                    swing_arr[p1] = np.nan
                changed = True
                i += 1
            elif s0 == -1.0 and s1 == -1.0:
                if lows[p0] > lows[p1]:
                    swing_arr[p0] = np.nan
                else:
                    swing_arr[p1] = np.nan
                changed = True
                i += 1
            else:
                i += 1

        if not changed:
            break

    return swing_arr


def fast_swing_highs_lows(ohlc, swing_length=50):
    """Numba-accelerated swing_highs_lows replacement."""
    sl = swing_length * 2
    highs = ohlc["high"].values.astype(np.float64)
    lows = ohlc["low"].values.astype(np.float64)

    shifted_high = ohlc["high"].shift(-(sl // 2)).rolling(sl).max().values
    shifted_low = ohlc["low"].shift(-(sl // 2)).rolling(sl).min().values

    swing_arr = np.where(
        highs == shifted_high,
        1.0,
        np.where(lows == shifted_low, -1.0, np.nan),
    )

    swing_arr = _swing_dedup(swing_arr, highs, lows)

    positions = np.flatnonzero(~np.isnan(swing_arr))
    if len(positions) > 0:
        # 1:1 port of upstream smartmoneyconcepts.swing_highs_lows boundary
        # fix-up: force endpoints to the opposite of the nearest real swing.
        # When positions[0]==0 (or positions[-1]==n-1) the two sibling ifs
        # touch the same cell and cancel out — by design, leaving the existing
        # endpoint swing untouched. Do not rewrite as elif: the no-op behaviour
        # in the overlap case is intentional.
        if swing_arr[positions[0]] == 1.0:
            swing_arr[0] = -1.0
        if swing_arr[positions[0]] == -1.0:
            swing_arr[0] = 1.0
        if swing_arr[positions[-1]] == -1.0:
            swing_arr[-1] = 1.0
        if swing_arr[positions[-1]] == 1.0:
            swing_arr[-1] = -1.0

    level = np.where(
        ~np.isnan(swing_arr),
        np.where(swing_arr == 1.0, highs, lows),
        np.nan,
    )

    return pd.concat(
        [
            pd.Series(swing_arr, name="HighLow"),
            pd.Series(level, name="Level"),
        ],
        axis=1,
    )


# ---------------------------------------------------------------------------
# fvg — mitigation inner loop
# ---------------------------------------------------------------------------


@njit(cache=True)
def _fvg_mitigation(fvg, top, bottom, ohlc_low, ohlc_high, n):
    """Find the first candle that mitigates each FVG (early-break)."""
    mitigated = np.zeros(n, dtype=np.int32)
    for i in range(n):
        if np.isnan(fvg[i]):
            continue
        if fvg[i] == 1.0:
            for j in range(i + 2, n):
                if ohlc_low[j] <= top[i]:
                    mitigated[i] = j
                    break
        else:
            for j in range(i + 2, n):
                if ohlc_high[j] >= bottom[i]:
                    mitigated[i] = j
                    break
    return mitigated


def fast_fvg(ohlc, join_consecutive=False):
    """Numba-accelerated fvg replacement."""
    n = len(ohlc)
    hi = ohlc["high"].values.astype(np.float64)
    lo = ohlc["low"].values.astype(np.float64)
    op = ohlc["open"].values.astype(np.float64)
    cl = ohlc["close"].values.astype(np.float64)

    h_s1 = np.empty(n, dtype=np.float64)
    h_s1[0] = np.nan
    h_s1[1:] = hi[:-1]

    l_s1 = np.empty(n, dtype=np.float64)
    l_s1[0] = np.nan
    l_s1[1:] = lo[:-1]

    h_sn1 = np.empty(n, dtype=np.float64)
    h_sn1[-1] = np.nan
    h_sn1[:-1] = hi[1:]

    l_sn1 = np.empty(n, dtype=np.float64)
    l_sn1[-1] = np.nan
    l_sn1[:-1] = lo[1:]

    bullish = (h_s1 < l_sn1) & (cl > op)
    bearish = (l_s1 > h_sn1) & (cl < op)

    fvg = np.where(bullish | bearish, np.where(cl > op, 1.0, -1.0), np.nan)

    top = np.where(
        ~np.isnan(fvg),
        np.where(cl > op, l_sn1, l_s1),
        np.nan,
    )
    bottom = np.where(
        ~np.isnan(fvg),
        np.where(cl > op, h_s1, h_sn1),
        np.nan,
    )

    if join_consecutive:
        for i in range(n - 1):
            if fvg[i] == fvg[i + 1]:
                top[i + 1] = max(top[i], top[i + 1])
                bottom[i + 1] = min(bottom[i], bottom[i + 1])
                fvg[i] = top[i] = bottom[i] = np.nan

    mitigated = _fvg_mitigation(fvg, top, bottom, lo, hi, n)
    mitigated_f = np.where(np.isnan(fvg), np.nan, mitigated.astype(np.float64))

    return pd.concat(
        [
            pd.Series(fvg, name="FVG"),
            pd.Series(top, name="Top"),
            pd.Series(bottom, name="Bottom"),
            pd.Series(mitigated_f, name="MitigatedIndex"),
        ],
        axis=1,
    )


# ---------------------------------------------------------------------------
# bos_choch — structure detection + broken detection
# ---------------------------------------------------------------------------


@njit(cache=True)
def _bos_choch_inner(swing_hl, swing_level, n):
    """Build BOS/CHoCH arrays from swing data."""
    bos = np.zeros(n, dtype=np.int32)
    choch = np.zeros(n, dtype=np.int32)
    level = np.zeros(n, dtype=np.float64)

    # Collect swing positions
    positions = np.empty(n, dtype=np.int64)
    levels = np.empty(n, dtype=np.float64)
    hls = np.empty(n, dtype=np.float64)
    n_pos = 0

    for i in range(n):
        if np.isnan(swing_hl[i]):
            continue
        positions[n_pos] = i
        levels[n_pos] = swing_level[i]
        hls[n_pos] = swing_hl[i]
        n_pos += 1

        if n_pos < 4:
            continue

        idx = positions[n_pos - 3]
        h0 = hls[n_pos - 4]
        h1 = hls[n_pos - 3]
        h2 = hls[n_pos - 2]
        h3 = hls[n_pos - 1]
        l0 = levels[n_pos - 4]
        l1 = levels[n_pos - 3]
        l2 = levels[n_pos - 2]
        l3 = levels[n_pos - 1]

        # bullish BOS: [-1, 1, -1, 1] with l0 < l2 < l1 < l3
        if h0 == -1 and h1 == 1 and h2 == -1 and h3 == 1:
            if l0 < l2 < l1 < l3:
                bos[idx] = 1
                level[idx] = l1
        # bearish BOS: [1, -1, 1, -1] with l0 > l2 > l1 > l3
        if h0 == 1 and h1 == -1 and h2 == 1 and h3 == -1:
            if l0 > l2 > l1 > l3:
                bos[idx] = -1
                level[idx] = l1

        # bullish CHoCH: [-1, 1, -1, 1] with l3 > l1 > l0 > l2
        if bos[idx] == 0:
            if h0 == -1 and h1 == 1 and h2 == -1 and h3 == 1:
                if l3 > l1 > l0 > l2:
                    choch[idx] = 1
                    level[idx] = l1
        # bearish CHoCH: [1, -1, 1, -1] with l3 < l1 < l0 < l2
        if choch[idx] == 0:
            if h0 == 1 and h1 == -1 and h2 == 1 and h3 == -1:
                if l3 < l1 < l0 < l2:
                    choch[idx] = -1
                    level[idx] = l1

    return bos, choch, level


@njit(cache=True)
def _bos_choch_broken(bos, choch, level, price_arr, n):
    """Find break indices and clean up overlapping events."""
    broken = np.zeros(n, dtype=np.int32)
    event_indices = np.flatnonzero((bos != 0) | (choch != 0))

    for ii in range(len(event_indices)):
        i = event_indices[ii]
        if bos[i] == 1 or choch[i] == 1:
            for j in range(i + 2, n):
                if price_arr[j] > level[i]:
                    broken[i] = j
                    break
        elif bos[i] == -1 or choch[i] == -1:
            for j in range(i + 2, n):
                if price_arr[j] < level[i]:
                    broken[i] = j
                    break

        if broken[i] != 0:
            for kk in range(ii):
                k = event_indices[kk]
                if (bos[k] != 0 or choch[k] != 0) and broken[k] >= broken[i]:
                    bos[k] = 0
                    choch[k] = 0
                    level[k] = 0

    # Remove unbroken events
    for ii in range(len(event_indices)):
        i = event_indices[ii]
        if (bos[i] != 0 or choch[i] != 0) and broken[i] == 0:
            bos[i] = 0
            choch[i] = 0
            level[i] = 0

    return bos, choch, level, broken


def fast_bos_choch(ohlc, swing_highs_lows, close_break=True):
    """Numba-accelerated bos_choch replacement."""
    n = len(ohlc)
    swing_hl = swing_highs_lows["HighLow"].values.astype(np.float64)
    swing_level = swing_highs_lows["Level"].values.astype(np.float64)

    bos, choch, level = _bos_choch_inner(swing_hl, swing_level, n)

    col = "close" if close_break else "high"
    price_arr = ohlc[col].values.astype(np.float64)
    # For bearish, we need low if not close_break
    if not close_break:
        low_arr = ohlc["low"].values.astype(np.float64)
        bos, choch, level, broken = _bos_choch_broken_bidir(
            bos, choch, level, price_arr, low_arr, n
        )
    else:
        bos, choch, level, broken = _bos_choch_broken(bos, choch, level, price_arr, n)

    bos_f = np.where(bos != 0, bos.astype(np.float64), np.nan)
    choch_f = np.where(choch != 0, choch.astype(np.float64), np.nan)
    level_f = np.where(level != 0, level, np.nan)
    broken_f = np.where(broken != 0, broken.astype(np.float64), np.nan)

    return pd.concat(
        [
            pd.Series(bos_f, name="BOS"),
            pd.Series(choch_f, name="CHOCH"),
            pd.Series(level_f, name="Level"),
            pd.Series(broken_f, name="BrokenIndex"),
        ],
        axis=1,
    )


@njit(cache=True)
def _bos_choch_broken_bidir(bos, choch, level, high_arr, low_arr, n):
    """Break detection using high for bullish, low for bearish."""
    broken = np.zeros(n, dtype=np.int32)
    event_indices = np.flatnonzero((bos != 0) | (choch != 0))

    for ii in range(len(event_indices)):
        i = event_indices[ii]
        if bos[i] == 1 or choch[i] == 1:
            for j in range(i + 2, n):
                if high_arr[j] > level[i]:
                    broken[i] = j
                    break
        elif bos[i] == -1 or choch[i] == -1:
            for j in range(i + 2, n):
                if low_arr[j] < level[i]:
                    broken[i] = j
                    break

        if broken[i] != 0:
            for kk in range(ii):
                k = event_indices[kk]
                if (bos[k] != 0 or choch[k] != 0) and broken[k] >= broken[i]:
                    bos[k] = 0
                    choch[k] = 0
                    level[k] = 0

    for ii in range(len(event_indices)):
        i = event_indices[ii]
        if (bos[i] != 0 or choch[i] != 0) and broken[i] == 0:
            bos[i] = 0
            choch[i] = 0
            level[i] = 0

    return bos, choch, level, broken


# ---------------------------------------------------------------------------
# ob — order block detection (two full loops → two njit functions)
# ---------------------------------------------------------------------------


@njit(cache=True)
def _ob_bullish_loop(
    open_arr,
    high_arr,
    low_arr,
    close_arr,
    volume_arr,
    swing_high_indices,
    close_mitigation,
    n,
    crossed,
    ob,
    top_arr,
    bottom_arr,
    ob_volume,
    low_volume,
    high_volume,
    percentage,
    mitigated_index,
    breaker,
):
    """Detect bullish order blocks in a single pass."""
    active = np.empty(n, dtype=np.int64)
    n_active = 0

    for i in range(n):
        # Update existing bullish OBs
        j = 0
        while j < n_active:
            idx = active[j]
            if breaker[idx]:
                if high_arr[i] > top_arr[idx]:
                    ob[idx] = 0
                    top_arr[idx] = 0.0
                    bottom_arr[idx] = 0.0
                    ob_volume[idx] = 0.0
                    low_volume[idx] = 0.0
                    high_volume[idx] = 0.0
                    mitigated_index[idx] = 0
                    percentage[idx] = 0.0
                    active[j] = active[n_active - 1]
                    n_active -= 1
                    continue
                j += 1
            else:
                if not close_mitigation:
                    if low_arr[i] < bottom_arr[idx]:
                        breaker[idx] = True
                        mitigated_index[idx] = i - 1
                else:
                    mc = min(open_arr[i], close_arr[i])
                    if mc < bottom_arr[idx]:
                        breaker[idx] = True
                        mitigated_index[idx] = i - 1
                j += 1

        # Find last swing high before this candle
        pos = np.searchsorted(swing_high_indices, i)
        if pos <= 0:
            continue
        last_top = swing_high_indices[pos - 1]
        if close_arr[i] <= high_arr[last_top]:
            continue
        if crossed[last_top]:
            continue
        crossed[last_top] = True

        default_idx = i - 1
        ob_btm = high_arr[default_idx]
        ob_top = low_arr[default_idx]
        ob_idx = default_idx

        if i - last_top > 1:
            start = last_top + 1
            end = i
            if end > start:
                min_val = low_arr[start]
                min_i = start
                for k in range(start + 1, end):
                    if low_arr[k] <= min_val:
                        min_val = low_arr[k]
                        min_i = k
                ob_btm = low_arr[min_i]
                ob_top = high_arr[min_i]
                ob_idx = min_i

        ob[ob_idx] = 1
        top_arr[ob_idx] = ob_top
        bottom_arr[ob_idx] = ob_btm
        vol_cur = volume_arr[i]
        vol_p1 = volume_arr[i - 1] if i >= 1 else 0.0
        vol_p2 = volume_arr[i - 2] if i >= 2 else 0.0
        ob_volume[ob_idx] = vol_cur + vol_p1 + vol_p2
        low_volume[ob_idx] = vol_p2
        high_volume[ob_idx] = vol_cur + vol_p1
        mx = max(high_volume[ob_idx], low_volume[ob_idx])
        if mx != 0.0:
            percentage[ob_idx] = (
                min(high_volume[ob_idx], low_volume[ob_idx]) / mx * 100.0
            )
        else:
            percentage[ob_idx] = 100.0
        active[n_active] = ob_idx
        n_active += 1


@njit(cache=True)
def _ob_bearish_loop(
    open_arr,
    high_arr,
    low_arr,
    close_arr,
    volume_arr,
    swing_low_indices,
    close_mitigation,
    n,
    crossed,
    ob,
    top_arr,
    bottom_arr,
    ob_volume,
    low_volume,
    high_volume,
    percentage,
    mitigated_index,
    breaker,
):
    """Detect bearish order blocks in a single pass."""
    active = np.empty(n, dtype=np.int64)
    n_active = 0

    for i in range(n):
        # Update existing bearish OBs
        j = 0
        while j < n_active:
            idx = active[j]
            if breaker[idx]:
                if low_arr[i] < bottom_arr[idx]:
                    ob[idx] = 0
                    top_arr[idx] = 0.0
                    bottom_arr[idx] = 0.0
                    ob_volume[idx] = 0.0
                    low_volume[idx] = 0.0
                    high_volume[idx] = 0.0
                    mitigated_index[idx] = 0
                    percentage[idx] = 0.0
                    active[j] = active[n_active - 1]
                    n_active -= 1
                    continue
                j += 1
            else:
                if not close_mitigation:
                    if high_arr[i] > top_arr[idx]:
                        breaker[idx] = True
                        mitigated_index[idx] = i
                else:
                    mc = max(open_arr[i], close_arr[i])
                    if mc > top_arr[idx]:
                        breaker[idx] = True
                        mitigated_index[idx] = i
                j += 1

        # Find last swing low before this candle
        pos = np.searchsorted(swing_low_indices, i)
        if pos <= 0:
            continue
        last_btm = swing_low_indices[pos - 1]
        if close_arr[i] >= low_arr[last_btm]:
            continue
        if crossed[last_btm]:
            continue
        crossed[last_btm] = True

        default_idx = i - 1
        ob_top = high_arr[default_idx]
        ob_btm = low_arr[default_idx]
        ob_idx = default_idx

        if i - last_btm > 1:
            start = last_btm + 1
            end = i
            if end > start:
                max_val = high_arr[start]
                max_i = start
                for k in range(start + 1, end):
                    if high_arr[k] >= max_val:
                        max_val = high_arr[k]
                        max_i = k
                ob_top = high_arr[max_i]
                ob_btm = low_arr[max_i]
                ob_idx = max_i

        ob[ob_idx] = -1
        top_arr[ob_idx] = ob_top
        bottom_arr[ob_idx] = ob_btm
        vol_cur = volume_arr[i]
        vol_p1 = volume_arr[i - 1] if i >= 1 else 0.0
        vol_p2 = volume_arr[i - 2] if i >= 2 else 0.0
        ob_volume[ob_idx] = vol_cur + vol_p1 + vol_p2
        low_volume[ob_idx] = vol_cur + vol_p1
        high_volume[ob_idx] = vol_p2
        mx = max(high_volume[ob_idx], low_volume[ob_idx])
        if mx != 0.0:
            percentage[ob_idx] = (
                min(high_volume[ob_idx], low_volume[ob_idx]) / mx * 100.0
            )
        else:
            percentage[ob_idx] = 100.0
        active[n_active] = ob_idx
        n_active += 1


def fast_ob(ohlc, swing_highs_lows, close_mitigation=False):
    """Numba-accelerated ob replacement."""
    n = len(ohlc)
    open_arr = ohlc["open"].values.astype(np.float64)
    high_arr = ohlc["high"].values.astype(np.float64)
    low_arr = ohlc["low"].values.astype(np.float64)
    close_arr = ohlc["close"].values.astype(np.float64)
    volume_arr = ohlc["volume"].values.astype(np.float64)
    swing_hl = swing_highs_lows["HighLow"].values

    swing_high_idx = np.flatnonzero(swing_hl == 1).astype(np.int64)
    swing_low_idx = np.flatnonzero(swing_hl == -1).astype(np.int64)

    crossed = np.zeros(n, dtype=np.bool_)
    ob = np.zeros(n, dtype=np.int32)
    top_arr = np.zeros(n, dtype=np.float64)
    bottom_arr = np.zeros(n, dtype=np.float64)
    ob_volume = np.zeros(n, dtype=np.float64)
    low_volume = np.zeros(n, dtype=np.float64)
    high_volume = np.zeros(n, dtype=np.float64)
    percentage = np.zeros(n, dtype=np.float64)
    mitigated_index = np.zeros(n, dtype=np.int32)
    breaker = np.zeros(n, dtype=np.bool_)

    _ob_bullish_loop(
        open_arr,
        high_arr,
        low_arr,
        close_arr,
        volume_arr,
        swing_high_idx,
        close_mitigation,
        n,
        crossed,
        ob,
        top_arr,
        bottom_arr,
        ob_volume,
        low_volume,
        high_volume,
        percentage,
        mitigated_index,
        breaker,
    )

    _ob_bearish_loop(
        open_arr,
        high_arr,
        low_arr,
        close_arr,
        volume_arr,
        swing_low_idx,
        close_mitigation,
        n,
        crossed,
        ob,
        top_arr,
        bottom_arr,
        ob_volume,
        low_volume,
        high_volume,
        percentage,
        mitigated_index,
        breaker,
    )

    ob_f = np.where(ob != 0, ob.astype(np.float64), np.nan)
    top_f = np.where(~np.isnan(ob_f), top_arr, np.nan)
    bottom_f = np.where(~np.isnan(ob_f), bottom_arr, np.nan)
    volume_f = np.where(~np.isnan(ob_f), ob_volume, np.nan)
    mitigated_f = np.where(~np.isnan(ob_f), mitigated_index.astype(np.float64), np.nan)
    pct_f = np.where(~np.isnan(ob_f), percentage, np.nan)

    return pd.concat(
        [
            pd.Series(ob_f, name="OB"),
            pd.Series(top_f, name="Top"),
            pd.Series(bottom_f, name="Bottom"),
            pd.Series(volume_f, name="OBVolume"),
            pd.Series(mitigated_f, name="MitigatedIndex"),
            pd.Series(pct_f, name="Percentage"),
        ],
        axis=1,
    )


# ---------------------------------------------------------------------------
# patch() — apply replacements
# ---------------------------------------------------------------------------


_patched = False


def patch():
    """Monkeypatch the ``smc`` class with numba-accelerated methods."""
    global _patched
    if _patched:
        return

    from smartmoneyconcepts.smc import smc

    smc.swing_highs_lows = fast_swing_highs_lows  # type: ignore[assignment]
    smc.fvg = fast_fvg  # type: ignore[assignment]
    smc.bos_choch = fast_bos_choch  # type: ignore[assignment]
    smc.ob = fast_ob  # type: ignore[assignment]

    _patched = True
