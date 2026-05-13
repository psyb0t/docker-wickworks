"""ATR / NATR — Wilder-smoothed average true range."""

from __future__ import annotations

from typing import Any

import pytest

from _helpers import (  # type: ignore[import-not-found]
    assert_last_bar_matches,
    bars_to_df,
    flat_bars,
    post,
    ref_atr,
    ref_ema,
    ref_true_range,
)


def test_atr_flat_is_zero() -> None:
    out = post(flat_bars(200), {"atr": True})
    assert out["atr"][-1] == pytest.approx(0.0, abs=1e-9)


def test_natr_flat_is_zero() -> None:
    out = post(flat_bars(200), {"natr": True})
    assert out["natr"][-1] == pytest.approx(0.0, abs=1e-9)


@pytest.mark.parametrize("length", [7, 14, 28])
def test_atr_matches_closed_form_on_real_data(
    eurusd_h1_fixture: dict[str, Any], length: int
) -> None:
    bars = eurusd_h1_fixture["bars"]
    df = bars_to_df(bars)
    expected = ref_atr(df["high"], df["low"], df["close"], length=length)

    out = post(bars, {"atr": {"type": "atr", "length": length}})
    assert_last_bar_matches(out["atr"], expected)


def test_natr_equals_ema_atr_over_close_pct(
    eurusd_h1_fixture: dict[str, Any],
) -> None:
    """NATR = 100 * EMA-smoothed ATR / close.

    pandas_ta natr explicitly passes mamode="ema" (NOT Wilder/rma), so the inner
    ATR here is EMA-smoothed true range — different from the default atr().
    """
    bars = eurusd_h1_fixture["bars"]
    df = bars_to_df(bars)
    tr = ref_true_range(df["high"], df["low"], df["close"])
    ema_atr = ref_ema(tr, length=14)
    expected_natr = 100 * ema_atr / df["close"]

    out = post(bars, {"natr": True})
    assert_last_bar_matches(out["natr"], expected_natr, rtol=1e-4)
