"""SMA / EMA / alt moving averages.

The 16 alt MAs (hma/wma/dema/...) all share the same registry plumbing —
verifying SMA + EMA closed-form + a "shape + finite + ordering" check across
the rest is sufficient to lock in the wiring without re-implementing every
formula.
"""

from __future__ import annotations

from typing import Any

import pytest

from _helpers import (  # type: ignore[import-not-found]
    assert_last_bar_matches,
    bars_to_df,
    flat_bars,
    monotone_up_bars,
    post,
    ref_ema,
    ref_sma,
    ref_vwma,
)


# -----------------------------------------------------------------------------
# SMA — closed-form arithmetic, hits exactly.
# -----------------------------------------------------------------------------


def test_sma_of_arithmetic_series() -> None:
    n = 200
    bars = [
        {
            "time": 1_700_000_000 + i * 3600,
            "open": float(i + 1),
            "high": float(i + 1),
            "low": float(i + 1),
            "close": float(i + 1),
            "tickVolume": 1,
        }
        for i in range(n)
    ]
    out = post(bars, {"sma": {"type": "sma", "length": 5}})
    expected = (n - 4 + n) / 2  # mean of last 5 = (n-4+n)/2
    assert out["sma"][-1] == pytest.approx(expected, abs=1e-9)


def test_sma_flat_equals_price() -> None:
    out = post(flat_bars(200, price=42.5), {"sma": {"type": "sma", "length": 20}})
    assert out["sma"][-1] == pytest.approx(42.5, abs=1e-9)


@pytest.mark.parametrize("length", [10, 20, 50, 200])
def test_sma_matches_rolling_mean_on_real_data(
    eurusd_h1_fixture: dict[str, Any], length: int
) -> None:
    bars = eurusd_h1_fixture["bars"]
    df = bars_to_df(bars)
    expected = ref_sma(df["close"], length=length)
    out = post(bars, {"sma": {"type": "sma", "length": length}})
    assert_last_bar_matches(out["sma"], expected)


# -----------------------------------------------------------------------------
# EMA — pandas_ta seeds with SMA(N) then recursive.
# -----------------------------------------------------------------------------


def test_ema_flat_equals_price() -> None:
    out = post(flat_bars(200, price=42.5), {"ema": {"type": "ema", "length": 20}})
    assert out["ema"][-1] == pytest.approx(42.5, abs=1e-9)


@pytest.mark.parametrize("length", [10, 21, 50])
def test_ema_matches_closed_form_on_real_data(
    eurusd_h1_fixture: dict[str, Any], length: int
) -> None:
    bars = eurusd_h1_fixture["bars"]
    df = bars_to_df(bars)
    expected = ref_ema(df["close"], length=length)
    out = post(bars, {"ema": {"type": "ema", "length": length}})
    assert_last_bar_matches(out["ema"], expected)


# -----------------------------------------------------------------------------
# VWMA — closed form: sum(close*vol) / sum(vol).
# -----------------------------------------------------------------------------


@pytest.mark.parametrize("length", [10, 20])
def test_vwma_matches_closed_form_on_real_data(
    eurusd_h1_fixture: dict[str, Any], length: int
) -> None:
    bars = eurusd_h1_fixture["bars"]
    df = bars_to_df(bars)
    expected = ref_vwma(df["close"], df["volume"], length=length)
    out = post(bars, {"vwma": {"type": "vwma", "length": length}})
    assert_last_bar_matches(out["vwma"], expected)


# -----------------------------------------------------------------------------
# Alt MAs — wiring smoke: every registered MA returns a finite tail on
# monotone-up bars and the tail lies inside the price range.
# -----------------------------------------------------------------------------


_ALT_MAS = [
    "hma",
    "wma",
    "dema",
    "tema",
    "t3",
    "kama",
    "alma",
    "linreg",
    "jma",
    "zlma",
    "rma",
    "fwma",
    "swma",
    "sinwma",
    "trima",
]


@pytest.mark.parametrize("ma", _ALT_MAS)
def test_alt_ma_finite_and_within_price_range(ma: str) -> None:
    bars = monotone_up_bars(300, start=100.0, step=1.0)
    out = post(bars, {ma: True})
    tail = out[ma][-1]
    assert tail is not None
    # Last close=100+299=399; all alt MAs must be inside [100, 399].
    assert 100.0 <= tail <= 399.0, f"{ma} tail {tail} outside price range"
