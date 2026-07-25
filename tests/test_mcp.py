"""MCP surface — the streamable-HTTP server mounted at ``/mcp``.

``stateless_http=True`` + ``json_response=True`` means each JSON-RPC call is
self-contained (no initialize handshake, JSON body back — not an SSE stream), so
we drive it with a plain ``TestClient``. Contract tests through the mounted ASGI
app: tools/list plus tools/call for health, list_indicators, metadata, and
compute (happy path + the error paths). The MCP tools mirror the REST surface, so
the ``compute`` envelope must match ``POST /`` (symbol / timeframe / candles + one
series per requested output). Per-indicator math is already covered by the
``test_<indicator>.py`` suite — this file guards the MCP wrapper + wiring only.

Test plan: .testing/2026-07-25/wickworks-mcp.md
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from wickworks.server import app

_MCP_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}

_WARMUP_BARS = 80


@pytest.fixture(scope="module")
def client() -> Any:
    # Module-scoped: the MCP streamable-HTTP session manager can only be run once
    # per server instance, and the app builds a single module-global one — so all
    # tests share one client (a single lifespan enter/exit).
    with TestClient(app) as c:
        yield c


def _rpc(
    client: TestClient,
    method: str,
    params: dict[str, Any],
    req_id: int = 1,
) -> dict[str, Any]:
    resp = client.post(
        "/mcp/",
        headers=_MCP_HEADERS,
        json={"jsonrpc": "2.0", "id": req_id, "method": method, "params": params},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _structured(body: dict[str, Any]) -> dict[str, Any]:
    result = body["result"]
    assert result.get("isError") is not True, body
    return result["structuredContent"]


def _call(
    client: TestClient,
    name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    return _rpc(client, "tools/call", {"name": name, "arguments": arguments})


def _ramp_bars(n: int, base: float = 100.0) -> list[dict[str, Any]]:
    """Monotonically rising OHLC bars — enough signal for an indicator to warm up
    and produce a non-null tail."""
    bars: list[dict[str, Any]] = []
    for i in range(n):
        close = base + i
        bars.append(
            {
                "time": 1_700_000_000 + i * 3600,
                "open": close - 0.5,
                "high": close + 1.0,
                "low": close - 1.0,
                "close": close,
                "tickVolume": 1000 + i,
            }
        )
    return bars


def test_tools_list_exposes_every_tool(client: TestClient) -> None:
    body = _rpc(client, "tools/list", {})
    names = {t["name"] for t in body["result"]["tools"]}
    assert {"health", "list_indicators", "metadata", "compute"} <= names


def test_health(client: TestClient) -> None:
    out = _structured(_call(client, "health", {}))
    assert out["ok"] is True
    assert isinstance(out["version"], str) and out["version"]


def test_list_indicators(client: TestClient) -> None:
    out = _structured(_call(client, "list_indicators", {}))
    indicators = out["indicators"]
    assert {"rsi", "macd", "atr"} <= set(indicators)
    assert indicators == sorted(indicators)


def test_metadata(client: TestClient) -> None:
    out = _structured(_call(client, "metadata", {}))
    assert out["count"] > 0
    assert "version" in out
    assert "entries" in out


def test_compute_mirrors_rest_envelope(client: TestClient) -> None:
    out = _structured(
        _call(
            client,
            "compute",
            {
                "bars": _ramp_bars(_WARMUP_BARS),
                "indicators": {"rsi": True},
                "symbol": "TEST",
                "timeframe": "H1",
            },
        )
    )
    assert out["symbol"] == "TEST"
    assert out["timeframe"] == "H1"
    assert out["candles"] == _WARMUP_BARS
    assert isinstance(out["rsi"], list)
    assert len(out["rsi"]) == _WARMUP_BARS
    assert out["rsi"][-1] is not None


def test_compute_unknown_indicator_is_error(client: TestClient) -> None:
    body = _call(
        client,
        "compute",
        {"bars": _ramp_bars(_WARMUP_BARS), "indicators": {"not_a_real_one": True}},
    )
    assert body["result"].get("isError") is True, body


def test_compute_empty_bars_is_error(client: TestClient) -> None:
    body = _call(client, "compute", {"bars": [], "indicators": {"rsi": True}})
    assert body["result"].get("isError") is True, body


def test_compute_empty_indicators_is_error(client: TestClient) -> None:
    body = _call(
        client,
        "compute",
        {"bars": _ramp_bars(_WARMUP_BARS), "indicators": {}},
    )
    assert body["result"].get("isError") is True, body
