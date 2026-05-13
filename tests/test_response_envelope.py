"""HTTP response envelope — meta echo, requested-keys filter, series length.

These guard the server wrapper, not any one indicator. Per-indicator math
lives in the named test_<indicator>.py files.
"""

from __future__ import annotations

from typing import Any

import pytest

from _helpers import post  # type: ignore[import-not-found]


def test_meta_is_echoed(eurusd_h1_fixture: dict[str, Any]) -> None:
    bars = eurusd_h1_fixture["bars"]
    resp = post(bars, {"rsi": True}, symbol="EURUSD", timeframe="H1")
    assert resp["symbol"] == "EURUSD"
    assert resp["timeframe"] == "H1"
    assert resp["candles"] == eurusd_h1_fixture["count"]


@pytest.mark.parametrize("indicator", ["rsi", "atr"])
def test_series_length_matches_input(
    eurusd_h1_fixture: dict[str, Any], indicator: str
) -> None:
    series = post(eurusd_h1_fixture["bars"], {indicator: True})[indicator]
    assert isinstance(series, list)
    assert len(series) == eurusd_h1_fixture["count"]
    assert series[-1] is not None
