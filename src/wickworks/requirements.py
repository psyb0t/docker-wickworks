"""Per-indicator minimum-bar requirements.

The compute pipeline runs each requested indicator with whatever bars the
caller sent. If a caller asks for SMA(200) with 100 bars, we'd hand back a
fully-null series — useless and confusing. This module pre-flights every
requested indicator before any work happens, so the response is either a
correct result or a structured 400 listing exactly which output keys are
under-fed.

Each entry maps an indicator `type` to a callable that takes the per-call
params dict and returns the minimum number of bars needed to emit at least
one non-null value at the tail. Indicators backed by the SMC analysis
pipeline share a floor of `MIN_BARS` (default 50) because the analysis
itself assumes a meaningful history.

Indicators not listed here fall back to `MIN_BARS` (safe-by-default) so
adding a new indicator without updating this table never produces an
all-null series — it produces a clean error until the requirement is
declared.
"""

from __future__ import annotations

from typing import Any, Callable

from .config import MIN_BARS


def _len(default: int) -> Callable[[dict[str, Any]], int]:
    return lambda p: int(p.get("length", default))


def _len_plus_one(default: int) -> Callable[[dict[str, Any]], int]:
    return lambda p: int(p.get("length", default)) + 1


def _macd(p: dict[str, Any]) -> int:
    return int(p.get("slow", 26)) + int(p.get("signal", 9))


def _stoch(p: dict[str, Any]) -> int:
    k = int(p.get("k", 14))
    d = int(p.get("d", 3))
    smooth_k = int(p.get("smoothK", p.get("smooth_k", p.get("smooth", 3))))
    return k + d + smooth_k


def _adx(p: dict[str, Any]) -> int:
    return int(p.get("length", 14)) * 2


def _ichimoku(p: dict[str, Any]) -> int:
    return int(p.get("senkou", 52))


def _stochrsi(p: dict[str, Any]) -> int:
    rsi_length = int(p.get("rsiLength", p.get("rsi_length", 14)))
    length = int(p.get("length", 14))
    k = int(p.get("k", 3))
    d = int(p.get("d", 3))
    return rsi_length + length + k + d


def _kvo(p: dict[str, Any]) -> int:
    return int(p.get("slow", 55)) + int(p.get("signal", 13))


def _trix(p: dict[str, Any]) -> int:
    return 3 * int(p.get("length", 30)) + int(p.get("signal", 9))


def _tsi(p: dict[str, Any]) -> int:
    return int(p.get("slow", 25)) + int(p.get("signal", 13))


def _squeeze(p: dict[str, Any]) -> int:
    bb = int(p.get("bbLength", p.get("bb_length", 20)))
    kc = int(p.get("kcLength", p.get("kc_length", 20)))
    return max(bb, kc)


def _chandelier(p: dict[str, Any]) -> int:
    length = int(p.get("length", 22))
    atr_length = int(p.get("atrLength", p.get("atr_length", 22)))
    return max(length, atr_length) + 1


def _fisher(p: dict[str, Any]) -> int:
    return int(p.get("length", 9)) + 1


def _uo(p: dict[str, Any]) -> int:
    return int(p.get("slow", 28)) + 1


def _adosc(p: dict[str, Any]) -> int:
    return int(p.get("slow", 10))


def _smc(_p: dict[str, Any]) -> int:
    """SMC / analysis-backed outputs need the full analysis floor."""
    return MIN_BARS


def _trivial(_p: dict[str, Any]) -> int:
    return 1


REQUIREMENTS: dict[str, Callable[[dict[str, Any]], int]] = {
    # Series oscillators / MAs.
    "rsi": _len_plus_one(14),
    "ema": _len(21),
    "sma": _len(50),
    "atr": _len_plus_one(14),
    "mfi": _len_plus_one(14),
    "vwap": _trivial,
    "macd": _macd,
    "stoch": _stoch,
    "adx": _adx,
    "bbands": _len(20),
    "donchian": _len(20),
    "willr": _len(14),
    "cci": _len(14),
    "roc": _len_plus_one(10),
    "mom": _len_plus_one(10),
    "natr": _len_plus_one(14),
    "uo": _uo,
    "obv": _trivial,
    "ad": _trivial,
    "cmf": _len(20),
    "adosc": _adosc,
    "vwma": _len(10),
    # Alt moving averages.
    "hma": _len(14),
    "wma": _len(14),
    "dema": _len(10),
    "tema": _len(10),
    "t3": _len(10),
    "kama": _len(10),
    "alma": _len(10),
    "linreg": _len(14),
    "jma": _len(7),
    "zlma": _len(10),
    "rma": _len(10),
    "fwma": _len(10),
    "swma": _len(10),
    "sinwma": _len(14),
    "trima": _len(10),
    # Multi-output trend / volatility.
    "supertrend": _len_plus_one(7),
    "psar": lambda _p: 2,
    "ichimoku": _ichimoku,
    "aroon": _len_plus_one(14),
    "kc": _len(20),
    "vortex": _len_plus_one(14),
    "stochrsi": _stochrsi,
    "kvo": _kvo,
    "chandelierExit": _chandelier,
    "fisher": _fisher,
    "trix": _trix,
    "tsi": _tsi,
    "squeeze": _squeeze,
    # SMC objects + analysis summaries — all read from the shared analysis(),
    # which assumes >= MIN_BARS history.
    "orderBlocks": _smc,
    "fvg": _smc,
    "fvgs": _smc,
    "bosChoch": _smc,
    "swingLevels": _smc,
    "srLevels": _smc,
    "recentRange": _smc,
    "liquidity": _smc,
    "previousHighLow": _smc,
    "sessions": _smc,
    "retracements": _smc,
    "price": _smc,
    "levels": _smc,
    "momentum": _smc,
    "volume": _smc,
    "position": _smc,
    "slope": _smc,
}


def required_bars(type_: str, params: dict[str, Any]) -> int:
    """Minimum number of bars needed for `type_` to emit a non-null tail value.

    Falls back to `MIN_BARS` for unknown types and on any computation
    error — both cases prefer over-requiring to silently producing nulls.
    """
    fn = REQUIREMENTS.get(type_)
    if fn is None:
        return MIN_BARS
    try:
        return max(1, int(fn(params)))
    except Exception:
        return MIN_BARS
