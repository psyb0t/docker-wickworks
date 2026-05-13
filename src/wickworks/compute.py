"""Request dispatcher. Bars in, only-what-was-asked-for out.

Pure compute. No IO, no state, no scoring. The caller specifies which
indicators they want under which output names — the response mirrors that
shape exactly.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

import pandas as pd
from numpyencoder import NumpyEncoder

from .config import MIN_BARS
from .indicators import add_all
from .registry import INDICATORS, RECENT_TAGGABLE, Context

log = logging.getLogger("wickworks.compute")


class UnknownIndicatorError(ValueError):
    """Raised when a request references an indicator that's not registered."""


def _normalize_spec(key: str, spec: Any) -> tuple[str, dict[str, Any]]:
    """Resolve (type, params) from a request entry.

    spec=True / spec=None  -> (key, {})
    spec=dict              -> (spec.pop("type") or key, rest)
    """
    if spec is True or spec is None:
        return key, {}
    if isinstance(spec, dict):
        params = dict(spec)
        type_ = params.pop("type", key)
        return str(type_), params
    raise ValueError(f"indicator {key!r}: spec must be true or an object, got {type(spec).__name__}")


def _tag_recent(items: list[dict[str, Any]], end_bar_key: str, threshold: int) -> list[dict[str, Any]]:
    for e in items:
        end_bar = e.get(end_bar_key)
        e["is_recent"] = bool(end_bar is not None and end_bar >= threshold)
        e["id"] = hashlib.sha256(
            json.dumps(e, sort_keys=True, cls=NumpyEncoder).encode()
        ).hexdigest()
    return items


def compute_dataframe(
    df: pd.DataFrame,
    indicators: dict[str, Any],
    timeframe: str = "",
    symbol: str = "",
    recent_bars: int = 10,
) -> dict[str, Any] | None:
    """Run only the requested primitives. Returns None if too few bars."""
    if df is None or len(df) < MIN_BARS:
        return None

    # Indicator columns + bar states are cheap and required by SMC/signals.
    # We always compute them upfront; the registry projects the requested
    # outputs from the resulting rich DataFrame.
    df = add_all(df)

    ctx = Context(df, timeframe)
    last_idx = len(df) - 1
    recent_threshold = last_idx - recent_bars

    result: dict[str, Any] = {
        "symbol": symbol,
        "timeframe": timeframe,
        "candles": len(df),
    }

    for output_key, spec in indicators.items():
        type_, params = _normalize_spec(output_key, spec)
        fn = INDICATORS.get(type_)
        if fn is None:
            raise UnknownIndicatorError(
                f"unknown indicator type {type_!r} for output {output_key!r}"
            )
        try:
            value = fn(ctx, params)
        except Exception:
            log.exception("indicator %s (type=%s) failed", output_key, type_)
            raise

        if type_ in RECENT_TAGGABLE and isinstance(value, list):
            value = _tag_recent(value, RECENT_TAGGABLE[type_], recent_threshold)

        result[output_key] = value

    return result
