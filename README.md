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

| Category | Primitives |
|----------|------------|
| **Trend** | SMA/EMA + 15 other moving averages, slope, Donchian channels, Ichimoku |
| **Momentum** | RSI, MACD, Stochastic, StochRSI, ADX, MFI, CCI, Williams %R, ROC, MOM, TSI, TRIX, UO, Fisher |
| **Volatility** | ATR, NATR, Bollinger Bands, Keltner Channels, Squeeze |
| **Volume** | VWAP (anchored), VWMA, OBV, AD, ADOSC, CMF, KVO |
| **SMC** | Order Blocks, Fair Value Gaps, BOS/CHoCH, swing structure, S/R levels, liquidity, retracements, sessions, previous-period H/L |
| **Divergences** | Regular + hidden divergence detection, divergence trends, signal-tagged with stable IDs |
| **Summaries** | Position, slope, momentum, volume regime, recent range — pre-baked projections over the raw series |

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

### Available indicators

**Oscillators / momentum**

| Type | Params (defaults) | Output shape |
|------|-------------------|--------------|
| `rsi` | `length=14` | `number[]` |
| `stoch` | `k=14, d=3, smoothK=3` | `{ k, d }` |
| `stochrsi` | `length=14, rsiLength=14, k=3, d=3` | `{ k, d }` |
| `macd` | `fast=12, slow=26, signal=9` | `{ macd, signal, hist }` |
| `cci` | `length=14` | `number[]` |
| `willr` | `length=14` | `number[]` |
| `roc` | `length=10` | `number[]` |
| `mom` | `length=10` | `number[]` |
| `uo` | `fast=7, medium=14, slow=28` | `number[]` |
| `tsi` | `fast=13, slow=25, signal=13` | `{ tsi, signal }` |
| `trix` | `length=30, signal=9` | `{ trix, signal }` |
| `fisher` | `length=9, signal=1` | `{ fisher, signal }` |

**Trend**

| Type | Params (defaults) | Output shape |
|------|-------------------|--------------|
| `adx` | `length=14` | `{ adx, diPlus, diMinus }` |
| `aroon` | `length=14` | `{ up, down, oscillator }` |
| `supertrend` | `length=7, multiplier=3.0` | `{ value, direction, long, short }` |
| `psar` | `af=0.02, max=0.2` | `{ long, short, af, reversal }` |
| `ichimoku` | `tenkan=9, kijun=26, senkou=52` | `{ spanA, spanB, tenkan, kijun, chikou }` |
| `vortex` | `length=14` | `{ plus, minus }` |
| `chandelierExit` | `length=22, atrLength=22, multiplier=2.0` | `{ long, short, direction }` |

**Volatility / channels**

| Type | Params (defaults) | Output shape |
|------|-------------------|--------------|
| `atr` | `length=14` | `number[]` |
| `natr` | `length=14` | `number[]` |
| `bbands` | `length=20, std=2.0` | `{ upper, middle, lower }` |
| `kc` | `length=20, scalar=2.0` | `{ upper, middle, lower }` |
| `donchian` | `length=20` | `{ upper, middle, lower }` |
| `squeeze` | `bbLength=20, bbStd=2.0, kcLength=20, kcScalar=1.5` | `{ value, on, off, no }` |

**Volume**

| Type | Params (defaults) | Output shape |
|------|-------------------|--------------|
| `mfi` | `length=14` | `number[]` |
| `obv` | — | `number[]` |
| `ad` | — | `number[]` |
| `adosc` | `fast=3, slow=10` | `number[]` |
| `cmf` | `length=20` | `number[]` |
| `kvo` | `fast=34, slow=55, signal=13` | `{ kvo, signal }` |
| `vwap` | `anchor="D", sessionOffset="0s"` | `number[]` |
| `vwma` | `length=10` | `number[]` |

`vwap` accepts:
- `anchor` — pandas freq for the session reset: `"D"` (daily, default), `"W"`, `"M"`.
- `sessionOffset` — Go-style duration shifting the reset away from UTC midnight (`"-5h"` for NY open, `"-2h"` for EET broker, `"7h"` for Tokyo). Plain seconds also work.

**Moving averages**

| Type | Params (defaults) | Output shape |
|------|-------------------|--------------|
| `ema` / `sma` | `length=21` / `50` | `number[]` |
| `hma`, `wma`, `dema`, `tema`, `t3`, `kama`, `alma`, `linreg`, `jma`, `zlma`, `rma`, `fwma`, `swma`, `sinwma`, `trima` | `length=<each>` | `number[]` |

**SMC primitives & summaries**

| Type | Params (defaults) | Output shape |
|------|-------------------|--------------|
| `orderBlocks` | — | `object[]` |
| `fvg` | — | `object[]` |
| `bosChoch` | — | `object[]` |
| `swingLevels` | — | `object[]` |
| `srLevels` | — | `object[]` |
| `recentRange` | — | `object` |
| `liquidity` | `swingLength=10, rangePercent=0.01` | `object[]` |
| `previousHighLow` | `timeFrame="1D"` | `object[]` |
| `sessions` | `session="London"` | `object[]` |
| `retracements` | `swingLength=10` | `object[]` |
| `price`, `levels`, `momentum`, `volume`, `position`, `slope` | — | `object` summaries |
| `divergences` | — | `object[]` (signal-tagged with `isRecent`, `id`) |
| `divTrends` | — | `object[]` (signal-tagged) |

Signal-tagged outputs carry a stable `id` (sha256 of the event content — same event, same id across calls) and an `isRecent` boolean (true if the event landed within `recentBars` of the latest bar).

### Request fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `symbol` | string | `""` | Echoed back. |
| `timeframe` | string | `""` | Echoed back. |
| `bars` | `Bar[]` | — | **Required.** OHLC(V) bars, chronological. |
| `indicators` | object | — | **Required.** Map of `outputName -> spec`. |
| `recentBars` | int | `10` | Signal-like outputs within N bars of the last bar get `isRecent: true`. |

**`Bar`**

| Field | Type | Description |
|-------|------|-------------|
| `time` | int | UTC unix seconds. |
| `open` / `high` / `low` / `close` | float | Self-explanatory. |
| `tickVolume` | int | Optional. **This is the canonical volume field.** All volume-based indicators (VWAP, OBV, VWMA, MFI, etc.) read it. |
| `realVolume` | int | Optional. Currently informational only — accepted in the schema for forward-compat with broker feeds that publish both, but the indicator math reads `tickVolume`. |

### Response

```json
{
  "symbol": "EURUSD",
  "timeframe": "H1",
  "candles": 500,
  "rsi": [ ... ],
  "rsi21": [ ... ],
  "stochFast": { "k": [...], "d": [...] },
  "stochSlow": { "k": [...], "d": [...] },
  "macd": { "macd": [...], "signal": [...], "hist": [...] },
  "orderBlocks": [ ... ],
  "fvg": [ ... ],
  "divergences": [ { "id": "<sha256>", "isRecent": true, ... } ]
}
```

Only the keys you requested. Plus `symbol`, `timeframe`, `candles`. That's it.

### Errors

| Status | Reason |
|--------|--------|
| 400 | empty `bars`, empty `indicators`, or unknown indicator `type` |
| 413 | `len(bars) > MAX_BARS` |
| 422 | `len(bars) < MIN_BARS`, or malformed bar payload |
| 500 | internal computation error (should never happen — open an issue) |

## Configuration

All env-driven. Sensible defaults. Nothing to tune for a first run.

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Standard Python logging level. |
| `MAX_BARS` | `5000` | Reject requests with more bars than this (HTTP 413). |
| `MIN_BARS` | `50` | Reject requests with fewer bars than this (HTTP 422). Indicators need warmup. |
| `WORKERS` | `2` | uvicorn worker count. |

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
