"""Canonical volume field contract."""

from __future__ import annotations

import pytest
from _helpers import post  # type: ignore[import-not-found]
from fastapi.testclient import TestClient

from wickworks.server import app

client = TestClient(app)


def _bars(n: int, volume: int = 1000) -> list[dict]:
    return [
        {
            "time": 1_700_000_000 + i * 3600,
            "open": 100.0 + i * 0.1,
            "high": 100.5 + i * 0.1,
            "low": 99.5 + i * 0.1,
            "close": 100.0 + i * 0.1,
            "volume": volume,
        }
        for i in range(n)
    ]


@pytest.mark.parametrize("indicator", ["obv", "vwma", "vwap"])
def test_volume_indicators_read_canonical_volume(indicator: str) -> None:
    out = post(_bars(200), {indicator: True})
    value = out[indicator]
    tail = value[-1] if isinstance(value, list) else None
    assert tail is not None


@pytest.mark.parametrize(
    "legacy_field",
    ["tickVolume", "realVolume", "tick_volume", "real_volume"],
)
def test_legacy_volume_fields_are_rejected(legacy_field: str) -> None:
    bars = _bars(20)
    bars[0][legacy_field] = bars[0].pop("volume")
    response = client.post("/", json={"bars": bars, "indicators": {"rsi": True}})
    assert response.status_code == 422


def test_zero_volume_does_not_crash() -> None:
    out = post(_bars(200, volume=0), {"obv": True})
    assert isinstance(out["obv"], list)
    assert len(out["obv"]) == 200
