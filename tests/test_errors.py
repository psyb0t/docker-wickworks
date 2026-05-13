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


def test_insufficient_bars_returns_400_with_deficits() -> None:
    """Too few bars for a requested indicator → 400 with per-indicator deficits.

    rsi default length=14 → needs 15 bars to emit a first non-null value.
    Sending 3 bars must produce a structured deficit, not a silent all-null
    series and not the old generic 422.
    """
    r = client.post(
        "/",
        json={"bars": [_one_bar(i) for i in range(3)], "indicators": {"rsi": True}},
    )
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["error"] == "insufficient_bars"
    assert detail["available"] == 3
    deficits = detail["deficits"]
    assert len(deficits) == 1
    d = deficits[0]
    assert d["outputKey"] == "rsi"
    assert d["type"] == "rsi"
    assert d["required"] == 15
    assert d["available"] == 3


def test_insufficient_bars_lists_all_deficits_at_once() -> None:
    """Multiple under-fed indicators all surface in a single 400 — no whack-a-mole."""
    r = client.post(
        "/",
        json={
            "bars": [_one_bar(i) for i in range(30)],
            "indicators": {
                "fastSma": {"type": "sma", "length": 10},     # OK: needs 10
                "slowSma": {"type": "sma", "length": 200},    # FAIL: needs 200
                "longRsi": {"type": "rsi", "length": 50},     # FAIL: needs 51
            },
        },
    )
    assert r.status_code == 400
    deficits = r.json()["detail"]["deficits"]
    keys = {d["outputKey"] for d in deficits}
    assert keys == {"slowSma", "longRsi"}
    by_key = {d["outputKey"]: d for d in deficits}
    assert by_key["slowSma"]["required"] == 200
    assert by_key["longRsi"]["required"] == 51


def test_sufficient_bars_with_custom_length_succeeds() -> None:
    """Caller supplying the exact-needed bar count gets a result, not an error."""
    r = client.post(
        "/",
        json={
            "bars": [_one_bar(i, price=100.0 + i * 0.1) for i in range(15)],
            "indicators": {"rsi": {"type": "rsi", "length": 14}},
        },
    )
    assert r.status_code == 200, r.text
    assert "rsi" in r.json()


def test_health_endpoint() -> None:
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert isinstance(body["version"], str)
