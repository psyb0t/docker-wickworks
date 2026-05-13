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

from .indicators import add_all
from .registry import INDICATORS, RECENT_TAGGABLE, Context
from .requirements import required_bars

log = logging.getLogger("wickworks.compute")


class UnknownIndicatorError(ValueError):
    """Raised when a request references an indicator that's not registered."""


class InsufficientBarsError(ValueError):
    """Raised when one or more requested indicators need more bars than provided.

    Carries the structured per-indicator deficit list so the HTTP layer can
    surface exactly which output keys are under-fed and by how much.
    """

    def __init__(self, available: int, deficits: list[dict[str, Any]]) -> None:
        self.available = available
        self.deficits = deficits
        summary = ", ".join(
            f"{d['outputKey']} (type={d['type']}) needs {d['required']}"
            for d in deficits
        )
        super().__init__(
            f"insufficient bars: have {available}, but: {summary}"
        )


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
) -> dict[str, Any]:
    """Run only the requested primitives.

    Raises:
        UnknownIndicatorError: if a requested indicator type is not registered.
        InsufficientBarsError: if any requested indicator needs more bars
            than were supplied. The error lists every deficit so the caller
            sees the whole picture in one shot, not whack-a-mole.
    """
    available = 0 if df is None else len(df)

    # Pre-flight: resolve every spec, ensure it's a known indicator, and
    # check its per-indicator bar requirement. Collect ALL deficits before
    # erroring so the caller gets a complete picture in one response.
    plan: list[tuple[str, str, dict[str, Any]]] = []
    deficits: list[dict[str, Any]] = []
    for output_key, spec in indicators.items():
        type_, params = _normalize_spec(output_key, spec)
        if type_ not in INDICATORS:
            raise UnknownIndicatorError(
                f"unknown indicator type {type_!r} for output {output_key!r}"
            )
        plan.append((output_key, type_, params))
        need = required_bars(type_, params)
        if available < need:
            deficits.append({
                "outputKey": output_key,
                "type": type_,
                "required": need,
                "available": available,
            })
    if deficits:
        raise InsufficientBarsError(available, deficits)

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

    for output_key, type_, params in plan:
        fn = INDICATORS[type_]
        try:
            value = fn(ctx, params)
        except Exception:
            log.exception("indicator %s (type=%s) failed", output_key, type_)
            raise

        if type_ in RECENT_TAGGABLE and isinstance(value, list):
            value = _tag_recent(value, RECENT_TAGGABLE[type_], recent_threshold)

        result[output_key] = value

    return result
