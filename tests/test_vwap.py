"""VWAP — typical-price weighted by volume, anchored daily by pandas_ta default."""

from __future__ import annotations

from typing import Any

import pytest

from _helpers import (  # type: ignore[import-not-found]
    flat_bars,
    post,
)


def test_vwap_flat_equals_price() -> None:
    out = post(flat_bars(200, price=123.45), {"vwap": True})
    tail = [v for v in out["vwap"][-20:] if v is not None]
    assert tail, "VWAP tail is all None"
    for v in tail:
        assert v == pytest.approx(123.45, abs=1e-6)


def test_vwap_finite_on_real_data(eurusd_h1_fixture: dict[str, Any]) -> None:
    """Smoke check — non-None tail, within plausible FX price band."""
    out = post(eurusd_h1_fixture["bars"], {"vwap": True})
    tail = out["vwap"][-1]
    assert tail is not None
    assert 0.5 < tail < 2.0, f"VWAP {tail} outside plausible EURUSD range"
