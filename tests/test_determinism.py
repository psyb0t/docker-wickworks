"""Same input → identical bytes out across repeated calls.

Catches accidental dict-iteration / hash-seed leaks, non-deterministic
ordering in SMC list outputs, and any RNG that snuck into the pipeline.
"""

from __future__ import annotations

import json
from typing import Any

from _helpers import post  # type: ignore[import-not-found]


_FULL_INDICATORS: dict[str, Any] = {
    "rsi": True,
    "ema21": {"type": "ema", "length": 21},
    "atr": True,
    "macd": True,
    "bbands": True,
    "stoch": True,
    "adx": True,
    "orderBlocks": True,
    "fvg": True,
    "bosChoch": True,
    "swingLevels": True,
    "srLevels": True,
    "momentum": True,
    "volume": True,
    "position": True,
    "slope": True,
    "levels": True,
    "recentRange": True,
    "price": True,
}


def test_response_bytes_identical_across_calls(
    eurusd_h1_fixture: dict[str, Any],
) -> None:
    bars = eurusd_h1_fixture["bars"]
    a = post(bars, _FULL_INDICATORS, symbol="EURUSD", timeframe="H1")
    b = post(bars, _FULL_INDICATORS, symbol="EURUSD", timeframe="H1")
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
