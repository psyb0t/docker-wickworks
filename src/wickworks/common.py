"""Shared utilities used across the package."""

from __future__ import annotations

import re
from typing import Any, Union

import pandas as pd

_DURATION_RE = re.compile(r"(\d+)\s*([hms])", re.IGNORECASE)
_UNIT_SECONDS = {"h": 3600, "m": 60, "s": 1}


def find_col(df: pd.DataFrame, prefix: str) -> str | None:
    """First column starting with `prefix`, or None. Pandas_ta suffixes column
    names with their parameters (e.g. ``STOCHk_14_3_3``), so callers match by
    prefix to stay robust against length changes."""
    for c in df.columns:
        if c.startswith(prefix):
            return c
    return None


def safe_float(val: Any, decimals: int | None = 6) -> float | None:
    """Convert val to float, returning None for NaN / ±Inf / unconvertible.

    Rounds to `decimals` (default 6) so indicator outputs round-trip cleanly
    through JSON without 14-digit precision tails that bloat payloads and
    break diffs. Pass ``decimals=None`` to skip rounding — needed for crypto
    prices where significant digits live below 1e-6 (e.g. SHIB at ~1e-8,
    micro-cap tokens at ~1e-15) and rounding to 6 decimals would silently
    floor them to 0."""
    try:
        f = float(val)
    except (TypeError, ValueError):
        return None
    if f != f or f == float("inf") or f == float("-inf"):
        return None
    if decimals is None:
        return f
    return round(f, decimals)


def parse_duration(value: Union[str, int, float, None]) -> int:
    """Parse a Go-style duration string into seconds.

    Accepts ``"6h32m11s"``, ``"-5h"``, ``"-1h30m"``, ``"30m"``, a bare
    ``"3600"``, or a numeric value (returned as int). A leading sign applies
    to the whole expression (Go semantics). Returns 0 for None / empty.
    """
    if value is None or value == "":
        return 0
    if isinstance(value, (int, float)):
        return int(value)

    s = str(value).strip()
    if not s:
        return 0

    sign = 1
    if s[0] in "+-":
        if s[0] == "-":
            sign = -1
        s = s[1:].strip()

    try:
        return sign * int(s)
    except ValueError:
        pass

    total = 0
    matched = 0
    pos = 0
    for m in _DURATION_RE.finditer(s):
        if m.start() != pos:
            raise ValueError(f"invalid duration: {value!r}")
        total += int(m.group(1)) * _UNIT_SECONDS[m.group(2).lower()]
        matched += 1
        pos = m.end()
    if matched == 0 or pos != len(s):
        raise ValueError(f"invalid duration: {value!r}")
    return sign * total
