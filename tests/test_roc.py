"""Rate of change (ROC) and momentum (MOM).

ROC = 100 * (close - close[-N]) / close[-N]
MOM = close - close[-N]
"""

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
    ref_mom,
    ref_roc,
)


def test_roc_sign() -> None:
    up = post(monotone_up_bars(200), {"roc": True})
    dn = post(monotone_down_bars(200), {"roc": True})
    flat = post(flat_bars(200), {"roc": True})
    assert up["roc"][-1] > 0
    assert dn["roc"][-1] < 0
    assert flat["roc"][-1] == pytest.approx(0.0, abs=1e-9)


@pytest.mark.parametrize("length", [5, 10, 20])
def test_roc_matches_closed_form_on_real_data(
    eurusd_h1_fixture: dict[str, Any], length: int
) -> None:
    bars = eurusd_h1_fixture["bars"]
    df = bars_to_df(bars)
    expected = ref_roc(df["close"], length=length)
    out = post(bars, {"roc": {"type": "roc", "length": length}})
    assert_last_bar_matches(out["roc"], expected)


@pytest.mark.parametrize("length", [5, 10, 20])
def test_mom_matches_closed_form_on_real_data(
    eurusd_h1_fixture: dict[str, Any], length: int
) -> None:
    bars = eurusd_h1_fixture["bars"]
    df = bars_to_df(bars)
    expected = ref_mom(df["close"], length=length)
    out = post(bars, {"mom": {"type": "mom", "length": length}})
    assert_last_bar_matches(out["mom"], expected)
