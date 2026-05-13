"""Summary projections — momentum, volume, position, slope, levels, recentRange, price.

Per-field math/golden coverage lives in test_smc_analyze.py. This file verifies
the projections survive end-to-end against the real EURUSD fixture (no NaN
explosions, dict shape, scalar price).
"""

from __future__ import annotations

from typing import Any

import pytest

from _helpers import post  # type: ignore[import-not-found]


_SUMMARY_INDICATORS = [
    "momentum",
    "volume",
    "position",
    "slope",
    "levels",
    "recentRange",
]


@pytest.fixture(scope="module")
def summary_response(eurusd_h1_fixture: dict[str, Any]) -> dict[str, Any]:
    return post(
        eurusd_h1_fixture["bars"],
        {ind: True for ind in _SUMMARY_INDICATORS + ["price"]},
    )


@pytest.mark.parametrize("indicator", _SUMMARY_INDICATORS)
def test_summary_is_non_empty_dict(
    summary_response: dict[str, Any], indicator: str
) -> None:
    val = summary_response[indicator]
    assert isinstance(val, dict)
    assert val, f"{indicator} returned empty dict on real data"


def test_price_is_scalar_float(summary_response: dict[str, Any]) -> None:
    assert isinstance(summary_response["price"], float)
