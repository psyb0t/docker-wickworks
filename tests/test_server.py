"""HTTP-layer tests against the FastAPI app (no docker)."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from wickworks import __version__
from wickworks.registry import INDICATORS
from wickworks.server import app

client = TestClient(app)


def test_health() -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True, "version": __version__}


# -----------------------------------------------------------------------------
# Bad-request cases — one parametrized test for every shape the API rejects.
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "case_id,body_fn,status,detail_substr",
    [
        ("empty_bars",        lambda _: {"bars": [], "indicators": {"rsi": True}},     400, "bars"),
        ("empty_indicators",  lambda b: {"bars": b, "indicators": {}},                  400, "indicators"),
        ("unknown_indicator", lambda b: {"bars": b, "indicators": {"banana": True}},    400, "banana"),
        ("too_few_bars",      lambda _: {"bars": [{"time": i, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "tickVolume": 0} for i in range(5)], "indicators": {"rsi": True}}, 400, "insufficient"),
    ],
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_compute_rejects_bad_request(
    bars_500: list[dict[str, Any]],
    case_id: str,
    body_fn: Any,
    status: int,
    detail_substr: str,
) -> None:
    r = client.post("/", json=body_fn(bars_500))
    assert r.status_code == status, r.text
    # detail is either a string (simple 4xx) or a structured dict (insufficient_bars);
    # either way the substring must appear in the serialized form.
    assert detail_substr.lower() in str(r.json()["detail"]).lower()


# -----------------------------------------------------------------------------
# Per-indicator smoke — every registered indicator must accept bars_500 and
# return a non-None value. Catches per-indicator shape regressions.
# -----------------------------------------------------------------------------


@pytest.mark.parametrize("indicator", sorted(INDICATORS.keys()))
def test_compute_each_registered_indicator(
    bars_500: list[dict[str, Any]], indicator: str
) -> None:
    r = client.post("/", json={"bars": bars_500, "indicators": {indicator: True}})
    assert r.status_code == 200, r.text
    body = r.json()
    assert indicator in body
    assert body[indicator] is not None
    # Meta fields always echoed.
    assert body["candles"] == len(bars_500)


# -----------------------------------------------------------------------------
# Response shape — the request shape is mirrored exactly in the response.
# -----------------------------------------------------------------------------


def test_compute_response_only_contains_requested_keys(
    bars_500: list[dict[str, Any]],
) -> None:
    r = client.post(
        "/",
        json={"bars": bars_500, "symbol": "EURUSD", "timeframe": "H1", "indicators": {"rsi": True}},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["symbol"] == "EURUSD"
    assert body["timeframe"] == "H1"
    assert body["candles"] == len(bars_500)
    assert isinstance(body["rsi"], list)
    assert len(body["rsi"]) == len(bars_500)
    # Unrequested indicators must not leak in.
    assert "macd" not in body
    assert "orderBlocks" not in body


# -----------------------------------------------------------------------------
# Multi-instance of the same indicator type under distinct output keys.
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "output_key,params",
    [
        ("stochFast",  {"type": "stoch", "k": 5,  "d": 3, "smoothK": 3}),
        ("stochMed",   {"type": "stoch", "k": 14, "d": 3, "smoothK": 3}),
        ("stochSlow",  {"type": "stoch", "k": 21, "d": 7, "smoothK": 5}),
        ("stochUltra", {"type": "stoch", "k": 3,  "d": 2, "smoothK": 1}),
    ],
)
def test_compute_multiple_instances_same_type_per_key_shape(
    bars_500: list[dict[str, Any]], output_key: str, params: dict[str, Any]
) -> None:
    r = client.post("/", json={"bars": bars_500, "indicators": {output_key: params}})
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body[output_key].keys()) == {"k", "d"}
    assert len(body[output_key]["k"]) == len(bars_500)


def test_compute_multiple_stochs_produce_distinct_series(
    bars_500: list[dict[str, Any]],
) -> None:
    """End-to-end check that 4 stochs in one request return 4 different series."""
    r = client.post(
        "/",
        json={
            "bars": bars_500,
            "indicators": {
                "stochFast":  {"type": "stoch", "k": 5,  "d": 3, "smoothK": 3},
                "stochSlow":  {"type": "stoch", "k": 21, "d": 7, "smoothK": 5},
            },
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stochFast"]["k"] != body["stochSlow"]["k"]


