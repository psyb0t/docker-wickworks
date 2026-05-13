"""Bollinger Bands — SMA centerline + N*stdev rails."""

from __future__ import annotations

from typing import Any

import pytest

from _helpers import (  # type: ignore[import-not-found]
    assert_last_bar_matches,
    bars_to_df,
    flat_bars,
    monotone_up_bars,
    post,
    ref_bbands,
    ref_sma,
)


def test_bbands_middle_equals_sma() -> None:
    bars = monotone_up_bars(200, start=100.0, step=0.7)
    out = post(bars, {"bbands": True, "sma20": {"type": "sma", "length": 20}})
    assert out["bbands"]["middle"][-1] == pytest.approx(
        out["sma20"][-1], rel=1e-9, abs=1e-9
    )


def test_bbands_symmetric_around_middle() -> None:
    bars = monotone_up_bars(200, start=100.0, step=0.7)
    out = post(bars, {"bbands": True})
    upper = out["bbands"]["upper"][-1]
    middle = out["bbands"]["middle"][-1]
    lower = out["bbands"]["lower"][-1]
    assert upper - middle == pytest.approx(middle - lower, rel=1e-6, abs=1e-6)
    assert upper > middle > lower


def test_bbands_flat_collapses_to_price() -> None:
    out = post(flat_bars(200, price=50.0), {"bbands": True})
    for key in ("upper", "middle", "lower"):
        assert out["bbands"][key][-1] == pytest.approx(50.0, abs=1e-6)


@pytest.mark.parametrize("length", [10, 20, 50])
def test_bbands_matches_closed_form_on_real_data(
    eurusd_h1_fixture: dict[str, Any], length: int
) -> None:
    """pandas_ta bbands uses ddof=1 (sample stddev) — exact match expected."""
    bars = eurusd_h1_fixture["bars"]
    df = bars_to_df(bars)
    expected = ref_bbands(df["close"], length=length, std=2.0)
    out = post(bars, {"bbands": {"type": "bbands", "length": length, "std": 2.0}})
    assert_last_bar_matches(out["bbands"]["middle"], expected["middle"])
    assert_last_bar_matches(out["bbands"]["upper"], expected["upper"])
    assert_last_bar_matches(out["bbands"]["lower"], expected["lower"])


def test_bbands_middle_equals_rolling_sma_on_real_data(
    eurusd_h1_fixture: dict[str, Any],
) -> None:
    bars = eurusd_h1_fixture["bars"]
    df = bars_to_df(bars)
    expected = ref_sma(df["close"], length=20)
    out = post(bars, {"bbands": True})
    assert_last_bar_matches(out["bbands"]["middle"], expected)
