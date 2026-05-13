"""Warmup-region None counts — first K bars must be None, exactly.

Catches off-by-one in `_series()` (the float→None converter for NaN warmup
values) and indicator length-routing bugs (e.g. ignored `length` param).
"""

from __future__ import annotations

from typing import Any

import pytest

from _helpers import (  # type: ignore[import-not-found]
    monotone_up_bars,
    post,
)


def _leading_none_count(series: list[Any]) -> int:
    n = 0
    for v in series:
        if v is None:
            n += 1
            continue
        break
    return n


@pytest.mark.parametrize("length", [10, 20, 50])
def test_sma_warmup_is_length_minus_one(length: int) -> None:
    bars = monotone_up_bars(300, start=100.0, step=1.0)
    out = post(bars, {"sma": {"type": "sma", "length": length}})
    assert _leading_none_count(out["sma"]) == length - 1


@pytest.mark.parametrize("length", [10, 20, 50])
def test_ema_warmup_is_length_minus_one(length: int) -> None:
    """pandas_ta EMA seeded with SMA(N) at index N-1, so leading None = N-1."""
    bars = monotone_up_bars(300, start=100.0, step=1.0)
    out = post(bars, {"ema": {"type": "ema", "length": length}})
    assert _leading_none_count(out["ema"]) == length - 1


def test_rsi_has_leading_warmup_none(eurusd_h1_fixture: dict[str, Any]) -> None:
    """pandas_ta RSI emits at least one leading None (the first diff is NaN).

    Stricter `=length` counts aren't portable — pandas_ta back-fills the
    pre-Wilder-seed region with running averages rather than NaN. The
    closed-form match at the tail (test_rsi.py) is the authoritative check.
    """
    out = post(eurusd_h1_fixture["bars"], {"rsi": True})
    assert _leading_none_count(out["rsi"]) >= 1


def test_response_series_length_matches_input(
    eurusd_h1_fixture: dict[str, Any],
) -> None:
    """Every series indicator returns exactly len(bars) entries — never trimmed."""
    bars = eurusd_h1_fixture["bars"]
    n = len(bars)
    out = post(bars, {"rsi": True, "atr": True, "ema": True})
    for key in ("rsi", "atr", "ema"):
        assert len(out[key]) == n, f"{key}: len={len(out[key])} != input {n}"
