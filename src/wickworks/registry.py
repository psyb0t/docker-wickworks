"""Indicator registry: name -> compute function.

Each compute fn takes (ctx, params) and returns its JSON-serializable result.
Callers run multiple instances of the same indicator under different output
keys by setting "type" in the params dict (see compute.py).
"""

from __future__ import annotations

from typing import Any, Callable

import numpy as np
import pandas as pd
import pandas_ta as ta

from smartmoneyconcepts import smc as smc_lib

from . import smc as smc_module
from .common import parse_duration


def _col(out: pd.DataFrame, prefix: str, fallback_idx: int = 0) -> pd.Series:
    """Pick the first column whose name starts with `prefix`, or fall back by index."""
    for c in out.columns:
        if c.startswith(prefix):
            return out[c]
    return out.iloc[:, fallback_idx]


def _vol_col(df: pd.DataFrame) -> str:
    return "tick_volume" if "tick_volume" in df.columns else "volume"


def _series(s: pd.Series | None) -> list[float | None]:
    """pandas Series -> JSON-safe list (NaN -> None)."""
    if s is None:
        return []
    return [None if (v is None or (isinstance(v, float) and np.isnan(v))) else float(v) for v in s]


class Context:
    """Per-request scratch space. Builds expensive things lazily and once."""

    def __init__(self, df: pd.DataFrame, timeframe: str) -> None:
        self.df = df
        self.timeframe = timeframe
        self._analysis: dict[str, Any] | None = None

    def analysis(self) -> dict[str, Any]:
        if self._analysis is None:
            self._analysis = smc_module.analyze(self.df, self.timeframe)
        return self._analysis


# -----------------------------------------------------------------------------
# Series indicators — each returns either a list[float|None] or a dict of them.
# -----------------------------------------------------------------------------


def _rsi(ctx: Context, p: dict[str, Any]) -> list[float | None]:
    length = int(p.get("length", 14))
    return _series(ta.rsi(ctx.df["close"], length=length))


def _ema(ctx: Context, p: dict[str, Any]) -> list[float | None]:
    length = int(p.get("length", 21))
    return _series(ta.ema(ctx.df["close"], length=length))


def _sma(ctx: Context, p: dict[str, Any]) -> list[float | None]:
    length = int(p.get("length", 50))
    return _series(ta.sma(ctx.df["close"], length=length))


def _atr(ctx: Context, p: dict[str, Any]) -> list[float | None]:
    length = int(p.get("length", 14))
    return _series(ta.atr(ctx.df["high"], ctx.df["low"], ctx.df["close"], length=length))


def _mfi(ctx: Context, p: dict[str, Any]) -> list[float | None]:
    length = int(p.get("length", 14))
    vol_col = "tick_volume" if "tick_volume" in ctx.df.columns else "volume"
    return _series(
        ta.mfi(ctx.df["high"], ctx.df["low"], ctx.df["close"], ctx.df[vol_col], length=length)
    )


def _vwap(ctx: Context, p: dict[str, Any]) -> list[float | None]:
    anchor = str(p.get("anchor", "D"))
    offset_sec = parse_duration(p.get("sessionOffset", p.get("session_offset", 0)))
    vol_col = "tick_volume" if "tick_volume" in ctx.df.columns else "volume"
    # pandas_ta vwap groups by anchor on the DatetimeIndex. Shifting the index
    # by `sessionOffset` moves session boundaries away from UTC midnight.
    df = ctx.df
    if "datetime" in df.columns:
        idx = df["datetime"] + pd.Timedelta(seconds=offset_sec) if offset_sec else df["datetime"]
        s = df.set_index(idx, drop=False)
    else:
        s = df
    return _series(ta.vwap(s["high"], s["low"], s["close"], s[vol_col], anchor=anchor))


def _macd(ctx: Context, p: dict[str, Any]) -> dict[str, list[float | None]]:
    fast = int(p.get("fast", 12))
    slow = int(p.get("slow", 26))
    signal = int(p.get("signal", 9))
    out = ta.macd(ctx.df["close"], fast=fast, slow=slow, signal=signal)
    if out is None or out.empty:
        return {"macd": [], "signal": [], "hist": []}
    cols = list(out.columns)
    macd_col = next((c for c in cols if c.startswith("MACD_")), cols[0])
    sig_col = next((c for c in cols if c.startswith("MACDs_")), cols[-1])
    hist_col = next((c for c in cols if c.startswith("MACDh_")), cols[1])
    return {"macd": _series(out[macd_col]), "signal": _series(out[sig_col]), "hist": _series(out[hist_col])}


def _stoch(ctx: Context, p: dict[str, Any]) -> dict[str, list[float | None]]:
    k = int(p.get("k", 14))
    d = int(p.get("d", 3))
    smooth_k = int(p.get("smoothK", p.get("smooth_k", p.get("smooth", 3))))
    out = ta.stoch(ctx.df["high"], ctx.df["low"], ctx.df["close"], k=k, d=d, smooth_k=smooth_k)
    if out is None or out.empty:
        return {"k": [], "d": []}
    cols = list(out.columns)
    k_col = next((c for c in cols if c.startswith("STOCHk_")), cols[0])
    d_col = next((c for c in cols if c.startswith("STOCHd_")), cols[-1])
    return {"k": _series(out[k_col]), "d": _series(out[d_col])}


def _adx(ctx: Context, p: dict[str, Any]) -> dict[str, list[float | None]]:
    length = int(p.get("length", 14))
    out = ta.adx(ctx.df["high"], ctx.df["low"], ctx.df["close"], length=length)
    if out is None or out.empty:
        return {"adx": [], "diPlus": [], "diMinus": []}
    cols = list(out.columns)
    adx_col = next((c for c in cols if c.startswith("ADX_")), cols[0])
    dmp_col = next((c for c in cols if c.startswith("DMP_")), cols[1])
    dmn_col = next((c for c in cols if c.startswith("DMN_")), cols[2])
    return {"adx": _series(out[adx_col]), "diPlus": _series(out[dmp_col]), "diMinus": _series(out[dmn_col])}


def _bbands(ctx: Context, p: dict[str, Any]) -> dict[str, list[float | None]]:
    length = int(p.get("length", 20))
    std = float(p.get("std", 2.0))
    out = ta.bbands(ctx.df["close"], length=length, std=std)
    if out is None or out.empty:
        return {"upper": [], "middle": [], "lower": []}
    cols = list(out.columns)
    lower = next((c for c in cols if c.startswith("BBL_")), cols[0])
    middle = next((c for c in cols if c.startswith("BBM_")), cols[1])
    upper = next((c for c in cols if c.startswith("BBU_")), cols[2])
    return {"upper": _series(out[upper]), "middle": _series(out[middle]), "lower": _series(out[lower])}


def _donchian(ctx: Context, p: dict[str, Any]) -> dict[str, list[float | None]]:
    length = int(p.get("length", 20))
    out = ta.donchian(ctx.df["high"], ctx.df["low"], lower_length=length, upper_length=length)
    if out is None or out.empty:
        return {"upper": [], "middle": [], "lower": []}
    cols = list(out.columns)
    lower = next((c for c in cols if c.startswith("DCL_")), cols[0])
    middle = next((c for c in cols if c.startswith("DCM_")), cols[1])
    upper = next((c for c in cols if c.startswith("DCU_")), cols[2])
    return {"upper": _series(out[upper]), "middle": _series(out[middle]), "lower": _series(out[lower])}


# -----------------------------------------------------------------------------
# Additional series oscillators — single-output.
# -----------------------------------------------------------------------------


def _willr(ctx: Context, p: dict[str, Any]) -> list[float | None]:
    length = int(p.get("length", 14))
    return _series(ta.willr(ctx.df["high"], ctx.df["low"], ctx.df["close"], length=length))


def _cci(ctx: Context, p: dict[str, Any]) -> list[float | None]:
    # pandas_ta 0.4.71b0 ships ta.cci with a precedence bug (missing parens
    # around the numerator). Compute it ourselves: (tp - sma(tp)) / (c*mad).
    length = int(p.get("length", 14))
    c = float(p.get("c", 0.015))
    tp = (ctx.df["high"] + ctx.df["low"] + ctx.df["close"]) / 3.0
    mean = tp.rolling(length).mean()
    mad = tp.rolling(length).apply(lambda x: np.fabs(x - x.mean()).mean(), raw=True)
    return _series((tp - mean) / (c * mad))


def _roc(ctx: Context, p: dict[str, Any]) -> list[float | None]:
    length = int(p.get("length", 10))
    return _series(ta.roc(ctx.df["close"], length=length))


def _mom(ctx: Context, p: dict[str, Any]) -> list[float | None]:
    length = int(p.get("length", 10))
    return _series(ta.mom(ctx.df["close"], length=length))


def _natr(ctx: Context, p: dict[str, Any]) -> list[float | None]:
    length = int(p.get("length", 14))
    return _series(ta.natr(ctx.df["high"], ctx.df["low"], ctx.df["close"], length=length))


def _uo(ctx: Context, p: dict[str, Any]) -> list[float | None]:
    fast = int(p.get("fast", 7))
    medium = int(p.get("medium", 14))
    slow = int(p.get("slow", 28))
    return _series(ta.uo(ctx.df["high"], ctx.df["low"], ctx.df["close"], fast=fast, medium=medium, slow=slow))


# -----------------------------------------------------------------------------
# Volume indicators — single-output.
# -----------------------------------------------------------------------------


def _obv(ctx: Context, _p: dict[str, Any]) -> list[float | None]:
    return _series(ta.obv(ctx.df["close"], ctx.df[_vol_col(ctx.df)]))


def _ad(ctx: Context, _p: dict[str, Any]) -> list[float | None]:
    return _series(ta.ad(ctx.df["high"], ctx.df["low"], ctx.df["close"], ctx.df[_vol_col(ctx.df)]))


def _cmf(ctx: Context, p: dict[str, Any]) -> list[float | None]:
    length = int(p.get("length", 20))
    return _series(
        ta.cmf(ctx.df["high"], ctx.df["low"], ctx.df["close"], ctx.df[_vol_col(ctx.df)], length=length)
    )


def _adosc(ctx: Context, p: dict[str, Any]) -> list[float | None]:
    fast = int(p.get("fast", 3))
    slow = int(p.get("slow", 10))
    return _series(
        ta.adosc(ctx.df["high"], ctx.df["low"], ctx.df["close"], ctx.df[_vol_col(ctx.df)], fast=fast, slow=slow)
    )


def _vwma(ctx: Context, p: dict[str, Any]) -> list[float | None]:
    length = int(p.get("length", 10))
    return _series(ta.vwma(ctx.df["close"], ctx.df[_vol_col(ctx.df)], length=length))


# -----------------------------------------------------------------------------
# Alt moving averages — all single Series of close prices.
# -----------------------------------------------------------------------------


def _ma_factory(fn_name: str, default_length: int):
    def _impl(ctx: Context, p: dict[str, Any]) -> list[float | None]:
        length = int(p.get("length", default_length))
        return _series(getattr(ta, fn_name)(ctx.df["close"], length=length))
    _impl.__name__ = f"_{fn_name}"
    return _impl


_hma = _ma_factory("hma", 14)
_wma = _ma_factory("wma", 14)
_dema = _ma_factory("dema", 10)
_tema = _ma_factory("tema", 10)
_t3 = _ma_factory("t3", 10)
_kama = _ma_factory("kama", 10)
_alma = _ma_factory("alma", 10)
_linreg = _ma_factory("linreg", 14)
_jma = _ma_factory("jma", 7)
_zlma = _ma_factory("zlma", 10)
_rma = _ma_factory("rma", 10)
_fwma = _ma_factory("fwma", 10)
_swma = _ma_factory("swma", 10)
_sinwma = _ma_factory("sinwma", 14)
_trima = _ma_factory("trima", 10)


# -----------------------------------------------------------------------------
# Multi-output trend / volatility indicators.
# -----------------------------------------------------------------------------


def _supertrend(ctx: Context, p: dict[str, Any]) -> dict[str, list[float | None]]:
    length = int(p.get("length", 7))
    multiplier = float(p.get("multiplier", 3.0))
    out = ta.supertrend(ctx.df["high"], ctx.df["low"], ctx.df["close"], length=length, multiplier=multiplier)
    if out is None or out.empty:
        return {"value": [], "direction": [], "long": [], "short": []}
    return {
        "value": _series(_col(out, "SUPERT_", 0)),
        "direction": _series(_col(out, "SUPERTd_", 1)),
        "long": _series(_col(out, "SUPERTl_", 2)),
        "short": _series(_col(out, "SUPERTs_", 3)),
    }


def _psar(ctx: Context, p: dict[str, Any]) -> dict[str, list[float | None]]:
    step = float(p.get("af", p.get("step", 0.02)))
    max_step = float(p.get("max", p.get("maxAf", 0.2)))
    out = ta.psar(ctx.df["high"], ctx.df["low"], ctx.df["close"], af=step, max_af=max_step)
    if out is None or out.empty:
        return {"long": [], "short": [], "af": [], "reversal": []}
    return {
        "long": _series(_col(out, "PSARl_", 0)),
        "short": _series(_col(out, "PSARs_", 1)),
        "af": _series(_col(out, "PSARaf_", 2)),
        "reversal": _series(_col(out, "PSARr_", 3)),
    }


def _ichimoku(ctx: Context, p: dict[str, Any]) -> dict[str, list[float | None]]:
    tenkan = int(p.get("tenkan", 9))
    kijun = int(p.get("kijun", 26))
    senkou = int(p.get("senkou", 52))
    visible, _future = ta.ichimoku(
        ctx.df["high"], ctx.df["low"], ctx.df["close"], tenkan=tenkan, kijun=kijun, senkou=senkou
    )
    if visible is None or visible.empty:
        return {"spanA": [], "spanB": [], "tenkan": [], "kijun": [], "chikou": []}
    return {
        "spanA": _series(_col(visible, "ISA_", 0)),
        "spanB": _series(_col(visible, "ISB_", 1)),
        "tenkan": _series(_col(visible, "ITS_", 2)),
        "kijun": _series(_col(visible, "IKS_", 3)),
        "chikou": _series(_col(visible, "ICS_", 4)),
    }


def _aroon(ctx: Context, p: dict[str, Any]) -> dict[str, list[float | None]]:
    length = int(p.get("length", 14))
    out = ta.aroon(ctx.df["high"], ctx.df["low"], length=length)
    if out is None or out.empty:
        return {"up": [], "down": [], "oscillator": []}
    return {
        "down": _series(_col(out, "AROOND_", 0)),
        "up": _series(_col(out, "AROONU_", 1)),
        "oscillator": _series(_col(out, "AROONOSC_", 2)),
    }


def _kc(ctx: Context, p: dict[str, Any]) -> dict[str, list[float | None]]:
    length = int(p.get("length", 20))
    scalar = float(p.get("scalar", 2.0))
    out = ta.kc(ctx.df["high"], ctx.df["low"], ctx.df["close"], length=length, scalar=scalar)
    if out is None or out.empty:
        return {"upper": [], "middle": [], "lower": []}
    return {
        "lower": _series(_col(out, "KCLe_", 0)),
        "middle": _series(_col(out, "KCBe_", 1)),
        "upper": _series(_col(out, "KCUe_", 2)),
    }


def _vortex(ctx: Context, p: dict[str, Any]) -> dict[str, list[float | None]]:
    length = int(p.get("length", 14))
    out = ta.vortex(ctx.df["high"], ctx.df["low"], ctx.df["close"], length=length)
    if out is None or out.empty:
        return {"plus": [], "minus": []}
    return {
        "plus": _series(_col(out, "VTXP_", 0)),
        "minus": _series(_col(out, "VTXM_", 1)),
    }


def _stochrsi(ctx: Context, p: dict[str, Any]) -> dict[str, list[float | None]]:
    length = int(p.get("length", 14))
    rsi_length = int(p.get("rsiLength", p.get("rsi_length", 14)))
    k = int(p.get("k", 3))
    d = int(p.get("d", 3))
    out = ta.stochrsi(ctx.df["close"], length=length, rsi_length=rsi_length, k=k, d=d)
    if out is None or out.empty:
        return {"k": [], "d": []}
    return {
        "k": _series(_col(out, "STOCHRSIk_", 0)),
        "d": _series(_col(out, "STOCHRSId_", 1)),
    }


def _kvo(ctx: Context, p: dict[str, Any]) -> dict[str, list[float | None]]:
    fast = int(p.get("fast", 34))
    slow = int(p.get("slow", 55))
    signal = int(p.get("signal", 13))
    out = ta.kvo(
        ctx.df["high"], ctx.df["low"], ctx.df["close"], ctx.df[_vol_col(ctx.df)],
        fast=fast, slow=slow, signal=signal,
    )
    if out is None or out.empty:
        return {"kvo": [], "signal": []}
    return {
        "kvo": _series(_col(out, "KVO_", 0)),
        "signal": _series(_col(out, "KVOs_", 1)),
    }


def _chandelier_exit(ctx: Context, p: dict[str, Any]) -> dict[str, list[float | None]]:
    length = int(p.get("length", 22))
    atr_length = int(p.get("atrLength", p.get("atr_length", 22)))
    mult = float(p.get("multiplier", 2.0))
    out = ta.chandelier_exit(
        ctx.df["high"], ctx.df["low"], ctx.df["close"],
        high_length=length, low_length=length, atr_length=atr_length, mult=mult,
    )
    if out is None or out.empty:
        return {"long": [], "short": [], "direction": []}
    return {
        "long": _series(_col(out, "CHDLREXTl_", 0)),
        "short": _series(_col(out, "CHDLREXTs_", 1)),
        "direction": _series(_col(out, "CHDLREXTd_", 2)),
    }


def _fisher(ctx: Context, p: dict[str, Any]) -> dict[str, list[float | None]]:
    length = int(p.get("length", 9))
    signal = int(p.get("signal", 1))
    out = ta.fisher(ctx.df["high"], ctx.df["low"], length=length, signal=signal)
    if out is None or out.empty:
        return {"fisher": [], "signal": []}
    return {
        "fisher": _series(_col(out, "FISHERT_", 0)),
        "signal": _series(_col(out, "FISHERTs_", 1)),
    }


def _trix(ctx: Context, p: dict[str, Any]) -> dict[str, list[float | None]]:
    length = int(p.get("length", 30))
    signal = int(p.get("signal", 9))
    out = ta.trix(ctx.df["close"], length=length, signal=signal)
    if out is None or out.empty:
        return {"trix": [], "signal": []}
    return {
        "trix": _series(_col(out, "TRIX_", 0)),
        "signal": _series(_col(out, "TRIXs_", 1)),
    }


def _tsi(ctx: Context, p: dict[str, Any]) -> dict[str, list[float | None]]:
    fast = int(p.get("fast", 13))
    slow = int(p.get("slow", 25))
    signal = int(p.get("signal", 13))
    out = ta.tsi(ctx.df["close"], fast=fast, slow=slow, signal=signal)
    if out is None or out.empty:
        return {"tsi": [], "signal": []}
    return {
        "tsi": _series(_col(out, "TSI_", 0)),
        "signal": _series(_col(out, "TSIs_", 1)),
    }


def _squeeze(ctx: Context, p: dict[str, Any]) -> dict[str, list[float | None]]:
    bb_length = int(p.get("bbLength", p.get("bb_length", 20)))
    kc_length = int(p.get("kcLength", p.get("kc_length", 20)))
    bb_std = float(p.get("bbStd", p.get("bb_std", 2.0)))
    kc_scalar = float(p.get("kcScalar", p.get("kc_scalar", 1.5)))
    out = ta.squeeze(
        ctx.df["high"], ctx.df["low"], ctx.df["close"],
        bb_length=bb_length, bb_std=bb_std, kc_length=kc_length, kc_scalar=kc_scalar,
    )
    if out is None or out.empty:
        return {"value": [], "on": [], "off": [], "no": []}
    return {
        "value": _series(_col(out, "SQZ_2", 0)),
        "on": _series(out["SQZ_ON"]) if "SQZ_ON" in out.columns else [],
        "off": _series(out["SQZ_OFF"]) if "SQZ_OFF" in out.columns else [],
        "no": _series(out["SQZ_NO"]) if "SQZ_NO" in out.columns else [],
    }


# -----------------------------------------------------------------------------
# Additional SMC primitives — sparse event lists keyed by bar.
# -----------------------------------------------------------------------------


def _smc_events_from_col(out: pd.DataFrame, df: pd.DataFrame, label_col: str) -> list[dict[str, Any]]:
    """Project a smartmoneyconcepts DataFrame into a sparse event list.

    Rows where `label_col` is NaN are skipped. Each kept row contributes one
    event with all non-null fields from `out`, plus the bar `time` and `idx`.
    """
    mask = out[label_col].notna() if label_col in out.columns else pd.Series([True] * len(out))
    rows = out[mask]
    events: list[dict[str, Any]] = []
    for idx, row in rows.iterrows():
        i = int(idx) if isinstance(idx, (int, np.integer)) else df.index.get_loc(idx)
        ev: dict[str, Any] = {"idx": i, "time": int(df.iloc[i]["time"])}
        for c in out.columns:
            v = row[c]
            if pd.isna(v):
                continue
            ev[c] = float(v) if isinstance(v, (int, float, np.floating, np.integer)) else v
        events.append(ev)
    return events


def _smc_df(ctx: Context) -> pd.DataFrame:
    """smartmoneyconcepts expects a 'volume' column and a DatetimeIndex."""
    df = ctx.df.copy()
    if "volume" not in df.columns:
        df["volume"] = df["tick_volume"] if "tick_volume" in df.columns else 0
    if "datetime" in df.columns:
        df = df.set_index("datetime", drop=False)
    return df


def _liquidity(ctx: Context, p: dict[str, Any]) -> list[dict[str, Any]]:
    swing_length = int(p.get("swingLength", p.get("swing_length", 10)))
    range_pct = float(p.get("rangePercent", p.get("range_percent", 0.01)))
    df = _smc_df(ctx)
    sh = smc_lib.swing_highs_lows(df, swing_length=swing_length)
    out = smc_lib.liquidity(df, sh, range_percent=range_pct)
    return _smc_events_from_col(out, ctx.df, "Liquidity")


def _previous_high_low(ctx: Context, p: dict[str, Any]) -> list[dict[str, Any]]:
    time_frame = str(p.get("timeFrame", p.get("time_frame", "1D")))
    df = _smc_df(ctx)
    out = smc_lib.previous_high_low(df, time_frame=time_frame)
    return _smc_events_from_col(out, ctx.df, "PreviousHigh")


def _sessions(ctx: Context, p: dict[str, Any]) -> list[dict[str, Any]]:
    session = str(p.get("session", "London"))
    start_time = p.get("startTime", p.get("start_time"))
    end_time = p.get("endTime", p.get("end_time"))
    kwargs: dict[str, Any] = {"session": session}
    if start_time is not None:
        kwargs["start_time"] = start_time
    if end_time is not None:
        kwargs["end_time"] = end_time
    out = smc_lib.sessions(_smc_df(ctx), **kwargs)
    return _smc_events_from_col(out, ctx.df, "Active")


def _retracements(ctx: Context, p: dict[str, Any]) -> list[dict[str, Any]]:
    swing_length = int(p.get("swingLength", p.get("swing_length", 10)))
    df = _smc_df(ctx)
    sh = smc_lib.swing_highs_lows(df, swing_length=swing_length)
    out = smc_lib.retracements(df, sh)
    return _smc_events_from_col(out, ctx.df, "Direction")


# -----------------------------------------------------------------------------
# SMC objects + summaries — read from cached analysis().
# -----------------------------------------------------------------------------


def _order_blocks(ctx: Context, _p: dict[str, Any]) -> list[dict[str, Any]]:
    return ctx.analysis().get("order_blocks", [])


def _fvgs(ctx: Context, _p: dict[str, Any]) -> list[dict[str, Any]]:
    return ctx.analysis().get("fvgs", [])


def _bos_choch(ctx: Context, _p: dict[str, Any]) -> list[dict[str, Any]]:
    return ctx.analysis().get("bos_choch", [])


def _swing_levels(ctx: Context, _p: dict[str, Any]) -> list[dict[str, Any]]:
    return ctx.analysis().get("swing_levels", [])


def _sr_levels(ctx: Context, _p: dict[str, Any]) -> list[dict[str, Any]]:
    return ctx.analysis().get("sr_levels", [])


def _recent_range(ctx: Context, _p: dict[str, Any]) -> dict[str, Any]:
    return ctx.analysis().get("recent_range", {})


def _position(ctx: Context, _p: dict[str, Any]) -> dict[str, Any]:
    return ctx.analysis().get("position", {})


def _slope(ctx: Context, _p: dict[str, Any]) -> dict[str, Any]:
    return ctx.analysis().get("slope", {})


def _levels(ctx: Context, _p: dict[str, Any]) -> dict[str, Any]:
    return ctx.analysis().get("levels", {})


def _momentum(ctx: Context, _p: dict[str, Any]) -> dict[str, Any]:
    return ctx.analysis().get("momentum", {})


def _volume(ctx: Context, _p: dict[str, Any]) -> dict[str, Any]:
    return ctx.analysis().get("volume", {})


def _price(ctx: Context, _p: dict[str, Any]) -> dict[str, Any]:
    return ctx.analysis().get("price", {})


# -----------------------------------------------------------------------------
# Registry
# -----------------------------------------------------------------------------

INDICATORS: dict[str, Callable[[Context, dict[str, Any]], Any]] = {
    # Series
    "rsi": _rsi,
    "ema": _ema,
    "sma": _sma,
    "atr": _atr,
    "mfi": _mfi,
    "vwap": _vwap,
    "macd": _macd,
    "stoch": _stoch,
    "adx": _adx,
    "bbands": _bbands,
    "donchian": _donchian,
    "willr": _willr,
    "cci": _cci,
    "roc": _roc,
    "mom": _mom,
    "natr": _natr,
    "uo": _uo,
    "obv": _obv,
    "ad": _ad,
    "cmf": _cmf,
    "adosc": _adosc,
    "vwma": _vwma,
    # Alt moving averages
    "hma": _hma,
    "wma": _wma,
    "dema": _dema,
    "tema": _tema,
    "t3": _t3,
    "kama": _kama,
    "alma": _alma,
    "linreg": _linreg,
    "jma": _jma,
    "zlma": _zlma,
    "rma": _rma,
    "fwma": _fwma,
    "swma": _swma,
    "sinwma": _sinwma,
    "trima": _trima,
    # Multi-output trend / volatility
    "supertrend": _supertrend,
    "psar": _psar,
    "ichimoku": _ichimoku,
    "aroon": _aroon,
    "kc": _kc,
    "vortex": _vortex,
    "stochrsi": _stochrsi,
    "kvo": _kvo,
    "chandelierExit": _chandelier_exit,
    "fisher": _fisher,
    "trix": _trix,
    "tsi": _tsi,
    "squeeze": _squeeze,
    # SMC objects
    "orderBlocks": _order_blocks,
    "fvg": _fvgs,
    "fvgs": _fvgs,
    "bosChoch": _bos_choch,
    "swingLevels": _swing_levels,
    "srLevels": _sr_levels,
    "recentRange": _recent_range,
    "liquidity": _liquidity,
    "previousHighLow": _previous_high_low,
    "sessions": _sessions,
    "retracements": _retracements,
    # Analysis summaries
    "price": _price,
    "levels": _levels,
    "momentum": _momentum,
    "volume": _volume,
    "position": _position,
    "slope": _slope,
}


# Signal-like outputs get isRecent tagging + sha256 ids. Wickworks emits
# primitives only — no signals — so this is empty by design. Kept as a
# typed empty mapping so callers can iterate without a None check.
RECENT_TAGGABLE: dict[str, str] = {}
