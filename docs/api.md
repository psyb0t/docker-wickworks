---
title: "REST API"
description: "The wickworks HTTP API: GET /health, GET /metadata and POST /, the bar and indicator request shapes, the response envelope and every error status."
nav_order: 4
---

# REST API

Three endpoints, no authentication, JSON in and out. Every field name in a response is camelCase. The machine-readable contract is [`schema.json`](https://github.com/psyb0t/docker-wickworks/blob/main/schema.json), a JSON Schema (Draft 2020-12) covering the request, every indicator's parameters and every output shape. This page is the human version.

The same operations are available over MCP; see [MCP server](mcp.md).

## GET /health

```bash
curl -s http://localhost:8000/health
```

```json
{
  "ok": true,
  "version": "0.7.1"
}
```

`version` is the installed package version. The Docker healthcheck calls this endpoint.

## GET /metadata

Returns a static catalog with a label, description and unit for every output path `POST /` can produce. A frontend or report builder can fetch it once and cache it for the running version.

```bash
curl -s http://localhost:8000/metadata
```

```json
{
  "version": 1,
  "count": 198,
  "entries": {
    "rsi": {
      "label": "RSI",
      "displayName": "Relative Strength Index",
      "description": "Ratio of average gains to average losses over the lookback window.",
      "interpretation": ">70 overbought (potential reversal lower); <30 oversold (potential bounce). 50 = no edge. Divergences with price flag exhaustion.",
      "unit": "0–100",
      "category": "momentum"
    }
  }
}
```

`version` is the catalog format version, not the service version. Keys in `entries` are dot paths into a response: a top-level output (`rsi`, `orderBlocks`), a field of a compound output (`macd.hist`, `momentum.macdHist`), or a field inside array elements (`orderBlocks[].type`). `category` is one of `trend`, `momentum`, `volatility`, `volume`, `smc`, `range`, `summary`, `structure`.

To look up a path from a live response, try in this order:

1. The exact path (`momentum.macdHist`).
2. The path with array indexes replaced by `[]` (`retracements[42].Direction` becomes `retracements[].Direction`).
3. The last segment on its own (`macdHist`).

The keys follow output types, not your output names. A custom output name such as `rsi21` is looked up through its type, `rsi`.

## POST /

Send bars and the indicators you want. The response holds only what you asked for.

```bash
curl -s -X POST http://localhost:8000/ \
  -H 'Content-Type: application/json' \
  -d @request.json
```

with `request.json`:

```json
{
  "symbol": "EURUSD",
  "timeframe": "H1",
  "bars": [
    {
      "time": 1700000000,
      "open": 1.0832,
      "high": 1.0851,
      "low": 1.0828,
      "close": 1.0844,
      "volume": 1247
    }
  ],
  "indicators": {
    "rsi": true,
    "rsi21": {
      "type": "rsi",
      "length": 21
    },
    "stochFast": {
      "type": "stoch",
      "k": 5,
      "d": 3,
      "smoothK": 3
    },
    "macd": true,
    "orderBlocks": true
  }
}
```

The `bars` array above shows one bar to keep the example short. A real request needs enough bars for every indicator it names; see [insufficient bars](#insufficient-bars).

### Request fields

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `bars` | array of bars | yes | OHLCV bars, oldest first. At most `MAX_BARS` (default 5000). |
| `indicators` | object | yes | Output name to spec, at least one entry. See [the indicators object](#the-indicators-object). |
| `symbol` | string | no | Your instrument label, up to 128 characters. Echoed back unchanged. Default `""`. |
| `timeframe` | string | no | Your chart interval label, such as `H4`, up to 32 characters. Echoed back unchanged. wickworks does not parse it and never resamples bars; calculations use only the bar values and timestamps. Default `""`. |

Any other top-level field is rejected with 422.

### Bars

| Field | Type | Rules |
| --- | --- | --- |
| `time` | integer | UTC unix seconds, `>= 0`. Strictly increasing across the array, so no duplicates and no out-of-order bars. |
| `open`, `high`, `low`, `close` | number | Finite and greater than 0. `low <= open <= high`, `low <= close <= high`. |
| `volume` | number | Required. Finite and `>= 0`. |

`volume` is whatever activity series you choose: exchange volume, tick volume, trade count. wickworks treats it as one number per bar and does not interpret it. Fields other than these six are rejected with 422, which includes the `tickVolume` and `realVolume` fields older versions accepted.

### The indicators object

Each entry maps an output name (the key) to a spec:

- `true` runs the indicator with default parameters. The key is also the indicator type.
- `{ ...params }` runs the indicator named by the key with those parameters.
- `{ "type": "<name>", ...params }` runs the indicator `<name>` under your own output name. This is how you run the same indicator several times with different settings.

```json
{
  "rsi": true,
  "rsi21": {
    "type": "rsi",
    "length": 21
  },
  "stochA": {
    "type": "stoch",
    "k": 5,
    "d": 3
  },
  "stochB": {
    "type": "stoch",
    "k": 21,
    "d": 7
  }
}
```

The response contains `rsi`, `rsi21`, `stochA` and `stochB`. A JSON object cannot hold the same key twice, so output names never collide.

Parameters are checked before anything is computed. An unknown parameter name, a wrong type, a non-positive length or an inconsistent combination (MACD `fast` not below `slow`, for example) is a 400 that names the output key. Most parameters also accept a snake_case spelling (`smooth_k` for `smoothK`); the [indicator reference](indicators.md) and [SMC page](smc.md) list both. The full list of types is on those two pages, and `GET /metadata` or the MCP `list_indicators` tool returns it at runtime.

### Response

```json
{
  "symbol": "EURUSD",
  "timeframe": "H1",
  "candles": 300,
  "rsi": [null, null, 61.662137478335254, 60.9187902109813],
  "stochFast": {
    "k": [null, 27.734488750099562],
    "d": [null, 32.72630473499031]
  },
  "macd": {
    "macd": [null, 0.0011595122874938912],
    "signal": [null, 0.0010061843242014739],
    "hist": [null, 0.00015332796329241738]
  },
  "orderBlocks": [
    {
      "type": "bearish",
      "top": 1.1762299999999999,
      "bottom": 1.17388,
      "candleIdx": 136,
      "time": 1776834000,
      "originAt": 1776834000,
      "confirmedAt": 1776866400,
      "observedAsOf": 1777593600,
      "mitigatedWickAt": null,
      "mitigatedCloseAt": null,
      "distancePct": 0.097,
      "mitigatedWick": false,
      "mitigatedClose": false,
      "touchCount": 3,
      "touchEvents": [1, 8, 74, 157]
    }
  ]
}
```

The arrays are cut short here; a real series has one value per bar.

| Field | Type | Description |
| --- | --- | --- |
| `symbol` | string | Echo of the request field |
| `timeframe` | string | Echo of the request field |
| `candles` | integer | Number of bars processed |
| one key per requested output | varies | The output's return shape, documented per indicator |

### Value shapes

Most outputs use one of these:

- **Series:** an array with one `number` or `null` per input bar, aligned with `bars`. Positions before the indicator has enough history (the warmup) are `null`.
- **Flag series:** one value per bar, `0` or `1`.
- **Direction series:** one value per bar, `1` for bullish or long and `-1` for bearish or short.

Flag and direction values come out of floating-point columns, so a JSON encoder writes them as `1.0`, `0.0` and `-1.0`. Compare them as numbers.

`NaN` and infinity never appear in a response. They become `null`. Series values keep full float precision, so prices far below `1e-6` survive; the summaries round to six decimal places.

## Errors

| Status | When |
| --- | --- |
| 400 | `bars` is empty, `indicators` is empty, an indicator type is unknown, a parameter is unknown or invalid, or there are too few bars for one or more requested indicators |
| 413 | More than `MAX_BARS` bars |
| 422 | The body fails schema validation: a missing or extra field, a wrong type, a non-positive or non-finite price, bad candle geometry, bar times not strictly increasing, or a spec that is neither `true` nor an object |
| 500 | An indicator failed while computing. The body is `{"detail": "indicator computation failed"}` and the server log holds the traceback |

FastAPI validates the whole body before wickworks sees it, so a malformed request gets 422 even when it also has too many bars. Every message is listed with its fix on the [troubleshooting page](troubleshooting.md).

400, 413 and 500 bodies carry a string `detail`:

```json
{
  "detail": "indicator 'macd': fast must be less than slow"
}
```

422 bodies are FastAPI's standard list of validation errors, each with a `loc` path and a `msg`:

```json
{
  "detail": [
    {
      "type": "extra_forbidden",
      "loc": ["body", "bars", 5, "tickVolume"],
      "msg": "Extra inputs are not permitted",
      "input": 3
    }
  ]
}
```

### Insufficient bars

Every indicator needs a minimum number of bars before it can produce a value at the last bar. wickworks checks every requested output before computing anything. If any is short, the request fails with 400 and a body that lists every short output at once, so you can fix the whole request in one go:

```json
{
  "detail": {
    "error": "insufficient_bars",
    "message": "insufficient bars: have 30, but: slowSma (type=sma) needs 200, longRsi (type=rsi) needs 51",
    "available": 30,
    "deficits": [
      {
        "outputKey": "slowSma",
        "type": "sma",
        "required": 200,
        "available": 30
      },
      {
        "outputKey": "longRsi",
        "type": "rsi",
        "required": 51,
        "available": 30
      }
    ]
  }
}
```

The minimum comes from the parameters: `sma` needs `length` bars, `rsi` needs `length + 1`, `macd` needs `slow + signal`. The [indicator reference](indicators.md) lists the rule for each type. Every SMC output and every summary needs `MIN_BARS` (default 50), because the shared analysis behind them assumes a real history.

Meeting the minimum guarantees a value at the last bar, not a fully populated series. Earlier positions stay `null` through the warmup.
