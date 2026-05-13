"""HTTP error paths — bad input must return structured 4xx, not 500."""

from __future__ import annotations

from fastapi.testclient import TestClient

from wickworks.server import app

client = TestClient(app)


def _one_bar(i: int = 0, price: float = 100.0) -> dict:
    return {
        "time": 1_700_000_000 + i * 3600,
        "open": price,
        "high": price,
        "low": price,
        "close": price,
        "tickVolume": 1,
    }


def test_empty_bars_returns_400() -> None:
    r = client.post("/", json={"bars": [], "indicators": {"rsi": True}})
    assert r.status_code == 400
    assert "bars" in r.json()["detail"].lower()


def test_empty_indicators_returns_400() -> None:
    r = client.post("/", json={"bars": [_one_bar(0)], "indicators": {}})
    assert r.status_code == 400
    assert "indicators" in r.json()["detail"].lower()


def test_unknown_indicator_returns_400() -> None:
    r = client.post(
        "/",
        json={"bars": [_one_bar(i) for i in range(200)], "indicators": {"notARealOne": True}},
    )
    assert r.status_code == 400


def test_missing_ohlc_field_returns_422() -> None:
    """Pydantic catches malformed bars at the validation layer → 422."""
    bad_bar = {"time": 1_700_000_000, "open": 1.0}  # no high/low/close
    r = client.post("/", json={"bars": [bad_bar], "indicators": {"rsi": True}})
    assert r.status_code == 422


def test_insufficient_bars_returns_422() -> None:
    """Too few bars to compute anything → 422 (per server contract)."""
    r = client.post(
        "/",
        json={"bars": [_one_bar(i) for i in range(3)], "indicators": {"rsi": True}},
    )
    assert r.status_code == 422
    assert "insufficient" in r.json()["detail"].lower()


def test_health_endpoint() -> None:
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert isinstance(body["version"], str)
