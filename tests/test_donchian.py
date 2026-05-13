"""Donchian channel — rolling max-high / min-low (shifted, current bar excluded)."""

from __future__ import annotations

from typing import Any

import pytest

from _helpers import (  # type: ignore[import-not-found]
    assert_last_bar_matches,
    bars_to_df,
    monotone_up_bars,
    post,
    ref_donchian,
)


def test_donchian_middle_is_midpoint() -> None:
    bars = monotone_up_bars(200, start=100.0, step=1.0)
    out = post(bars, {"donchian": {"type": "donchian", "length": 20}})
    upper = out["donchian"]["upper"][-1]
    middle = out["donchian"]["middle"][-1]
    lower = out["donchian"]["lower"][-1]
    assert middle == pytest.approx((upper + lower) / 2, abs=1e-9)
    assert upper > middle > lower


@pytest.mark.parametrize("length", [10, 20, 55])
def test_donchian_matches_closed_form_on_real_data(
    eurusd_h1_fixture: dict[str, Any], length: int
) -> None:
    bars = eurusd_h1_fixture["bars"]
    df = bars_to_df(bars)
    expected = ref_donchian(df["high"], df["low"], length=length)
    out = post(
        bars, {"donchian": {"type": "donchian", "length": length}}
    )
    assert_last_bar_matches(out["donchian"]["upper"], expected["upper"])
    assert_last_bar_matches(out["donchian"]["lower"], expected["lower"])
    assert_last_bar_matches(out["donchian"]["middle"], expected["middle"])
