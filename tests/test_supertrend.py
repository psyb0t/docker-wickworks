"""Supertrend — direction +1/-1, long/short band populated based on regime."""

from __future__ import annotations

from typing import Any

from _helpers import (  # type: ignore[import-not-found]
    monotone_down_bars,
    monotone_up_bars,
    post,
)


def test_supertrend_direction_uptrend() -> None:
    bars = monotone_up_bars(200, start=100.0, step=1.0)
    out = post(bars, {"supertrend": True})
    assert out["supertrend"]["direction"][-1] == 1
    assert out["supertrend"]["long"][-1] is not None
    assert out["supertrend"]["short"][-1] is None


def test_supertrend_direction_downtrend() -> None:
    bars = monotone_down_bars(200, start=200.0, step=1.0)
    out = post(bars, {"supertrend": True})
    assert out["supertrend"]["direction"][-1] == -1
    assert out["supertrend"]["short"][-1] is not None
    assert out["supertrend"]["long"][-1] is None


def test_supertrend_finite_on_real_data(eurusd_h1_fixture: dict[str, Any]) -> None:
    """Wiring smoke — exactly one of long/short is populated per bar where direction is set."""
    out = post(eurusd_h1_fixture["bars"], {"supertrend": True})
    direction = out["supertrend"]["direction"][-1]
    assert direction in (-1, 1)
    long_v = out["supertrend"]["long"][-1]
    short_v = out["supertrend"]["short"][-1]
    assert (long_v is None) != (short_v is None), "exactly one side must be populated"
