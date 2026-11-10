---
title: "Indicator reference"
description: "Every wickworks indicator series: moving averages, oscillators, trend strength, volatility, volume, bands, trailing stops and squeeze, with parameters and outputs."
nav_order: 5
---

# Indicator reference

This page covers the 50 indicator types that return per-bar series. The Smart Money Concepts outputs and the last-bar summaries are on [SMC and summaries](smc.md). For how to request an indicator, run it under your own output name, or run it several times with different settings, see [the indicators object](api.md#the-indicators-object).

Each indicator below lists its parameters, their defaults, the minimum number of bars it needs (see [insufficient bars](api.md#insufficient-bars)) and the shape it returns. **Series**, **flag series** and **direction series** are defined under [value shapes](api.md#value-shapes). Every integer parameter must be a positive integer and every number parameter a positive finite number; anything else is a 400.

Most series come straight from [`pandas-ta`](https://github.com/twopirllc/pandas-ta) 0.4.71b0. CCI is computed in-house because that `pandas-ta` release has an operator-precedence bug in its CCI. The [test suite](development.md#testing) checks the standard indicators against formulas written from scratch on real EURUSD H1 bars.

The descriptions say how traders commonly read each indicator. wickworks only computes the numbers; it never turns them into signals.

## Moving averages

Smoothed price lines. Each type trades responsiveness against lag in its own way, so pick by how fast you want the line to react to new bars. Traders use them to define the dominant direction (price above or below the line), as dynamic support and resistance, and for fast-over-slow crossovers.

All of them take one `length` parameter, read `close` (`vwma` also reads `volume`), need `length` bars, and return a series.

| `type` | default `length` | What it is |
| --- | ---: | --- |
| `ema` | 21 | Exponential MA. Weights recent bars more. The usual trend filter. |
| `sma` | 50 | Simple MA. A flat average, slow and smooth. 50 and 200 SMA crosses are the "golden cross" and "death cross". |
| `hma` | 14 | Hull MA. Low lag and smooth; reacts faster than an EMA of the same length without the extra noise. |
| `wma` | 14 | Linearly weighted MA. Sits between SMA and EMA in lag. |
| `dema` | 10 | Double EMA. Less lag than an EMA through a correction term. |
| `tema` | 10 | Triple EMA. Even less lag, and more whipsaw in a range. |
| `t3` | 10 | Tillson T3. Smooth like an SMA, fast like an EMA. |
| `kama` | 10 | Kaufman Adaptive MA. Speeds up in trends and slows down in ranges. |
| `alma` | 10 | Arnaud Legoux MA. Gaussian weights; low noise for its lag. |
| `linreg` | 14 | Linear regression line over the window, evaluated at the current bar. |
| `jma` | 7 | Jurik MA. Very smooth with very low lag. |
| `zlma` | 10 | Zero-lag MA. An EMA with an error correction that tries to remove the lag. |
| `rma` | 10 | Wilder's smoothing, the average used inside RSI and ATR. Heavy and slow. |
| `fwma` | 10 | Fibonacci-weighted MA. |
| `swma` | 10 | Symmetric-weighted MA. Weights peak in the middle of the window. |
| `sinwma` | 14 | Sine-weighted MA. Very smooth. |
| `trima` | 10 | Triangular MA, a double-smoothed SMA. Smoother than an SMA, with more lag. |
| `vwma` | 10 | Volume-weighted MA. Bars with more volume count more. |

```json
{
  "ema": true,
  "ema50": {
    "type": "ema",
    "length": 50
  }
}
```

### vwap

Volume-weighted average price of the typical price `(high + low + close) / 3`, reset at each anchor boundary. Unlike a rolling average, VWAP accumulates from a fixed start.

| Parameter | Type | Default | Description |
| --- | --- | ---: | --- |
| `anchor` | `"D"`, `"W"` or `"M"` | `"D"` | Reset at each UTC day, week or month |
| `sessionOffset` (`session_offset`) | string or number | `0` | Shift the anchor away from UTC midnight. A Go-style duration (`"-5h"`, `"1h30m"`, `"90s"`) or a number of seconds |

Needs 1 bar. Returns a series.

The offset moves the boundary by a fixed amount. It does not follow exchange calendars or daylight saving changes. Only `"D"`, `"W"` and `"M"` are known to work as `anchor`; other values pass validation but can fail inside `pandas-ta` with a 500.

## Momentum oscillators

These measure the rate of price change rather than the price. Most are bounded or centered on zero, so readings compare across instruments and timeframes. Traders watch for overbought and oversold extremes, for momentum that fades while price keeps going, and for zero-line or midline crosses.

### Single-line oscillators

One `length` parameter, one series back.

| `type` | default | Reads | Scale | Minimum bars | What it is |
| --- | ---: | --- | --- | --- | --- |
| `rsi` | 14 | close | 0 to 100 | `length + 1` | Relative Strength Index. Above 70 is commonly called overbought, below 30 oversold. |
| `mfi` | 14 | high, low, close, volume | 0 to 100 | `length + 1` | Money Flow Index, an RSI weighted by volume. |
| `willr` | 14 | high, low, close | -100 to 0 | `length` | Williams %R, an inverted stochastic. -20 and -80 are the usual thresholds. |
| `cci` | 14 | typical price | unbounded | `length` | Commodity Channel Index: distance of the typical price from its moving average in units of mean absolute deviation. ±100 are the usual thresholds. |
| `roc` | 10 | close | percent | `length + 1` | Rate of change: percent move over `length` bars. |
| `mom` | 10 | close | price units | `length + 1` | Momentum: `close - close[length bars ago]`. |

`cci` also takes `c` (number, default `0.015`), the scaling constant in Lambert's formula. CCI on a perfectly flat window divides by zero; wickworks returns `null` there.

### uo

Ultimate Oscillator. Blends three lookback windows into one 0 to 100 line, designed to cut the false readings a single-window oscillator gives in a range.

| Parameter | Type | Default | Description |
| --- | --- | ---: | --- |
| `fast` | integer | `7` | Short window |
| `medium` | integer | `14` | Medium window |
| `slow` | integer | `28` | Long window |

`fast < medium < slow` is required. Needs `slow + 1` bars. Returns a series from 0 to 100.

### stoch

Stochastic oscillator: where the close sits in the recent high-to-low range. `k` is the raw position, `d` a smoothed `k`. Faster to react than RSI, and noisier for it.

| Parameter | Type | Default | Description |
| --- | --- | ---: | --- |
| `k` | integer | `14` | Lookback for `%K` |
| `d` | integer | `3` | `%D` smoothing |
| `smoothK` (`smooth_k`, `smooth`) | integer | `3` | `%K` smoothing |

Needs `k + d + smoothK` bars. Returns `{ k, d }`, each a series from 0 to 100.

### stochrsi

The stochastic formula applied to RSI values instead of price. Reacts far more often than a plain stochastic.

| Parameter | Type | Default | Description |
| --- | --- | ---: | --- |
| `length` | integer | `14` | Stochastic lookback over RSI |
| `rsiLength` (`rsi_length`) | integer | `14` | RSI length |
| `k` | integer | `3` | `%K` smoothing |
| `d` | integer | `3` | `%D` smoothing |

Needs `rsiLength + length + k + d` bars. Returns `{ k, d }`, each a series from 0 to 100.

### macd

Moving Average Convergence Divergence: a fast EMA minus a slow EMA, plus a signal EMA of that difference. `hist` is `macd - signal`.

| Parameter | Type | Default | Description |
| --- | --- | ---: | --- |
| `fast` | integer | `12` | Fast EMA |
| `slow` | integer | `26` | Slow EMA |
| `signal` | integer | `9` | Signal EMA over `macd` |

`fast < slow` is required. Needs `slow + signal` bars. Returns `{ macd, signal, hist }`, each a series.

### tsi, trix and fisher

All three return the line under their own name plus a signal line: `{ tsi, signal }`, `{ trix, signal }`, `{ fisher, signal }`.

**`tsi`**, True Strength Index: double-smoothed close momentum. Smoother and slower to flip than MACD.

| Parameter | Type | Default |
| --- | --- | ---: |
| `fast` | integer | `13` |
| `slow` | integer | `25` |
| `signal` | integer | `13` |

`fast < slow` is required. Needs `slow + signal` bars.

**`trix`**: rate of change of a triple-smoothed EMA. It filters out cycles shorter than `length`, so it reads longer-term momentum.

| Parameter | Type | Default | Description |
| --- | --- | ---: | --- |
| `length` | integer | `30` | EMA length for the triple smoothing |
| `signal` | integer | `9` | Signal EMA over `trix` |

Needs `3 × length + signal` bars.

**`fisher`**, Ehlers Fisher Transform: reshapes price into a near-Gaussian distribution so turning points stand out. Reads `high` and `low` only.

| Parameter | Type | Default |
| --- | --- | ---: |
| `length` | integer | `9` |
| `signal` | integer | `1` |

Needs `length + 1` bars.

## Trend strength and direction

These say how strongly the market trends, or which side is in control, rather than where price is. Traders pair them with a price-based indicator to decide whether to trust trend readings at all.

### adx

Average Directional Index with the directional movement lines. `adx` measures trend strength regardless of direction; `diPlus` and `diMinus` are the directional components. A common rule of thumb reads `adx` above 25 as trending and below 20 as ranging.

| Parameter | Type | Default |
| --- | --- | ---: |
| `length` | integer | `14` |

Needs `2 × length` bars. Returns `{ adx, diPlus, diMinus }`, each a series.

### aroon

Bars since the highest high and since the lowest low over the window, scaled to 0 to 100. `up` near 100 means new highs keep coming; `down` near 100 means new lows. `oscillator` is `up - down`.

| Parameter | Type | Default |
| --- | --- | ---: |
| `length` | integer | `14` |

Needs `length + 1` bars. Returns `{ up, down, oscillator }`; `up` and `down` run 0 to 100, `oscillator` -100 to 100.

### vortex

Positive (`plus`) and negative (`minus`) trend movement relative to true range. A `plus` line crossing above `minus` is read as a bullish shift, the reverse as bearish.

| Parameter | Type | Default |
| --- | --- | ---: |
| `length` | integer | `14` |

Needs `length + 1` bars. Returns `{ plus, minus }`, each a series.

## Volatility

These measure how far price moves, not which way. Traders use them for stop distance (rarely tighter than one or two ATR), position sizing (smaller size when volatility is high) and regime detection.

| `type` | default `length` | Scale | Minimum bars | What it is |
| --- | ---: | --- | --- | --- |
| `atr` | 14 | price units | `length + 1` | Average True Range: the average bar range including gaps. |
| `natr` | 14 | percent of close | `length + 1` | Normalized ATR: ATR as a percentage of close, comparable across instruments. |

Both read `high`, `low` and `close` and return a series.

## Volume and money flow

These compare price movement with the `volume` series you sent. They show whether activity grew or shrank with a move. They do not identify who traded or prove a breakout is real.

### obv and ad

No parameters. Each needs 1 bar and returns a cumulative series.

- **`obv`**, On-Balance Volume: adds the bar's volume on up closes and subtracts it on down closes.
- **`ad`**, Accumulation/Distribution: weights each bar's volume by where the close sits in the bar's range (near the high counts as buying, near the low as selling).

### cmf

Chaikin Money Flow: the A/D calculation over a rolling window instead of from the start. Runs from -1 to 1; positive means net accumulation over the window.

| Parameter | Type | Default |
| --- | --- | ---: |
| `length` | integer | `20` |

Needs `length` bars. Returns a series.

### adosc

Chaikin A/D Oscillator: fast EMA minus slow EMA of the A/D line. Tracks acceleration in accumulation rather than its direction.

| Parameter | Type | Default | Description |
| --- | --- | ---: | --- |
| `fast` | integer | `3` | Fast EMA over A/D |
| `slow` | integer | `10` | Slow EMA over A/D |

`fast < slow` is required. Needs `slow` bars. Returns a series.

### kvo

Klinger Volume Oscillator with a signal line. Built to track long-term money flow while staying sensitive to short swings.

| Parameter | Type | Default |
| --- | --- | ---: |
| `fast` | integer | `34` |
| `slow` | integer | `55` |
| `signal` | integer | `13` |

`fast < slow` is required. Needs `slow + signal` bars. Returns `{ kvo, signal }`, each a series.

## Bands and channels

Lines that wrap price. Traders fade touches of the outer band in ranges, treat closes outside the band as breakouts, and watch narrowing bands as compression before expansion. The three types use different widths: standard deviation, ATR and raw range.

All three return `{ upper, middle, lower }`, each a series.

### bbands

Bollinger Bands: an SMA plus and minus `std` standard deviations. The width adapts to recent volatility. In strong trends price can ride one band for a long time.

| Parameter | Type | Default | Description |
| --- | --- | ---: | --- |
| `length` | integer | `20` | SMA window |
| `std` | number | `2.0` | Band width in standard deviations |

Needs `length` bars.

### kc

Keltner Channels: an EMA plus and minus `scalar` ATRs. Smoother than Bollinger Bands, because a single outlier bar moves the ATR less than the standard deviation.

| Parameter | Type | Default | Description |
| --- | --- | ---: | --- |
| `length` | integer | `20` | EMA and ATR window |
| `scalar` | number | `2.0` | ATR multiplier |

Needs `length` bars.

### donchian

Donchian Channels: the highest high and lowest low over the window, with `middle` halfway between. A close above `upper` is a new `length`-bar high, the classic Turtle breakout.

| Parameter | Type | Default |
| --- | --- | ---: |
| `length` | integer | `20` |

Needs `length` bars.

## Trailing trend lines

Single lines that flip sides with the trend. Traders use them as a trend filter (longs only while bullish) and as a trailing stop (the line is the exit if the trend turns). They differ in how tight they trail and how often they flip.

### supertrend

An ATR band that sits below price in an uptrend and above it in a downtrend, and jumps to the other side when price closes through it.

| Parameter | Type | Default | Description |
| --- | --- | ---: | --- |
| `length` | integer | `7` | ATR window |
| `multiplier` | number | `3.0` | ATR multiplier |

Needs `length + 1` bars. Returns `{ value, direction, long, short }`. `value` is the band (series), `direction` a direction series, and `long` and `short` carry the band only while that side is active, `null` otherwise, so you can draw the two sides in different colors.

### psar

Parabolic SAR: Wilder's stop-and-reverse. The level accelerates toward price during a trend and flips sides when price reaches it. The tightest of the trailing stops, which makes it flip often in a range.

| Parameter | Type | Default | Description |
| --- | --- | ---: | --- |
| `af` (`step`) | number | `0.02` | Acceleration step per bar |
| `max` (`maxAf`) | number | `0.2` | Maximum acceleration |

`af` must not exceed `max`. Needs 2 bars. Returns `{ long, short, af, reversal }`: `long` and `short` are the SAR level on the active side (series, `null` on the other), `af` is the current acceleration (series), and `reversal` is a flag series that is `1` on bars where the trend flipped.

### chandelierExit

An ATR stop hung from the highest high (long side) or the lowest low (short side) over the window. Trails further from price than supertrend, so it flips less.

| Parameter | Type | Default | Description |
| --- | --- | ---: | --- |
| `length` | integer | `22` | High and low lookback |
| `atrLength` (`atr_length`) | integer | `22` | ATR window |
| `multiplier` | number | `2.0` | ATR multiplier |

Needs `max(length, atrLength) + 1` bars. Returns `{ long, short, direction }`: the long and short exit levels (series) and a direction series.

### ichimoku

Ichimoku Kinko Hyo. `tenkan` and `kijun` are midpoints of the high-low range over their windows. `spanA` and `spanB` form the cloud and are shifted `kijun` bars forward, so the value at a bar is the one computed `kijun` bars earlier. `chikou` is the close shifted `kijun` bars back: the value at a bar is the close from `kijun` bars later, so the last `kijun - 1` values are `null`. That makes `chikou` the one output on this page that looks into the future; do not feed it to anything that must only use past bars.

| Parameter | Type | Default | Description |
| --- | --- | ---: | --- |
| `tenkan` | integer | `9` | Conversion line window |
| `kijun` | integer | `26` | Base line window, and the shift for the spans and `chikou` |
| `senkou` | integer | `52` | Leading span B window |

`tenkan < kijun < senkou` is required. Needs `senkou` bars. Returns `{ spanA, spanB, tenkan, kijun, chikou }`, each a series in price units, aligned with your bars. The part of the cloud projected past the last bar is not returned.

## Compression

### squeeze

TTM Squeeze. Compares Bollinger Bands with Keltner Channels to find compression, and adds a momentum value.

| Parameter | Type | Default |
| --- | --- | ---: |
| `bbLength` (`bb_length`) | integer | `20` |
| `bbStd` (`bb_std`) | number | `2.0` |
| `kcLength` (`kc_length`) | integer | `20` |
| `kcScalar` (`kc_scalar`) | number | `1.5` |

Needs `max(bbLength, kcLength)` bars. Returns `{ value, on, off, no }`:

- `value`: the squeeze momentum (series). Positive is upward momentum, negative downward.
- `on`: flag series, `1` while both Bollinger Bands sit inside the Keltner Channels. The market is compressed.
- `off`: flag series, `1` while both Bollinger Bands sit outside the Keltner Channels.
- `no`: flag series, `1` when neither is true.

Each bar has exactly one of the three flags set. The flags describe the state at that bar; a release is the first `off` or `no` bar after a run of `on` bars, which you detect yourself.
