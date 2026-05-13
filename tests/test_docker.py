"""End-to-end tests against the real Docker image.

Opt-in: marked with @pytest.mark.docker. Run with `pytest -m docker`.
The image is built once per test session if missing, started on an ephemeral
host port, health-checked, and torn down (auto_remove=True) on exit.
"""

from __future__ import annotations

import math
import time
from pathlib import Path
from typing import Any, Iterator

import pytest
import requests

docker_sdk = pytest.importorskip("docker")
testcontainers_core = pytest.importorskip("testcontainers.core.container")
DockerContainer = testcontainers_core.DockerContainer

pytestmark = pytest.mark.docker

IMAGE = "psyb0t/wickworks:test"
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _bars(n: int = 200) -> list[dict[str, Any]]:
    out = []
    p = 1.10000
    for i in range(n):
        o = p + math.sin(i / 5.0) * 0.002
        c = o + math.cos(i / 7.0) * 0.001
        out.append(
            {
                "time": 1_700_000_000 + i * 3600,
                "open": round(o, 5),
                "high": round(max(o, c) + 0.0003, 5),
                "low": round(min(o, c) - 0.0003, 5),
                "close": round(c, 5),
                "tickVolume": 1000 + (i % 50),
            }
        )
        p = c
    return out


@pytest.fixture(scope="session")
def _image() -> str:
    """Build the image once per session if not already present."""
    client = docker_sdk.from_env()
    try:
        client.images.get(IMAGE)
    except docker_sdk.errors.ImageNotFound:
        client.images.build(path=str(PROJECT_ROOT), tag=IMAGE, rm=True)
    return IMAGE


@pytest.fixture(scope="session")
def base_url(_image: str) -> Iterator[str]:
    """Start the container on an ephemeral host port; tear down on exit."""
    container = (
        DockerContainer(_image)
        .with_exposed_ports(8000)
        .with_env("LOG_LEVEL", "WARNING")
        .with_env("WORKERS", "1")
        .with_kwargs(auto_remove=True)
    )
    container.start()
    try:
        # Prefer the container's internal docker IP — works from the host AND
        # from a sibling dev container running on the same docker daemon. The
        # host-mapped port path breaks under DIND when the dev container can't
        # route to the host's docker0 gateway.
        wrapped = container.get_wrapped_container()
        wrapped.reload()
        networks = wrapped.attrs["NetworkSettings"]["Networks"]
        ip = next(iter(networks.values()))["IPAddress"]
        url = f"http://{ip}:8000"

        # Wait for /health; container is fresh and may need a couple seconds.
        deadline = time.monotonic() + 30
        last_err: Exception | None = None
        while time.monotonic() < deadline:
            try:
                r = requests.get(f"{url}/health", timeout=2)
                if r.status_code == 200 and r.json().get("ok") is True:
                    break
            except Exception as e:
                last_err = e
            time.sleep(0.5)
        else:
            raise RuntimeError(f"container never became healthy: {last_err}")

        yield url
    finally:
        container.stop()


def test_docker_health(base_url: str) -> None:
    r = requests.get(f"{base_url}/health", timeout=5)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert isinstance(body["version"], str)


def test_docker_compute_minimal(base_url: str) -> None:
    r = requests.post(
        f"{base_url}/",
        json={"bars": _bars(), "symbol": "EURUSD", "timeframe": "H1", "indicators": {"rsi": True}},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["symbol"] == "EURUSD"
    assert body["candles"] == 200
    assert isinstance(body["rsi"], list)
    assert len(body["rsi"]) == 200


def test_docker_compute_multi_stoch(base_url: str) -> None:
    r = requests.post(
        f"{base_url}/",
        json={
            "bars": _bars(),
            "indicators": {
                "stochFast": {"type": "stoch", "k": 5, "d": 3, "smoothK": 3},
                "stochSlow": {"type": "stoch", "k": 21, "d": 7, "smoothK": 5},
            },
        },
        timeout=10,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body["stochFast"].keys()) == {"k", "d"}
    assert set(body["stochSlow"].keys()) == {"k", "d"}
    assert body["stochFast"]["k"] != body["stochSlow"]["k"]


@pytest.mark.parametrize(
    "case_id,body,status,detail_substr",
    [
        ("unknown_indicator", {"bars": _bars(),   "indicators": {"banana": True}}, 400, "banana"),
        ("too_few_bars",      {"bars": _bars(10), "indicators": {"rsi": True}},    422, "insufficient"),
        ("empty_bars",        {"bars": [],        "indicators": {"rsi": True}},    400, "bars"),
        ("empty_indicators",  {"bars": _bars(),   "indicators": {}},                400, "indicators"),
    ],
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_docker_rejects_bad_request(
    base_url: str, case_id: str, body: dict[str, Any], status: int, detail_substr: str
) -> None:
    r = requests.post(f"{base_url}/", json=body, timeout=5)
    assert r.status_code == status, r.text
    assert detail_substr.lower() in r.json()["detail"].lower()
