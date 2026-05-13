"""Keltner Channels — EMA centerline with ATR-derived rails."""

from __future__ import annotations

from typing import Any

import pytest

from _helpers import (  # type: ignore[import-not-found]
    monotone_up_bars,
    post,
)


def test_kc_symmetric_around_middle() -> None:
    bars = monotone_up_bars(200, start=100.0, step=0.5)
    out = post(bars, {"kc": True})
    upper = out["kc"]["upper"][-1]
    middle = out["kc"]["middle"][-1]
    lower = out["kc"]["lower"][-1]
    assert upper - middle == pytest.approx(middle - lower, rel=1e-6, abs=1e-6)
    assert upper > middle > lower


def test_kc_finite_on_real_data(eurusd_h1_fixture: dict[str, Any]) -> None:
    """Wiring smoke — all three rails populated, ordered, on real FX data."""
    out = post(eurusd_h1_fixture["bars"], {"kc": True})
    upper = out["kc"]["upper"][-1]
    middle = out["kc"]["middle"][-1]
    lower = out["kc"]["lower"][-1]
    assert upper is not None and middle is not None and lower is not None
    assert upper > middle > lower
