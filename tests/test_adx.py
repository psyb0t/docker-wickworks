"""ADX / +DI / -DI — directional movement index.

The notorious +DI/-DI swap is the highest-risk bug here, so direction tests
are the primary defense.
"""

from __future__ import annotations

from typing import Any

from _helpers import (  # type: ignore[import-not-found]
    monotone_down_bars,
    monotone_up_bars,
    post,
)


def test_adx_di_plus_dominant_on_uptrend() -> None:
    out = post(monotone_up_bars(200), {"adx": True})
    assert out["adx"]["diPlus"][-1] > out["adx"]["diMinus"][-1]


def test_adx_di_minus_dominant_on_downtrend() -> None:
    out = post(monotone_down_bars(200), {"adx": True})
    assert out["adx"]["diMinus"][-1] > out["adx"]["diPlus"][-1]


def test_adx_strong_on_trending_data() -> None:
    out = post(monotone_up_bars(300, step=1.0), {"adx": True})
    assert out["adx"]["adx"][-1] > 25.0


def test_adx_keys_populated_on_real_data(
    eurusd_h1_fixture: dict[str, Any],
) -> None:
    out = post(eurusd_h1_fixture["bars"], {"adx": True})
    for key in ("adx", "diPlus", "diMinus"):
        assert out["adx"][key][-1] is not None
