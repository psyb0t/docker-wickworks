"""Validation for the dynamic indicator specification map."""

from __future__ import annotations

import math
import re
from typing import Any

from .common import parse_duration
from .constants import PREVIOUS_PERIOD_FREQUENCIES, SUPPORTED_SESSIONS
from .errors import InvalidIndicatorSpecError

_LENGTH_ONLY = {
    "rsi",
    "ema",
    "sma",
    "atr",
    "mfi",
    "adx",
    "donchian",
    "willr",
    "roc",
    "mom",
    "natr",
    "cmf",
    "vwma",
    "hma",
    "wma",
    "dema",
    "tema",
    "t3",
    "kama",
    "alma",
    "linreg",
    "jma",
    "zlma",
    "rma",
    "fwma",
    "swma",
    "sinwma",
    "trima",
    "aroon",
    "vortex",
}

_PARAMS_BY_INDICATOR: dict[str, set[str]] = {
    **{name: {"length"} for name in _LENGTH_ONLY},
    "bbands": {"length", "std"},
    "cci": {"length", "c"},
    "kc": {"length", "scalar"},
    "vwap": {"anchor", "sessionOffset", "session_offset"},
    "macd": {"fast", "slow", "signal"},
    "stoch": {"k", "d", "smoothK", "smooth_k", "smooth"},
    "uo": {"fast", "medium", "slow"},
    "obv": set(),
    "ad": set(),
    "adosc": {"fast", "slow"},
    "supertrend": {"length", "multiplier"},
    "psar": {"af", "step", "max", "maxAf"},
    "ichimoku": {"tenkan", "kijun", "senkou"},
    "stochrsi": {"length", "rsiLength", "rsi_length", "k", "d"},
    "kvo": {"fast", "slow", "signal"},
    "chandelierExit": {"length", "atrLength", "atr_length", "multiplier"},
    "fisher": {"length", "signal"},
    "trix": {"length", "signal"},
    "tsi": {"fast", "slow", "signal"},
    "squeeze": {
        "bbLength",
        "bb_length",
        "kcLength",
        "kc_length",
        "bbStd",
        "bb_std",
        "kcScalar",
        "kc_scalar",
    },
    "orderBlocks": set(),
    "fvg": set(),
    "fvgs": set(),
    "bosChoch": set(),
    "swingLevels": set(),
    "srLevels": set(),
    "recentRange": set(),
    "liquidity": {"swingLength", "swing_length", "rangePercent", "range_percent"},
    "previousHighLow": {"timeFrame", "time_frame"},
    "sessions": {"session", "startTime", "start_time", "endTime", "end_time"},
    "retracements": {"swingLength", "swing_length"},
    "price": set(),
    "levels": set(),
    "momentum": set(),
    "volume": set(),
    "position": set(),
    "slope": set(),
}

_POSITIVE_INTEGER_PARAMS = {
    "length",
    "fast",
    "medium",
    "slow",
    "signal",
    "k",
    "d",
    "smoothK",
    "smooth_k",
    "smooth",
    "tenkan",
    "kijun",
    "senkou",
    "rsiLength",
    "rsi_length",
    "atrLength",
    "atr_length",
    "bbLength",
    "bb_length",
    "kcLength",
    "kc_length",
    "swingLength",
    "swing_length",
}

_POSITIVE_NUMBER_PARAMS = {
    "c",
    "std",
    "multiplier",
    "scalar",
    "af",
    "step",
    "max",
    "maxAf",
    "bbStd",
    "bb_std",
    "kcScalar",
    "kc_scalar",
    "rangePercent",
    "range_percent",
}

_NON_EMPTY_STRING_PARAMS = {
    "anchor",
    "timeFrame",
    "time_frame",
    "session",
    "startTime",
    "start_time",
    "endTime",
    "end_time",
}

_SESSION_TIME_PATTERN = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


def _invalid(output_key: str, message: str) -> InvalidIndicatorSpecError:
    return InvalidIndicatorSpecError(f"indicator {output_key!r}: {message}")


def _positive_integer(output_key: str, name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise _invalid(output_key, f"{name} must be a positive integer")
    return value


def _positive_number(output_key: str, name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _invalid(output_key, f"{name} must be a positive finite number")
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise _invalid(output_key, f"{name} must be a positive finite number")
    return number


def validate_indicator_params(
    output_key: str,
    indicator_type: str,
    params: dict[str, Any],
) -> None:
    """Reject ignored, malformed, and internally inconsistent parameters."""
    allowed = _PARAMS_BY_INDICATOR[indicator_type]
    unknown = sorted(set(params) - allowed)
    if unknown:
        raise _invalid(output_key, f"unknown parameters: {', '.join(unknown)}")

    for name, value in params.items():
        if name in _POSITIVE_INTEGER_PARAMS:
            _positive_integer(output_key, name, value)
        elif name in _POSITIVE_NUMBER_PARAMS:
            _positive_number(output_key, name, value)
        elif name in _NON_EMPTY_STRING_PARAMS:
            if not isinstance(value, str) or not value.strip():
                raise _invalid(output_key, f"{name} must be a non-empty string")
        elif name in {"sessionOffset", "session_offset"}:
            try:
                parse_duration(value)
            except (TypeError, ValueError) as error:
                raise _invalid(output_key, f"{name} is not a valid duration") from error

    if indicator_type in {"macd", "adosc", "kvo", "tsi"}:
        fast_defaults = {"macd": 12, "adosc": 3, "kvo": 34, "tsi": 13}
        slow_defaults = {"macd": 26, "adosc": 10, "kvo": 55, "tsi": 25}
        fast = int(params.get("fast", fast_defaults[indicator_type]))
        slow = int(params.get("slow", slow_defaults[indicator_type]))
        if fast >= slow:
            raise _invalid(output_key, "fast must be less than slow")

    if indicator_type == "uo":
        fast = int(params.get("fast", 7))
        medium = int(params.get("medium", 14))
        slow = int(params.get("slow", 28))
        if not fast < medium < slow:
            raise _invalid(output_key, "fast, medium, and slow must increase")

    if indicator_type == "ichimoku":
        tenkan = int(params.get("tenkan", 9))
        kijun = int(params.get("kijun", 26))
        senkou = int(params.get("senkou", 52))
        if not tenkan < kijun < senkou:
            raise _invalid(output_key, "tenkan, kijun, and senkou must increase")

    if indicator_type == "psar":
        step = float(params.get("af", params.get("step", 0.02)))
        maximum = float(params.get("max", params.get("maxAf", 0.2)))
        if step > maximum:
            raise _invalid(output_key, "step must not exceed max")

    if indicator_type == "liquidity":
        range_percent = float(params.get("rangePercent", params.get("range_percent", 0.01)))
        if range_percent > 1:
            raise _invalid(output_key, "rangePercent must not exceed 1")

    if indicator_type == "previousHighLow":
        time_frame = str(params.get("timeFrame", params.get("time_frame", "1D")))
        if time_frame not in PREVIOUS_PERIOD_FREQUENCIES:
            supported = ", ".join(PREVIOUS_PERIOD_FREQUENCIES)
            raise _invalid(output_key, f"timeFrame must be one of: {supported}")

    if indicator_type == "sessions":
        session = str(params.get("session", "London"))
        if session not in SUPPORTED_SESSIONS:
            supported = ", ".join(sorted(SUPPORTED_SESSIONS))
            raise _invalid(output_key, f"session must be one of: {supported}")

        start_time = params.get("startTime", params.get("start_time"))
        end_time = params.get("endTime", params.get("end_time"))
        for name, value in (("startTime", start_time), ("endTime", end_time)):
            if value is not None and not _SESSION_TIME_PATTERN.fullmatch(str(value)):
                raise _invalid(output_key, f"{name} must use UTC HH:MM")

        if session == "Custom" and (start_time is None or end_time is None):
            raise _invalid(output_key, "Custom session requires startTime and endTime")
        if session != "Custom" and (start_time is not None or end_time is not None):
            raise _invalid(output_key, "startTime and endTime are only valid for Custom session")
