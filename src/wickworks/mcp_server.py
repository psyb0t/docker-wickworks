"""MCP server for wickworks — mounted at ``/mcp`` on the FastAPI app.

Exposes the same surface as the HTTP REST API as MCP tools so an agent can
drive wickworks over JSON-RPC / streamable-HTTP:

  - ``health``          — liveness + running version
  - ``list_indicators`` — the registered indicator types accepted by ``compute``
  - ``metadata``        — static catalog of labels/descriptions for every output path
  - ``compute``         — bars + indicator selection in, primitives out (mirrors ``POST /``)

Stateless by construction: every call is self-contained (bars in, primitives
out) — no server-side state, no files, no scoring, no opinions. Mirrors the REST
response envelope exactly (``NumpyEncoder`` then snake_case→camelCase keys).

Kept in a separate module so ``server.py`` can build + mount it without a
circular import. ``server.py`` calls ``build_mcp_server()`` at startup and mounts
the returned ASGI app under ``/mcp`` via FastMCP's streamable_http transport
(``streamable_http_path`` is ``"/"`` so the mount doesn't double-prefix).
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pandas as pd
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from numpyencoder import NumpyEncoder
from pydantic import ValidationError

from . import __version__, config
from .compute import InsufficientBarsError, UnknownIndicatorError, compute_dataframe
from .metadata import all_metadata
from .registry import INDICATORS
from .schemas import ComputeRequest


def _snake_to_camel(s: str) -> str:
    if "_" not in s:
        return s
    head, *rest = s.split("_")
    return head + "".join(p[:1].upper() + p[1:] for p in rest)


def _camelize_keys(obj: Any) -> Any:
    """Recursively rewrite dict keys snake_case -> camelCase — the same transform
    the REST layer applies, so MCP responses are byte-for-byte the REST shape."""
    if isinstance(obj, dict):
        return {_snake_to_camel(k): _camelize_keys(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_camelize_keys(x) for x in obj]
    return obj


def build_mcp_server() -> FastMCP:
    """Construct the FastMCP server. Mounted under ``/mcp`` so clients connect to
    ``/mcp`` directly (``streamable_http_path`` is ``"/"`` so the mount at
    ``/mcp`` doesn't double-prefix)."""
    mcp = FastMCP(
        name="wickworks",
        instructions=(
            "Stateless OHLC primitives service. Feed it candlestick bars plus a "
            "selection of technical indicators / Smart-Money-Concepts objects "
            "and it returns the computed primitives — no scoring, no opinions, "
            "no state. Call list_indicators for the indicator types you can "
            "request, metadata for the human-readable catalog of every output "
            "path, then compute with your bars. Every call is self-contained."
        ),
        stateless_http=True,
        json_response=True,
        # wickworks is a headless, self-hosted HTTP service that operators front
        # with their own reverse proxy / auth and reach at an arbitrary Host (the
        # MCP bridge points WICKWORKS_URL at it). The SDK's DNS-rebinding Host
        # allowlist is a browser-localhost mitigation that doesn't fit that model
        # and would 421 every real-hostname deployment (empty allowed_hosts +
        # protection-on rejects all) — disable it and let the operator's proxy own
        # network-level access control.
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=False,
        ),
    )
    mcp.settings.streamable_http_path = "/"

    @mcp.tool()
    async def health() -> dict[str, Any]:
        """Liveness check + the running wickworks version."""
        return {"ok": True, "version": __version__}

    @mcp.tool()
    async def list_indicators() -> dict[str, Any]:
        """List the registered indicator types accepted by ``compute``'s
        ``indicators`` map. Each name is a valid spec key: ``spec=true`` runs
        the indicator with its defaults; a params object overrides them (include
        ``"type"`` to run a known indicator under a different output name). This
        is the indicator catalog only — Smart-Money-Concepts objects and derived
        levels have their own output paths; call ``metadata`` for the full set."""
        return {"indicators": sorted(INDICATORS.keys())}

    @mcp.tool()
    async def metadata() -> dict[str, Any]:
        """Static catalog of human-readable labels + descriptions for every
        output path ``compute`` can produce. Content is static for a given
        wickworks version — cache it and invalidate on the ``version`` field."""
        return all_metadata()

    @mcp.tool()
    async def compute(
        bars: list[dict[str, Any]],
        indicators: dict[str, Any],
        timeframe: str = "",
        symbol: str = "",
        recent_bars: int = 10,
    ) -> dict[str, Any]:
        """Compute indicators + SMC primitives from OHLC bars.

        ``bars``: list of ``{time (UTC unix seconds), open, high, low, close,
        tickVolume?, realVolume?}``. ``indicators``: map of output-name -> spec,
        where ``spec=true`` runs the indicator (keyed by name) with defaults, or
        a params object overrides them (include ``"type"`` to run a known
        indicator under a different output name). ``recent_bars``: signal-like
        outputs within this many bars of the end get ``isRecent=true``.
        ``symbol`` / ``timeframe`` are echoed back.

        Returns the primitives as JSON (camelCase keys) — the same envelope as
        the REST ``POST /`` (``symbol``, ``timeframe``, ``candles``, plus one
        entry per requested output name). Raises on unknown indicator, empty
        bars/indicators, too many bars, or insufficient bars for a requested
        indicator's warm-up.
        """
        if not bars:
            raise ValueError("bars must not be empty")
        if not indicators:
            raise ValueError("indicators must not be empty")
        if len(bars) > config.MAX_BARS:
            raise ValueError(f"too many bars: {len(bars)} > MAX_BARS={config.MAX_BARS}")

        # Validate/normalize through the same pydantic model the REST endpoint
        # uses, so tickVolume/tick_volume alias handling matches exactly.
        try:
            req = ComputeRequest.model_validate(
                {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "recent_bars": recent_bars,
                    "bars": bars,
                    "indicators": indicators,
                }
            )
        except ValidationError as exc:
            raise ValueError(f"invalid request: {exc}") from exc

        df = pd.DataFrame([b.model_dump() for b in req.bars])
        df["datetime"] = pd.to_datetime(df["time"], unit="s", utc=True)

        # compute_dataframe is CPU-bound (pandas / numba); run it off the event
        # loop so a slow compute doesn't stall other MCP requests. The REST layer
        # gets the same isolation for free via FastAPI's sync-endpoint threadpool.
        try:
            result = await asyncio.to_thread(
                compute_dataframe,
                df,
                indicators=req.indicators,
                timeframe=req.timeframe,
                symbol=req.symbol,
                recent_bars=req.recent_bars,
            )
        except UnknownIndicatorError as exc:
            raise ValueError(str(exc)) from exc
        except InsufficientBarsError as exc:
            raise ValueError(
                f"insufficient_bars: {exc} " f"(available={exc.available}, deficits={exc.deficits})"
            ) from exc

        # Match the REST envelope: NumpyEncoder round-trip then camelCase keys.
        body = json.dumps(result, cls=NumpyEncoder)
        return _camelize_keys(json.loads(body))

    return mcp
