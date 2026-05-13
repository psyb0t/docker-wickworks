"""Indicator isolation — requesting two indicators together yields the same
values as requesting them separately.

Catches state leak across the registry (e.g. a shared mutable Context, or
one indicator mutating ctx.df in place).
"""

from __future__ import annotations

from typing import Any

import pytest

from _helpers import post  # type: ignore[import-not-found]


def _approx_equal_series(
    a: list[float | None], b: list[float | None], rtol: float = 1e-9
) -> bool:
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        if x is None and y is None:
            continue
        if x is None or y is None:
            return False
        if abs(x - y) > 1e-9 + rtol * max(abs(x), abs(y)):
            return False
    return True


@pytest.mark.parametrize(
    "ind_a,ind_b",
    [
        ("rsi", "atr"),
        ("ema21", "sma20"),
        ("macd", "bbands"),
        ("adx", "stoch"),
        ("obv", "vwap"),
    ],
)
def test_pairwise_indicator_isolation(
    eurusd_h1_fixture: dict[str, Any], ind_a: str, ind_b: str
) -> None:
    bars = eurusd_h1_fixture["bars"]
    spec: dict[str, Any] = {
        "rsi": True,
        "atr": True,
        "ema21": {"type": "ema", "length": 21},
        "sma20": {"type": "sma", "length": 20},
        "macd": True,
        "bbands": True,
        "adx": True,
        "stoch": True,
        "obv": True,
        "vwap": True,
    }

    solo_a = post(bars, {ind_a: spec[ind_a]})[ind_a]
    solo_b = post(bars, {ind_b: spec[ind_b]})[ind_b]
    combined = post(bars, {ind_a: spec[ind_a], ind_b: spec[ind_b]})

    def assert_equal(solo: Any, combined_val: Any, name: str) -> None:
        if isinstance(solo, list):
            assert _approx_equal_series(solo, combined_val), f"{name}: solo != combined"
            return
        if isinstance(solo, dict):
            assert solo.keys() == combined_val.keys()
            for k in solo:
                assert _approx_equal_series(solo[k], combined_val[k]), (
                    f"{name}.{k}: solo != combined"
                )
            return
        assert solo == combined_val

    assert_equal(solo_a, combined[ind_a], ind_a)
    assert_equal(solo_b, combined[ind_b], ind_b)
