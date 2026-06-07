"""Tests for the metadata catalog + lookup fallback rules + /metadata route.

Coverage rules:
  - Every key in registry.INDICATORS has a top-level metadata entry.
  - Every metadata entry has the required shape (label/displayName/
    description/interpretation/unit/category).
  - The lookup() helper applies the three fallback rules
    (exact → strip array indices → bare-leaf).
  - The /metadata FastAPI route returns the catalog wrapped in
    {version, count, entries}.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from wickworks.metadata import (
    INDICATOR_METADATA,
    all_metadata,
    lookup,
)
from wickworks.registry import INDICATORS
from wickworks.server import app


_REQUIRED_FIELDS = {
    "label",
    "displayName",
    "description",
    "interpretation",
    "unit",
    "category",
}

_KNOWN_CATEGORIES = {
    "trend",
    "momentum",
    "volatility",
    "volume",
    "smc",
    "range",
    "summary",
    "structure",
}


class TestCoverage:
    def test_every_registry_indicator_has_metadata(self) -> None:
        # Every top-level key the registry can emit MUST have a label so the
        # FE never hits a "no metadata" path for first-class indicators.
        missing = [name for name in INDICATORS if name not in INDICATOR_METADATA]
        assert missing == [], f"Registry indicators without metadata: {missing}"

    def test_every_entry_has_required_fields(self) -> None:
        bad: list[str] = []
        for path, entry in INDICATOR_METADATA.items():
            keys = set(entry.keys())
            if not _REQUIRED_FIELDS.issubset(keys):
                bad.append(f"{path}: missing {_REQUIRED_FIELDS - keys}")
        assert bad == [], "\n".join(bad)

    def test_every_entry_field_is_a_string(self) -> None:
        # Catch accidental None / int / list values that would crash a
        # consumer expecting strings.
        bad: list[str] = []
        for path, entry in INDICATOR_METADATA.items():
            for field in _REQUIRED_FIELDS:
                v = entry.get(field)
                if not isinstance(v, str):
                    bad.append(f"{path}.{field}: {type(v).__name__} (expected str)")
        assert bad == [], "\n".join(bad)

    def test_category_values_are_from_known_set(self) -> None:
        bad: list[str] = []
        for path, entry in INDICATOR_METADATA.items():
            cat = entry.get("category", "")
            if cat not in _KNOWN_CATEGORIES:
                bad.append(f"{path}: category={cat!r}")
        assert bad == [], "\n".join(bad)


class TestLookup:
    def test_exact_match(self) -> None:
        # Simple top-level key.
        m = lookup("rsi")
        assert m is not None
        assert m["label"] == "RSI"

    def test_dot_path_exact_match(self) -> None:
        # Nested sub-field.
        m = lookup("momentum.macdHist")
        assert m is not None
        assert "MACD" in m["displayName"]

    def test_array_index_strip(self) -> None:
        # `retracements[42].Direction` should fall back to
        # `retracements[].Direction` because indices vary per response but
        # the metadata describes the field shape.
        m = lookup("retracements[42].Direction")
        assert m is not None
        assert m["label"] == "Dir"
        assert "leg" in m["description"].lower() or "leg" in m["interpretation"].lower()

    def test_bare_leaf_fallback(self) -> None:
        # A path the catalog hasn't enumerated as a full dotted entry but
        # whose leaf name is a known top-level indicator (e.g. some
        # consumer-side wrapping like `prevTimeframe.rsi`) should still
        # resolve to the RSI entry.
        m = lookup("prevTimeframe.rsi")
        assert m is not None
        assert m["label"] == "RSI"

    def test_unknown_returns_none(self) -> None:
        assert lookup("totally.made.up.field") is None
        assert lookup("") is None or isinstance(lookup(""), dict)  # tolerant


class TestRouteEndpoint:
    def test_metadata_route_shape(self) -> None:
        client = TestClient(app)
        r = client.get("/metadata")
        assert r.status_code == 200
        body = r.json()
        assert body["version"] == 1
        assert body["count"] == len(INDICATOR_METADATA)
        assert "entries" in body
        # Sanity-spot a couple of known keys.
        assert "rsi" in body["entries"]
        assert "retracements[].Direction" in body["entries"]
        assert body["entries"]["rsi"]["label"] == "RSI"

    def test_metadata_matches_function_helper(self) -> None:
        # Route returns the same data the helper builds — no drift.
        client = TestClient(app)
        body = client.get("/metadata").json()
        assert body == all_metadata()
