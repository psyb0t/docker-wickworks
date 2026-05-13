"""Volume field contract — tickVolume is canonical for volume indicators.

The Bar schema accepts both `tickVolume` and `realVolume` for forward-compat
with broker feeds that publish both, but the registry always reads
`tick_volume` (see registry._vol_col + _smc_df). These tests pin that
contract so volume-based indicators don't silently change which field they
consume.
"""

from __future__ import annotations

import pytest

from _helpers import post  # type: ignore[import-not-found]


def _bars(n: int, **volume_fields: int) -> list[dict]:
    return [
        {
            "time": 1_700_000_000 + i * 3600,
            "open": 100.0 + i * 0.1,
            "high": 100.5 + i * 0.1,
            "low": 99.5 + i * 0.1,
            "close": 100.0 + i * 0.1,
            **volume_fields,
        }
        for i in range(n)
    ]


@pytest.mark.parametrize("indicator", ["obv", "vwma", "vwap"])
def test_volume_indicators_read_tick_volume(indicator: str) -> None:
    """Sending real values via tickVolume must produce a populated tail."""
    out = post(_bars(200, tickVolume=1000), {indicator: True})
    val = out[indicator]
    tail = val[-1] if isinstance(val, list) else None
    assert tail is not None, f"{indicator} tail is None with tickVolume populated"


@pytest.mark.parametrize("indicator", ["obv", "vwma", "vwap"])
def test_real_volume_only_does_not_drive_volume_indicators(indicator: str) -> None:
    """`realVolume` alone (tickVolume omitted → defaults to 0) yields the
    zero-volume result. This documents that realVolume is informational only.
    """
    only_real = post(_bars(200, realVolume=1000), {indicator: True})
    only_zero = post(_bars(200, tickVolume=0), {indicator: True})
    assert only_real[indicator] == only_zero[indicator]


def test_zero_volume_does_not_crash() -> None:
    out = post(_bars(200, tickVolume=0), {"obv": True})
    assert isinstance(out["obv"], list)
    assert len(out["obv"]) == 200
