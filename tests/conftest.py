"""Shared fixtures."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pytest

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _gen_bars(n: int, start_time: int = 1_700_000_000, step: int = 3600) -> list[dict[str, Any]]:
    """Deterministic synthetic OHLCV bars — sine-wave price + constant volume."""
    bars = []
    price = 1.10000
    for i in range(n):
        wave = math.sin(i / 5.0) * 0.002
        o = price + wave
        c = o + math.cos(i / 7.0) * 0.001
        h = max(o, c) + 0.0003
        lo = min(o, c) - 0.0003
        bars.append(
            {
                "time": start_time + i * step,
                "open": round(o, 5),
                "high": round(h, 5),
                "low": round(lo, 5),
                "close": round(c, 5),
                "tickVolume": 1000 + (i % 50),
            }
        )
        price = c
    return bars


@pytest.fixture
def bars_60() -> list[dict[str, Any]]:
    return _gen_bars(60)


@pytest.fixture
def bars_500() -> list[dict[str, Any]]:
    return _gen_bars(500)


@pytest.fixture(scope="session")
def eurusd_h1_fixture() -> dict[str, Any]:
    """Real EURUSD H1 bars (500) captured from voidalpha /market/symbols/eurusd/rates.

    Used to smoke-test the full pipeline against actual market data — catches
    NaN/inf issues, range edge cases, and pandas_ta quirks that synthetic
    sine-wave bars don't surface.
    """
    return json.loads((FIXTURE_DIR / "eurusd_h1.json").read_text())
