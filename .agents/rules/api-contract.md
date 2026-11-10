# API contract

Applies to `src/wickworks/server.py`, `mcp_server.py`, `schemas.py`, `compute.py`, `validation.py`, `requirements.py`, `registry.py`, `smc.py`, `metadata.py` and `schema.json`.

- The response holds `symbol`, `timeframe`, `candles` and exactly the output keys the request named. Never add an output the caller did not ask for.
- Every response key is camelCase. `server.py` and `mcp_server.py` both run `json.dumps(..., cls=NumpyEncoder)` and then `_camelize_keys`. Keep the two paths identical, so REST and MCP return the same bytes for the same input.
- NaN and infinity never reach the wire. Series go through `registry._series` (`safe_float(decimals=None)`), event fields through `safe_float`. Do not round prices in series: crypto prices sit far below `1e-6`.
- Wickworks returns measurements, never trading signals. No buy/sell tags, divergence or crossover events. Descriptions in `metadata.py`, `schema.json` and the docs state what an algorithm detected, not what price will do.
- REST status codes: 422 for Pydantic schema failures (FastAPI validates the whole body before the handler runs), then in the handler 413 when `len(bars) > MAX_BARS`, 400 for empty `bars` or `indicators`, unknown type, invalid params and insufficient bars, 500 with the fixed detail `indicator computation failed` for anything else. The insufficient-bars body is `{"detail": {"error": "insufficient_bars", "message", "available", "deficits"}}` and lists every deficit at once.
- MCP tools raise `ValueError` for every failure; the SDK turns it into an `isError` result. MCP `compute` validates through `ComputeRequest`, so REST and MCP accept the same input.
- Adding an indicator means, in one change: the function in `registry.INDICATORS`, its allowed params in `validation._PARAMS_BY_INDICATOR` (camelCase name plus any snake_case alias), positive-integer or positive-number checks, a bar requirement in `requirements.REQUIREMENTS`, a top-level entry and sub-field entries in `metadata.py`, its request and output definitions in `schema.json`, tests, the docs pages and the skill's indicator list.
- `validate_indicator_params` rejects unknown parameter names. Never accept and ignore a parameter.
- SMC objects and summaries read from `Context.analysis()`, which runs at most once per request. Do not call `add_all` or `smc.analyze` from a registry function directly; `tests/test_correctness_contract.py` counts the analysis runs.
- Structural objects carry `originAt`, `confirmedAt` and `observedAsOf` (snake_case in `smc.py`). A new structural object gets the same three timestamps.
- `GET /metadata` and the MCP `metadata` tool return `{"version": 1, "count", "entries"}`. Bump `version` only for a breaking change to the catalog shape.
- A breaking request or response change is called out in the CHANGELOG entry of the release that makes it.
