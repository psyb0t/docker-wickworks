"""Regression tests for request cost and point in time semantics."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import numpy as np
import pytest
from _helpers import post  # type: ignore[import-not-found]
from fastapi.testclient import TestClient

from wickworks import registry
from wickworks.server import app
from wickworks.smc import _count_sr_touches

client = TestClient(app)


def test_simple_indicator_does_not_run_full_analysis(
    bars_500: list[dict[str, Any]],
    monkeypatch: Any,
) -> None:
    def unexpected_analysis(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("full analysis ran for an RSI-only request")

    monkeypatch.setattr(registry, "add_all", unexpected_analysis)
    response = client.post("/", json={"bars": bars_500, "indicators": {"rsi": True}})
    assert response.status_code == 200, response.text


def test_analysis_is_computed_once_for_multiple_summary_outputs(
    bars_500: list[dict[str, Any]],
    monkeypatch: Any,
) -> None:
    calls = 0
    original = registry.add_all

    def count_analysis(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(registry, "add_all", count_analysis)
    response = client.post(
        "/",
        json={"bars": bars_500, "indicators": {"levels": True, "momentum": True}},
    )
    assert response.status_code == 200, response.text
    assert calls == 1


def test_previous_high_low_uses_immediately_completed_period() -> None:
    base = int(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp())
    bars = []
    for day, prices in enumerate(((10.0, 8.0), (20.0, 15.0), (30.0, 25.0))):
        high, low = prices
        for hour in range(20):
            bars.append(
                {
                    "time": base + day * 86_400 + hour * 3_600,
                    "open": low + 1,
                    "high": high,
                    "low": low,
                    "close": high - 1,
                    "volume": 100,
                }
            )

    result = post(
        bars,
        {"previous": {"type": "previousHighLow", "timeFrame": "1D"}},
    )["previous"]
    first_third_day = next(event for event in result if event["idx"] == 40)
    assert first_third_day["PreviousHigh"] == 20.0
    assert first_third_day["PreviousLow"] == 15.0


@pytest.mark.parametrize(
    "time_frame",
    ["15min", "30min", "1h", "4h", "1D", "1W", "1ME"],
)
def test_previous_high_low_accepts_voidalpha_period_spellings(
    bars_500: list[dict[str, Any]],
    time_frame: str,
) -> None:
    response = client.post(
        "/",
        json={
            "bars": bars_500,
            "indicators": {
                "previous": {
                    "type": "previousHighLow",
                    "timeFrame": time_frame,
                }
            },
        },
    )
    assert response.status_code == 200, response.text


def test_previous_high_low_week_changes_at_monday_utc() -> None:
    monday = int(datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp())
    bars = []
    for day in range(50):
        week = day // 7
        low = 10.0 + week * 10
        high = low + 5
        bars.append(
            {
                "time": monday + day * 86_400,
                "open": low + 1,
                "high": high,
                "low": low,
                "close": high - 1,
                "volume": 100,
            }
        )

    result = post(
        bars,
        {"previous": {"type": "previousHighLow", "timeFrame": "1W"}},
    )["previous"]
    first_third_week = next(event for event in result if event["idx"] == 14)
    assert first_third_week["PreviousHigh"] == 25.0
    assert first_third_week["PreviousLow"] == 20.0


def test_support_touch_spacing_is_not_request_length_dependent() -> None:
    highs = np.full(100, 110.0)
    lows = np.full(100, 105.0)
    for index in (10, 20, 30, 40, 50):
        lows[index] = 100.0
    padded_highs = np.concatenate((np.full(1900, 110.0), highs))
    padded_lows = np.concatenate((np.full(1900, 105.0), lows))

    assert _count_sr_touches(highs, lows, 100.0, 1.0) == 5
    assert _count_sr_touches(padded_highs, padded_lows, 100.0, 1.0) == 5


def test_structural_objects_expose_availability_times(
    bars_500: list[dict[str, Any]],
) -> None:
    result = post(
        bars_500,
        {
            "orderBlocks": True,
            "fvgs": True,
            "bosChoch": True,
            "swingLevels": True,
        },
    )
    objects = [
        item for key in ("orderBlocks", "fvgs", "bosChoch", "swingLevels") for item in result[key]
    ]
    assert objects
    for item in objects:
        assert item["originAt"] <= item["confirmedAt"] <= item["observedAsOf"]
