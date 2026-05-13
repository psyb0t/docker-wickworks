# wickworks

[![Docker Pulls](https://img.shields.io/docker/pulls/psyb0t/wickworks)](https://hub.docker.com/r/psyb0t/wickworks)
[![License: WTFPL](https://img.shields.io/badge/License-WTFPL-brightgreen.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.136-009688.svg)](https://fastapi.tiangolo.com/)

The dumb-as-rocks OHLC analyzer. You throw bars at it over HTTP, it throws indicators and SMC objects back. That's the whole product. No database, no queue, no state, no opinions, no "AI-powered signals," no upsell to a $97/mo Discord. Just primitives.

Every snake-oil-flavored TA SaaS out there wants to tell you when to buy. Wickworks tells you the order block is at 1.0832 and the RSI is 71.4. The "what does that mean?" part is where your strategy lives — and it should live in your code, not behind someone else's paywall.

Built on `pandas_ta` and `smartmoneyconcepts`, wrapped in a FastAPI server, locked behind 280+ tests that diff our output against closed-form references on real EURUSD ticks. If a math bug slips in, the test suite screams before the container builds.

## Table of Contents

- [What's Inside](#whats-inside)
- [Quick Start](#quick-start)
- [API](#api)
  - [`GET /health`](#get-health)
  - [`POST /` — compute](#post---compute)
  - [The `indicators` object](#the-indicators-object--the-whole-point)
  - [Available indicators](#available-indicators)
  - [Request fields](#request-fields)
  - [Response](#response)
  - [Errors](#errors)
- [Configuration](#configuration)
- [Architecture](#architecture)
- [Development](#development)
- [Testing philosophy](#testing-philosophy)
- [License](#license)

## What's Inside

| Category        | Primitives                                                                                                                    |
| --------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| **Trend**       | SMA/EMA + 15 other moving averages, slope, Donchian channels, Ichimoku                                                        |
| **Momentum**    | RSI, MACD, Stochastic, StochRSI, ADX, MFI, CCI, Williams %R, ROC, MOM, TSI, TRIX, UO, Fisher                                  |
| **Volatility**  | ATR, NATR, Bollinger Bands, Keltner Channels, Squeeze                                                                         |
| **Volume**      | VWAP (anchored), VWMA, OBV, AD, ADOSC, CMF, KVO                                                                               |
| **SMC**         | Order Blocks, Fair Value Gaps, BOS/CHoCH, swing structure, S/R levels, liquidity, retracements, sessions, previous-period H/L |
| **Divergences** | Regular + hidden divergence detection, divergence trends, signal-tagged with stable IDs                                       |
| **Summaries**   | Position, slope, momentum, volume regime, recent range — pre-baked projections over the raw series                            |

All JSON field names are camelCase. Output is NaN-safe — `NaN` becomes `null`, never a literal `NaN` token that blows up downstream parsers. NumPy/Pandas scalars and arrays are serialized cleanly (no `numpy.float64(...)` leaks). Bars in UTC, math in UTC, container runs `TZ=UTC` — timezone bullshit is your problem, not ours.

## Quick Start

```bash
docker run --rm -p 8000:8000 psyb0t/wickworks:latest
```

That's it. The service listens on `:8000`.

### docker compose

```yaml
services:
  wickworks:
    image: psyb0t/wickworks:latest
    ports: ["8000:8000"]
    environment:
      LOG_LEVEL: INFO
      MAX_BARS: "5000"
      MIN_BARS: "50"
```

### Local (uv-based)

```bash
make install     # uv sync from lockfile (supply-chain-pinned, see below)
make run         # uvicorn on :8000
```

## API

Two endpoints. That's the whole surface.

### `GET /health`

```bash
curl -s http://localhost:8000/health
```

```json
{ "ok": true, "version": "0.1.0" }
```

### `POST /` — compute

Send OHLC(V) bars + the indicators you want. Get back **only what you asked for** — response keys mirror the keys you sent. No "let me also throw in 40 indicators you didn't ask for" energy.

```bash
curl -s -X POST http://localhost:8000/ \
  -H 'Content-Type: application/json' \
  -d '{
    "symbol": "EURUSD",
    "timeframe": "H1",
    "bars": [
      { "time": 1700000000, "open": 1.0832, "high": 1.0851, "low": 1.0828, "close": 1.0844, "tickVolume": 1247 },
      ...
    ],
    "indicators": {
      "rsi":         true,
      "rsi21":       { "type": "rsi",   "length": 21 },
      "stochFast":   { "type": "stoch", "k": 5,  "d": 3, "smoothK": 3 },
      "stochSlow":   { "type": "stoch", "k": 21, "d": 7, "smoothK": 5 },
      "macd":        true,
      "orderBlocks": true,
      "fvg":         true,
      "divergences": true
    }
  }'
```

### The `indicators` object — the whole point

Each entry maps an **output name** (the key) to a **spec**:

- `true` — run the indicator with default params; key doubles as the type.
- `{ ...params }` — params object; missing `type` falls back to the key.
- `{ "type": "<name>", ...params }` — run a known indicator under a custom output name. This is how you stack multiple instances of the same indicator (e.g. four stochs with different params, three EMAs at different lengths).

```json
"indicators": {
  "rsi":    true,
  "rsi21":  { "type": "rsi",   "length": 21 },
  "stochA": { "type": "stoch", "k": 5,  "d": 3 },
  "stochB": { "type": "stoch", "k": 21, "d": 7 }
}
```

The response contains `rsi`, `rsi21`, `stochA`, `stochB`. Nothing else. Duplicate output names are physically impossible by JSON-object construction — you can't shoot yourself in the foot with this API even if you try.

### Request and response schemas

Everything below is **JSON Schema (Draft 2020-12)**. Each indicator has a `RequestSpec` (the value of your output key — what goes in) and a `ResponseValue` (what comes back under that key). Field-level docs live in JSON Schema's `description`. The top-level request body schema is in [Top-level request](#top-level-request).

#### Shared definitions

All series outputs reference these `$defs`:

```json
{
  "$defs": {
    "Series": {
      "type": "array",
      "items": { "type": ["number", "null"] },
      "description": "One value per bar (aligned 1:1 with the input bars array). Warmup positions are null."
    },
    "FlagSeries": {
      "type": "array",
      "items": { "type": "integer", "enum": [0, 1] },
      "description": "0/1 flag per bar."
    },
    "DirectionSeries": {
      "type": "array",
      "items": { "type": "integer", "enum": [-1, 1] },
      "description": "Per-bar direction marker: 1 = bullish/long, -1 = bearish/short."
    }
  }
}
```

### Available indicators

#### Length-based single-output series

A single shared spec covers every indicator that takes one `length` parameter and returns one `Series`. Per-type default lengths are in the table that follows.

```json
{
  "$id": "wickworks://indicator/LengthBased.request",
  "type": "object",
  "properties": {
    "type": {
      "enum": [
        "rsi",
        "atr",
        "natr",
        "cci",
        "willr",
        "roc",
        "mom",
        "mfi",
        "cmf",
        "vwma",
        "ema",
        "sma",
        "hma",
        "wma",
        "dema",
        "tema",
        "t3",
        "kama",
        "alma",
        "linreg",
        "jma",
        "zlma",
        "rma",
        "fwma",
        "swma",
        "sinwma",
        "trima"
      ],
      "description": "Indicator identifier. When omitted at the API layer, the output-key name is used as the type."
    },
    "length": {
      "type": "integer",
      "minimum": 1,
      "description": "Lookback window. Default depends on type — see the per-type table."
    },
    "c": {
      "type": "number",
      "exclusiveMinimum": 0,
      "default": 0.015,
      "description": "Scaling constant — only read by type=\"cci\"."
    }
  },
  "additionalProperties": false
}
```

```json
{
  "$id": "wickworks://indicator/LengthBased.response",
  "$ref": "#/$defs/Series"
}
```

**Per-type default `length`** (and inputs used):

| `type`   | default `length` | inputs         | description                                              |
| -------- | ---------------- | -------------- | -------------------------------------------------------- |
| `rsi`    | 14               | close          | Relative Strength Index, range 0–100                     |
| `cci`    | 14               | (h+l+c)/3      | Commodity Channel Index (in-house — pandas_ta has a bug) |
| `willr`  | 14               | h/l/c          | Williams %R, range -100..0                               |
| `roc`    | 10               | close          | Rate of Change, %                                        |
| `mom`    | 10               | close          | Absolute momentum: `close - close.shift(length)`         |
| `mfi`    | 14               | h/l/c + volume | Money Flow Index, range 0–100                            |
| `atr`    | 14               | h/l/c          | Average True Range, price units                          |
| `natr`   | 14               | h/l/c          | Normalized ATR (% of price)                              |
| `cmf`    | 20               | h/l/c + volume | Chaikin Money Flow, range -1..+1                         |
| `vwma`   | 10               | close + volume | Volume-weighted moving average                           |
| `ema`    | 21               | close          | Exponential moving average                               |
| `sma`    | 50               | close          | Simple moving average                                    |
| `hma`    | 14               | close          | Hull MA                                                  |
| `wma`    | 14               | close          | Weighted MA                                              |
| `dema`   | 10               | close          | Double-EMA                                               |
| `tema`   | 10               | close          | Triple-EMA                                               |
| `t3`     | 10               | close          | Tillson T3                                               |
| `kama`   | 10               | close          | Kaufman Adaptive MA                                      |
| `alma`   | 10               | close          | Arnaud Legoux MA                                         |
| `linreg` | 14               | close          | Linear regression MA                                     |
| `jma`    | 7                | close          | Jurik MA                                                 |
| `zlma`   | 10               | close          | Zero-lag MA                                              |
| `rma`    | 10               | close          | Wilder's RMA                                             |
| `fwma`   | 10               | close          | Fibonacci-weighted MA                                    |
| `swma`   | 10               | close          | Symmetric-weighted MA                                    |
| `sinwma` | 14               | close          | Sine-weighted MA                                         |
| `trima`  | 10               | close          | Triangular MA                                            |

#### `obv` and `ad` — parameterless cumulative volume lines

```json
{
  "$id": "wickworks://indicator/ObvAd.request",
  "type": "object",
  "properties": { "type": { "enum": ["obv", "ad"] } },
  "additionalProperties": false
}
```

```json
{ "$ref": "#/$defs/Series" }
```

- `obv` — On-Balance Volume. Cumulative; uses close + volume.
- `ad` — Accumulation/Distribution line. Cumulative; uses high/low/close + volume.

#### `adosc` — Chaikin Accumulation/Distribution Oscillator

```json
{
  "$id": "wickworks://indicator/adosc.request",
  "type": "object",
  "properties": {
    "type": { "const": "adosc" },
    "fast": {
      "type": "integer",
      "minimum": 1,
      "default": 3,
      "description": "Fast EMA length over the A/D line."
    },
    "slow": {
      "type": "integer",
      "minimum": 1,
      "default": 10,
      "description": "Slow EMA length over the A/D line."
    }
  },
  "additionalProperties": false
}
```

```json
{ "$ref": "#/$defs/Series" }
```

#### `uo` — Ultimate Oscillator

```json
{
  "$id": "wickworks://indicator/uo.request",
  "type": "object",
  "properties": {
    "type": { "const": "uo" },
    "fast": { "type": "integer", "minimum": 1, "default": 7 },
    "medium": { "type": "integer", "minimum": 1, "default": 14 },
    "slow": { "type": "integer", "minimum": 1, "default": 28 }
  },
  "additionalProperties": false
}
```

```json
{ "$ref": "#/$defs/Series", "description": "0–100 oscillator." }
```

#### `vwap` — session-anchored Volume-Weighted Average Price

```json
{
  "$id": "wickworks://indicator/vwap.request",
  "type": "object",
  "properties": {
    "type": { "const": "vwap" },
    "anchor": {
      "type": "string",
      "enum": ["D", "W", "M"],
      "default": "D",
      "description": "Pandas resample freq for the session reset: D=daily, W=weekly, M=monthly."
    },
    "sessionOffset": {
      "type": ["string", "number"],
      "default": "0s",
      "description": "Duration shifting the session reset away from UTC midnight. Go-style strings (\"-5h\", \"1h30m\") or plain seconds. Examples: -5h NY open, -2h EET broker open, 7h Tokyo open."
    }
  },
  "additionalProperties": false
}
```

```json
{ "$ref": "#/$defs/Series" }
```

#### `macd` — Moving Average Convergence Divergence

```json
{
  "$id": "wickworks://indicator/macd.request",
  "type": "object",
  "properties": {
    "type": { "const": "macd" },
    "fast": {
      "type": "integer",
      "minimum": 1,
      "default": 12,
      "description": "Fast EMA length."
    },
    "slow": {
      "type": "integer",
      "minimum": 1,
      "default": 26,
      "description": "Slow EMA length."
    },
    "signal": {
      "type": "integer",
      "minimum": 1,
      "default": 9,
      "description": "Signal-line EMA length over (fast - slow)."
    }
  },
  "additionalProperties": false
}
```

```json
{
  "$id": "wickworks://indicator/macd.response",
  "type": "object",
  "properties": {
    "macd": { "$ref": "#/$defs/Series", "description": "fast EMA - slow EMA" },
    "signal": {
      "$ref": "#/$defs/Series",
      "description": "EMA(signal) of macd"
    },
    "hist": { "$ref": "#/$defs/Series", "description": "macd - signal" }
  },
  "required": ["macd", "signal", "hist"]
}
```

#### `stoch` — Stochastic oscillator

```json
{
  "$id": "wickworks://indicator/stoch.request",
  "type": "object",
  "properties": {
    "type": { "const": "stoch" },
    "k": {
      "type": "integer",
      "minimum": 1,
      "default": 14,
      "description": "Lookback for raw %K."
    },
    "d": {
      "type": "integer",
      "minimum": 1,
      "default": 3,
      "description": "Smoothing length for %D."
    },
    "smoothK": {
      "type": "integer",
      "minimum": 1,
      "default": 3,
      "description": "Smoothing applied to %K before %D is computed.",
      "x-aliases": ["smooth_k", "smooth"]
    }
  },
  "additionalProperties": false
}
```

```json
{
  "$id": "wickworks://indicator/stoch.response",
  "type": "object",
  "properties": {
    "k": {
      "$ref": "#/$defs/Series",
      "description": "Smoothed %K, range 0–100."
    },
    "d": {
      "$ref": "#/$defs/Series",
      "description": "%D — moving average of %K, range 0–100."
    }
  },
  "required": ["k", "d"]
}
```

#### `stochrsi` — Stochastic RSI

```json
{
  "$id": "wickworks://indicator/stochrsi.request",
  "type": "object",
  "properties": {
    "type": { "const": "stochrsi" },
    "length": {
      "type": "integer",
      "minimum": 1,
      "default": 14,
      "description": "Stoch lookback applied to the RSI series."
    },
    "rsiLength": {
      "type": "integer",
      "minimum": 1,
      "default": 14,
      "description": "RSI period (input to the Stoch).",
      "x-aliases": ["rsi_length"]
    },
    "k": {
      "type": "integer",
      "minimum": 1,
      "default": 3,
      "description": "%K smoothing."
    },
    "d": {
      "type": "integer",
      "minimum": 1,
      "default": 3,
      "description": "%D smoothing."
    }
  },
  "additionalProperties": false
}
```

```json
{
  "type": "object",
  "properties": {
    "k": { "$ref": "#/$defs/Series", "description": "Range 0–1." },
    "d": { "$ref": "#/$defs/Series", "description": "Range 0–1." }
  },
  "required": ["k", "d"]
}
```

#### `adx` — Average Directional Index + DMI

```json
{
  "$id": "wickworks://indicator/adx.request",
  "type": "object",
  "properties": {
    "type": { "const": "adx" },
    "length": { "type": "integer", "minimum": 1, "default": 14 }
  },
  "additionalProperties": false
}
```

```json
{
  "type": "object",
  "properties": {
    "adx": {
      "$ref": "#/$defs/Series",
      "description": "Trend strength, 0–100 (no direction)."
    },
    "diPlus": {
      "$ref": "#/$defs/Series",
      "description": "+DI — bullish directional pressure."
    },
    "diMinus": {
      "$ref": "#/$defs/Series",
      "description": "-DI — bearish directional pressure."
    }
  },
  "required": ["adx", "diPlus", "diMinus"]
}
```

#### `aroon` — Aroon up/down + oscillator

```json
{
  "$id": "wickworks://indicator/aroon.request",
  "type": "object",
  "properties": {
    "type": { "const": "aroon" },
    "length": { "type": "integer", "minimum": 1, "default": 14 }
  },
  "additionalProperties": false
}
```

```json
{
  "type": "object",
  "properties": {
    "up": {
      "$ref": "#/$defs/Series",
      "description": "0–100; recency of highest high in lookback."
    },
    "down": {
      "$ref": "#/$defs/Series",
      "description": "0–100; recency of lowest low in lookback."
    },
    "oscillator": {
      "$ref": "#/$defs/Series",
      "description": "up - down, range -100..+100."
    }
  },
  "required": ["up", "down", "oscillator"]
}
```

#### `vortex`

```json
{
  "$id": "wickworks://indicator/vortex.request",
  "type": "object",
  "properties": {
    "type": { "const": "vortex" },
    "length": { "type": "integer", "minimum": 1, "default": 14 }
  },
  "additionalProperties": false
}
```

```json
{
  "type": "object",
  "properties": {
    "plus": {
      "$ref": "#/$defs/Series",
      "description": "Upward momentum (VI+)."
    },
    "minus": {
      "$ref": "#/$defs/Series",
      "description": "Downward momentum (VI-). Crossovers signal trend changes."
    }
  },
  "required": ["plus", "minus"]
}
```

#### `tsi` / `trix` / `kvo` / `fisher` — value + signal-line indicators

Four indicators share the same response shape (`{ <name>: Series, signal: Series }`) but differ in params.

```json
{
  "$id": "wickworks://indicator/tsi.request",
  "type": "object",
  "properties": {
    "type": { "const": "tsi" },
    "fast": { "type": "integer", "minimum": 1, "default": 13 },
    "slow": { "type": "integer", "minimum": 1, "default": 25 },
    "signal": { "type": "integer", "minimum": 1, "default": 13 }
  },
  "additionalProperties": false
}
```

```json
{
  "type": "object",
  "properties": {
    "tsi": { "$ref": "#/$defs/Series" },
    "signal": { "$ref": "#/$defs/Series" }
  },
  "required": ["tsi", "signal"]
}
```

```json
{
  "$id": "wickworks://indicator/trix.request",
  "type": "object",
  "properties": {
    "type": { "const": "trix" },
    "length": {
      "type": "integer",
      "minimum": 1,
      "default": 30,
      "description": "EMA chain length for the triple-smoothed series."
    },
    "signal": {
      "type": "integer",
      "minimum": 1,
      "default": 9,
      "description": "Signal-line EMA length over trix."
    }
  },
  "additionalProperties": false
}
```

```json
{
  "type": "object",
  "properties": {
    "trix": { "$ref": "#/$defs/Series" },
    "signal": { "$ref": "#/$defs/Series" }
  },
  "required": ["trix", "signal"]
}
```

```json
{
  "$id": "wickworks://indicator/kvo.request",
  "type": "object",
  "description": "Klinger Volume Oscillator — requires volume.",
  "properties": {
    "type": { "const": "kvo" },
    "fast": { "type": "integer", "minimum": 1, "default": 34 },
    "slow": { "type": "integer", "minimum": 1, "default": 55 },
    "signal": { "type": "integer", "minimum": 1, "default": 13 }
  },
  "additionalProperties": false
}
```

```json
{
  "type": "object",
  "properties": {
    "kvo": { "$ref": "#/$defs/Series" },
    "signal": { "$ref": "#/$defs/Series" }
  },
  "required": ["kvo", "signal"]
}
```

```json
{
  "$id": "wickworks://indicator/fisher.request",
  "type": "object",
  "description": "Ehlers Fisher Transform.",
  "properties": {
    "type": { "const": "fisher" },
    "length": { "type": "integer", "minimum": 1, "default": 9 },
    "signal": { "type": "integer", "minimum": 1, "default": 1 }
  },
  "additionalProperties": false
}
```

```json
{
  "type": "object",
  "properties": {
    "fisher": { "$ref": "#/$defs/Series" },
    "signal": { "$ref": "#/$defs/Series" }
  },
  "required": ["fisher", "signal"]
}
```

#### `bbands` — Bollinger Bands

```json
{
  "$id": "wickworks://indicator/bbands.request",
  "type": "object",
  "properties": {
    "type": { "const": "bbands" },
    "length": {
      "type": "integer",
      "minimum": 1,
      "default": 20,
      "description": "SMA window."
    },
    "std": {
      "type": "number",
      "exclusiveMinimum": 0,
      "default": 2.0,
      "description": "Number of standard deviations for the bands."
    }
  },
  "additionalProperties": false
}
```

```json
{
  "type": "object",
  "properties": {
    "upper": {
      "$ref": "#/$defs/Series",
      "description": "middle + std * rolling-stdev(close, length)"
    },
    "middle": { "$ref": "#/$defs/Series", "description": "SMA(close, length)" },
    "lower": {
      "$ref": "#/$defs/Series",
      "description": "middle - std * rolling-stdev(close, length)"
    }
  },
  "required": ["upper", "middle", "lower"]
}
```

#### `kc` — Keltner Channels

```json
{
  "$id": "wickworks://indicator/kc.request",
  "type": "object",
  "properties": {
    "type": { "const": "kc" },
    "length": {
      "type": "integer",
      "minimum": 1,
      "default": 20,
      "description": "EMA / ATR window."
    },
    "scalar": {
      "type": "number",
      "exclusiveMinimum": 0,
      "default": 2.0,
      "description": "ATR multiplier for the bands."
    }
  },
  "additionalProperties": false
}
```

```json
{
  "type": "object",
  "properties": {
    "upper": { "$ref": "#/$defs/Series", "description": "EMA + scalar * ATR" },
    "middle": { "$ref": "#/$defs/Series", "description": "EMA(close, length)" },
    "lower": { "$ref": "#/$defs/Series", "description": "EMA - scalar * ATR" }
  },
  "required": ["upper", "middle", "lower"]
}
```

#### `donchian` — Donchian Channels

```json
{
  "$id": "wickworks://indicator/donchian.request",
  "type": "object",
  "properties": {
    "type": { "const": "donchian" },
    "length": { "type": "integer", "minimum": 1, "default": 20 }
  },
  "additionalProperties": false
}
```

```json
{
  "type": "object",
  "properties": {
    "upper": {
      "$ref": "#/$defs/Series",
      "description": "Rolling max(high, length)."
    },
    "middle": {
      "$ref": "#/$defs/Series",
      "description": "(upper + lower) / 2."
    },
    "lower": {
      "$ref": "#/$defs/Series",
      "description": "Rolling min(low, length)."
    }
  },
  "required": ["upper", "middle", "lower"]
}
```

#### `squeeze` — TTM Squeeze (Bollinger inside Keltner)

```json
{
  "$id": "wickworks://indicator/squeeze.request",
  "type": "object",
  "properties": {
    "type": { "const": "squeeze" },
    "bbLength": {
      "type": "integer",
      "minimum": 1,
      "default": 20,
      "x-aliases": ["bb_length"]
    },
    "bbStd": {
      "type": "number",
      "exclusiveMinimum": 0,
      "default": 2.0,
      "x-aliases": ["bb_std"]
    },
    "kcLength": {
      "type": "integer",
      "minimum": 1,
      "default": 20,
      "x-aliases": ["kc_length"]
    },
    "kcScalar": {
      "type": "number",
      "exclusiveMinimum": 0,
      "default": 1.5,
      "x-aliases": ["kc_scalar"]
    }
  },
  "additionalProperties": false
}
```

```json
{
  "type": "object",
  "properties": {
    "value": {
      "$ref": "#/$defs/Series",
      "description": "Momentum value (signed)."
    },
    "on": {
      "$ref": "#/$defs/FlagSeries",
      "description": "1 = BB inside KC (squeeze ACTIVE)."
    },
    "off": {
      "$ref": "#/$defs/FlagSeries",
      "description": "1 = squeeze fired/released this bar."
    },
    "no": {
      "$ref": "#/$defs/FlagSeries",
      "description": "1 = no squeeze state."
    }
  },
  "required": ["value", "on", "off", "no"]
}
```

#### `supertrend`

```json
{
  "$id": "wickworks://indicator/supertrend.request",
  "type": "object",
  "properties": {
    "type": { "const": "supertrend" },
    "length": {
      "type": "integer",
      "minimum": 1,
      "default": 7,
      "description": "ATR period."
    },
    "multiplier": {
      "type": "number",
      "exclusiveMinimum": 0,
      "default": 3.0,
      "description": "ATR multiplier for band width."
    }
  },
  "additionalProperties": false
}
```

```json
{
  "type": "object",
  "properties": {
    "value": {
      "$ref": "#/$defs/Series",
      "description": "Current trailing band value."
    },
    "direction": {
      "$ref": "#/$defs/DirectionSeries",
      "description": "1 = uptrend, -1 = downtrend."
    },
    "long": {
      "$ref": "#/$defs/Series",
      "description": "Band value when in uptrend; null otherwise."
    },
    "short": {
      "$ref": "#/$defs/Series",
      "description": "Band value when in downtrend; null otherwise."
    }
  },
  "required": ["value", "direction", "long", "short"]
}
```

#### `psar` — Parabolic SAR

```json
{
  "$id": "wickworks://indicator/psar.request",
  "type": "object",
  "properties": {
    "type": { "const": "psar" },
    "af": {
      "type": "number",
      "exclusiveMinimum": 0,
      "default": 0.02,
      "description": "Acceleration step.",
      "x-aliases": ["step"]
    },
    "max": {
      "type": "number",
      "exclusiveMinimum": 0,
      "default": 0.2,
      "description": "Maximum acceleration factor.",
      "x-aliases": ["maxAf"]
    }
  },
  "additionalProperties": false
}
```

```json
{
  "type": "object",
  "properties": {
    "long": {
      "$ref": "#/$defs/Series",
      "description": "SAR value while long; null otherwise."
    },
    "short": {
      "$ref": "#/$defs/Series",
      "description": "SAR value while short; null otherwise."
    },
    "af": {
      "$ref": "#/$defs/Series",
      "description": "Current acceleration factor on the active leg."
    },
    "reversal": {
      "$ref": "#/$defs/FlagSeries",
      "description": "1 = trend reversal printed this bar."
    }
  },
  "required": ["long", "short", "af", "reversal"]
}
```

#### `ichimoku`

```json
{
  "$id": "wickworks://indicator/ichimoku.request",
  "type": "object",
  "properties": {
    "type": { "const": "ichimoku" },
    "tenkan": {
      "type": "integer",
      "minimum": 1,
      "default": 9,
      "description": "Conversion line length (Tenkan-sen)."
    },
    "kijun": {
      "type": "integer",
      "minimum": 1,
      "default": 26,
      "description": "Base line length (Kijun-sen)."
    },
    "senkou": {
      "type": "integer",
      "minimum": 1,
      "default": 52,
      "description": "Leading span B length (Senkou-B)."
    }
  },
  "additionalProperties": false
}
```

```json
{
  "type": "object",
  "description": "All values in price units. spanA/spanB are forward-projected by `kijun` bars.",
  "properties": {
    "spanA": {
      "$ref": "#/$defs/Series",
      "description": "Senkou Span A — kumo edge."
    },
    "spanB": {
      "$ref": "#/$defs/Series",
      "description": "Senkou Span B — kumo edge."
    },
    "tenkan": { "$ref": "#/$defs/Series", "description": "Conversion line." },
    "kijun": { "$ref": "#/$defs/Series", "description": "Base line." },
    "chikou": {
      "$ref": "#/$defs/Series",
      "description": "Lagging span — close shifted -kijun bars."
    }
  },
  "required": ["spanA", "spanB", "tenkan", "kijun", "chikou"]
}
```

#### `chandelierExit`

```json
{
  "$id": "wickworks://indicator/chandelierExit.request",
  "type": "object",
  "properties": {
    "type": { "const": "chandelierExit" },
    "length": {
      "type": "integer",
      "minimum": 1,
      "default": 22,
      "description": "High/low lookback."
    },
    "atrLength": {
      "type": "integer",
      "minimum": 1,
      "default": 22,
      "description": "ATR period.",
      "x-aliases": ["atr_length"]
    },
    "multiplier": {
      "type": "number",
      "exclusiveMinimum": 0,
      "default": 2.0,
      "description": "ATR multiplier."
    }
  },
  "additionalProperties": false
}
```

```json
{
  "type": "object",
  "properties": {
    "long": {
      "$ref": "#/$defs/Series",
      "description": "Exit-long level when long; null otherwise."
    },
    "short": {
      "$ref": "#/$defs/Series",
      "description": "Exit-short level when short; null otherwise."
    },
    "direction": {
      "$ref": "#/$defs/DirectionSeries",
      "description": "1 = long, -1 = short."
    }
  },
  "required": ["long", "short", "direction"]
}
```

### SMC primitives

Event-list outputs derived from Smart-Money-Concepts analysis. Most are filtered/sorted/clipped on the server so you get the most relevant subset, not the firehose.

#### Object schemas

```json
{
  "$id": "wickworks://smc/OrderBlock",
  "type": "object",
  "description": "Used for both orderBlocks and fvg responses (identical shape).",
  "properties": {
    "type": { "enum": ["bullish", "bearish"] },
    "top": {
      "type": "number",
      "description": "Upper price boundary of the block/gap."
    },
    "bottom": {
      "type": "number",
      "description": "Lower price boundary of the block/gap."
    },
    "candleIdx": {
      "type": "integer",
      "minimum": 0,
      "description": "0-based index into the bars you submitted."
    },
    "time": { "type": "integer", "description": "Bar time, UTC seconds." },
    "distancePct": {
      "type": "number",
      "description": "|reference - price| / price * 100, away from current price."
    }
  },
  "required": ["type", "top", "bottom", "candleIdx", "time", "distancePct"]
}
```

```json
{
  "$id": "wickworks://smc/BosChochEvent",
  "type": "object",
  "properties": {
    "event": { "enum": ["BOS", "CHoCH"] },
    "direction": { "enum": ["bullish", "bearish"] },
    "level": {
      "type": ["number", "null"],
      "description": "Structure level broken (may be null)."
    },
    "time": { "type": "integer", "description": "Bar time, UTC seconds." }
  },
  "required": ["event", "direction", "level", "time"]
}
```

```json
{
  "$id": "wickworks://smc/SwingLevel",
  "type": "object",
  "properties": {
    "type": { "enum": ["high", "low"] },
    "level": { "type": "number" },
    "time": { "type": "integer", "description": "UTC seconds." }
  },
  "required": ["type", "level", "time"]
}
```

```json
{
  "$id": "wickworks://smc/SrLevel",
  "type": "object",
  "properties": {
    "level": { "type": "number" },
    "type": { "enum": ["support", "resistance"] },
    "distancePct": {
      "type": "number",
      "description": "|price - level| / price * 100."
    },
    "touches": {
      "type": "integer",
      "minimum": 2,
      "description": "Bars touching within ±0.5*ATR of the level."
    }
  },
  "required": ["level", "type", "distancePct", "touches"]
}
```

```json
{
  "$id": "wickworks://smc/RecentRange",
  "type": "object",
  "properties": {
    "high": {
      "type": "number",
      "description": "Max high over the last 20 bars."
    },
    "low": {
      "type": "number",
      "description": "Min low over the last 20 bars."
    },
    "periodHigh": {
      "type": "number",
      "description": "Max high over the entire submitted series."
    },
    "periodLow": {
      "type": "number",
      "description": "Min low over the entire submitted series."
    }
  },
  "required": ["high", "low", "periodHigh", "periodLow"]
}
```

```json
{
  "$id": "wickworks://smc/SmcEvent",
  "type": "object",
  "description": "Sparse event used by liquidity / previousHighLow / sessions / retracements. idx + time are always present; remaining fields are forwarded as-is from the upstream smartmoneyconcepts DataFrame (skipping null values).",
  "properties": {
    "idx": { "type": "integer", "minimum": 0 },
    "time": { "type": "integer", "description": "UTC seconds." }
  },
  "required": ["idx", "time"],
  "additionalProperties": true
}
```

#### Request specs and response shapes

```json
{
  "$id": "wickworks://indicator/orderBlocks.request",
  "type": "object",
  "properties": { "type": { "const": "orderBlocks" } },
  "additionalProperties": false
}
```

```json
{
  "type": "array",
  "maxItems": 20,
  "items": { "$ref": "#/$defs/OrderBlock" },
  "description": "Up to 20 closest unmitigated order blocks, sorted ascending by |distancePct|."
}
```

---

```json
{
  "$id": "wickworks://indicator/fvg.request",
  "type": "object",
  "properties": { "type": { "enum": ["fvg", "fvgs"] } },
  "additionalProperties": false
}
```

```json
{
  "type": "array",
  "maxItems": 15,
  "items": { "$ref": "#/$defs/OrderBlock" },
  "description": "Up to 15 closest unmitigated Fair Value Gaps, sorted ascending by distance. Same object shape as OrderBlock."
}
```

---

```json
{
  "$id": "wickworks://indicator/bosChoch.request",
  "type": "object",
  "properties": { "type": { "const": "bosChoch" } },
  "additionalProperties": false
}
```

```json
{
  "type": "array",
  "maxItems": 10,
  "items": { "$ref": "#/$defs/BosChochEvent" },
  "description": "Last 10 Break-of-Structure / Change-of-Character events in the trailing 50 bars."
}
```

---

```json
{
  "$id": "wickworks://indicator/swingLevels.request",
  "type": "object",
  "properties": { "type": { "const": "swingLevels" } },
  "additionalProperties": false
}
```

```json
{
  "type": "array",
  "maxItems": 10,
  "items": { "$ref": "#/$defs/SwingLevel" },
  "description": "Last 10 swing highs/lows in the trailing 50 bars."
}
```

---

```json
{
  "$id": "wickworks://indicator/srLevels.request",
  "type": "object",
  "properties": { "type": { "const": "srLevels" } },
  "additionalProperties": false
}
```

```json
{
  "type": "array",
  "maxItems": 6,
  "items": { "$ref": "#/$defs/SrLevel" },
  "description": "Up to 3 support + 3 resistance levels above/below price, ranked by proximity, filtered by ≥2 touches and an ATR-based separation rule."
}
```

---

```json
{
  "$id": "wickworks://indicator/recentRange.request",
  "type": "object",
  "properties": { "type": { "const": "recentRange" } },
  "additionalProperties": false
}
```

```json
{ "$ref": "#/$defs/RecentRange" }
```

---

```json
{
  "$id": "wickworks://indicator/liquidity.request",
  "type": "object",
  "properties": {
    "type": { "const": "liquidity" },
    "swingLength": {
      "type": "integer",
      "minimum": 1,
      "default": 10,
      "x-aliases": ["swing_length"]
    },
    "rangePercent": {
      "type": "number",
      "exclusiveMinimum": 0,
      "default": 0.01,
      "x-aliases": ["range_percent"]
    }
  },
  "additionalProperties": false
}
```

```json
{ "type": "array", "items": { "$ref": "#/$defs/SmcEvent" } }
```

---

```json
{
  "$id": "wickworks://indicator/previousHighLow.request",
  "type": "object",
  "properties": {
    "type": { "const": "previousHighLow" },
    "timeFrame": {
      "type": "string",
      "default": "1D",
      "description": "Pandas resample freq for the previous-period reference (e.g. \"1D\", \"1W\", \"4h\").",
      "x-aliases": ["time_frame"]
    }
  },
  "additionalProperties": false
}
```

```json
{ "type": "array", "items": { "$ref": "#/$defs/SmcEvent" } }
```

---

```json
{
  "$id": "wickworks://indicator/sessions.request",
  "type": "object",
  "properties": {
    "type": { "const": "sessions" },
    "session": {
      "type": "string",
      "default": "London",
      "description": "Session name as accepted by smartmoneyconcepts (e.g. \"London\", \"New York\", \"Tokyo\", \"Sydney\")."
    },
    "startTime": {
      "type": ["string", "null"],
      "default": null,
      "description": "Override session start (HH:MM, exchange-local).",
      "x-aliases": ["start_time"]
    },
    "endTime": {
      "type": ["string", "null"],
      "default": null,
      "description": "Override session end (HH:MM, exchange-local).",
      "x-aliases": ["end_time"]
    }
  },
  "additionalProperties": false
}
```

```json
{ "type": "array", "items": { "$ref": "#/$defs/SmcEvent" } }
```

---

```json
{
  "$id": "wickworks://indicator/retracements.request",
  "type": "object",
  "properties": {
    "type": { "const": "retracements" },
    "swingLength": {
      "type": "integer",
      "minimum": 1,
      "default": 10,
      "x-aliases": ["swing_length"]
    }
  },
  "additionalProperties": false
}
```

```json
{ "type": "array", "items": { "$ref": "#/$defs/SmcEvent" } }
```

### Analysis summaries

Six outputs read from the **same** cached analysis pass — requesting all six costs no more than requesting one. All are parameterless.

```json
{
  "$id": "wickworks://indicator/price.request",
  "type": "object",
  "properties": { "type": { "const": "price" } },
  "additionalProperties": false
}
```

```json
{
  "type": "number",
  "description": "Last bar's close. Plain scalar, not an object."
}
```

---

```json
{
  "$id": "wickworks://indicator/levels.request",
  "type": "object",
  "properties": { "type": { "const": "levels" } },
  "additionalProperties": false
}
```

```json
{
  "$id": "wickworks://summary/Levels",
  "type": "object",
  "description": "Latest values of common reference levels. Each field is number or null if undefined for the series.",
  "properties": {
    "ema21": { "type": ["number", "null"] },
    "sma50": { "type": ["number", "null"] },
    "sma100": { "type": ["number", "null"] },
    "sma200": { "type": ["number", "null"] },
    "atr": { "type": ["number", "null"] },
    "vwap": { "type": ["number", "null"] },
    "donchianUpper": { "type": ["number", "null"] },
    "donchianLower": { "type": ["number", "null"] },
    "donchianMid": { "type": ["number", "null"] }
  },
  "required": [
    "ema21",
    "sma50",
    "sma100",
    "sma200",
    "atr",
    "vwap",
    "donchianUpper",
    "donchianLower",
    "donchianMid"
  ]
}
```

---

```json
{
  "$id": "wickworks://indicator/momentum.request",
  "type": "object",
  "properties": { "type": { "const": "momentum" } },
  "additionalProperties": false
}
```

```json
{
  "$id": "wickworks://summary/Momentum",
  "type": "object",
  "properties": {
    "rsi": { "type": ["number", "null"] },
    "mfi": { "type": ["number", "null"] },
    "macdHist": { "type": ["number", "null"] },
    "macdLine": { "type": ["number", "null"] },
    "macdSignal": { "type": ["number", "null"] },
    "adx": { "type": ["number", "null"] },
    "stochK": { "type": ["number", "null"] },
    "stochD": { "type": ["number", "null"] }
  },
  "required": [
    "rsi",
    "mfi",
    "macdHist",
    "macdLine",
    "macdSignal",
    "adx",
    "stochK",
    "stochD"
  ]
}
```

---

```json
{
  "$id": "wickworks://indicator/volume.request",
  "type": "object",
  "properties": { "type": { "const": "volume" } },
  "additionalProperties": false
}
```

```json
{
  "$id": "wickworks://summary/Volume",
  "type": "object",
  "properties": {
    "volRatio": {
      "type": ["number", "null"],
      "description": "Current tick volume / rolling-mean tick volume."
    },
    "obv": { "type": ["number", "null"], "description": "Latest OBV value." },
    "isSpike": { "type": "boolean", "description": "True when volRatio > 2.0." }
  },
  "required": ["volRatio", "obv", "isSpike"]
}
```

---

```json
{
  "$id": "wickworks://indicator/position.request",
  "type": "object",
  "properties": { "type": { "const": "position" } },
  "additionalProperties": false
}
```

```json
{
  "$id": "wickworks://summary/Position",
  "type": "object",
  "description": "Where price sits vs. each MA/VWAP. Only keys whose MA is computable are present.",
  "properties": {
    "ema21": { "enum": ["above", "below"] },
    "sma50": { "enum": ["above", "below"] },
    "sma100": { "enum": ["above", "below"] },
    "sma200": { "enum": ["above", "below"] },
    "vwap": { "enum": ["above", "below"] }
  },
  "additionalProperties": false
}
```

---

```json
{
  "$id": "wickworks://indicator/slope.request",
  "type": "object",
  "properties": { "type": { "const": "slope" } },
  "additionalProperties": false
}
```

```json
{
  "$id": "wickworks://summary/Slope",
  "type": "object",
  "description": "Direction of each MA/VWAP over the last 10 bars. Only present keys appear.",
  "properties": {
    "ema21": { "enum": ["up", "down"] },
    "sma50": { "enum": ["up", "down"] },
    "sma100": { "enum": ["up", "down"] },
    "sma200": { "enum": ["up", "down"] },
    "vwap": { "enum": ["up", "down"] }
  },
  "additionalProperties": false
}
```

### Signal-tagged outputs

These are the only outputs that carry stable `id` + `isRecent` fields. Other event lists do not — recency is implicit in `time` vs. the last bar.

```json
{
  "$id": "wickworks://signal/Divergence",
  "type": "object",
  "properties": {
    "indicator": {
      "type": "string",
      "description": "Exact indicator column name (e.g. \"RSI_14\", \"MACDh_12_26_9\")."
    },
    "label": {
      "enum": ["RSI", "MFI", "Stochastic", "MACD"],
      "description": "Human-readable label."
    },
    "type": { "enum": ["bearish", "bullish"] },
    "idx1": {
      "type": "integer",
      "minimum": 0,
      "description": "Bar index of the older pivot."
    },
    "idx2": {
      "type": "integer",
      "minimum": 0,
      "description": "Bar index of the newer pivot."
    },
    "time1": {
      "type": ["integer", "null"],
      "description": "UTC seconds at idx1."
    },
    "time2": {
      "type": ["integer", "null"],
      "description": "UTC seconds at idx2."
    },
    "price1": {
      "type": "number",
      "description": "Price extreme (±1 bar window) at idx1 — high for bearish, low for bullish."
    },
    "price2": {
      "type": "number",
      "description": "Price extreme (±1 bar window) at idx2."
    },
    "ind1": { "type": "number", "description": "Indicator value at idx1." },
    "ind2": { "type": "number", "description": "Indicator value at idx2." },
    "isRecent": {
      "type": "boolean",
      "description": "true if idx2 >= last_bar - recentBars."
    },
    "id": {
      "type": "string",
      "description": "sha256 over the event content (after isRecent is set). Stable across calls for the same event."
    }
  },
  "required": [
    "indicator",
    "label",
    "type",
    "idx1",
    "idx2",
    "time1",
    "time2",
    "price1",
    "price2",
    "ind1",
    "ind2",
    "isRecent",
    "id"
  ]
}
```

```json
{
  "$id": "wickworks://indicator/divergences.request",
  "type": "object",
  "properties": { "type": { "const": "divergences" } },
  "additionalProperties": false
}
```

```json
{
  "type": "array",
  "items": { "$ref": "#/$defs/Divergence" },
  "description": "At most one bearish + one bullish divergence per tracked oscillator (RSI, MFI, Stochastic, MACD histogram)."
}
```

---

```json
{
  "$id": "wickworks://signal/DivTrend",
  "type": "object",
  "properties": {
    "type": { "enum": ["bearish", "bullish"] },
    "barStart": {
      "type": "integer",
      "minimum": 0,
      "description": "Earliest idx1 in the chain."
    },
    "barEnd": {
      "type": "integer",
      "minimum": 0,
      "description": "Latest idx2 in the chain."
    },
    "indicators": {
      "type": "array",
      "items": { "type": "string" },
      "description": "Distinct labels in chronological fire order."
    },
    "count": {
      "type": "integer",
      "minimum": 2,
      "description": "Number of distinct indicators in the chain."
    },
    "isRecent": {
      "type": "boolean",
      "description": "true if barEnd >= last_bar - recentBars."
    },
    "id": { "type": "string" }
  },
  "required": [
    "type",
    "barStart",
    "barEnd",
    "indicators",
    "count",
    "isRecent",
    "id"
  ]
}
```

```json
{
  "$id": "wickworks://indicator/divTrends.request",
  "type": "object",
  "properties": { "type": { "const": "divTrends" } },
  "additionalProperties": false
}
```

```json
{
  "type": "array",
  "items": { "$ref": "#/$defs/DivTrend" },
  "description": "Chains of 2+ distinct-indicator divergences of the same direction whose pivot endpoints (idx2) are within 10 bars of the next."
}
```

### Top-level request

```json
{
  "$id": "wickworks://request/Compute",
  "type": "object",
  "properties": {
    "symbol": {
      "type": "string",
      "default": "",
      "description": "Echoed back in the response."
    },
    "timeframe": {
      "type": "string",
      "default": "",
      "description": "Echoed back in the response."
    },
    "recentBars": {
      "type": "integer",
      "minimum": 1,
      "default": 10,
      "x-aliases": ["recent_bars"],
      "description": "Window (in bars from the latest bar) within which divergences and divTrends are tagged isRecent=true. Other event lists ignore this."
    },
    "bars": {
      "type": "array",
      "minItems": 1,
      "items": { "$ref": "#/$defs/Bar" },
      "description": "OHLC(V) bars in chronological order. Length must be <= MAX_BARS (default 5000)."
    },
    "indicators": {
      "type": "object",
      "minProperties": 1,
      "additionalProperties": {
        "oneOf": [
          {
            "const": true,
            "description": "Shortcut: run the indicator named by the output key, with default params."
          },
          {
            "type": "object",
            "description": "Params object. If omitted, the output-key name is used as the indicator type. Include \"type\" to run a known indicator under a different output name."
          }
        ]
      },
      "description": "Map of outputKey -> spec. Output keys are arbitrary; spec selects the indicator and its params."
    }
  },
  "required": ["bars", "indicators"]
}
```

```json
{
  "$id": "wickworks://schema/Bar",
  "type": "object",
  "properties": {
    "time": { "type": "integer", "description": "UTC unix seconds." },
    "open": { "type": "number" },
    "high": { "type": "number" },
    "low": { "type": "number" },
    "close": { "type": "number" },
    "tickVolume": {
      "type": "integer",
      "minimum": 0,
      "default": 0,
      "description": "Canonical volume field. All volume-based indicators (VWAP, OBV, VWMA, MFI, CMF, AD, ADOSC, KVO) read this.",
      "x-aliases": ["tick_volume"]
    },
    "realVolume": {
      "type": "integer",
      "minimum": 0,
      "default": 0,
      "description": "Accepted for forward-compat. Indicator math currently reads tickVolume, not this.",
      "x-aliases": ["real_volume"]
    }
  },
  "required": ["time", "open", "high", "low", "close"]
}
```

### Response

```json
{
  "$id": "wickworks://response/Compute",
  "type": "object",
  "properties": {
    "symbol": { "type": "string", "description": "Echo of the request field." },
    "timeframe": {
      "type": "string",
      "description": "Echo of the request field."
    },
    "candles": {
      "type": "integer",
      "minimum": 0,
      "description": "Number of bars processed."
    }
  },
  "required": ["symbol", "timeframe", "candles"],
  "additionalProperties": {
    "description": "One entry per output key from indicators. The value shape is the ResponseValue of the requested indicator type."
  }
}
```

Concrete example:

```json
{
  "symbol": "EURUSD",
  "timeframe": "H1",
  "candles": 500,
  "rsi": [null, null, 71.4],
  "rsi21": [null, null, 64.2],
  "stochFast": { "k": [78.4], "d": [72.1] },
  "macd": { "macd": [0.00124], "signal": [0.00098], "hist": [0.00026] },
  "orderBlocks": [
    {
      "type": "bullish",
      "top": 1.0892,
      "bottom": 1.0871,
      "candleIdx": 312,
      "time": 1700123400,
      "distancePct": 0.082
    }
  ],
  "fvg": [
    {
      "type": "bearish",
      "top": 1.0945,
      "bottom": 1.0938,
      "candleIdx": 401,
      "time": 1700152800,
      "distancePct": 0.063
    }
  ],
  "divergences": [
    {
      "indicator": "RSI_14",
      "label": "RSI",
      "type": "bearish",
      "idx1": 410,
      "idx2": 478,
      "time1": 1700101200,
      "time2": 1700125200,
      "price1": 1.0901,
      "price2": 1.0918,
      "ind1": 72.4,
      "ind2": 68.1,
      "isRecent": true,
      "id": "f3a1c0b29e..."
    }
  ]
}
```

Only the keys you requested. Plus `symbol`, `timeframe`, `candles`. Warmup positions in series outputs are `null`, never `NaN`.

### Errors

| Status | Reason                                                                                                                                                                            |
| ------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 400    | empty `bars`, empty `indicators`, unknown indicator `type`, malformed indicator spec, **or insufficient bars for one or more requested indicators** (structured body — see below) |
| 413    | `len(bars) > MAX_BARS`                                                                                                                                                            |
| 422    | bar payload fails Pydantic schema validation (missing required field, wrong type, etc.)                                                                                           |
| 500    | internal computation error (should never happen — open an issue with the request body)                                                                                            |

When you ask for an indicator that needs more bars than you sent (e.g. `sma` `length=200` with 100 bars), the request is rejected up front — no silent all-null series. The response lists **every** under-fed indicator at once so you can fix the whole call in one round trip:

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
      { "outputKey": "longRsi", "type": "rsi", "required": 51, "available": 30 }
    ]
  }
}
```

The per-indicator requirement is derived from its params (`length`, `slow`, `signal`, etc.) — not a global floor. SMC-backed outputs (`orderBlocks`, `fvgs`, `bosChoch`, summaries, divergences, …) share a baseline floor of `MIN_BARS` (default 50) because the analysis pipeline assumes meaningful history.

## Configuration

All env-driven. Sensible defaults. Nothing to tune for a first run.

| Variable    | Default | Description                                                                                                                                                                                                                                                                          |
| ----------- | ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `LOG_LEVEL` | `INFO`  | Standard Python logging level.                                                                                                                                                                                                                                                       |
| `MAX_BARS`  | `5000`  | Reject requests with more bars than this (HTTP 413).                                                                                                                                                                                                                                 |
| `MIN_BARS`  | `50`    | Baseline floor for SMC-backed outputs (`orderBlocks`, `fvgs`, summaries, divergences, …) and the fallback requirement for any indicator not explicitly listed in the per-indicator requirement table. Series indicators (`sma`, `rsi`, `macd`, …) compute their own min from params. |
| `WORKERS`   | `2`     | uvicorn worker count.                                                                                                                                                                                                                                                                |

## Architecture

```
┌─────────────┐    ┌──────────────────────┐    ┌─────────────────┐
│  Your app   │───▶│  POST /              │───▶│  primitives     │
│  (any lang) │    │  bars in, JSON out   │    │  (camelCase)    │
└─────────────┘    └──────────────────────┘    └─────────────────┘
                              │
                              ▼
                   ┌──────────────────────┐
                   │  pandas_ta + SMC     │
                   │  divergences · S/R   │
                   │  swing structure     │
                   └──────────────────────┘
```

Stateless. No DB. No queues. No external calls. Bars in → JSON out. Horizontally scale by adding replicas. Two replicas hit the same input deterministically — same bars, same bytes, every time. Test suite pins it.

## Development

```bash
make help          # list all targets
make install       # uv sync from lockfile
make dev           # uvicorn with --reload
make run           # production-style uvicorn in the dev container
make test          # full suite (unit + docker integration)
make test-unit     # in-process only — fast feedback loop
make test-docker   # docker-in-docker integration tests
make lint          # flake8 + mypy + pyright
make format        # isort + black
make check         # lint + tests
```

### Package management — supply-chain defense

Wickworks uses `uv`'s `exclude-newer` to refuse any package version published after a fixed date. The date is **bumped to today** automatically by the package-mutation make targets — so you can't accidentally pull in a freshly-published malicious release that's still in its detection window.

```bash
make pkg-add PKG=foo==1.2.3   # bump exclude-newer, then uv add
make pkg-remove PKG=foo       # bump exclude-newer, then uv remove
make pkg-update PKG=foo       # bump exclude-newer, then uv lock --upgrade-package
make pkg-lock                 # bump exclude-newer, then uv lock
make pkg-upgrade              # bump exclude-newer + lock --upgrade everything
```

Never hand-edit `[tool.uv].exclude-newer` unless you know what you're doing. The bump-on-mutation pattern is the whole point.

### Optional `ta` extras

`pandas-ta` and `smartmoneyconcepts` pin conflicting transitive deps. They're declared in the `[ta]` optional-dependencies group but installed **without** resolution (the Dockerfile does this at build time, so you never have to think about it).

## Testing philosophy

The test suite is the receipts. Three categories:

1. **Closed-form math diffs** — for every standard indicator (RSI, MACD, ATR, Bollinger, Stochastic, Aroon, CCI, Williams %R, ROC, MOM, OBV, Donchian, VWMA, EMA, SMA, MACD…), the suite implements the formula from scratch in plain numpy/pandas and diffs the last-bar value against wickworks' output on real EURUSD H1 data. Tolerance: `rtol=1e-5`. If pandas_ta or our wiring drifts, the diff catches it before the container ships.
2. **smc_fast parity** — wickworks ships a numba-accelerated port of `smartmoneyconcepts`. Eight parity tests prove the fast path produces byte-identical results to the upstream library on the same inputs.
3. **Pipeline contract tests** — determinism (same bars → same bytes), append-stability (causal indicators don't change historical values when new bars arrive), warmup-region None counts, indicator isolation (requesting two together == requesting separately), HTTP error paths, volume field contract.

Run `make test-unit` for the fast loop (~20s, 280+ tests). Run `make test` for the full thing including a docker-in-docker integration build.

## License

WTFPL — see [LICENSE](LICENSE). Do what the fuck you want.
