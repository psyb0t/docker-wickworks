"""On-Balance Volume — cumulative signed volume."""

from __future__ import annotations

from typing import Any

import pytest

from _helpers import (  # type: ignore[import-not-found]
    assert_last_bar_matches,
    bars_to_df,
    monotone_up_bars,
    post,
    ref_obv,
)


def test_obv_accumulates_on_uptrend() -> None:
    bars = monotone_up_bars(200, start=100.0, step=1.0)
    out = post(bars, {"obv": True})
    series = [v for v in out["obv"] if v is not None]
    assert series[-1] > series[0]
    # 199 up-moves × 1000 volume each.
    assert series[-1] == pytest.approx(199 * 1000, abs=10)


def test_obv_matches_closed_form_on_real_data(
    eurusd_h1_fixture: dict[str, Any],
) -> None:
    bars = eurusd_h1_fixture["bars"]
    df = bars_to_df(bars)
    expected = ref_obv(df["close"], df["volume"])
    out = post(bars, {"obv": True})
    assert_last_bar_matches(out["obv"], expected, rtol=1e-6)
