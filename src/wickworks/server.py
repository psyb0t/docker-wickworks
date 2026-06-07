"""FastAPI HTTP layer.

Single root endpoint:  POST /   bars + indicators in, primitives out.
Health endpoint:       GET /health
"""

from __future__ import annotations

import json
import logging
from typing import Any

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from numpyencoder import NumpyEncoder

from . import __version__, config
from .compute import (
    InsufficientBarsError,
    UnknownIndicatorError,
    compute_dataframe,
)
from .metadata import all_metadata
from .schemas import ComputeRequest, HealthResponse


def _snake_to_camel(s: str) -> str:
    if "_" not in s:
        return s
    head, *rest = s.split("_")
    return head + "".join(p[:1].upper() + p[1:] for p in rest)


def _camelize_keys(obj: Any) -> Any:
    """Recursively rewrite dict keys snake_case -> camelCase. Values untouched."""
    if isinstance(obj, dict):
        return {_snake_to_camel(k): _camelize_keys(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_camelize_keys(x) for x in obj]
    return obj


logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("wickworks")

app = FastAPI(
    title="wickworks",
    version=__version__,
    description=(
        "Stateless OHLC primitives service. Bars + indicator selection in, "
        "primitives out. No scoring, no opinions."
    ),
)


@app.get("/health", response_model=HealthResponse)
def health() -> dict[str, Any]:
    return {"ok": True, "version": __version__}


@app.get("/metadata")
def metadata() -> dict[str, Any]:
    """Static catalog of human-readable labels + descriptions for every
    output path the compute endpoint can produce.

    Consumers (frontends, report builders) should fetch this once on startup
    and cache it — the content is static for a given wickworks version. Use
    the `version` field in the response to invalidate the cache after a
    wickworks upgrade.

    See src/wickworks/metadata.py for the lookup-fallback rules consumers
    should apply when a path isn't an exact match (array-index strip,
    bare-leaf fallback).
    """
    return all_metadata()


@app.post("/")
def compute(req: ComputeRequest) -> JSONResponse:
    if len(req.bars) > config.MAX_BARS:
        raise HTTPException(
            status_code=413,
            detail=f"too many bars: {len(req.bars)} > MAX_BARS={config.MAX_BARS}",
        )
    if not req.bars:
        raise HTTPException(status_code=400, detail="bars must not be empty")
    if not req.indicators:
        raise HTTPException(status_code=400, detail="indicators must not be empty")

    df = pd.DataFrame([b.model_dump() for b in req.bars])
    df["datetime"] = pd.to_datetime(df["time"], unit="s", utc=True)

    try:
        result = compute_dataframe(
            df,
            indicators=req.indicators,
            timeframe=req.timeframe,
            symbol=req.symbol,
            recent_bars=req.recent_bars,
        )
    except UnknownIndicatorError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except InsufficientBarsError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "insufficient_bars",
                "message": str(e),
                "available": e.available,
                "deficits": e.deficits,
            },
        ) from e
    except Exception as e:
        log.exception("compute failed for %s %s", req.symbol, req.timeframe)
        raise HTTPException(status_code=500, detail=f"compute failed: {e}") from e

    body = json.dumps(result, cls=NumpyEncoder)
    return JSONResponse(content=_camelize_keys(json.loads(body)))
