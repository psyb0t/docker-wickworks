"""Parity checks for the checked-in machine-readable API contract."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from _helpers import post  # type: ignore[import-not-found]

from wickworks.constants import PREVIOUS_PERIOD_FREQUENCIES, SUPPORTED_SESSIONS
from wickworks.schemas import ComputeRequest

_SCHEMA_PATH = Path(__file__).parents[1] / "schema.json"
_ORDER_BLOCK_STATE_FIELDS = {
    "mitigatedWickAt",
    "mitigatedCloseAt",
    "mitigatedWick",
    "mitigatedClose",
    "touchCount",
    "touchEvents",
}
_FORBIDDEN_DESCRIPTION_PHRASES = {
    "tick volume",
    "real volume",
    "exchange-local",
}


def _schema() -> dict[str, Any]:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def _descriptions(value: Any) -> list[str]:
    if isinstance(value, list):
        return [text for item in value for text in _descriptions(item)]
    if not isinstance(value, dict):
        return []

    descriptions = []
    if isinstance(value.get("description"), str):
        descriptions.append(value["description"])
    for nested in value.values():
        descriptions.extend(_descriptions(nested))
    return descriptions


def test_schema_previous_period_values_match_runtime() -> None:
    schema = _schema()
    values = schema["$defs"]["PreviousHighLowRequest"]["properties"]["timeFrame"]["enum"]
    assert set(values) == set(PREVIOUS_PERIOD_FREQUENCIES)


def test_schema_session_values_match_runtime() -> None:
    schema = _schema()
    values = schema["$defs"]["SessionsRequest"]["properties"]["session"]["enum"]
    assert set(values) == SUPPORTED_SESSIONS


def test_schema_advertises_order_block_state_fields() -> None:
    schema = _schema()
    fields = schema["$defs"]["OrderBlock"]["properties"]
    assert _ORDER_BLOCK_STATE_FIELDS <= set(fields)


def test_schema_descriptions_do_not_assign_vendor_volume_semantics() -> None:
    descriptions = "\n".join(_descriptions(_schema())).lower()
    for phrase in _FORBIDDEN_DESCRIPTION_PHRASES:
        assert phrase not in descriptions


def test_schema_distinguishes_chart_and_previous_period_timeframes() -> None:
    schema = _schema()
    chart_field = schema["$defs"]["ComputeRequest"]["properties"]["timeframe"]
    previous_field = schema["$defs"]["PreviousHighLowRequest"]["properties"]["timeFrame"]
    chart_description = chart_field["description"]
    previous_description = previous_field["description"]
    assert chart_field["title"] == "Chart interval label only"
    assert previous_field["title"] == "Previous-period aggregation bucket"
    assert "Top-level ComputeRequest.timeframe" in chart_description
    assert "does not parse it or use it to bucket bars" in chart_description
    assert "Nested indicators.<output-name>.timeFrame" in previous_description
    assert "independent of top-level ComputeRequest.timeframe" in previous_description


def test_static_chart_and_volume_descriptions_match_runtime_schema() -> None:
    static_properties = _schema()["$defs"]["ComputeRequest"]["properties"]
    static_bar_properties = _schema()["$defs"]["Bar"]["properties"]
    runtime_schema = ComputeRequest.model_json_schema()
    runtime_properties = runtime_schema["properties"]
    runtime_bar_properties = runtime_schema["$defs"]["Bar"]["properties"]

    assert (
        static_properties["timeframe"]["description"]
        == runtime_properties["timeframe"]["description"]
    )
    assert static_properties["timeframe"]["title"] == runtime_properties["timeframe"]["title"]
    assert (
        static_bar_properties["volume"]["description"]
        == runtime_bar_properties["volume"]["description"]
    )


def test_chart_timeframe_label_does_not_change_indicator_math(
    bars_500: list[dict[str, Any]],
) -> None:
    first = post(
        bars_500,
        {"rsi": True},
        timeframe="first-label",
    )
    second = post(
        bars_500,
        {"rsi": True},
        timeframe="second-label",
    )

    assert first["timeframe"] == "first-label"
    assert second["timeframe"] == "second-label"
    assert first["rsi"] == second["rsi"]
