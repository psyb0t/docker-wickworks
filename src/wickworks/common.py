"""Shared utilities used across the package."""

from __future__ import annotations

import re
from typing import Union

_DURATION_RE = re.compile(r"(\d+)\s*([hms])", re.IGNORECASE)
_UNIT_SECONDS = {"h": 3600, "m": 60, "s": 1}


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
