"""Vortex Indicator — +VI dominates on uptrend, -VI on downtrend."""

from __future__ import annotations

from typing import Any

from _helpers import (  # type: ignore[import-not-found]
    monotone_down_bars,
    monotone_up_bars,
    post,
)


def test_vortex_plus_dominant_on_uptrend() -> None:
    out = post(monotone_up_bars(200), {"vortex": True})
    assert out["vortex"]["plus"][-1] > out["vortex"]["minus"][-1]


def test_vortex_minus_dominant_on_downtrend() -> None:
    out = post(monotone_down_bars(200), {"vortex": True})
    assert out["vortex"]["minus"][-1] > out["vortex"]["plus"][-1]


def test_vortex_finite_on_real_data(eurusd_h1_fixture: dict[str, Any]) -> None:
    out = post(eurusd_h1_fixture["bars"], {"vortex": True})
    assert out["vortex"]["plus"][-1] is not None
    assert out["vortex"]["minus"][-1] is not None
