"""Stochastic oscillator + StochRSI.

stoch %K = 100 * (close - min_low) / (max_high - min_low), smoothed by SMA(smoothK).
%D = SMA(%K, d).
"""

from __future__ import annotations

import math
from typing import Any

import pytest

from _helpers import (  # type: ignore[import-not-found]
    assert_last_bar_matches,
    bars_to_df,
    monotone_down_bars,
    monotone_up_bars,
    post,
    ref_stoch,
)


def test_stoch_uptrend_pegs_high() -> None:
    bars = monotone_up_bars(200, start=100.0, step=1.0)
    out = post(bars, {"stoch": True})
    assert out["stoch"]["k"][-1] >= 80.0
    assert out["stoch"]["d"][-1] >= 80.0


def test_stoch_downtrend_pegs_low() -> None:
    bars = monotone_down_bars(200, start=200.0, step=1.0)
    out = post(bars, {"stoch": True})
    assert out["stoch"]["k"][-1] <= 20.0
    assert out["stoch"]["d"][-1] <= 20.0


@pytest.mark.parametrize(
    "k,d,smooth_k",
    [(14, 3, 3), (5, 3, 3), (21, 7, 5)],
)
def test_stoch_matches_closed_form_on_real_data(
    eurusd_h1_fixture: dict[str, Any], k: int, d: int, smooth_k: int
) -> None:
    bars = eurusd_h1_fixture["bars"]
    df = bars_to_df(bars)
    expected = ref_stoch(
        df["high"], df["low"], df["close"], k=k, d=d, smooth_k=smooth_k
    )
    out = post(
        bars, {"stoch": {"type": "stoch", "k": k, "d": d, "smoothK": smooth_k}}
    )
    assert_last_bar_matches(out["stoch"]["k"], expected["k"])
    assert_last_bar_matches(out["stoch"]["d"], expected["d"])


def test_stochrsi_keys_mapped() -> None:
    """Sine-wave input so RSI varies and stochrsi has a real value."""
    n = 300
    bars = []
    for i in range(n):
        c = 100.0 + math.sin(i / 4.0) * 5.0 + i * 0.1
        bars.append(
            {
                "time": 1_700_000_000 + i * 3600,
                "open": c,
                "high": c + 0.5,
                "low": c - 0.5,
                "close": c,
                "tickVolume": 1000,
            }
        )
    out = post(bars, {"stochrsi": True})
    k_tail = [v for v in out["stochrsi"]["k"][-20:] if v is not None]
    d_tail = [v for v in out["stochrsi"]["d"][-20:] if v is not None]
    assert k_tail and d_tail
    for v in k_tail + d_tail:
        assert 0 <= v <= 100


def test_stochrsi_bounded_on_real_data(eurusd_h1_fixture: dict[str, Any]) -> None:
    out = post(eurusd_h1_fixture["bars"], {"stochrsi": True})
    for sub in ("k", "d"):
        values = [v for v in out["stochrsi"][sub] if v is not None]
        assert all(0.0 <= v <= 100.0 for v in values)
