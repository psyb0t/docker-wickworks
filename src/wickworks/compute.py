"""Request dispatcher. Bars in, only-what-was-asked-for out.

Pure compute. No IO, no state, no scoring. The caller specifies which
indicators they want under which output names — the response mirrors that
shape exactly.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from .errors import InsufficientBarsError, InvalidIndicatorSpecError, UnknownIndicatorError
from .registry import INDICATORS, Context
from .requirements import required_bars
from .validation import validate_indicator_params

log = logging.getLogger("wickworks.compute")


def _normalize_spec(key: str, spec: Any) -> tuple[str, dict[str, Any]]:
    """Resolve (type, params) from a request entry.

    spec=True              -> (key, {})
    spec=dict              -> (spec.pop("type") or key, rest)
    """
    if spec is True:
        return key, {}
    if isinstance(spec, dict):
        params = dict(spec)
        type_ = params.pop("type", key)
        return str(type_), params
    raise InvalidIndicatorSpecError(
        f"indicator {key!r}: spec must be true or an object, got {type(spec).__name__}"
    )


def compute_dataframe(
    df: pd.DataFrame,
    indicators: dict[str, Any],
    timeframe: str = "",
    symbol: str = "",
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
        validate_indicator_params(output_key, type_, params)
        plan.append((output_key, type_, params))
        need = required_bars(type_, params)
        if available < need:
            deficits.append(
                {
                    "outputKey": output_key,
                    "type": type_,
                    "required": need,
                    "available": available,
                }
            )
    if deficits:
        raise InsufficientBarsError(available, deficits)

    ctx = Context(df, timeframe)

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

        result[output_key] = value

    return result
