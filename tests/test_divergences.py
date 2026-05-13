"""Divergence detection — divergences + divTrends.

These are signal-tagged outputs: every item carries `isRecent` (bool) and
`id` (sha256 hex). The tag is computed by the response builder and must
appear on every emitted item.
"""

from __future__ import annotations

from typing import Any

import pytest

from _helpers import post  # type: ignore[import-not-found]


@pytest.fixture(scope="module")
def divergence_response(eurusd_h1_fixture: dict[str, Any]) -> dict[str, Any]:
    return post(
        eurusd_h1_fixture["bars"], {"divergences": True, "divTrends": True}
    )


@pytest.mark.parametrize("indicator", ["divergences", "divTrends"])
def test_divergence_outputs_are_lists(
    divergence_response: dict[str, Any], indicator: str
) -> None:
    assert isinstance(divergence_response[indicator], list)


@pytest.mark.parametrize("indicator", ["divergences", "divTrends"])
def test_divergence_items_carry_signal_tags(
    divergence_response: dict[str, Any], indicator: str
) -> None:
    for item in divergence_response[indicator]:
        assert "isRecent" in item and isinstance(item["isRecent"], bool)
        assert "id" in item and isinstance(item["id"], str) and len(item["id"]) == 64
