---
title: "Troubleshooting"
description: "Every wickworks error message with its cause and fix: insufficient bars, too many bars, unknown indicators and parameters, bar validation and MCP errors."
nav_order: 10
---

# Troubleshooting

Each entry gives the message as wickworks sends it, what causes it, and the fix. Over REST the message is in `detail`; over [MCP](mcp.md) the same text comes back in an `isError` result, prefixed with `Error executing tool compute:`.

## 400: insufficient bars

```text
insufficient bars: have 30, but: slowSma (type=sma) needs 200, longRsi (type=rsi) needs 51
```

One or more requested indicators need more history than you sent. The 400 body also has a `deficits` array with `outputKey`, `type`, `required` and `available` for each one; see [insufficient bars](api.md#insufficient-bars).

Fix: send at least the largest `required` value, or shorten the indicator's lengths. Every SMC output and summary needs `MIN_BARS` (default 50).

## 400: unknown indicator type

```text
unknown indicator type 'foo' for output 'foo'
```

The output key, or its `type`, is not a known indicator. Types are case sensitive: `orderBlocks`, not `orderblocks`. A key you invent as an output name needs a `type`:

```json
{
  "fastRsi": {
    "type": "rsi",
    "length": 7
  }
}
```

Fix: use a name from the [indicator reference](indicators.md) or [SMC page](smc.md), or call the MCP `list_indicators` tool.

## 400: unknown parameters

```text
indicator 'rsi': unknown parameters: len
```

The spec has a parameter the indicator does not take. wickworks rejects it instead of ignoring it, so a typo never runs with the default by accident.

Fix: use the parameter names from the indicator's table. Remember `type` is not a parameter of the indicator; everything else in the object is.

## 400: invalid parameter values

```text
indicator 'macd': fast must be less than slow
```

Other messages of this kind:

- `<name> must be a positive integer` (lengths and windows)
- `<name> must be a positive finite number` (multipliers, `std`, `af`, `rangePercent`)
- `<name> must be a non-empty string`
- `sessionOffset is not a valid duration`
- `fast, medium, and slow must increase` (`uo`)
- `tenkan, kijun, and senkou must increase` (`ichimoku`)
- `step must not exceed max` (`psar`)
- `rangePercent must not exceed 1` (`liquidity`)
- `timeFrame must be one of: ...` (`previousHighLow`)
- `session must be one of: ...` (`sessions`)
- `startTime must use UTC HH:MM`, `endTime must use UTC HH:MM`
- `Custom session requires startTime and endTime`
- `startTime and endTime are only valid for Custom session`

Each message starts with `indicator '<output key>':`, so you know which entry to fix.

## 400: empty bars or indicators

```text
bars must not be empty
```

```text
indicators must not be empty
```

Fix: send at least one bar and at least one indicator.

## 413: too many bars

```text
too many bars: 6000 > MAX_BARS=5000
```

Fix: send fewer bars, or raise [`MAX_BARS`](configuration.md) on the server.

## 422: bar validation

422 responses list each problem with its location. The common ones:

| `msg` | Cause |
| --- | --- |
| `Value error, bar times must be strictly increasing and unique` | Two bars share a `time`, or the bars are not oldest first |
| `Value error, high must be greater than or equal to low` | A bar has `high < low` |
| `Value error, open must be between low and high` | `open` lies outside the bar's range |
| `Value error, close must be between low and high` | `close` lies outside the bar's range |
| `Input should be greater than 0` | A price is zero or negative |
| `Input should be greater than or equal to 0` | `volume` is negative |
| `Field required` | A bar is missing a field, often `volume` |
| `Extra inputs are not permitted` | An unknown field, such as `tickVolume` or `realVolume` from before 0.7.0, or a top-level field such as `recentBars` |
| `Value error, indicator '<key>' must be true or an object` | A spec is `false`, a string or a number |

The `loc` array points at the field, for example `["body", "bars", 5, "tickVolume"]`.

Fix the data, or map your vendor's volume field to `volume` before sending.

Standard JSON cannot carry `NaN` or `Infinity`. Some encoders write them anyway as bare `NaN` and `Infinity` tokens. wickworks rejects such a value, but the 422 response then fails to serialize, and the client gets a plain-text `Internal Server Error` with status 500 instead. Drop or fill missing values before sending.

## 500: indicator computation failed

```text
indicator computation failed
```

An indicator raised an error that validation did not catch. The server log has the traceback, under `compute failed for <symbol> <timeframe>`.

One known cause: a `vwap` `anchor` other than `"D"`, `"W"` or `"M"` passes validation and then fails inside `pandas-ta`. Use one of those three. For anything else, open an issue with the request body.

## The first request is slow

The first request that needs SMC objects or summaries in a new container takes several seconds while numba compiles. Later requests are fast. See [scaling](deployment.md#scaling).

## /health reports 0.0.0+unknown

You are running the service from source with `make run`, where the package is not installed and has no version metadata. The Docker image reports the real version.

## An MCP client gets a redirect or 404

Use `http://<host>:8000/mcp` or `/mcp/`. Both work. A path such as `/mcp/mcp` does not. Clients that need a stdio server should use the [plugin](agent-integrations.md#openclaw-and-other-stdio-clients) instead of pointing at the URL directly.
