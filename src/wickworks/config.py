"""Env-driven service config."""

from __future__ import annotations

import os


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO").upper()
MAX_BARS: int = _int_env("MAX_BARS", 5000)
MIN_BARS: int = _int_env("MIN_BARS", 50)
WORKERS: int = _int_env("WORKERS", 2)
