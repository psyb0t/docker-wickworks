"""CCI = (typical_price - SMA(tp)) / (c * mean_abs_deviation(tp)).

Sign sanity (positive on uptrend, negative on downtrend) — and locked-in
closed-form match guarding against the parenthesization bug fixed previously.
"""

from __future__ import annotations

from typing import Any

import pytest

from _helpers import (  # type: ignore[import-not-found]
    assert_last_bar_matches,
    bars_to_df,
    monotone_down_bars,
    monotone_up_bars,
    post,
    ref_cci,
)


def test_cci_sign_follows_trend() -> None:
    up = post(monotone_up_bars(200), {"cci": True})
    dn = post(monotone_down_bars(200), {"cci": True})
    assert up["cci"][-1] > 0
    assert dn["cci"][-1] < 0


@pytest.mark.parametrize("length", [14, 20])
def test_cci_matches_closed_form_on_real_data(
    eurusd_h1_fixture: dict[str, Any], length: int
) -> None:
    """Patched formula — guard against regression of the parens fix."""
    bars = eurusd_h1_fixture["bars"]
    df = bars_to_df(bars)
    expected = ref_cci(df["high"], df["low"], df["close"], length=length)
    out = post(bars, {"cci": {"type": "cci", "length": length}})
    assert_last_bar_matches(out["cci"], expected, rtol=1e-4)
