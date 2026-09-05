"""Shared Wickworks domain constants."""

from __future__ import annotations

PREVIOUS_PERIOD_FREQUENCIES = {
    "15m": "15min",
    "15min": "15min",
    "30m": "30min",
    "30min": "30min",
    "1H": "h",
    "1h": "h",
    "4H": "4h",
    "4h": "4h",
    "1D": "D",
    "1d": "D",
    "1W": "W-SUN",
    "1w": "W-SUN",
    "1M": "M",
    "1ME": "M",
}

SUPPORTED_SESSIONS = frozenset(
    {
        "Sydney",
        "Tokyo",
        "London",
        "New York",
        "Asian kill zone",
        "London open kill zone",
        "New York kill zone",
        "london close kill zone",
        "Custom",
    }
)
