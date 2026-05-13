"""Ichimoku Kinko Hyo — tenkan/kijun/spanA/spanB/chikou."""

from __future__ import annotations

from typing import Any

from _helpers import (  # type: ignore[import-not-found]
    monotone_up_bars,
    post,
)


def test_ichimoku_ordering_uptrend() -> None:
    """Strong uptrend → tenkan > kijun > spanB (cloud below price)."""
    bars = monotone_up_bars(300, start=100.0, step=1.0)
    out = post(bars, {"ichimoku": True})
    tenkan = out["ichimoku"]["tenkan"][-1]
    kijun = out["ichimoku"]["kijun"][-1]
    span_b = out["ichimoku"]["spanB"][-1]
    assert tenkan > kijun > span_b


def test_ichimoku_subkeys_populated_on_real_data(
    eurusd_h1_fixture: dict[str, Any],
) -> None:
    out = post(eurusd_h1_fixture["bars"], {"ichimoku": True})
    # tenkan/kijun/spanA/spanB always present on a long enough series.
    for key in ("tenkan", "kijun", "spanA", "spanB"):
        assert out["ichimoku"][key][-1] is not None, f"{key} tail is None"
