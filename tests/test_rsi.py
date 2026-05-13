"""RSI — Wilder-smoothed momentum oscillator."""

from __future__ import annotations

from typing import Any

import pytest

from _helpers import (  # type: ignore[import-not-found]
    assert_last_bar_matches,
    bars_to_df,
    flat_bars,
    monotone_down_bars,
    monotone_up_bars,
    post,
    ref_rsi,
)


@pytest.mark.parametrize(
    "bars_fn,expected_tail",
    [(monotone_up_bars, 100.0), (monotone_down_bars, 0.0)],
)
def test_rsi_extremes(bars_fn, expected_tail: float) -> None:
    out = post(bars_fn(200), {"rsi": True})
    assert out["rsi"][-1] == pytest.approx(expected_tail, abs=1e-6)


def test_rsi_flat_is_neutral_or_nan() -> None:
    """Flat bars: gain==loss==0 → undefined; either None or ~50 is OK."""
    out = post(flat_bars(200), {"rsi": True})
    tail = out["rsi"][-1]
    assert tail is None or tail == pytest.approx(50.0, abs=1.0)


def test_rsi_bounded_0_100_on_real_data(eurusd_h1_fixture: dict[str, Any]) -> None:
    out = post(eurusd_h1_fixture["bars"], {"rsi": True})
    values = [v for v in out["rsi"] if v is not None]
    assert all(0.0 <= v <= 100.0 for v in values)


@pytest.mark.parametrize("length", [7, 14, 21])
def test_rsi_matches_closed_form_on_real_data(
    eurusd_h1_fixture: dict[str, Any], length: int
) -> None:
    """Closed-form Wilder RSI vs wickworks last bar — exact within float tol."""
    bars = eurusd_h1_fixture["bars"]
    df = bars_to_df(bars)
    expected = ref_rsi(df["close"], length=length)

    out = post(bars, {"rsi": {"type": "rsi", "length": length}})
    assert_last_bar_matches(out["rsi"], expected)
