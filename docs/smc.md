---
title: "SMC and summaries"
description: "wickworks Smart Money Concepts outputs (order blocks, FVGs, BOS/CHoCH, swing and S/R levels, liquidity, sessions, retracements) and the last-bar summaries."
nav_order: 6
---

# SMC and summaries

Smart Money Concepts (SMC) is a price-action framework that labels zones, levels and structural breaks from OHLC patterns. wickworks reports what the configured algorithms detected in the bars you sent. It does not see orders, and it does not predict whether price will react to a level.

Most of these outputs come from the [`smartmoneyconcepts`](https://github.com/joshyattridge/smart-money-concepts) library 0.0.26. wickworks runs a numba port of its order block, FVG, BOS/CHoCH and swing functions ([`smc_fast.py`](https://github.com/psyb0t/docker-wickworks/blob/main/src/wickworks/smc_fast.py)) that the test suite proves gives the same results as the library. Support and resistance levels, touch counts and the summaries are wickworks' own code.

Every output on this page needs at least `MIN_BARS` bars (default 50; see [configuration](configuration.md)). For how to request them, see [the indicators object](api.md#the-indicators-object).

## Terms

- **Order block:** the zone of the last opposite-direction candle before a qualifying move, as the algorithm detects it.
- **Fair value gap (FVG):** a three-bar pattern where the first and third bars' wicks do not overlap, leaving a gap.
- **Mitigation:** a later return of price into a zone.
- **Swing high or low:** a local pivot. SMC reads trend from the sequence of swings: higher highs and higher lows up, lower highs and lower lows down.
- **BOS (break of structure):** a break of a swing level in the direction of the current structure.
- **CHoCH (change of character):** a break of a swing level against the current structure. It is not proof of a reversal.
- **Liquidity:** in SMC terms, clusters of equal highs or equal lows, where stop orders are assumed to sit.

## The shared analysis pass

`orderBlocks`, `fvg`, `bosChoch`, `swingLevels`, `srLevels`, `recentRange` and all six summaries read from one analysis of the whole history. wickworks runs it at most once per request, the first time an output needs it. Asking for all of them costs about the same as asking for one.

`liquidity`, `previousHighLow`, `sessions` and `retracements` are computed separately and take parameters.

## Time fields

Structural objects carry three timestamps, all UTC unix seconds, so you can tell where a pattern formed from when it became knowable:

| Field | Meaning |
| --- | --- |
| `originAt` | Time of the bar where the pattern formed (the same value as `time`) |
| `confirmedAt` | Time of the first bar at which the pattern was knowable. `null` when that bar is past the end of your data |
| `observedAsOf` | Time of the last bar you sent, the moment the snapshot describes |

A backtest that only uses objects with `confirmedAt` at or before its current bar avoids lookahead.

## orderBlocks

Every order block found in the submitted history, mitigated or not, with the state you need to apply your own freshness rule. No parameters.

```json
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
```

| Field | Type | Description |
| --- | --- | --- |
| `type` | `"bullish"` or `"bearish"` | Zone direction. Bullish zones sit below price as support, bearish ones above as resistance |
| `top`, `bottom` | number | Zone boundaries |
| `candleIdx` | integer | Zero-based index of the origin bar in your `bars` |
| `time`, `originAt`, `confirmedAt`, `observedAsOf` | integer | See [time fields](#time-fields) |
| `mitigatedWick` | boolean | A later bar's wick went through the zone in the invalidating direction |
| `mitigatedWickAt` | integer or null | Time of that bar |
| `mitigatedClose` | boolean | A later bar closed through the zone in the invalidating direction |
| `mitigatedCloseAt` | integer or null | Time of that bar |
| `touchEvents` | array of integers | Each entry is the offset in bars from the origin bar where price entered the zone again after leaving it. `[1, 8]` means the next bar touched the zone, price left, and a new touch started 8 bars after the origin |
| `touchCount` | integer | Entries in `touchEvents` with an offset above 5. The first five bars after the origin are the move that created the block, so wickworks does not count them as tests |
| `distancePct` | number | Signed distance from price to the near edge, in percent of the last close: `(close - top) / close × 100` for bullish blocks, `(bottom - close) / close × 100` for bearish ones. Negative when price is already past that edge |

Returns at most 40 blocks, sorted by absolute `distancePct`, nearest first.

## fvg

Fair value gaps that price has not yet filled. Also accepted as `fvgs`. No parameters.

| Field | Type | Description |
| --- | --- | --- |
| `type` | `"bullish"` or `"bearish"` | Gap direction |
| `top`, `bottom` | number | Gap boundaries |
| `candleIdx` | integer | Zero-based index of the bar the gap is attributed to |
| `time`, `originAt`, `confirmedAt`, `observedAsOf` | integer | See [time fields](#time-fields). `confirmedAt` is one bar after the origin |
| `distancePct` | number | Absolute distance from the last close to the middle of the gap, in percent of the close |

Returns at most 15 gaps, nearest first. Mitigated gaps are dropped, so the mitigation fields order blocks carry do not appear here.

## bosChoch

Breaks of structure and changes of character found in the last 50 bars. No parameters.

```json
{
  "event": "BOS",
  "direction": "bullish",
  "level": 1.0918,
  "time": 1700125200,
  "originAt": 1700125200,
  "confirmedAt": 1700132400,
  "observedAsOf": 1700200000
}
```

`event` is `"BOS"` or `"CHoCH"`, `direction` is `"bullish"` or `"bearish"`, `level` is the broken swing level (number or `null`). `confirmedAt` is the time of the bar that broke the level. Returns the 10 most recent events, oldest first.

## swingLevels

Swing highs and lows from the structural pass in the last 50 bars, the raw input SMC builds its trend on. Useful for drawing structure or writing your own break detection. No parameters.

```json
{
  "type": "high",
  "level": 1.17203,
  "time": 1777420800,
  "originAt": 1777420800,
  "confirmedAt": 1777474800,
  "observedAsOf": 1777593600
}
```

`type` is `"high"` or `"low"`. wickworks treats a swing as confirmed 15 bars after its pivot, so `confirmedAt` is the time of the bar 15 bars after `originAt`, or `null` when that bar is past the end of your data. Returns the 10 most recent, oldest first.

## srLevels

wickworks' own support and resistance levels. No parameters.

1. Take at most the latest 500 bars.
2. Take pivots from a 7-bar swing detector.
3. Keep a swing high above the last close as resistance, or a swing low below it as support, when bars came within half an ATR (14) of it at least twice, counting touches more than five bars apart.
4. Space kept levels at least three ATR apart.
5. Return up to three levels below price and three above, nearest first.

```json
{
  "level": 1.17547,
  "type": "resistance",
  "distancePct": 0.233,
  "touches": 8
}
```

`type` is `"support"` or `"resistance"`, `touches` is the touch count (at least 2), and `distancePct` is the distance from the last close in percent. Returns an empty array with fewer than 50 bars or when ATR is zero.

## recentRange

The high and low of the last 20 bars next to the high and low of everything you sent. No parameters.

```json
{
  "high": 1.17415,
  "low": 1.16576,
  "periodHigh": 1.18489,
  "periodLow": 1.16548
}
```

## liquidity

Clusters of equal highs or equal lows among swing points, grouped when they lie within `rangePercent` of each other.

| Parameter | Type | Default | Description |
| --- | --- | ---: | --- |
| `swingLength` (`swing_length`) | integer | `10` | Swing detection window |
| `rangePercent` (`range_percent`) | number | `0.01` | Largest distance, as a fraction, for grouping levels. At most 1 |

Returns an array of [SMC events](#smc-events), one per cluster, with the library's fields `Liquidity` (`1` for highs, `-1` for lows), `Level`, `End` (bar index of the last level in the cluster) and `Swept` (bar index of the candle that took it out).

## previousHighLow

The high and low of the previous completed period, on every bar.

| Parameter | Type | Default | Description |
| --- | --- | ---: | --- |
| `timeFrame` (`time_frame`) | string | `"1D"` | The period length: `15m`, `30m`, `1H`, `4H`, `1D`, `1W` or `1M`. The spellings `15min`, `30min`, `1h`, `4h`, `1d`, `1w` and `1ME` also work |

Periods are fixed UTC buckets, not exchange sessions. Weeks run Monday to Sunday. Despite the name, `timeFrame` has nothing to do with the request's top-level `timeframe` label.

Returns an array of [SMC events](#smc-events), one per bar from the second period on, with `PreviousHigh`, `PreviousLow`, and `BrokenHigh` / `BrokenLow`, which become `1` once a bar in the current period has gone above the previous high or below the previous low.

## sessions

Marks which bars fall inside a fixed UTC clock window.

| Parameter | Type | Default | Description |
| --- | --- | ---: | --- |
| `session` | string | `"London"` | A named window from the table below, or `"Custom"` |
| `startTime` (`start_time`) | `"HH:MM"` | none | UTC start. Required for `"Custom"`, rejected for named windows |
| `endTime` (`end_time`) | `"HH:MM"` | none | UTC end. Required for `"Custom"`, rejected for named windows |

| `session` | UTC window |
| --- | --- |
| `Sydney` | 21:00 to 06:00 |
| `Tokyo` | 00:00 to 09:00 |
| `London` | 07:00 to 16:00 |
| `New York` | 13:00 to 22:00 |
| `Asian kill zone` | 00:00 to 04:00 |
| `London open kill zone` | 06:00 to 09:00 |
| `New York kill zone` | 11:00 to 14:00 |
| `london close kill zone` | 14:00 to 16:00 |

The names are case sensitive, including the lowercase `london close kill zone`. The windows never move for holidays or daylight saving time.

Returns an array of [SMC events](#smc-events), one per bar, with `Active` (`1` inside the window, `0` outside) and the session's running `High` and `Low`.

## retracements

How far price has pulled back from the most recent swing.

| Parameter | Type | Default | Description |
| --- | --- | ---: | --- |
| `swingLength` (`swing_length`) | integer | `10` | Swing detection window |

Returns an array of [SMC events](#smc-events), one per bar, with `Direction` (`1` bullish, `-1` bearish, `0` before the first swing), `CurrentRetracement%` and `DeepestRetracement%`. These are percentages of the swing leg. wickworks does not compute Fibonacci levels; compare the percentages with 38.2, 50 or 61.8 yourself if you want them.

## SMC events

`liquidity`, `previousHighLow`, `sessions` and `retracements` return arrays of flat objects. Each has `idx` (zero-based bar index) and `time`, plus the library's columns for that output, named as the library names them (so `CurrentRetracement%`, not camelCase). Fields that are `null` for a bar are left out of that object. Numbers are rounded to six decimal places, and flags such as `Active` come out as `1.0` and `0.0`.

## Analysis summaries

Six outputs that describe the last bar, read from the [shared analysis pass](#the-shared-analysis-pass). Use them for a one-call "where are we now" view instead of requesting full series and reading the last value. None takes parameters. Numbers are rounded to six decimal places, except `price`.

| Output | Returns |
| --- | --- |
| `price` | The last close, a plain number |
| `levels` | `{ ema21, sma50, sma100, sma200, atr, vwap, donchianUpper, donchianLower, donchianMid }`, each a number or `null` |
| `momentum` | `{ rsi, mfi, macdHist, macdLine, macdSignal, adx, stochK, stochD }`, each a number or `null` |
| `volume` | `{ volRatio, obv, isSpike }`. `volRatio` is the last bar's volume divided by its moving average (number or `null`), `isSpike` is `true` when `volRatio` is above 2 |
| `position` | Whether the last close is `"above"` or `"below"` each of `ema21`, `sma50`, `sma100`, `sma200` and `vwap`. A key is missing when that line has no value yet |
| `slope` | Whether each of the same lines is `"up"` or `"down"` compared with 10 bars earlier. A key is missing when the line has no value at either end or did not change |

The lines behind the summaries use fixed settings: EMA 21, SMA 50, 100 and 200, ATR 14, a daily UTC-anchored VWAP, Donchian 20, RSI 14, MFI 14, MACD 12/26/9, ADX 14 and Stochastic 14/3/3. Run the matching [indicator](indicators.md) with your own parameters if you need different ones.

The moving average under `volRatio` picks its length from the median spacing of your bar times: 200 bars for 1-minute bars, 100 for 5-minute, 60 for 15-minute, 50 for 30-minute, hourly and 4-hour, 200 for daily, 52 for weekly, aiming at about two weeks of history.

`sma200` and its `position` and `slope` entries stay `null` or missing until you send at least 200 bars.

Example with 300 hourly bars:

```json
{
  "price": 1.1727400000000001,
  "levels": {
    "ema21": 1.171421,
    "sma50": 1.16987,
    "sma100": 1.170796,
    "sma200": 1.171686,
    "atr": 0.001253,
    "vwap": 1.1727,
    "donchianUpper": 1.17415,
    "donchianLower": 1.16576,
    "donchianMid": 1.169955
  },
  "momentum": {
    "rsi": 60.91879,
    "mfi": 51.890517,
    "macdHist": 0.000153,
    "macdLine": 0.00116,
    "macdSignal": 0.001006,
    "adx": 28.226202,
    "stochK": 79.810212,
    "stochD": 81.760339
  },
  "volume": {
    "volRatio": 0.725984,
    "obv": -157406.0,
    "isSpike": false
  },
  "position": {
    "ema21": "above",
    "sma50": "above",
    "sma100": "above",
    "sma200": "above",
    "vwap": "above"
  },
  "slope": {
    "ema21": "up",
    "sma50": "up",
    "sma100": "up",
    "sma200": "down",
    "vwap": "up"
  }
}
```
