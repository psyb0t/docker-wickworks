"""Parabolic SAR — long band populated on uptrend, short on downtrend."""

from __future__ import annotations

from typing import Any

from _helpers import (  # type: ignore[import-not-found]
    monotone_down_bars,
    monotone_up_bars,
    post,
)


def test_psar_uptrend_long_populated() -> None:
    out = post(monotone_up_bars(200), {"psar": True})
    assert out["psar"]["long"][-1] is not None
    assert out["psar"]["short"][-1] is None


def test_psar_downtrend_short_populated() -> None:
    out = post(monotone_down_bars(200), {"psar": True})
    assert out["psar"]["short"][-1] is not None
    assert out["psar"]["long"][-1] is None


def test_psar_exclusive_sides_on_real_data(
    eurusd_h1_fixture: dict[str, Any],
) -> None:
    """At any bar, at most one of long/short carries a value (mutually exclusive sides)."""
    out = post(eurusd_h1_fixture["bars"], {"psar": True})
    longs = out["psar"]["long"]
    shorts = out["psar"]["short"]
    for lo, sh in zip(longs, shorts):
        assert not (lo is not None and sh is not None), (
            "PSAR long/short must not both be populated on same bar"
        )
