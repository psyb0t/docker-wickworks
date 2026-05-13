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
  - [Concepts](#concepts)
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
{ "ok": true, "version": "0.3.1" }
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
      "fvg":         true
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

### Concepts

The outputs below map to a handful of recurring trading ideas. If you've used any TradingView-style charting tool most of these will be familiar; if not, the short framing here is enough to pick the right output for the job.

**Series vs events.** A _Series_ output is one value per input bar (warmup positions are `null`) — these are continuous quantities you can chart. An _event_ output is a sparse array of objects pinpointing things that just happened (a swing, a block, a structure break). Series tell you _state_; events tell you _occurrences_.

**Primitives only — no signals.** Wickworks does not emit interpretive signals (no divergence detection, no MA-cross events, no "buy/sell" tags). Everything returned is either a raw indicator series, a structural fact (an order block was formed at this bar, price closed past this swing), or a pre-baked summary over those — never a judgment about what to do. If you want divergences, MACD-cross events, golden/death crosses, or any other derived signal, build that layer in your own consumer.

**The four questions every indicator answers part of:**

1. **What's the trend?** → Moving averages, ADX, supertrend, ichimoku.
2. **Is momentum behind it?** → RSI, MACD, stochastic, MFI.
3. **How much room is there?** → ATR, Bollinger Bands, Donchian, Keltner.
4. **Is volume backing it up?** → OBV, CMF, A/D, KVO, VWAP.

**In-house event constructs you won't find on TradingView:**

- **`srLevels`** — support / resistance construction: take pivot levels from a 7-bar swing detector (`sw7`), keep only those that price has tested at least **twice** (within ½·ATR of the level), enforce **≥3·ATR spacing** between kept levels so you don't get three nearly-identical levels stacked together, return up to 3 nearest above current price (resistance) and 3 nearest below (support).
- **Order block / FVG `mitigated` filter** — a zone is _unmitigated_ when price has not yet traded back into it since formation. We return **only unmitigated zones** — the live, untested ones. A mitigated zone is consumed history; it's filtered out of the response.
- **BOS vs CHoCH** — both come from Smart-Money-Concepts structural analysis. **BOS** (Break of Structure) = trend continuation: the most recent swing in the trend's direction is taken out (uptrend breaks the prior higher-high; downtrend breaks the prior lower-low). **CHoCH** (Change of Character) = trend reversal: price breaks _against_ the prior trend's structure for the first time (uptrend breaks a swing low; downtrend breaks a swing high). BOS = "trend is still alive"; CHoCH = "trend just died." These are structural facts (a level was crossed) — interpreting "alive" vs "died" is the consumer's job.

### Available indicators

> Want the formal contract for tooling / validators? See [`schema.json`](schema.json) — full JSON Schema Draft 2020-12. The reference below is the human version: categories + per-indicator blurbs + params tables + return shapes + examples.

**Three series shapes are shared across most outputs:**

- **Series** — one value per bar (`number | null`), aligned 1:1 with input `bars`. Warmup positions are `null`.
- **FlagSeries** — one `0/1` integer per bar.
- **DirectionSeries** — one `-1/+1` integer per bar (`1` = bullish/long, `-1` = bearish/short).

Indicators below are grouped by what they tell a trader, not by parameter shape. Each subsection starts with a one-paragraph framing of the category, then lists every indicator in it with a short "what it is / when to use it" blurb.

---

#### Moving averages — trend bias and dynamic levels

Smoothed price lines. Each flavor trades **responsiveness against lag** differently — pick by how fast you want the curve to react to new bars. Trader use: define the dominant direction (price above/below the MA = bull/bear bias), identify dynamic support/resistance the market keeps touching, fire crossover signals (fast MA crossing slow MA = trend shift).

All take a single `length` parameter and return a Series.

| `type`   | default | inputs      | what it is                                                                                                              |
| -------- | ------: | ----------- | ----------------------------------------------------------------------------------------------------------------------- |
| `ema`    |      21 | close       | **Exponential MA** — recent bars weighted more. Standard trend filter. The default trend MA in most strategies.         |
| `sma`    |      50 | close       | **Simple MA** — flat average. Slow, smooth, classic. 50/200-SMA crosses define the "Golden Cross" / "Death Cross".      |
| `hma`    |      14 | close       | **Hull MA** — low-lag, smooth. Reacts fast without the noise an EMA would give at the same period.                      |
| `wma`    |      14 | close       | **Weighted MA** — linear weights. Sits between SMA and EMA in lag.                                                      |
| `dema`   |      10 | close       | **Double-EMA** — less lag than EMA via a correction term.                                                               |
| `tema`   |      10 | close       | **Triple-EMA** — even less lag, but more whipsaw-prone in chop.                                                         |
| `t3`     |      10 | close       | **Tillson T3** — smooth like SMA, fast like EMA. Curve-looking output some traders prefer for visual clarity.           |
| `kama`   |      10 | close       | **Kaufman Adaptive MA** — speeds up in trends, slows down in chop. Self-tuning.                                         |
| `alma`   |      10 | close       | **Arnaud Legoux MA** — Gaussian-weighted. Low noise, low lag tradeoff.                                                  |
| `linreg` |      14 | close       | **Linear-regression MA** — best-fit line over the window, evaluated at "now". Statistically grounded smoothing.         |
| `jma`    |       7 | close       | **Jurik MA** — proprietary smooth, very low lag. Premium-feeling curve.                                                 |
| `zlma`   |      10 | close       | **Zero-Lag MA** — error-correction on EMA, attempting to remove lag entirely.                                           |
| `rma`    |      10 | close       | **Wilder's smoothing** — used inside RSI/ATR. Heavy, slow. Useful when you want indicator-internal smoothing semantics. |
| `fwma`   |      10 | close       | **Fibonacci-weighted MA** — weights by Fib sequence.                                                                    |
| `swma`   |      10 | close       | **Symmetric-weighted MA** — weights peak in the middle of the window.                                                   |
| `sinwma` |      14 | close       | **Sine-weighted MA** — sine-curve weights. Very smooth.                                                                 |
| `trima`  |      10 | close       | **Triangular MA** — double-smoothed SMA. Smoother than SMA, more lag.                                                   |
| `vwma`   |      10 | close + vol | **Volume-weighted MA** — heavy-volume bars count more. Closer to where actual trading interest was.                     |

```json
"ema":   true,
"ema50": { "type": "ema", "length": 50 }
```

##### `vwap` — session-anchored VWAP

Volume-weighted average price, **reset at the start of each session** (daily / weekly / monthly). Unlike a rolling MA, VWAP accumulates from a fixed anchor — by the end of the session everyone has been trading "around" it. Institutions use it as a fair-value benchmark and execution target: price below VWAP = the instrument is trading **cheap** for the session, above = **rich**. The `sessionOffset` lets you align the anchor to your trading session (NY = `-5h`, EET = `-2h`, Tokyo = `7h`) rather than UTC midnight.

| Param           | Type                    | Default | Description                                                                       |
| --------------- | ----------------------- | ------: | --------------------------------------------------------------------------------- |
| `anchor`        | `"D"` \| `"W"` \| `"M"` |   `"D"` | Session reset cadence                                                             |
| `sessionOffset` | string \| number        |  `"0s"` | Offset session start from UTC midnight. Go-style (`"-5h"`, `"1h30m"`) or seconds. |

**Returns:** Series.

---

#### Momentum oscillators — speed and exhaustion

Measure the _rate_ of price change, not the level itself. Most are bounded (0–100 or centered around zero), so readings are directly comparable across instruments and timeframes. Trader use: spot **overbought/oversold** extremes (mean-reversion edges), watch for **divergence vs price** (momentum fading while price extends = reversal hint), trade **zero-line / midline crosses** as momentum-shift triggers.

##### Length-based single-line oscillators

Same spec: one `length` parameter, returns one Series.

| `type`  | default | inputs      | scale       | what it tells you                                                                                                                                                                     |
| ------- | ------: | ----------- | ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `rsi`   |      14 | close       | 0–100       | **Relative Strength Index.** Classic momentum oscillator. `>70` overbought, `<30` oversold. Bounded, well-studied, the canonical input for momentum-vs-price analysis downstream.     |
| `mfi`   |      14 | h/l/c + vol | 0–100       | **Money Flow Index** — RSI weighted by volume. Stricter signal: needs both price _and_ volume agreeing.                                                                               |
| `willr` |      14 | h/l/c       | -100..0     | **Williams %R.** Inverted stochastic. `-20` ≈ overbought, `-80` ≈ oversold. Quick to flip.                                                                                            |
| `cci`   |      14 | (h+l+c)/3   | unbounded   | **Commodity Channel Index.** Measures deviation from a moving average in normalized units. `±100` are conventional thresholds. (In-house implementation — pandas_ta has a known bug.) |
| `roc`   |      10 | close       | %           | **Rate of Change.** Percent move over N bars. Most direct momentum number — no smoothing, no normalization.                                                                           |
| `mom`   |      10 | close       | price units | **Absolute momentum:** `close - close.shift(length)`. Raw price-unit version of ROC.                                                                                                  |

`cci` accepts an extra `c` parameter (number > 0, default `0.015`) — the constant scaling factor in the classic Lambert formula.

##### `uo` — Ultimate Oscillator

Williams' combo of three timeframes (short/medium/long) blended into one 0–100 line. Designed specifically to reduce the false signals single-period oscillators give in ranging markets. Watch for divergences and 30/70 extremes — same as RSI but with built-in multi-period confirmation.

| Param    | Type        | Default | Description   |
| -------- | ----------- | ------: | ------------- |
| `fast`   | integer ≥ 1 |     `7` | Short period  |
| `medium` | integer ≥ 1 |    `14` | Medium period |
| `slow`   | integer ≥ 1 |    `28` | Long period   |

**Returns:** Series (0–100).

##### `stoch` — Stochastic oscillator

"Where is the close within the recent high-to-low range?" Returns `%K` (raw position) and `%D` (smoothed `%K`). Classic signals: `%K` crossing `%D` is the trigger; both lines above 80 = overbought zone, below 20 = oversold zone. Like RSI but more reactive — fires more often, false-positives more often too.

| Param     | Type        | Default | Description           |
| --------- | ----------- | ------: | --------------------- |
| `k`       | integer ≥ 1 |    `14` | Lookback for raw `%K` |
| `d`       | integer ≥ 1 |     `3` | `%D` smoothing        |
| `smoothK` | integer ≥ 1 |     `3` | `%K` smoothing        |

**Returns:** `{ k, d }` — each a Series (0–100).

##### `stochrsi` — Stochastic of RSI

Stochastic formula applied to RSI values instead of price. Doubly sensitive — fires far more frequently than vanilla stoch and is especially good at picking turning points inside a ranging move. Pair with a trend filter; on its own it overtrades.

| Param       | Type        | Default | Description                 |
| ----------- | ----------- | ------: | --------------------------- |
| `length`    | integer ≥ 1 |    `14` | Stoch lookback over RSI     |
| `rsiLength` | integer ≥ 1 |    `14` | RSI period (input to Stoch) |
| `k`         | integer ≥ 1 |     `3` | `%K` smoothing              |
| `d`         | integer ≥ 1 |     `3` | `%D` smoothing              |

**Returns:** `{ k, d }` — each a Series (**0–1**, not 0–100).

##### `macd` — Moving Average Convergence Divergence

Difference between a fast and slow EMA, plus a signal-line smoothing of that difference. Three lenses: the `macd` line (raw momentum), the `signal` line (smoothed), the `hist` (macd − signal — what most traders actually watch). Hist crossing zero = momentum direction change; hist diverging from price = momentum exhaustion.

| Param    | Type        | Default | Description                        |
| -------- | ----------- | ------: | ---------------------------------- |
| `fast`   | integer ≥ 1 |    `12` | Fast EMA                           |
| `slow`   | integer ≥ 1 |    `26` | Slow EMA                           |
| `signal` | integer ≥ 1 |     `9` | Signal-line EMA over (fast − slow) |

**Returns:** `{ macd, signal, hist }` — each a Series. `hist = macd - signal`.

##### `tsi` / `trix` / `fisher` — momentum with signal line

All return the same shape: `{ <name>: Series, signal: Series }`. Watch zero-line crosses and value-vs-signal crosses, same as MACD.

**`tsi`** — True Strength Index. Double-smoothed price momentum (close-based). Smoother than MACD, slower to flip — fewer false signals, more lag.

| Param    | Type        | Default |
| -------- | ----------- | ------: |
| `fast`   | integer ≥ 1 |    `13` |
| `slow`   | integer ≥ 1 |    `25` |
| `signal` | integer ≥ 1 |    `13` |

**`trix`** — Triple-smoothed exponential ROC. By design it filters out cycles shorter than its `length`, so it's a longer-term momentum read — useful for higher-timeframe trend confirmation, not scalping.

| Param    | Type        | Default | Description                           |
| -------- | ----------- | ------: | ------------------------------------- |
| `length` | integer ≥ 1 |    `30` | EMA chain length for triple smoothing |
| `signal` | integer ≥ 1 |     `9` | Signal-line EMA over trix             |

**`fisher`** — Ehlers Fisher Transform. Reshapes price into a Gaussian-like distribution so extremes are sharper and turning points are easier to spot than in RSI.

| Param    | Type        | Default |
| -------- | ----------- | ------: |
| `length` | integer ≥ 1 |     `9` |
| `signal` | integer ≥ 1 |     `1` |

---

#### Trend strength & cross-direction

These don't tell you the price level — they tell you **how trendy** the market is right now, or **which side is in control**. Pair them with a price-based indicator: trend-strength tells you whether to trust trend signals at all.

##### `adx` — ADX + DMI

Average Directional Index measures trend **strength** only, not direction. `adx` rises when one side is winning decisively (regardless of which side). The `+DI` and `-DI` lines are the directional pressure components — `+DI > -DI` = bulls in control, and vice versa. Rule of thumb: `adx > 25` = market is trendable, follow signals; `adx < 20` = chop, avoid trend strategies and prefer mean-reversion.

| Param    | Type        | Default |
| -------- | ----------- | ------: |
| `length` | integer ≥ 1 |    `14` |

**Returns:** `{ adx, diPlus, diMinus }` — each a Series.

##### `aroon`

Race between "how many bars since the highest high?" and "how many bars since the lowest low?", normalized 0–100. `up` near 100 = recent action keeps making new highs (strong uptrend); `down` near 100 = recent lows (strong downtrend). `oscillator = up - down` is the net directional read on the same -100..+100 scale.

| Param    | Type        | Default |
| -------- | ----------- | ------: |
| `length` | integer ≥ 1 |    `14` |

**Returns:** `{ up, down, oscillator }` — `up`/`down` are 0–100; `oscillator` ranges -100..+100.

##### `vortex`

Two lines measuring positive (`plus`) vs negative (`minus`) true-range movement. Pure trend-flip detector: `plus` crossing above `minus` = bullish shift; the inverse = bearish shift. No overbought/oversold concept here.

| Param    | Type        | Default |
| -------- | ----------- | ------: |
| `length` | integer ≥ 1 |    `14` |

**Returns:** `{ plus, minus }` — each a Series.

---

#### Volatility

Measure the _spread_ of price action, not its direction. These don't generate buy/sell signals on their own — they're inputs to **stop placement** (don't set a stop tighter than 1–2 ATR), **position sizing** (size inversely to volatility so each trade risks the same dollar amount), and **regime detection** (rising volatility = breakout regime; collapsing volatility = consolidation, watch for squeeze).

| `type` | default | inputs | scale       | what it tells you                                                                                                             |
| ------ | ------: | ------ | ----------- | ----------------------------------------------------------------------------------------------------------------------------- |
| `atr`  |      14 | h/l/c  | price units | **Average True Range** — average bar range over N bars, in raw price units. The universal stop-distance unit.                 |
| `natr` |      14 | h/l/c  | % of price  | **Normalized ATR** — ATR as a percentage of close. Same information, comparable across instruments at different price levels. |

---

#### Volume / money flow

Volume-derived lines that tell you **who's behind the move**. Use to **confirm breakouts** (price breaks resistance + rising volume line = real; same break with flat/falling volume = suspect, often fades) and **spot accumulation/distribution** (price flat but money-flow rising = quiet buying behind the scenes; price flat but money-flow falling = quiet distribution).

##### `obv` and `ad` — parameterless cumulative lines

No params. **Returns:** Series.

- **`obv`** — On-Balance Volume. Adds volume on up bars, subtracts on down bars. Cumulative running total. When OBV diverges from price (price up, OBV flat or down) = warning sign that the move lacks volume backing.
- **`ad`** — Accumulation/Distribution. Weighted by where close lands within the bar's range (close near high = mostly buying; close near low = mostly selling). Cumulative. More precise than OBV when bars have long ranges.

##### `cmf` — Chaikin Money Flow

The A/D formula normalized to a rolling window instead of accumulating forever. Returns -1..+1: positive = net accumulation pressure over the window, negative = distribution. Use the zero line as a regime filter — only take longs when CMF is positive.

| Param    | Type        | Default |
| -------- | ----------- | ------: |
| `length` | integer ≥ 1 |    `20` |

**Returns:** Series.

##### `adosc` — Chaikin A/D Oscillator

MACD-style oscillator built over the A/D line — fast EMA minus slow EMA of A/D. Detects shifts in accumulation **momentum** (acceleration), not just direction. Zero-line crosses signal regime change in volume pressure.

| Param  | Type        | Default | Description                |
| ------ | ----------- | ------: | -------------------------- |
| `fast` | integer ≥ 1 |     `3` | Fast EMA over the A/D line |
| `slow` | integer ≥ 1 |    `10` | Slow EMA over the A/D line |

**Returns:** Series.

##### `kvo` — Klinger Volume Oscillator

Volume-force indicator with signal line. Designed to spot long-term reversals while staying sensitive to short-term swings — the dual-period structure (fast/slow) makes it useful both as a primary signal and as a confirmation overlay. Requires volume bars.

| Param    | Type        | Default |
| -------- | ----------- | ------: |
| `fast`   | integer ≥ 1 |    `34` |
| `slow`   | integer ≥ 1 |    `55` |
| `signal` | integer ≥ 1 |    `13` |

**Returns:** `{ kvo, signal }` — each a Series.

---

#### Bands & channels — dynamic price envelopes

Lines wrapping price action. Three trader uses: **mean-reversion edges** (touch upper band = stretched up, fade candidate; touch lower = stretched down), **breakout triggers** (close _outside_ the band = volatility regime change), and **squeeze detection** (bands narrowing = compression preceding expansion). The three flavors below use different math (std-dev vs ATR vs raw range) but serve the same role.

##### `bbands` — Bollinger Bands

SMA ± N standard deviations. The width self-adapts to recent volatility. Classic 2σ touch in theory contains ~95% of bars; in practice price _walks the band_ in strong trends, so don't blindly fade band-touches in a trend.

| Param    | Type        | Default | Description        |
| -------- | ----------- | ------: | ------------------ |
| `length` | integer ≥ 1 |    `20` | SMA window         |
| `std`    | number > 0  |   `2.0` | Std-dev band width |

**Returns:** `{ upper, middle, lower }` — each a Series.

##### `kc` — Keltner Channels

Like Bollinger but uses ATR instead of standard deviation for width. Smoother — doesn't react as sharply to a single outlier bar. Often paired with `bbands` as a squeeze detector (see `squeeze` below).

| Param    | Type        | Default | Description      |
| -------- | ----------- | ------: | ---------------- |
| `length` | integer ≥ 1 |    `20` | EMA / ATR window |
| `scalar` | number > 0  |   `2.0` | ATR multiplier   |

**Returns:** `{ upper, middle, lower }` — each a Series.

##### `donchian` — Donchian Channels

Rolling max(high) and min(low) over N bars. The original "Turtle Trader" channel — breaking above the upper = new N-bar high = trend-long signal; breaking below the lower = new N-bar low = trend-short signal. Brutally simple, surprisingly effective on trending instruments.

| Param    | Type        | Default |
| -------- | ----------- | ------: |
| `length` | integer ≥ 1 |    `20` |

**Returns:** `{ upper, middle, lower }` — `upper`/`lower` are rolling max/min; `middle` is their midpoint.

---

#### Trailing trend signals

Single-line trend filters that flip direction with the trend. Two roles: **trend filter** (only take longs when bullish, only shorts when bearish) and **trailing stop** (the line value _is_ where you'd exit if the trend reverses). Use one — they're all variations on the same idea, with different lag/whipsaw tradeoffs.

##### `supertrend`

ATR-based trailing band. When price is above, the band sits below acting as a trailing-stop support line; when price closes through it, the band jumps to the opposite side and flips direction. The default 7×3.0 ATR is the canonical "TradingView Supertrend" setting.

| Param        | Type        | Default | Description    |
| ------------ | ----------- | ------: | -------------- |
| `length`     | integer ≥ 1 |     `7` | ATR period     |
| `multiplier` | number > 0  |   `3.0` | ATR multiplier |

**Returns:** `{ value, direction, long, short }` — `value` is the trailing band (Series); `direction` is DirectionSeries; `long`/`short` carry the band value only on that direction's leg, `null` otherwise (so you can plot two distinct-colored series).

##### `psar` — Parabolic SAR

Wilder's "stop and reverse" — dots that accelerate toward price during a trend, flipping to the other side when hit. **Tightest** of the trailing-stop family: dots get close to price fast. Brilliant in clean trends; disastrous in chop, where it whipsaws constantly.

| Param | Type       | Default | Description                 |
| ----- | ---------- | ------: | --------------------------- |
| `af`  | number > 0 |  `0.02` | Acceleration step per bar   |
| `max` | number > 0 |   `0.2` | Maximum acceleration factor |

**Returns:** `{ long, short, af, reversal }` — `long`/`short` are the SAR value on that leg (Series, `null` on the other); `af` is the current acceleration value (Series); `reversal` is a FlagSeries (`1` = trend flipped this bar).

##### `chandelierExit`

ATR-based trailing stop pinned to the highest high (long leg) or lowest low (short leg) over a lookback window. Trails _further_ from price than supertrend — wider stops, fewer flips. Good for swing trading where you want to give the trend room to breathe.

| Param        | Type        | Default | Description       |
| ------------ | ----------- | ------: | ----------------- |
| `length`     | integer ≥ 1 |    `22` | High/low lookback |
| `atrLength`  | integer ≥ 1 |    `22` | ATR period        |
| `multiplier` | number > 0  |   `2.0` | ATR multiplier    |

**Returns:** `{ long, short, direction }` — `long`/`short` are exit levels on that leg (Series, `null` otherwise); `direction` is DirectionSeries.

##### `ichimoku`

Five-line Japanese trend system. The **"cloud"** (between `spanA` and `spanB`, projected `kijun` bars into the future) is the headline read: price above the cloud = bullish regime; price inside the cloud = neutral/chop, no high-conviction trades; price below the cloud = bearish regime. `tenkan` (fast) and `kijun` (slow) are midpoint lines used for crossover triggers; `chikou` is the close shifted back, used to confirm signals against historical price.

| Param    | Type        | Default | Description                                 |
| -------- | ----------- | ------: | ------------------------------------------- |
| `tenkan` | integer ≥ 1 |     `9` | Conversion line — fast midpoint of high/low |
| `kijun`  | integer ≥ 1 |    `26` | Base line — slow midpoint                   |
| `senkou` | integer ≥ 1 |    `52` | Leading span B period                       |

**Returns:** `{ spanA, spanB, tenkan, kijun, chikou }` — all Series in price units. `spanA`/`spanB` are **forward-projected** by `kijun` bars (the cloud lives in the future); `chikou` is close shifted **back** by `kijun` bars.

---

#### Compression / regime

##### `squeeze` — TTM Squeeze

Detects when **Bollinger Bands sit entirely inside Keltner Channels** — i.e., realized volatility (the BB width) has dropped below average volatility (the KC width). The market is compressing, coiling. Squeeze releases historically precede sharp directional moves: when `off` fires (squeeze just released this bar), trade the breakout direction indicated by `value`.

The flag fields form a per-bar state machine:

- **`on`** — squeeze is **active** this bar (BB inside KC). Market is coiled.
- **`off`** — squeeze **just released** this bar (BB exited KC). Trigger bar.
- **`no`** — no squeeze (default state).

| Param      | Type        | Default |
| ---------- | ----------- | ------: |
| `bbLength` | integer ≥ 1 |    `20` |
| `bbStd`    | number > 0  |   `2.0` |
| `kcLength` | integer ≥ 1 |    `20` |
| `kcScalar` | number > 0  |   `1.5` |

**Returns:** `{ value, on, off, no }` — `value` is signed momentum (Series, positive = bullish momentum during/after squeeze, negative = bearish); `on`/`off`/`no` are FlagSeries.

### SMC primitives

**Smart Money Concepts** is a price-action framework that maps where institutional ("smart money") order flow likely sat on the chart. Instead of summary indicators, it produces **event-list outputs**: concrete zones, levels, and structural shifts you can point to. Most outputs are filtered, sorted, and clipped server-side — you get the relevant subset, not the firehose.

The core SMC ideas you'll see in the outputs below:

- **Order block** — the last opposite-direction candle (or cluster) right before a strong impulsive move. The theory: institutions placed large orders here and didn't fill them all; when price retests the zone, they finish filling, and price reacts.
- **Fair Value Gap (FVG)** — a 3-bar imbalance where bar 1's wick and bar 3's wick don't overlap, leaving a "gap" of price action that traded too fast to fill on the way through. Markets tend to revisit these gaps to fill them.
- **Mitigation** — when price trades back into an order block or FVG, the zone is "mitigated" (its liquidity is used up). **We return unmitigated zones only** — the live, untested ones.
- **Swing high/low** — local pivots in price structure. SMC trend identification is built on the sequence of swings (HH/HL = uptrend, LH/LL = downtrend).
- **BOS (Break of Structure)** — price breaks the most recent swing **in the trend's direction**. Trend is alive, continuation signal.
- **CHoCH (Change of Character)** — price breaks **against** the prior trend's swing structure for the first time. Trend may have just died — first heads-up of a reversal.
- **Liquidity** — clusters of presumed stop-loss orders that sit above equal highs / below equal lows. Price tends to "hunt liquidity" before reversing.

#### Shared object shapes

**OrderBlock** (used by `orderBlocks` and `fvg`):

```json
{
  "type": "bullish|bearish",
  "top": 1.0892,
  "bottom": 1.0871,
  "candleIdx": 312,
  "time": 1700123400,
  "distancePct": 0.082
}
```

| Field         | Type                       | Description                                                                      |
| ------------- | -------------------------- | -------------------------------------------------------------------------------- | ----------------- | ----------------------------------------------------------------------------- |
| `type`        | `"bullish"` \| `"bearish"` | Block direction. Bullish = expected support zone; bearish = expected resistance. |
| `top`         | number                     | Upper price boundary of the zone                                                 |
| `bottom`      | number                     | Lower price boundary of the zone                                                 |
| `candleIdx`   | integer ≥ 0                | 0-based index into your submitted bars (the originating candle)                  |
| `time`        | integer                    | Bar time, UTC seconds                                                            |
| `distancePct` | number                     | `                                                                                | reference - price | / price \* 100`, distance from current price. Lower = closer = more imminent. |

**BosChochEvent**, **SwingLevel**, **SrLevel**, **RecentRange**:

| Output               | Object shape                                                           |
| -------------------- | ---------------------------------------------------------------------- | ---------------------------------------------------------- | ------------------------ | ---------------------- |
| `bosChoch` events    | `{ event: "BOS"                                                        | "CHoCH", direction: "bullish"                              | "bearish", level: number | null, time: integer }` |
| `swingLevels` events | `{ type: "high"                                                        | "low", level: number, time: integer }`                     |
| `srLevels` events    | `{ level: number, type: "support"                                      | "resistance", distancePct: number, touches: integer ≥ 2 }` |
| `recentRange`        | `{ high: number, low: number, periodHigh: number, periodLow: number }` |

**SmcEvent** (used by `liquidity`, `previousHighLow`, `sessions`, `retracements`): sparse object with `idx` + `time` always present; remaining fields forwarded as-is from the underlying `smartmoneyconcepts` library (null fields stripped to keep payloads small).

#### Outputs

##### `orderBlocks`

Live (unmitigated) order blocks across the submitted history. Use as **target zones**: a bullish block below price = a likely bounce zone; a bearish block above = a likely rejection zone.

- **Params:** none.
- **Returns:** array of OrderBlock, max 20, sorted ascending by `|distancePct|` (closest to current price first).

##### `fvg` (alias `fvgs`)

Live (unmitigated) Fair Value Gaps. Same OrderBlock shape. Trader use: gap-fill targets — bullish FVG below = likely magnet for a pullback; bearish FVG above = likely magnet for a rally before reversal.

- **Params:** none.
- **Returns:** array of OrderBlock-shaped objects, max 15, sorted ascending by distance.

##### `bosChoch`

Recent structural events. **BOS** entries say "the prior trend just continued"; **CHoCH** entries say "the prior trend just broke." A CHoCH followed by a BOS in the new direction is the canonical SMC reversal sequence.

- **Params:** none.
- **Returns:** array of BosChochEvent, max 10, scanned across the trailing 50 bars.

##### `swingLevels`

Recent confirmed swing highs and lows from the structural pass. The raw inputs SMC uses to define trend. Useful for plotting structure or for building your own break-detection logic on top of ours.

- **Params:** none.
- **Returns:** array of SwingLevel, max 10, scanned across the trailing 50 bars.

##### `srLevels`

In-house **support / resistance levels**. Construction: take pivot levels from the 7-bar swing detector (`sw7`), keep only levels touched ≥2 times (touch = high or low within ½·ATR of the level, with bars between touches), enforce ≥3·ATR spacing so you don't get near-duplicate levels stacked, return up to 3 above price (resistance) and 3 below (support), ranked by proximity. This is what most traders mean by "S/R" — actual tested levels, not arbitrary swing points.

- **Params:** none.
- **Returns:** array of SrLevel, up to 3 support + 3 resistance.

##### `recentRange`

Compact summary of the chart's range: last 20 bars vs the full submitted history. Quick context for "is current price near recent highs / lows?"

- **Params:** none.
- **Returns:** RecentRange object (`{ high, low, periodHigh, periodLow }`).

##### `liquidity`

Equal-high / equal-low clusters where stop orders likely sit. Price often runs through these before reversing ("liquidity sweep") — a classic SMC trade-trigger pattern.

| Param          | Type        | Default | Description                                        |
| -------------- | ----------- | ------: | -------------------------------------------------- |
| `swingLength`  | integer ≥ 1 |    `10` | Swing-detection window                             |
| `rangePercent` | number > 0  |  `0.01` | Max % distance for equal-high / equal-low grouping |

**Returns:** array of SmcEvent.

##### `previousHighLow`

Prior-session / prior-period high and low markers (e.g. yesterday's daily H/L). High-attention reference levels — institutions and algos commonly target them.

| Param       | Type   | Default | Description                                              |
| ----------- | ------ | ------: | -------------------------------------------------------- |
| `timeFrame` | string |  `"1D"` | Pandas resample frequency (`"1D"`, `"4H"`, `"1W"`, etc.) |

**Returns:** array of SmcEvent.

##### `sessions`

Marks bars belonging to a named trading session (London / NY / Tokyo / Sydney etc.). Use to filter signals to a specific session, or to overlay session-open/close moments.

| Param       | Type              |    Default | Description                  |
| ----------- | ----------------- | ---------: | ---------------------------- |
| `session`   | string            | `"London"` | Session name                 |
| `startTime` | `"HH:MM"` \| null | `start_time` | Override session start (UTC) |
| `endTime`   | `"HH:MM"` \| null | `end_time`   | Override session end (UTC)   |

**Returns:** array of SmcEvent.

##### `retracements`

Fibonacci retracement events relative to the most recent swing. Trader use: standard Fib levels (38.2 / 50 / 61.8) on the active leg, computed automatically without you picking the swing endpoints.

| Param         | Type        | Default | Description            |
| ------------- | ----------- | ------: | ---------------------- |
| `swingLength` | integer ≥ 1 |    `10` | Swing-detection window |

**Returns:** array of SmcEvent.

### Analysis summaries

These outputs are **last-bar snapshots** computed in a single shared analysis pass. The pass runs once per request and stores its results; each output below just reads its slice from that cached result. Requesting all six costs the same as requesting one — these are essentially free if you already need any of them.

Use them when you want a **structured "current state" view** of the chart in one shot, without subscribing to full Series outputs and reading only the last value yourself.

All are parameterless.

| Output     | Returns                                                                                                                        | Trader use                                                                                       |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------ |
| `price`    | number — last bar's close (plain scalar, not an object)                                                                        | Reference price for distance/level calculations.                                                 |
| `levels`   | `{ ema21, sma50, sma100, sma200, atr, vwap, donchianUpper, donchianLower, donchianMid }` — each `number \| null`               | Snapshot of standard MAs + ATR + VWAP + Donchian. The "where are the levels right now" view.     |
| `momentum` | `{ rsi, mfi, macdHist, macdLine, macdSignal, adx, stochK, stochD }` — each `number \| null`                                    | One-glance momentum scorecard across the popular oscillators.                                    |
| `volume`   | `{ volRatio: number\|null, obv: number\|null, isSpike: boolean }` — `isSpike` is `true` when `volRatio > 2.0`                  | Quick "is the current bar a volume spike?" check. `volRatio` is current volume / recent average. |
| `position` | object — keys from `{ema21, sma50, sma100, sma200, vwap}`, each `"above" \| "below"`. Only keys whose MA is computable appear. | Bias map: is price above or below each major reference line right now?                           |
| `slope`    | object — same keys as `position`, each `"up" \| "down"`. Direction over the last 10 bars.                                      | Are the lines themselves rising or falling? Combines with `position` for full regime read.       |

### Request fields

| Field        | Type         | Default | Required | Description                                                                           |
| ------------ | ------------ | ------- | -------- | ------------------------------------------------------------------------------------- |
| `bars`       | array of Bar | —       | **yes**  | OHLC(V) bars in chronological order. `len(bars) <= MAX_BARS` (default 5000).          |
| `indicators` | object       | —       | **yes**  | Map of `outputKey → spec`. ≥ 1 entry.                                                 |
| `symbol`     | string       | `""`    | no       | Echoed back in the response.                                                          |
| `timeframe`  | string       | `""`    | no       | Echoed back in the response.                                                          |
| `recentBars` | integer ≥ 1  | `10`    | no       | Reserved for future signal-tagging windows. Currently inert — no output type is recency-tagged. |

**Bar shape:**

| Field                          | Type        | Default | Required | Description                                                                                                |
| ------------------------------ | ----------- | ------- | -------- | ---------------------------------------------------------------------------------------------------------- |
| `time`                         | integer     | —       | **yes**  | UTC unix seconds                                                                                           |
| `open`, `high`, `low`, `close` | number      | —       | **yes**  | OHLC prices                                                                                                |
| `tickVolume`                   | integer ≥ 0 | `0`     | no       | Canonical volume field. All volume-based indicators (VWAP, OBV, VWMA, MFI, CMF, AD, ADOSC, KVO) read this. |
| `realVolume`                   | integer ≥ 0 | `0`     | no       | Accepted for forward-compat. Indicator math currently reads `tickVolume`, not this.                        |

**Spec value for each `indicators` entry:**

- `true` — run the indicator named by the output key with default params.
- `{ ...params }` — params object. Missing `type` falls back to the output key. Include `"type"` to run a known indicator under a custom output name.

### Response

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
  "bosChoch": [
    {
      "event": "BOS",
      "direction": "bullish",
      "level": 1.0918,
      "time": 1700125200
    }
  ]
}
```

| Field         | Type        | Description                                                                                       |
| ------------- | ----------- | ------------------------------------------------------------------------------------------------- |
| `symbol`      | string      | Echo of the request field                                                                         |
| `timeframe`   | string      | Echo of the request field                                                                         |
| `candles`     | integer ≥ 0 | Number of bars processed                                                                          |
| _(arbitrary)_ | varies      | One entry per output key from `indicators`. Value shape is the return of the requested indicator. |

Only the keys you requested. Plus `symbol`, `timeframe`, `candles`. Warmup positions in Series outputs are `null`, never `NaN`.

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

The per-indicator requirement is derived from its params (`length`, `slow`, `signal`, etc.) — not a global floor. SMC-backed outputs (`orderBlocks`, `fvgs`, `bosChoch`, summaries, …) share a baseline floor of `MIN_BARS` (default 50) because the analysis pipeline assumes meaningful history.

## Configuration

All env-driven. Sensible defaults. Nothing to tune for a first run.

| Variable    | Default | Description                                                                                                                                                                                                                                                                          |
| ----------- | ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `LOG_LEVEL` | `INFO`  | Standard Python logging level.                                                                                                                                                                                                                                                       |
| `MAX_BARS`  | `5000`  | Reject requests with more bars than this (HTTP 413).                                                                                                                                                                                                                                 |
| `MIN_BARS`  | `50`    | Baseline floor for SMC-backed outputs (`orderBlocks`, `fvgs`, summaries, …) and the fallback requirement for any indicator not explicitly listed in the per-indicator requirement table. Series indicators (`sma`, `rsi`, `macd`, …) compute their own min from params. |
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
                   │  swing structure     │
                   │  S/R · summaries     │
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
