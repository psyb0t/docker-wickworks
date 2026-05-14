"""Tests for wickworks.common utilities."""

from __future__ import annotations

import math

import pytest

from wickworks.common import parse_duration, safe_float


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, 0),
        ("", 0),
        (0, 0),
        (3600, 3600),
        (3600.5, 3600),
        ("3600", 3600),
        ("-3600", -3600),
        ("5s", 5),
        ("30m", 1800),
        ("6h", 21600),
        ("6h32m11s", 6 * 3600 + 32 * 60 + 11),
        ("-5h", -5 * 3600),
        ("-1h30m", -(3600 + 1800)),
        ("+2h", 7200),
        ("1H30M", 5400),
    ],
)
def test_parse_duration_valid(value, expected: int) -> None:
    assert parse_duration(value) == expected


@pytest.mark.parametrize("bad", ["banana", "5x", "5h30", "h", "5 30m", "5h-30m"])
def test_parse_duration_invalid(bad: str) -> None:
    with pytest.raises(ValueError):
        parse_duration(bad)


# ---------------------------------------------------------------------------
# safe_float — keep NaN/±Inf out of JSON, with optional decimal-preserving
# mode for ultra-low-magnitude values like crypto prices.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad",
    [
        float("nan"),
        float("inf"),
        float("-inf"),
        math.nan,
        "not a number",
        None,
        object(),
    ],
    ids=["nan", "+inf", "-inf", "math_nan", "string", "none", "object"],
)
def test_safe_float_returns_none_for_invalid(bad) -> None:
    """The whole reason safe_float exists: keep NaN/±Inf/unconvertible out
    of the JSON payload — FastAPI refuses to encode them and the request
    crashes with HTTPException 500."""
    assert safe_float(bad) is None


@pytest.mark.parametrize(
    "value,expected",
    [
        (1.123456789, 1.123457),
        (1.0, 1.0),
        (0, 0.0),
        # Default decimals=6 floors values below 5e-7 to 0 — this is fine
        # for indicators (RSI/MACD never get that small) but is exactly
        # why the price path opts out via decimals=None.
        (1e-8, 0.0),
    ],
    ids=["truncates_tail", "passthrough_1", "zero", "rounds_subepsilon_to_zero"],
)
def test_safe_float_default_rounds_to_six_decimals(value, expected: float) -> None:
    assert safe_float(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        1e-8,     # PEPE / SHIB territory
        1e-12,    # micro-cap altcoins
        1e-15,    # absurd-but-real new launches
        0.5,      # normal range still works
        12345.6789012345,  # tail digits preserved
    ],
    ids=["1e-8", "1e-12", "1e-15", "half", "long_tail"],
)
def test_safe_float_with_decimals_none_preserves_value(value: float) -> None:
    """decimals=None bypasses the rounding step so crypto prices below
    the default 1e-6 cutoff survive intact. Required for the price path
    in analyze() — rounding would clamp the guard's `price > 0` to false."""
    assert safe_float(value, decimals=None) == value
