"""Append-only stability — for causal indicators, bar i's value must not change
when more bars are appended after it.

Catches accidental future-leaks (e.g. accidentally using bars[i+1] in i's
calculation) and recompute-on-windowed-input bugs.
"""

from __future__ import annotations

from typing import Any

import pytest

from _helpers import post  # type: ignore[import-not-found]


# Causal series indicators that should be append-stable.
_CAUSAL_SERIES = ["rsi", "atr", "ema21", "sma20", "willr", "cci", "roc", "mom"]


@pytest.mark.parametrize("indicator", _CAUSAL_SERIES)
def test_series_is_append_stable(
    eurusd_h1_fixture: dict[str, Any], indicator: str
) -> None:
    """Value at bar i computed on bars[:N] must equal value at bar i on bars[:N+k]."""
    bars = eurusd_h1_fixture["bars"]
    n = len(bars)
    cut = n - 50

    indicators: dict[str, Any] = {
        "rsi": True,
        "atr": True,
        "ema21": {"type": "ema", "length": 21},
        "sma20": {"type": "sma", "length": 20},
        "willr": True,
        "cci": True,
        "roc": True,
        "mom": True,
    }

    full = post(bars, {indicator: indicators[indicator]})[indicator]
    truncated = post(bars[:cut], {indicator: indicators[indicator]})[indicator]

    # Compare last bar of the truncated run against the corresponding bar in full.
    assert truncated[-1] is not None, f"{indicator} tail of truncated run is None"
    assert full[cut - 1] is not None, f"{indicator} bar {cut - 1} of full run is None"

    a, b = truncated[-1], full[cut - 1]
    assert abs(a - b) <= 1e-6 + 1e-5 * abs(b), (
        f"{indicator} append-leak: truncated={a} full[{cut - 1}]={b} diff={a - b}"
    )


def test_macd_line_is_append_stable(eurusd_h1_fixture: dict[str, Any]) -> None:
    """MACD line is causal — bar N-50 must match between full and truncated runs."""
    bars = eurusd_h1_fixture["bars"]
    cut = len(bars) - 50

    full = post(bars, {"macd": True})["macd"]["macd"]
    truncated = post(bars[:cut], {"macd": True})["macd"]["macd"]

    a, b = truncated[-1], full[cut - 1]
    assert a is not None and b is not None
    assert abs(a - b) <= 1e-6 + 1e-5 * abs(b)
