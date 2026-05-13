"""Tests for wickworks.common utilities."""

from __future__ import annotations

import pytest

from wickworks.common import parse_duration


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, 0),
        ("", 0),
        (0, 0),
        (3600, 3600),
        (3600.5, 3600),
        ("3600", 3600),
        ("-3600", -3600),
        ("5s", 5),
        ("30m", 1800),
        ("6h", 21600),
        ("6h32m11s", 6 * 3600 + 32 * 60 + 11),
        ("-5h", -5 * 3600),
        ("-1h30m", -(3600 + 1800)),
        ("+2h", 7200),
        ("1H30M", 5400),
    ],
)
def test_parse_duration_valid(value, expected: int) -> None:
    assert parse_duration(value) == expected


@pytest.mark.parametrize("bad", ["banana", "5x", "5h30", "h", "5 30m", "5h-30m"])
def test_parse_duration_invalid(bad: str) -> None:
    with pytest.raises(ValueError):
        parse_duration(bad)
