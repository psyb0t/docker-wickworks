"""MACD = EMA(close, fast) - EMA(close, slow); signal = EMA(macd, 9)."""

from __future__ import annotations

from typing import Any

import pytest

from _helpers import (  # type: ignore[import-not-found]
    assert_last_bar_matches,
    bars_to_df,
    monotone_up_bars,
    post,
    ref_ema,
    ref_macd,
)


def test_macd_components_consistent() -> None:
    """Verify column wiring: macd_line == fast_ema - slow_ema; hist == macd - signal."""
    bars = monotone_up_bars(300, start=100.0, step=0.5)
    out = post(
        bars,
        {
            "macd": True,
            "emaFast": {"type": "ema", "length": 12},
            "emaSlow": {"type": "ema", "length": 26},
        },
    )
    macd_line = out["macd"]["macd"][-1]
    signal = out["macd"]["signal"][-1]
    hist = out["macd"]["hist"][-1]
    expected_macd = out["emaFast"][-1] - out["emaSlow"][-1]
    assert macd_line == pytest.approx(expected_macd, rel=1e-6, abs=1e-6)
    assert hist == pytest.approx(macd_line - signal, rel=1e-6, abs=1e-6)


def test_macd_line_matches_ema_diff_on_real_data(
    eurusd_h1_fixture: dict[str, Any],
) -> None:
    bars = eurusd_h1_fixture["bars"]
    df = bars_to_df(bars)
    expected = ref_ema(df["close"], 12) - ref_ema(df["close"], 26)
    out = post(bars, {"macd": True})
    assert_last_bar_matches(out["macd"]["macd"], expected)


def test_macd_full_matches_closed_form_on_real_data(
    eurusd_h1_fixture: dict[str, Any],
) -> None:
    bars = eurusd_h1_fixture["bars"]
    df = bars_to_df(bars)
    expected = ref_macd(df["close"], fast=12, slow=26, signal=9)
    out = post(bars, {"macd": True})

    # Higher tolerance on signal/hist — signal is EMA-of-EMA, accumulated
    # float drift from a 26-bar warmup gap into a 9-bar EMA.
    assert_last_bar_matches(out["macd"]["macd"], expected["macd"], rtol=1e-5)
    assert_last_bar_matches(
        out["macd"]["signal"], expected["signal"], rtol=1e-3, atol=1e-6
    )
    assert_last_bar_matches(
        out["macd"]["hist"], expected["hist"], rtol=1e-3, atol=1e-6
    )
