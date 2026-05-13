"""
SMC (Smart Money Concepts) analysis. Takes a DataFrame with all indicator
columns added and returns a structured analysis dict for a single timeframe.
"""

import numpy as np
import pandas as pd

from .common import find_col
from .common import safe_float as _safe


def _count_sr_touches(
    highs: np.ndarray,
    lows: np.ndarray,
    level: float,
    atr: float,
    window_pct: float = 0.05,
) -> int:
    n = len(highs)
    tolerance = atr * 0.5
    window = max(3, int(n * window_pct))
    touches = 0
    last_touch_idx = -window - 1
    for i in range(n):
        if abs(highs[i] - level) > tolerance and abs(lows[i] - level) > tolerance:
            continue
        if i - last_touch_idx <= window:
            continue
        touches += 1
        last_touch_idx = i
    return touches


def get_sr_levels(
    df: pd.DataFrame, price: float, atr: float, max_levels: int = 3
) -> list[dict]:
    if not atr or atr <= 0 or len(df) < 50:
        return []

    # Reuse sw7 columns already computed by price_action_swing_structure.add()
    if "sw7_hl" not in df.columns or "sw7_level" not in df.columns:
        return []

    sw7_type = df["sw7_hl"]
    sw7_level = df["sw7_level"]

    # Pre-extract numpy arrays once — avoids df.iloc per touch-count call
    highs = df["high"].to_numpy(dtype=float)
    lows = df["low"].to_numpy(dtype=float)

    threshold = atr * 3.0
    placed: list[float] = []
    levels: list[dict] = []

    for target_type, sr_type in [(1, "resistance"), (-1, "support")]:
        # Vectorized swing point lookup instead of row-by-row .iloc loop
        mask = (sw7_type == target_type) & sw7_level.notna()
        if target_type == 1:
            mask &= sw7_level > price
        else:
            mask &= sw7_level < price

        candidates = []
        for lvl in sw7_level[mask]:
            lvl_f = float(lvl)
            touches = _count_sr_touches(highs, lows, lvl_f, atr)
            if touches < 2:
                continue
            candidates.append((abs(lvl_f - price), lvl_f, touches))

        candidates.sort(key=lambda x: x[0])
        count = 0
        for dist, lvl, touches in candidates:
            if count >= max_levels:
                break
            if any(abs(lvl - p) < threshold for p in placed):
                continue
            placed.append(lvl)
            count += 1
            levels.append(
                {
                    "level": round(lvl, 6),
                    "type": sr_type,
                    "distance_pct": round(abs(price - lvl) / price * 100, 3),
                    "touches": touches,
                }
            )

    levels.sort(key=lambda x: float(x["distance_pct"]))  # type: ignore[arg-type]
    return levels


def analyze(df: pd.DataFrame, timeframe: str) -> dict:
    """
    Run full SMC + levels analysis on a single-timeframe DataFrame.
    Returns a structured dict with all analysis data.
    """
    latest = df.iloc[-1]
    price = float(latest["close"])

    dcu_col = find_col(df, "DCU_")
    dcl_col = find_col(df, "DCL_")
    dcm_col = find_col(df, "DCM_")
    macdh_col = find_col(df, "MACDh_")
    macdl_col = find_col(df, "MACD_")
    macds_col = find_col(df, "MACDs_")
    adx_col = find_col(df, "ADX_")
    stochk_col = find_col(df, "STOCHk_")
    stochd_col = find_col(df, "STOCHd_")

    atr_val = latest.get("atr")
    atr = (
        float(atr_val) if atr_val is not None and not np.isnan(float(atr_val)) else 0.0
    )

    result = {
        "timeframe": timeframe,
        "candles": len(df),
        "price": price,
        "time": int(latest["time"]),
        "levels": {
            "ema_21": _safe(latest.get("ema_21")),
            "sma_50": _safe(latest.get("sma_50")),
            "sma_100": _safe(latest.get("sma_100")),
            "sma_200": _safe(latest.get("sma_200")),
            "atr": _safe(latest.get("atr")),
            "vwap": _safe(latest.get("vwap")),
            "donchian_upper": _safe(latest.get(dcu_col)) if dcu_col else None,
            "donchian_lower": _safe(latest.get(dcl_col)) if dcl_col else None,
            "donchian_mid": _safe(latest.get(dcm_col)) if dcm_col else None,
        },
        "momentum": {
            "rsi": _safe(latest.get("rsi")),
            "mfi": _safe(latest.get("mfi")),
            "macd_hist": _safe(latest.get(macdh_col)) if macdh_col else None,
            "macd_line": _safe(latest.get(macdl_col)) if macdl_col else None,
            "macd_signal": _safe(latest.get(macds_col)) if macds_col else None,
            "adx": _safe(latest.get(adx_col)) if adx_col else None,
            "stoch_k": _safe(latest.get(stochk_col)) if stochk_col else None,
            "stoch_d": _safe(latest.get(stochd_col)) if stochd_col else None,
        },
        "volume": {
            "vol_ratio": _safe(latest.get("vol_ratio")),
            "obv": _safe(latest.get("obv")),
            "is_spike": (
                bool(latest.get("vol_ratio", 0) > 2.0)
                if pd.notna(latest.get("vol_ratio"))
                else False
            ),
        },
        "position": _price_position(latest, price),
        "slope": _ma_slopes(df),
        "order_blocks": _order_blocks(df, price),
        "fvgs": _fvgs(df, price),
        "bos_choch": _bos_choch(df),
        "swing_levels": _swing_levels(df),
        "sr_levels": get_sr_levels(df, price, atr),
        "recent_range": {
            "high": float(df["high"].tail(20).max()),
            "low": float(df["low"].tail(20).min()),
            "period_high": float(df["high"].max()),
            "period_low": float(df["low"].min()),
        },
    }

    return result


_SLOPE_LOOKBACK = 10


def _ma_slopes(df: pd.DataFrame) -> dict:
    """Direction of each MA over the last _SLOPE_LOOKBACK bars."""
    slopes: dict[str, str] = {}
    if len(df) <= _SLOPE_LOOKBACK:
        return slopes

    last = df.iloc[-1]
    prev = df.iloc[-1 - _SLOPE_LOOKBACK]
    for col in ("ema_21", "sma_50", "sma_100", "sma_200", "vwap"):
        cur = last.get(col)
        old = prev.get(col)
        if not pd.notna(cur) or not pd.notna(old) or cur <= 0 or old <= 0:
            continue
        if cur > old:
            slopes[col] = "up"
        elif cur < old:
            slopes[col] = "down"
    return slopes


def _price_position(latest: pd.Series, price: float) -> dict:
    position = {}
    for ma_name, col in [
        ("ema_21", "ema_21"),
        ("sma_50", "sma_50"),
        ("sma_100", "sma_100"),
        ("sma_200", "sma_200"),
    ]:
        val = latest.get(col)
        if not pd.notna(val) or val <= 0:
            continue
        position[ma_name] = "above" if price > val else "below"
    vwap_val = latest.get("vwap")
    if pd.notna(vwap_val) and vwap_val > 0:
        position["vwap"] = "above" if price > vwap_val else "below"
    return position


def _order_blocks(df: pd.DataFrame, price: float) -> list[dict]:
    # Vectorized: filter rows with ob_type != 0 and ob_mitigated is NaN
    mask = (df["ob_type"] != 0) & df["ob_mitigated"].isna()
    rows = df[mask][["ob_type", "ob_top", "ob_bottom", "time"]].copy()
    rows["_idx"] = np.where(mask)[0]

    obs = []
    for _, row in rows.iterrows():
        ob_type = "bullish" if row["ob_type"] == 1 else "bearish"
        top = float(row["ob_top"])
        bottom = float(row["ob_bottom"])
        if ob_type == "bullish":
            dist = round((price - top) / price * 100, 3)
        else:
            dist = round((bottom - price) / price * 100, 3)
        obs.append(
            {
                "type": ob_type,
                "top": top,
                "bottom": bottom,
                "candle_idx": int(row["_idx"]),
                "time": int(row["time"]),
                "distance_pct": dist,
            }
        )
    obs.sort(key=lambda x: abs(float(x["distance_pct"])))  # type: ignore[arg-type]
    return obs[:20]


def _fvgs(df: pd.DataFrame, price: float) -> list[dict]:
    # Vectorized: filter rows with fvg_type != 0 and fvg_mitigated is NaN
    mask = (df["fvg_type"] != 0) & df["fvg_mitigated"].isna()
    rows = df[mask][["fvg_type", "fvg_top", "fvg_bottom", "time"]].copy()
    rows["_idx"] = np.where(mask)[0]

    fvgs = []
    for _, row in rows.iterrows():
        top = float(row["fvg_top"])
        bottom = float(row["fvg_bottom"])
        mid = (top + bottom) / 2
        fvgs.append(
            {
                "type": "bullish" if row["fvg_type"] == 1 else "bearish",
                "top": top,
                "bottom": bottom,
                "candle_idx": int(row["_idx"]),
                "time": int(row["time"]),
                "distance_pct": round(abs(price - mid) / price * 100, 3),
            }
        )
    fvgs.sort(key=lambda x: float(x["distance_pct"]))  # type: ignore[arg-type]
    return fvgs[:15]


def _bos_choch(df: pd.DataFrame) -> list[dict]:
    tail = df.iloc[max(0, len(df) - 50) :]
    mask = (tail["bos"] != 0) | (tail["choch"] != 0)
    rows = tail[mask][["bos", "choch", "bos_choch_level", "time"]]

    events: list[dict] = []
    for bos_val, choch_val, level, t in zip(
        rows["bos"].to_numpy(),
        rows["choch"].to_numpy(),
        rows["bos_choch_level"].to_numpy(),
        rows["time"].to_numpy(),
    ):
        if bos_val != 0:
            events.append(
                {
                    "event": "BOS",
                    "direction": "bullish" if bos_val == 1 else "bearish",
                    "level": _safe(level),
                    "time": int(t),
                }
            )
        if choch_val != 0:
            events.append(
                {
                    "event": "CHoCH",
                    "direction": "bullish" if choch_val == 1 else "bearish",
                    "level": _safe(level),
                    "time": int(t),
                }
            )
    return events[-10:]


def _swing_levels(df: pd.DataFrame) -> list[dict]:
    tail = df.iloc[max(0, len(df) - 50) :]
    mask = tail["swing_type"] != 0
    rows = tail[mask][["swing_type", "swing_level", "time"]]

    return [
        {
            "type": "high" if st == 1 else "low",
            "level": float(lvl),
            "time": int(t),
        }
        for st, lvl, t in zip(
            rows["swing_type"].to_numpy(),
            rows["swing_level"].to_numpy(),
            rows["time"].to_numpy(),
        )
    ][-10:]
