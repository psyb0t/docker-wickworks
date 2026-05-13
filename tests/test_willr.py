"""Williams %R — -100 * (HH - close) / (HH - LL), bounded [-100, 0]."""

from __future__ import annotations

from typing import Any

import pytest

from _helpers import (  # type: ignore[import-not-found]
    assert_last_bar_matches,
    bars_to_df,
    monotone_down_bars,
    monotone_up_bars,
    post,
    ref_williams_r,
)


def test_willr_range_and_direction() -> None:
    up = post(monotone_up_bars(200), {"willr": True})
    dn = post(monotone_down_bars(200), {"willr": True})
    assert up["willr"][-1] >= -20.0
    assert dn["willr"][-1] <= -80.0


@pytest.mark.parametrize("length", [14, 21])
def test_willr_matches_closed_form_on_real_data(
    eurusd_h1_fixture: dict[str, Any], length: int
) -> None:
    bars = eurusd_h1_fixture["bars"]
    df = bars_to_df(bars)
    expected = ref_williams_r(df["high"], df["low"], df["close"], length=length)
    out = post(bars, {"willr": {"type": "willr", "length": length}})
    assert_last_bar_matches(out["willr"], expected)
