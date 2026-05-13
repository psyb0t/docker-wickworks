"""Aroon up/down oscillator — bars-since-extreme over a lookback window."""

from __future__ import annotations

from typing import Any

import pytest

from _helpers import (  # type: ignore[import-not-found]
    assert_last_bar_matches,
    bars_to_df,
    monotone_down_bars,
    monotone_up_bars,
    post,
    ref_aroon,
)


def test_aroon_up_pegged_on_uptrend() -> None:
    out = post(monotone_up_bars(200), {"aroon": True})
    assert out["aroon"]["up"][-1] == pytest.approx(100.0, abs=1e-6)
    assert out["aroon"]["down"][-1] == pytest.approx(0.0, abs=1e-6)
    assert out["aroon"]["oscillator"][-1] == pytest.approx(100.0, abs=1e-6)


def test_aroon_down_pegged_on_downtrend() -> None:
    out = post(monotone_down_bars(200), {"aroon": True})
    assert out["aroon"]["up"][-1] == pytest.approx(0.0, abs=1e-6)
    assert out["aroon"]["down"][-1] == pytest.approx(100.0, abs=1e-6)
    assert out["aroon"]["oscillator"][-1] == pytest.approx(-100.0, abs=1e-6)


@pytest.mark.parametrize("length", [14, 25])
def test_aroon_matches_closed_form_on_real_data(
    eurusd_h1_fixture: dict[str, Any], length: int
) -> None:
    bars = eurusd_h1_fixture["bars"]
    df = bars_to_df(bars)
    expected = ref_aroon(df["high"], df["low"], length=length)
    out = post(bars, {"aroon": {"type": "aroon", "length": length}})
    assert_last_bar_matches(out["aroon"]["up"], expected["up"])
    assert_last_bar_matches(out["aroon"]["down"], expected["down"])
    assert_last_bar_matches(out["aroon"]["oscillator"], expected["oscillator"])
