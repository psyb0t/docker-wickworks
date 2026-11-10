---
title: "Architecture"
description: "How a wickworks request flows from FastAPI or MCP through validation, the indicator registry and the shared SMC analysis pass to camelCase JSON."
nav_order: 11
---

# Architecture

wickworks is one Python process: a FastAPI app with an MCP server mounted inside it. Nothing is stored and nothing is called over the network. A request is a pure function of its body.

```text
┌──────────────┐    ┌───────────────────────┐    ┌──────────────────────┐
│  your app    │───▶│  POST /  or MCP       │───▶│  ComputeRequest      │
│  (any lang)  │    │  compute              │    │  validation          │
└──────────────┘    └───────────────────────┘    └──────────┬───────────┘
                                                            │
                                                            ▼
┌──────────────┐    ┌───────────────────────┐    ┌──────────────────────┐
│  camelCase   │◀───│  registry functions   │◀───│  pre-flight: types,  │
│  JSON        │    │  pandas-ta, SMC pass  │    │  params, min bars    │
└──────────────┘    └───────────────────────┘    └──────────────────────┘
```

## Request path

1. **Entry.** [`server.py`](https://github.com/psyb0t/docker-wickworks/blob/main/src/wickworks/server.py) serves `POST /`; [`mcp_server.py`](https://github.com/psyb0t/docker-wickworks/blob/main/src/wickworks/mcp_server.py) serves the MCP `compute` tool. Both validate the body with the same Pydantic model, `ComputeRequest` in [`schemas.py`](https://github.com/psyb0t/docker-wickworks/blob/main/src/wickworks/schemas.py), and check `MAX_BARS` and that `bars` and `indicators` are not empty. REST validates first (FastAPI does it before the handler runs); MCP checks the counts first.
2. **Pre-flight.** `compute_dataframe` in [`compute.py`](https://github.com/psyb0t/docker-wickworks/blob/main/src/wickworks/compute.py) turns each entry of `indicators` into a type and parameters, rejects unknown types, checks the parameters ([`validation.py`](https://github.com/psyb0t/docker-wickworks/blob/main/src/wickworks/validation.py)), and works out each one's minimum bars ([`requirements.py`](https://github.com/psyb0t/docker-wickworks/blob/main/src/wickworks/requirements.py)). It collects every shortfall before failing, so one error lists them all. Nothing is computed until every entry passes.
3. **Compute.** Each entry runs its function from `INDICATORS` in [`registry.py`](https://github.com/psyb0t/docker-wickworks/blob/main/src/wickworks/registry.py). Series indicators call `pandas-ta` on the bar columns directly. SMC objects and summaries read from the shared analysis pass.
4. **Serialize.** The result goes through `NumpyEncoder`, so numpy and pandas scalars become plain JSON, and every key is rewritten to camelCase. `NaN` and infinity were already turned into `null`.

REST runs the computation in FastAPI's thread pool; MCP runs it with `asyncio.to_thread`. Either way a slow request does not block others in the same worker.

## The shared analysis pass

Order blocks, FVGs, BOS/CHoCH, swing levels, S/R levels, the recent range and the six summaries all come from one analysis of the full history. A per-request `Context` object runs it the first time an output needs it and keeps the result for the rest of the request.

The pass first adds a fixed set of columns to the bar table ([`indicators/`](https://github.com/psyb0t/docker-wickworks/tree/main/src/wickworks/indicators)): EMA 21, SMA 50/100/200, ATR 14, RSI 14, MACD, Bollinger, MFI, Stochastic, ADX, VWAP, Donchian, volume ratios and OBV, the `smartmoneyconcepts` swing, order block, FVG and BOS/CHoCH columns, and a 7-bar swing structure. [`smc.py`](https://github.com/psyb0t/docker-wickworks/blob/main/src/wickworks/smc.py) then builds the objects and summaries from those columns.

`liquidity`, `previousHighLow`, `sessions` and `retracements` take parameters, so they call `smartmoneyconcepts` separately instead of using the pass.

## smc_fast

`smartmoneyconcepts` spends most of its time in Python loops. [`smc_fast.py`](https://github.com/psyb0t/docker-wickworks/blob/main/src/wickworks/smc_fast.py) replaces the library's `ob`, `fvg`, `bos_choch` and `swing_highs_lows` with numba-compiled versions when the `indicators` package is imported. It is a port of the MIT-licensed upstream code (see [`THIRD_PARTY.md`](https://github.com/psyb0t/docker-wickworks/blob/main/THIRD_PARTY.md)), and parity tests prove it returns the same values. Setting `DISABLE_SMC_FAST` turns the replacement off.

## Determinism

The same bars and indicators always produce the same response bytes. There is no randomness, clock or state in the computation, and the container runs `TZ=UTC`. The test suite checks determinism, that adding new bars does not change past values of causal indicators, and that requesting two outputs together gives the same values as requesting each alone.

Because of that, wickworks scales by adding replicas behind any load balancer, with no affinity.

## Why camelCase and null

Every consumer, whatever its language, gets one naming style and valid JSON. Python's `json` module would otherwise write `NaN` tokens that strict parsers reject. Series keep full float precision so very small prices survive; summaries round to six decimal places.

## Terms

| Term | Meaning |
| --- | --- |
| Output key | A key of `indicators` in the request, and the matching key in the response |
| Type | The indicator a spec runs: the key itself, or the spec's `type` field |
| Series | One value per bar, aligned with `bars` |
| Warmup | The leading bars of a series that are `null` because the indicator needs more history |
| Analysis pass | The single SMC and summary computation shared by a request |
