"""Human-readable metadata catalog for every wickworks output path.

Returned by `GET /metadata` as a static JSON catalog so consumers (frontends,
report builders, LLM tooling) can render labels, descriptions, and
interpretation hints without re-implementing domain knowledge.

Keys are dot-notation paths matching the JSON response of `POST /`:

  - Top-level keys exactly match registry.INDICATORS keys
    (`rsi`, `orderBlocks`, `momentum`, ...).
  - Sub-fields of compound outputs use a dot:
    `macd.hist`, `momentum.macdHist`, `levels.ema21`.
  - Fields inside elements of an array of objects use `[]`:
    `orderBlocks[].type`, `retracements[].CurrentRetracement%`.

Lookup precedence the consumer should follow:

  1. Exact match (`momentum.macdHist`).
  2. Strip the array index, match the bracket form
     (`retracements[42].Direction` → `retracements[].Direction`).
  3. Strip the leading section name and look up the bare field
     (`momentum.macdHist` → `macdHist`) — last-resort, for newly added
     sub-fields not yet enumerated here.

Categories the FE can group by:
  trend, momentum, volatility, volume, smc, range, summary, structure.

Every entry has the same shape:
  {
    "label":         "RSI",
    "displayName":   "Relative Strength Index",
    "description":   "Momentum oscillator: ratio of average gains to losses.",
    "interpretation":">70 overbought, <30 oversold.",
    "unit":          "0–100",
    "category":      "momentum",
  }

Field semantics:
  label          short chip label (3–8 chars; suitable for compact table cells)
  displayName    full human title (suitable for tooltips / headings)
  description    one sentence on WHAT it measures
  interpretation 1–2 sentences on HOW to read the value (bullish / bearish /
                 reversal / strength). May be empty for raw scalars where the
                 number doesn't have a standard reading.
  unit           "0–100" / "price units" / "−1..+1" / "+1=bullish, −1=bearish"
  category       trend | momentum | volatility | volume | smc | range |
                 summary | structure
"""

from __future__ import annotations

from typing import Any


# Internal type alias — every metadata row has this exact shape.
MetaEntry = dict[str, str]


def _entry(
    label: str,
    display_name: str,
    description: str,
    interpretation: str,
    unit: str,
    category: str,
) -> MetaEntry:
    return {
        "label": label,
        "displayName": display_name,
        "description": description,
        "interpretation": interpretation,
        "unit": unit,
        "category": category,
    }


# ---------------------------------------------------------------------------
# Top-level series (single line per bar) + their sub-fields where applicable
# ---------------------------------------------------------------------------

_MOMENTUM_OSCILLATORS: dict[str, MetaEntry] = {
    "rsi": _entry(
        "RSI", "Relative Strength Index",
        "Ratio of average gains to average losses over the lookback window.",
        ">70 overbought (potential reversal lower); <30 oversold (potential bounce). 50 = no edge. Divergences with price flag exhaustion.",
        "0–100", "momentum",
    ),
    "stochrsi": _entry(
        "StochRSI", "Stochastic RSI",
        "RSI passed through a stochastic oscillator — measures RSI's position within its own recent range.",
        "Faster than raw RSI. Crosses above 0.8 = overbought; below 0.2 = oversold. K/D crossovers in extremes flag pivots.",
        "0–1", "momentum",
    ),
    "stochrsi.k": _entry("%K", "StochRSI %K (fast line)",
        "Fast line of Stochastic RSI.",
        "Crosses above %D = bullish momentum kick. Below %D = bearish.",
        "0–1", "momentum"),
    "stochrsi.d": _entry("%D", "StochRSI %D (signal line)",
        "Slow signal line of Stochastic RSI (SMA of %K).",
        "Direction of %D = smoothed momentum trend.",
        "0–1", "momentum"),

    "willr": _entry(
        "Williams %R", "Williams Percent Range",
        "Where the current close sits relative to the highest high of the lookback period.",
        ">−20 overbought, <−80 oversold. Reading is INVERTED vs RSI: closer to 0 is stronger.",
        "−100..0", "momentum",
    ),
    "cci": _entry(
        "CCI", "Commodity Channel Index",
        "Deviation of typical price from its moving average, normalized by mean absolute deviation.",
        ">+100 strong up-move (often continuation early, exhaustion late). <−100 strong down-move. Crossing 0 = trend shift.",
        "unbounded", "momentum",
    ),
    "roc": _entry(
        "ROC", "Rate of Change",
        "Percent change in close over the lookback period.",
        "Sign = direction; magnitude = velocity. Positive divergence with falling price = bullish.",
        "%", "momentum",
    ),
    "mom": _entry(
        "MOM", "Momentum",
        "Absolute price difference vs N bars ago (close[t] − close[t−N]).",
        "Same as ROC but in price units rather than %. Useful for absolute-move comparisons.",
        "price units", "momentum",
    ),
    "uo": _entry(
        "UO", "Ultimate Oscillator",
        "Weighted blend of buying pressure across three different lookback periods.",
        ">70 overbought, <30 oversold. Reduces false signals vs single-period oscillators.",
        "0–100", "momentum",
    ),
    "mfi": _entry(
        "MFI", "Money Flow Index",
        "RSI calculation but weighted by volume — measures buying vs selling pressure.",
        ">80 overbought, <20 oversold. Diverging with price = volume isn't confirming the move.",
        "0–100", "momentum",
    ),

    "macd": _entry(
        "MACD", "Moving Average Convergence Divergence",
        "Difference between two EMAs (fast − slow), plus a signal line and histogram.",
        "MACD crossing above signal = bullish; below = bearish. Histogram = momentum acceleration.",
        "price units", "momentum",
    ),
    "macd.macd": _entry("MACD line", "MACD line",
        "Fast EMA minus slow EMA of close.",
        "Above zero = uptrend bias; below = downtrend.",
        "price units", "momentum"),
    "macd.signal": _entry("Signal", "MACD signal line",
        "EMA of the MACD line.",
        "MACD crossing above this line = bull cross; below = bear cross.",
        "price units", "momentum"),
    "macd.hist": _entry("Hist", "MACD histogram",
        "MACD line minus signal line — momentum acceleration.",
        "Growing positive = bullish momentum building; growing negative = bearish. Sign-flip ≈ MACD cross.",
        "price units", "momentum"),

    "stoch": _entry(
        "Stoch", "Stochastic Oscillator",
        "Position of close within the high-low range of the lookback window.",
        ">80 overbought, <20 oversold. %K/%D crosses in extremes are pivot signals.",
        "0–100", "momentum",
    ),
    "stoch.k": _entry("%K", "Stochastic %K (fast)",
        "Raw stochastic value.",
        "Crossing above %D in oversold = bullish; below in overbought = bearish.",
        "0–100", "momentum"),
    "stoch.d": _entry("%D", "Stochastic %D (signal)",
        "SMA of %K — smooths the fast line.",
        "Trend direction of momentum.",
        "0–100", "momentum"),

    "adx": _entry(
        "ADX", "Average Directional Index",
        "Trend strength regardless of direction, plus +DI/−DI directional lines.",
        "ADX >25 = trending market; <20 = ranging. +DI > −DI = bullish bias; reverse = bearish.",
        "0–100", "momentum",
    ),
    "adx.adx": _entry("ADX", "ADX trend-strength",
        "Smoothed directional movement — pure trend-strength gauge.",
        ">25 trending, >40 strong trend, <20 chop. Direction-agnostic.",
        "0–100", "momentum"),
    "adx.diPlus": _entry("+DI", "Positive Directional Index",
        "Strength of upward price movement.",
        "Above −DI = bullish dominance.",
        "0–100", "momentum"),
    "adx.diMinus": _entry("−DI", "Negative Directional Index",
        "Strength of downward price movement.",
        "Above +DI = bearish dominance.",
        "0–100", "momentum"),

    "aroon": _entry(
        "Aroon", "Aroon Indicator",
        "Time since the highest high and lowest low within the lookback window.",
        "Aroon Up >70 + Aroon Down <30 = strong uptrend. Reverse = strong downtrend. Oscillator >0 = bullish bias.",
        "0–100 (osc: −100..+100)", "momentum",
    ),
    "aroon.up": _entry("Aroon↑", "Aroon Up",
        "Bars since the recent high, expressed as % of lookback.",
        ">70 = fresh high recently (trending up); <30 = high was long ago.",
        "0–100", "momentum"),
    "aroon.down": _entry("Aroon↓", "Aroon Down",
        "Bars since the recent low, expressed as % of lookback.",
        ">70 = fresh low recently (trending down).",
        "0–100", "momentum"),
    "aroon.oscillator": _entry("Aroon Osc", "Aroon Oscillator",
        "Aroon Up minus Aroon Down.",
        ">+50 strong bullish; <−50 strong bearish; near 0 = no edge.",
        "−100..+100", "momentum"),

    "vortex": _entry(
        "Vortex", "Vortex Indicator",
        "Two lines (+VI and −VI) measuring positive vs negative price flow.",
        "+VI crossing above −VI = bullish trend start. Crossing below = bearish.",
        "ratio (1.0 ≈ neutral)", "momentum",
    ),
    "vortex.plus": _entry("+VI", "+Vortex line",
        "Positive vortex — sum of |high − prev low| over lookback, normalized by TR.",
        "Above −VI = bullish.",
        "ratio", "momentum"),
    "vortex.minus": _entry("−VI", "−Vortex line",
        "Negative vortex — sum of |low − prev high| over lookback, normalized by TR.",
        "Above +VI = bearish.",
        "ratio", "momentum"),

    "fisher": _entry(
        "Fisher", "Fisher Transform",
        "Price normalized to a Gaussian distribution so extrema become more visible.",
        "Crosses of fisher / signal line in extreme zones are sharp reversal signals.",
        "unbounded (typically −3..+3)", "momentum",
    ),
    "fisher.fisher": _entry("Fisher", "Fisher transform value",
        "Transformed price series.",
        "Sharp moves in/out of ±2 = strong reversal candidate.",
        "unbounded", "momentum"),
    "fisher.signal": _entry("Signal", "Fisher signal line",
        "Lagged version of Fisher.",
        "Crosses with Fisher = entry/exit triggers.",
        "unbounded", "momentum"),

    "trix": _entry(
        "TRIX", "Triple Exponential Average",
        "Rate of change of a triple-smoothed EMA — removes noise to isolate true trend turns.",
        "Crossing zero up = bullish; down = bearish. Signal-line crosses are early triggers.",
        "%", "momentum",
    ),
    "trix.trix": _entry("TRIX", "TRIX line",
        "ROC of triple-EMA of close.",
        "Sign + slope = smoothed momentum direction.",
        "%", "momentum"),
    "trix.signal": _entry("Signal", "TRIX signal line",
        "EMA of TRIX.",
        "Crosses with TRIX = trigger lines.",
        "%", "momentum"),

    "tsi": _entry(
        "TSI", "True Strength Index",
        "Double-smoothed momentum oscillator — reduces lag without sacrificing smoothness.",
        ">+25 overbought, <−25 oversold. Centerline crosses = trend shifts. Divergences are strong reversal hints.",
        "−100..+100", "momentum",
    ),
    "tsi.tsi": _entry("TSI", "True Strength Index value",
        "Double-smoothed momentum.",
        "Direction + position relative to 0 + signal line crosses.",
        "−100..+100", "momentum"),
    "tsi.signal": _entry("Signal", "TSI signal line",
        "EMA of TSI.",
        "Crossings with TSI act as entry/exit triggers.",
        "−100..+100", "momentum"),
}

_TREND_AND_MAS: dict[str, MetaEntry] = {
    "ema": _entry("EMA", "Exponential Moving Average",
        "Moving average that weights recent bars more heavily.",
        "Price above EMA = bullish; below = bearish. Slope = trend direction.",
        "price units", "trend"),
    "sma": _entry("SMA", "Simple Moving Average",
        "Arithmetic mean of close over the lookback window.",
        "Slope = trend direction. SMA50/200 cross = golden/death cross.",
        "price units", "trend"),
    "hma": _entry("HMA", "Hull Moving Average",
        "Weighted MA designed to reduce lag while smoothing.",
        "Sharper turning point detection than SMA/EMA.",
        "price units", "trend"),
    "wma": _entry("WMA", "Weighted Moving Average",
        "Linear-weighted MA — most recent bar weighted most.",
        "Faster than SMA, less reactive than EMA.",
        "price units", "trend"),
    "dema": _entry("DEMA", "Double Exponential MA",
        "2×EMA minus EMA of EMA — reduces lag of standard EMA.",
        "More responsive than EMA; use when you want quick turn detection.",
        "price units", "trend"),
    "tema": _entry("TEMA", "Triple Exponential MA",
        "3×EMA − 3×EMA(EMA) + EMA(EMA(EMA)) — even less lag than DEMA.",
        "Earliest of the smooth MAs — great for trend turns at the cost of more noise.",
        "price units", "trend"),
    "t3": _entry("T3", "Tillson T3 MA",
        "Generalized DEMA with adjustable volume factor — extremely smooth.",
        "Use as a slow trend line; crosses with price are reliable but lagging.",
        "price units", "trend"),
    "kama": _entry("KAMA", "Kaufman Adaptive MA",
        "MA that speeds up in trending markets and slows down in noise.",
        "Self-adjusting — fewer whipsaws than fixed-period MAs.",
        "price units", "trend"),
    "alma": _entry("ALMA", "Arnaud Legoux MA",
        "Gaussian-weighted MA — emphasizes the middle of the window.",
        "Lower lag + lower noise than SMA/EMA.",
        "price units", "trend"),
    "linreg": _entry("LinReg", "Linear Regression",
        "Endpoint of a least-squares linear fit over the lookback window.",
        "Slope = trend strength. Distance of price from line = mean-reversion candidate.",
        "price units", "trend"),
    "jma": _entry("JMA", "Jurik MA",
        "Adaptive filter — very low lag, very low overshoot.",
        "One of the smoothest curves available. Trend-following MA of choice for many.",
        "price units", "trend"),
    "zlma": _entry("ZLMA", "Zero-Lag EMA",
        "EMA with lag subtracted (price + (price − price[N])).",
        "Reacts faster than EMA; cross signals fire earlier (more false positives).",
        "price units", "trend"),
    "rma": _entry("RMA", "Rolling MA (Wilder)",
        "Wilder's smoothing — slower EMA used inside RSI/ATR/ADX.",
        "Slowest of the EMA family. Use for very stable trend lines.",
        "price units", "trend"),
    "fwma": _entry("FWMA", "Fibonacci Weighted MA",
        "MA with weights from the Fibonacci sequence.",
        "Slightly more weight on the middle of the window.",
        "price units", "trend"),
    "swma": _entry("SWMA", "Symmetric Weighted MA",
        "MA with a symmetric weight kernel.",
        "Smooth but lagging.",
        "price units", "trend"),
    "sinwma": _entry("SinWMA", "Sine-Weighted MA",
        "MA weighted by a sine curve.",
        "Smooth + low-lag balance, similar to ALMA.",
        "price units", "trend"),
    "trima": _entry("TRIMA", "Triangular MA",
        "Double-smoothed SMA — weighting peaks in the middle of the window.",
        "Very smooth; lags more than EMA.",
        "price units", "trend"),

    "vwap": _entry("VWAP", "Volume-Weighted Average Price",
        "Anchored mean of price weighted by volume across the session.",
        "Price above VWAP = bullish session bias; below = bearish. Mean-reversion magnet intraday.",
        "price units", "trend"),
    "vwma": _entry("VWMA", "Volume-Weighted MA",
        "MA where each bar's contribution is scaled by its volume.",
        "Diverges from price when low-volume bars stretch the move = thin tape warning.",
        "price units", "trend"),

    "ichimoku": _entry("Ichimoku", "Ichimoku Kinko Hyo",
        "Full Japanese trend system: cloud (spanA/spanB), conversion (tenkan), base (kijun), and lagging (chikou) lines.",
        "Price above cloud + bullish cloud = strong uptrend. Tenkan crossing kijun = trigger. Chikou clear of past price = confirmation.",
        "price units", "trend"),
    "ichimoku.spanA": _entry("Span A", "Senkou Span A (leading)",
        "(Tenkan + Kijun) / 2 plotted 26 bars forward — upper cloud boundary in uptrends.",
        "Above Span B = bullish cloud (green).",
        "price units", "trend"),
    "ichimoku.spanB": _entry("Span B", "Senkou Span B (leading)",
        "Midpoint of 52-bar range plotted 26 bars forward — lower cloud boundary in uptrends.",
        "Below Span A = bullish cloud.",
        "price units", "trend"),
    "ichimoku.tenkan": _entry("Tenkan", "Tenkan-sen (conversion line)",
        "Midpoint of 9-bar range — fast trend line.",
        "Crossing kijun upward = bullish trigger.",
        "price units", "trend"),
    "ichimoku.kijun": _entry("Kijun", "Kijun-sen (base line)",
        "Midpoint of 26-bar range — slower trend line.",
        "Price holding above kijun = uptrend intact.",
        "price units", "trend"),
    "ichimoku.chikou": _entry("Chikou", "Chikou Span (lagging)",
        "Current close plotted 26 bars backward — confirmation line.",
        "Above past price = bullish confirmation. Tangled with price = no clear trend.",
        "price units", "trend"),

    "supertrend": _entry("Supertrend", "Supertrend",
        "ATR-banded trailing stop that flips direction when price crosses it.",
        "Direction = current side (+1 long / −1 short). Acts as dynamic support/resistance until flipped.",
        "price units / ±1", "trend"),
    "supertrend.value": _entry("Value", "Supertrend value",
        "The active band — support in uptrend, resistance in downtrend.",
        "Price holding above (long-mode) = trend intact; close below = flip.",
        "price units", "trend"),
    "supertrend.direction": _entry("Dir", "Supertrend direction",
        "+1 = long mode (price above the band), −1 = short mode.",
        "Direction-flip bars are entry signals.",
        "±1", "trend"),
    "supertrend.long": _entry("Long band", "Supertrend long-side band",
        "Active band value only when in long mode (NaN otherwise).",
        "Trail stop for long positions.",
        "price units", "trend"),
    "supertrend.short": _entry("Short band", "Supertrend short-side band",
        "Active band value only when in short mode (NaN otherwise).",
        "Trail stop for short positions.",
        "price units", "trend"),

    "psar": _entry("PSAR", "Parabolic SAR",
        "Stop-and-reverse trailing dots — accelerates toward price each bar.",
        "Dots below price = uptrend; above = downtrend. Flip = entry/exit signal.",
        "price units", "trend"),
    "psar.long": _entry("Long PSAR", "PSAR long-mode dots",
        "Dot value when in long mode (NaN otherwise).",
        "Trail stop for longs.",
        "price units", "trend"),
    "psar.short": _entry("Short PSAR", "PSAR short-mode dots",
        "Dot value when in short mode (NaN otherwise).",
        "Trail stop for shorts.",
        "price units", "trend"),
    "psar.af": _entry("AF", "PSAR acceleration factor",
        "Current acceleration — rises as the trend continues.",
        "Higher AF = trail stop tightens faster.",
        "0.02–0.2", "trend"),
    "psar.reversal": _entry("Reversal", "PSAR reversal flag",
        "1 on bars where SAR flipped direction.",
        "Use as entry trigger.",
        "0 / 1", "trend"),

    "chandelierExit": _entry("Chandelier", "Chandelier Exit",
        "ATR-based trailing stop anchored to the highest high (long) or lowest low (short).",
        "Direction +1 / −1 indicates current regime. Use the active band as a stop.",
        "price units / ±1", "trend"),
    "chandelierExit.long": _entry("Long stop", "Chandelier long stop",
        "Trailing stop level for long positions (highest high − ATR×mult).",
        "Close below = exit long / flip short.",
        "price units", "trend"),
    "chandelierExit.short": _entry("Short stop", "Chandelier short stop",
        "Trailing stop level for short positions (lowest low + ATR×mult).",
        "Close above = exit short / flip long.",
        "price units", "trend"),
    "chandelierExit.direction": _entry("Dir", "Chandelier direction",
        "+1 = long mode, −1 = short mode.",
        "Same flip-as-entry logic as Supertrend.",
        "±1", "trend"),
}

_VOLATILITY: dict[str, MetaEntry] = {
    "atr": _entry("ATR", "Average True Range",
        "Average of the true range (max of high-low, |high-prevClose|, |low-prevClose|) over N bars.",
        "Rising = expanding volatility. Use for position-sizing and stop placement.",
        "price units", "volatility"),
    "natr": _entry("NATR", "Normalized ATR",
        "ATR expressed as a percentage of close price.",
        "Cross-instrument comparable. Spike + price move = real volatility event.",
        "%", "volatility"),

    "bbands": _entry("Bollinger Bands", "Bollinger Bands",
        "Middle SMA + upper/lower bands at N standard deviations.",
        "Squeeze (narrow bands) = volatility about to expand. Walks along upper/lower band = strong trend.",
        "price units", "volatility"),
    "bbands.upper": _entry("BB Upper", "Bollinger upper band",
        "Middle band + N std dev.",
        "Sustained tags = strong uptrend. Touch + reject = mean-revert candidate.",
        "price units", "volatility"),
    "bbands.middle": _entry("BB Middle", "Bollinger middle band",
        "Simple MA used as the basis.",
        "Acts as dynamic support/resistance in trends.",
        "price units", "volatility"),
    "bbands.lower": _entry("BB Lower", "Bollinger lower band",
        "Middle band − N std dev.",
        "Same as upper but for downtrends.",
        "price units", "volatility"),

    "kc": _entry("Keltner Channel", "Keltner Channel",
        "EMA middle + bands set N×ATR away.",
        "Narrower than BB = compressed volatility. Close outside KC = strong trending move.",
        "price units", "volatility"),
    "kc.upper": _entry("KC Upper", "Keltner upper band",
        "EMA + N × ATR.",
        "Close above = trending bullish breakout.",
        "price units", "volatility"),
    "kc.middle": _entry("KC Middle", "Keltner middle band",
        "EMA centerline.",
        "Trend direction reference.",
        "price units", "volatility"),
    "kc.lower": _entry("KC Lower", "Keltner lower band",
        "EMA − N × ATR.",
        "Close below = trending bearish breakout.",
        "price units", "volatility"),

    "donchian": _entry("Donchian Channel", "Donchian Channel",
        "Highest high and lowest low of the last N bars.",
        "Breakout above upper = new N-bar high. Below lower = new N-bar low. Classic Turtle trade trigger.",
        "price units", "volatility"),
    "donchian.upper": _entry("DC Upper", "Donchian upper",
        "Highest high in lookback.",
        "Close above = new range high.",
        "price units", "volatility"),
    "donchian.middle": _entry("DC Mid", "Donchian middle",
        "(Upper + lower) / 2 — channel midpoint.",
        "Mean-reversion anchor.",
        "price units", "volatility"),
    "donchian.lower": _entry("DC Lower", "Donchian lower",
        "Lowest low in lookback.",
        "Close below = new range low.",
        "price units", "volatility"),

    "squeeze": _entry("Squeeze", "TTM Squeeze",
        "Detects volatility compression (BB inside KC) and the subsequent release.",
        "`on=1` = squeeze active (volatility coiling). Transition `on→off` = explosive move starting. Histogram (value) gives direction.",
        "price units / boolean", "volatility"),
    "squeeze.value": _entry("Momentum", "Squeeze momentum histogram",
        "Linreg-based momentum reading — color-coded by sign and slope.",
        "Positive + growing = bullish breakout incoming. Negative + growing = bearish.",
        "price units", "volatility"),
    "squeeze.on": _entry("Sqz on", "Squeeze active",
        "1 when Bollinger Bands are inside Keltner Channels (compression).",
        "Continuous 1s = coil; transition to 0 = release into directional move.",
        "0 / 1", "volatility"),
    "squeeze.off": _entry("Sqz off", "Squeeze released",
        "1 when BB has expanded outside KC.",
        "Marks the start of the directional thrust.",
        "0 / 1", "volatility"),
    "squeeze.no": _entry("No sqz", "No-squeeze state",
        "1 when neither active nor released — normal volatility regime.",
        "Filter out: signals here are noise-prone.",
        "0 / 1", "volatility"),
}

_VOLUME: dict[str, MetaEntry] = {
    "obv": _entry("OBV", "On-Balance Volume",
        "Running cumulative sum: +volume on up bars, −volume on down bars.",
        "Trend confirmation — OBV new high with price = healthy uptrend. OBV diverging = accumulation/distribution warning.",
        "cumulative", "volume"),
    "ad": _entry("A/D", "Accumulation/Distribution",
        "Volume weighted by close position within the bar's range, cumulative.",
        "Like OBV but accounts for where price closed inside the bar. Divergence with price = trend weakening.",
        "cumulative", "volume"),
    "cmf": _entry("CMF", "Chaikin Money Flow",
        "Money-flow ratio averaged over N bars.",
        ">0 buying pressure, <0 selling pressure. Above +0.25 strong inflow; below −0.25 strong outflow.",
        "−1..+1", "volume"),
    "adosc": _entry("A/D Osc", "Chaikin Oscillator",
        "MACD-style oscillator on the A/D line.",
        "Crossing zero up = bullish; down = bearish. Divergence with price flags reversals.",
        "unbounded", "volume"),
    "kvo": _entry("KVO", "Klinger Volume Oscillator",
        "Difference between two volume-weighted EMAs of price flow.",
        "Crosses with signal line = entry/exit. Divergence with price = reversal candidate.",
        "unbounded", "volume"),
    "kvo.kvo": _entry("KVO", "KVO line",
        "Main KVO oscillator.",
        "Trend direction of long-term volume flow.",
        "unbounded", "volume"),
    "kvo.signal": _entry("Signal", "KVO signal line",
        "EMA of KVO.",
        "Crossovers with KVO = triggers.",
        "unbounded", "volume"),
}


# ---------------------------------------------------------------------------
# SMC primitives — sparse event lists keyed by bar
# ---------------------------------------------------------------------------

_SMC_EVENTS: dict[str, MetaEntry] = {
    "orderBlocks": _entry(
        "Order Blocks", "SMC Order Blocks",
        "Unmitigated bullish/bearish zones where institutional orders likely originated.",
        "Price re-entering an OB often reacts (bounce/reject). Bullish OB = support; bearish OB = resistance.",
        "object list", "smc",
    ),
    "orderBlocks[].type": _entry("Type", "OB direction",
        "Bullish (demand) or bearish (supply) zone.",
        "Bullish = expect bounce on re-test; bearish = expect rejection.",
        "bullish / bearish", "smc"),
    "orderBlocks[].top": _entry("Top", "OB upper edge",
        "Upper price boundary of the order block.",
        "Resistance edge for bearish OB; pullback target for bullish.",
        "price units", "smc"),
    "orderBlocks[].bottom": _entry("Bottom", "OB lower edge",
        "Lower price boundary of the order block.",
        "Support edge for bullish OB; pullback target for bearish.",
        "price units", "smc"),
    "orderBlocks[].candleIdx": _entry("Bar #", "Origin bar index",
        "Bar where the OB was created.",
        "Older = stronger (it has survived more re-tests).",
        "int", "smc"),
    "orderBlocks[].time": _entry("Time", "Origin bar timestamp",
        "Unix seconds of the OB origin bar.",
        "",
        "unix seconds", "smc"),
    "orderBlocks[].distancePct": _entry("Δ%", "Distance from price",
        "Percent distance from current price to the OB edge.",
        "Smaller = more imminent reaction; larger = looser target.",
        "%", "smc"),

    "fvgs": _entry("FVGs", "Fair Value Gaps",
        "3-candle imbalance zones where price moved fast leaving an unfilled gap.",
        "Price tends to revisit and fill FVGs. Bullish FVG = expected support; bearish = expected resistance.",
        "object list", "smc"),
    "fvg": _entry("FVGs", "Fair Value Gaps (alias)",
        "Same as `fvgs` — kept for backwards compatibility.",
        "Identical content.",
        "object list", "smc"),
    "fvgs[].type": _entry("Type", "FVG direction",
        "Bullish (low > prior high) or bearish (high < prior low).",
        "Bullish = support magnet; bearish = resistance magnet.",
        "bullish / bearish", "smc"),
    "fvgs[].top": _entry("Top", "FVG upper edge", "Upper boundary of the gap.", "", "price units", "smc"),
    "fvgs[].bottom": _entry("Bottom", "FVG lower edge", "Lower boundary of the gap.", "", "price units", "smc"),
    "fvgs[].candleIdx": _entry("Bar #", "Origin bar index", "Bar at the middle of the 3-candle pattern.", "", "int", "smc"),
    "fvgs[].time": _entry("Time", "Origin bar timestamp", "Unix seconds.", "", "unix seconds", "smc"),
    "fvgs[].distancePct": _entry("Δ%", "Distance from price", "Percent distance to the midpoint of the gap.", "Smaller = more imminent fill.", "%", "smc"),

    "bosChoch": _entry("BOS / CHoCH", "Break of Structure & Change of Character",
        "Market-structure pivot events: BOS = continuation of trend, CHoCH = first break against trend.",
        "BOS = trend health intact. CHoCH = early reversal signal (trend may be flipping).",
        "object list", "structure"),
    "bosChoch[].event": _entry("Event", "BOS or CHoCH",
        "BOS = break of structure (continuation). CHoCH = change of character (potential reversal).",
        "CHoCH after a strong trend is the most actionable.",
        "BOS / CHoCH", "structure"),
    "bosChoch[].direction": _entry("Dir", "Event direction",
        "Bullish or bearish break/change.",
        "Bullish = upward break of a swing high; bearish = downward break of a swing low.",
        "bullish / bearish", "structure"),
    "bosChoch[].level": _entry("Level", "Broken level price",
        "The swing-high/low that price broke through.",
        "Acts as the new support (after bullish break) or resistance (after bearish).",
        "price units", "structure"),
    "bosChoch[].time": _entry("Time", "Event bar timestamp", "Unix seconds.", "", "unix seconds", "structure"),

    "swingLevels": _entry("Swing Levels", "Swing Highs & Lows",
        "Confirmed pivot highs and pivot lows from the swing-structure detector.",
        "Higher highs + higher lows = uptrend. Lower highs + lower lows = downtrend. Break of last opposite-direction swing = trend shift.",
        "object list", "structure"),
    "swingLevels[].type": _entry("Type", "Swing direction",
        "High (pivot top) or low (pivot bottom).",
        "Latest high = supply; latest low = demand.",
        "high / low", "structure"),
    "swingLevels[].level": _entry("Level", "Swing price",
        "Price of the pivot.",
        "Acts as horizontal S/R.",
        "price units", "structure"),
    "swingLevels[].time": _entry("Time", "Pivot bar timestamp", "Unix seconds.", "", "unix seconds", "structure"),

    "srLevels": _entry("S/R Levels", "Support / Resistance Levels",
        "Multi-touch horizontal levels detected from swing structure, ranked by proximity.",
        "More touches = stronger level. Close above resistance / below support = breakout context.",
        "object list", "smc"),
    "srLevels[].level": _entry("Level", "Price of S/R",
        "Horizontal price level.",
        "",
        "price units", "smc"),
    "srLevels[].type": _entry("Type", "Support or Resistance",
        "Support (below current price) or resistance (above).",
        "",
        "support / resistance", "smc"),
    "srLevels[].distancePct": _entry("Δ%", "Distance from price",
        "Percent distance from current close to the level.",
        "",
        "%", "smc"),
    "srLevels[].touches": _entry("Touches", "Touch count",
        "How many times price has interacted with this level.",
        ">2 = significant. Higher = stronger reaction expected.",
        "int", "smc"),

    "recentRange": _entry("Recent Range", "Recent Range",
        "High and low of recent + full period — useful for breakout context.",
        "Close above recent.high = breakout up. Close below recent.low = breakout down.",
        "object", "range"),
    "recentRange.high": _entry("Recent High", "High of last 20 bars", "Highest high of the most recent 20 bars.", "Acts as near-term resistance.", "price units", "range"),
    "recentRange.low": _entry("Recent Low", "Low of last 20 bars", "Lowest low of the most recent 20 bars.", "Acts as near-term support.", "price units", "range"),
    "recentRange.periodHigh": _entry("Period High", "High of full window", "Highest high across all available bars.", "Longer-term ceiling.", "price units", "range"),
    "recentRange.periodLow": _entry("Period Low", "Low of full window", "Lowest low across all available bars.", "Longer-term floor.", "price units", "range"),

    "liquidity": _entry("Liquidity", "Liquidity Sweeps",
        "Clusters of stops / pivot equal-highs/lows that price hunts before reversing.",
        "Sweeps (touch + reverse) are the most actionable reversal signal. Sweep level = where stops were taken.",
        "object list", "smc"),
    "liquidity[].idx": _entry("Bar #", "Detection bar", "Bar index where the cluster was identified.", "", "int", "smc"),
    "liquidity[].time": _entry("Time", "Detection bar timestamp", "Unix seconds.", "", "unix seconds", "smc"),
    "liquidity[].Level": _entry("Level", "Liquidity price",
        "Price level where stops are clustered.",
        "Sweep = price wicks through then closes back inside.",
        "price units", "smc"),
    "liquidity[].Liquidity": _entry("Dir", "Direction",
        "+1 = bullish liquidity (stops below — sweep down then up); −1 = bearish (stops above — sweep up then down).",
        "Bullish liq sweep is often a long entry; bearish is often a short.",
        "±1", "smc"),
    "liquidity[].Swept": _entry("Swept", "Sweep bar",
        "Bar index where the level was swept (0 = not yet).",
        "Non-zero = the sweep already happened.",
        "int", "smc"),
    "liquidity[].End": _entry("End", "Cluster end bar", "Bar index where the cluster ends.", "", "int", "smc"),

    "previousHighLow": _entry("Prev HL", "Previous Period High/Low",
        "High and low of the previous higher-TF period (e.g. previous day, week, month) cascaded onto current TF.",
        "Classic supply/demand magnets. Price approaches PDH/PWH = expect reaction. Holds above = bullish continuation.",
        "object list", "smc"),
    "previousHighLow[].idx": _entry("Bar #", "Bar index", "Bar marker.", "", "int", "smc"),
    "previousHighLow[].time": _entry("Time", "Timestamp", "Unix seconds.", "", "unix seconds", "smc"),
    "previousHighLow[].PreviousHigh": _entry("Prev H", "Previous period high",
        "High of the prior session/day/week/month.",
        "Acts as resistance. Close above = bullish breakout of prior range.",
        "price units", "smc"),
    "previousHighLow[].PreviousLow": _entry("Prev L", "Previous period low",
        "Low of the prior session/day/week/month.",
        "Acts as support. Close below = bearish breakdown.",
        "price units", "smc"),
    "previousHighLow[].BrokenHigh": _entry("Broken H", "High broken flag",
        "1 if the previous high has been broken in the current period.",
        "Bullish breakout confirmation.",
        "0 / 1", "smc"),
    "previousHighLow[].BrokenLow": _entry("Broken L", "Low broken flag",
        "1 if the previous low has been broken in the current period.",
        "Bearish breakdown confirmation.",
        "0 / 1", "smc"),

    "sessions": _entry("Sessions", "Trading Sessions",
        "London / NY / Tokyo session window flags + session high/low tracking.",
        "Session H/L often becomes intraday liquidity. Active=1 bars are when this session is live.",
        "object list", "smc"),
    "sessions[].idx": _entry("Bar #", "Bar index", "Bar marker.", "", "int", "smc"),
    "sessions[].time": _entry("Time", "Timestamp", "Unix seconds.", "", "unix seconds", "smc"),
    "sessions[].Active": _entry("Active", "Session active flag", "1 when this session is currently open.", "Filter signals by session activity.", "0 / 1", "smc"),
    "sessions[].High": _entry("Sess High", "Session high",
        "Running session high.",
        "Acts as intraday resistance and stop-magnet.",
        "price units", "smc"),
    "sessions[].Low": _entry("Sess Low", "Session low",
        "Running session low.",
        "Acts as intraday support and stop-magnet.",
        "price units", "smc"),

    "retracements": _entry("Retracements", "Leg Retracements",
        "For each bar: direction of the active leg + how deeply price has pulled back from the leg extreme (current + worst seen).",
        "Fresh impulse: CurrentRetracement% ≈ 0. Deep pullback: > 50%. > 78% = leg likely invalidated. DeepestRetracement% records the worst pullback seen during the leg.",
        "object list", "structure"),
    "retracements[].idx": _entry("Bar #", "Bar index", "Bar marker.", "", "int", "structure"),
    "retracements[].time": _entry("Time", "Bar timestamp", "Unix seconds.", "", "unix seconds", "structure"),
    "retracements[].Direction": _entry("Dir", "Leg direction",
        "+1 = active up-leg (higher highs); −1 = active down-leg; 0 = no clear leg.",
        "Trade pullbacks WITH the direction — counter-trend retracement plays are riskier.",
        "−1, 0, +1", "structure"),
    "retracements[].CurrentRetracement%": _entry("Cur %", "Current retracement",
        "How much price has pulled back from the leg extreme RIGHT NOW, as % of the leg.",
        "<25% = fresh leg, momentum intact. 38–62% = classic Fibonacci pullback zone. >78% = leg fragile / likely flipping.",
        "%", "structure"),
    "retracements[].DeepestRetracement%": _entry("Deep %", "Deepest retracement",
        "Worst pullback the leg has taken since starting (high-water mark).",
        "Shallow (<25%) across many legs = strong trend. Deep (>50%) = trend taking heat — getting more reactive on each leg.",
        "%", "structure"),
}


# ---------------------------------------------------------------------------
# Analysis summary snapshots (last-bar scalars rolled up from cached analysis)
# ---------------------------------------------------------------------------

_SUMMARIES: dict[str, MetaEntry] = {
    "price": _entry("Price", "Latest close",
        "Most recent bar's close price.",
        "Reference value for every distance / position calculation.",
        "price units", "summary"),

    "levels": _entry("Key Levels", "Latest indicator levels (snapshot)",
        "Last-bar scalar of the standard reference levels: EMA21, SMA50/100/200, ATR, VWAP, Donchian U/M/L.",
        "Used to compute price-to-level distances and position-relative checks.",
        "object", "summary"),
    "levels.ema21": _entry("EMA21", "EMA(21) value at last bar", "Latest value of the 21-period EMA.", "Short-term trend reference.", "price units", "summary"),
    "levels.sma50": _entry("SMA50", "SMA(50) value at last bar", "Latest value of the 50-period SMA.", "Medium-term trend.", "price units", "summary"),
    "levels.sma100": _entry("SMA100", "SMA(100) value at last bar", "Latest value of the 100-period SMA.", "Intermediate trend.", "price units", "summary"),
    "levels.sma200": _entry("SMA200", "SMA(200) value at last bar", "Latest value of the 200-period SMA.", "Long-term trend reference. Price above = bull regime.", "price units", "summary"),
    "levels.atr": _entry("ATR", "ATR at last bar", "Volatility magnitude (avg true range).", "Use for stop-distance and position sizing.", "price units", "summary"),
    "levels.vwap": _entry("VWAP", "VWAP at last bar", "Session-anchored volume-weighted average price.", "Intraday mean-reversion magnet.", "price units", "summary"),
    "levels.donchianUpper": _entry("DC↑", "Donchian upper at last bar", "Highest high of lookback.", "Recent range ceiling.", "price units", "summary"),
    "levels.donchianLower": _entry("DC↓", "Donchian lower at last bar", "Lowest low of lookback.", "Recent range floor.", "price units", "summary"),
    "levels.donchianMid": _entry("DC mid", "Donchian middle at last bar", "Midpoint of the Donchian range.", "", "price units", "summary"),

    "momentum": _entry("Momentum (snapshot)", "Momentum scalars (snapshot)",
        "Last-bar values of RSI, MFI, MACD line/signal/hist, ADX, Stoch K/D.",
        "Combined read of multiple momentum families — useful for confirmation across regimes.",
        "object", "summary"),
    "momentum.rsi": _entry("RSI", "RSI at last bar", "Wilder's RSI(14) value.", ">70 OB, <30 OS.", "0–100", "summary"),
    "momentum.mfi": _entry("MFI", "MFI at last bar", "Money flow index value.", ">80 OB, <20 OS.", "0–100", "summary"),
    "momentum.macdLine": _entry("MACD", "MACD line at last bar", "Fast EMA − slow EMA.", "Above 0 = bullish bias.", "price units", "summary"),
    "momentum.macdSignal": _entry("MACD sig", "MACD signal at last bar", "EMA of MACD line.", "MACD > signal = bullish.", "price units", "summary"),
    "momentum.macdHist": _entry("MACD hist", "MACD histogram at last bar", "MACD − signal — momentum acceleration.", "Growing positive = bullish accel; growing negative = bearish accel.", "price units", "summary"),
    "momentum.adx": _entry("ADX", "ADX at last bar", "Trend strength.", ">25 trending.", "0–100", "summary"),
    "momentum.stochK": _entry("Stoch %K", "Stochastic %K at last bar", "Fast stochastic.", ">80 OB, <20 OS.", "0–100", "summary"),
    "momentum.stochD": _entry("Stoch %D", "Stochastic %D at last bar", "Signal stochastic.", "Trend direction of momentum.", "0–100", "summary"),

    "volume": _entry("Volume (snapshot)", "Volume scalars (snapshot)",
        "Last-bar volume ratio + OBV + spike flag.",
        "Quick read on whether the current bar is unusually heavy.",
        "object", "summary"),
    "volume.volRatio": _entry("Vol×", "Volume ratio",
        "Last bar's volume divided by rolling average.",
        ">2.0 = spike, <0.3 = dryup. Spike + strong close = real conviction.",
        "ratio", "summary"),
    "volume.obv": _entry("OBV", "OBV at last bar",
        "Cumulative on-balance volume.",
        "Trend confirmation gauge — diverging = warning.",
        "cumulative", "summary"),
    "volume.isSpike": _entry("Spike?", "Volume spike flag",
        "True when volRatio > 2.0.",
        "Use as a filter — only act on spike bars when other signals align.",
        "boolean", "summary"),

    "position": _entry("Position (snapshot)", "Price position vs MAs (snapshot)",
        "For each MA (EMA21, SMA50/100/200, VWAP): is price above or below?",
        "All-above = bullish stack. All-below = bearish stack. Mixed = transition zone.",
        "object (above/below)", "summary"),
    "position.ema21": _entry("vs EMA21", "Position vs EMA(21)", "above or below the 21-EMA.", "Short-term trend bias.", "above / below", "summary"),
    "position.sma50": _entry("vs SMA50", "Position vs SMA(50)", "above or below the 50-SMA.", "Medium-term trend bias.", "above / below", "summary"),
    "position.sma100": _entry("vs SMA100", "Position vs SMA(100)", "above or below the 100-SMA.", "Intermediate trend bias.", "above / below", "summary"),
    "position.sma200": _entry("vs SMA200", "Position vs SMA(200)", "above or below the 200-SMA.", "Long-term regime: above = bull, below = bear.", "above / below", "summary"),
    "position.vwap": _entry("vs VWAP", "Position vs VWAP", "above or below VWAP.", "Intraday auction bias.", "above / below", "summary"),

    "slope": _entry("Slope (snapshot)", "MA slope directions (snapshot)",
        "Direction (up/down) of each MA over the last 10 bars.",
        "All-up = trending bull. All-down = trending bear. Mixed = chop or transition.",
        "object (up/down)", "summary"),
    "slope.ema21": _entry("EMA21 slope", "EMA(21) slope", "Direction over 10 bars.", "Short-term trend direction.", "up / down", "summary"),
    "slope.sma50": _entry("SMA50 slope", "SMA(50) slope", "Direction over 10 bars.", "Medium-term trend direction.", "up / down", "summary"),
    "slope.sma100": _entry("SMA100 slope", "SMA(100) slope", "Direction over 10 bars.", "Intermediate trend direction.", "up / down", "summary"),
    "slope.sma200": _entry("SMA200 slope", "SMA(200) slope", "Direction over 10 bars.", "Long-term regime direction.", "up / down", "summary"),
    "slope.vwap": _entry("VWAP slope", "VWAP slope", "Direction over 10 bars.", "Session-bias drift.", "up / down", "summary"),
}


# Merge all sections into one flat catalog. Order matters for `categories`
# inference downstream but the API ships it as a single dict regardless.
INDICATOR_METADATA: dict[str, MetaEntry] = {
    **_MOMENTUM_OSCILLATORS,
    **_TREND_AND_MAS,
    **_VOLATILITY,
    **_VOLUME,
    **_SMC_EVENTS,
    **_SUMMARIES,
}


def lookup(path: str) -> MetaEntry | None:
    """Look up metadata for a dot-notation path, applying fallback rules.

    1) exact match
    2) replace array indices `[42]` → `[]` and retry
    3) strip leading section, try the bare leaf key
    """
    if path in INDICATOR_METADATA:
        return INDICATOR_METADATA[path]

    # Index-strip: `retracements[42].Direction` → `retracements[].Direction`
    import re

    stripped = re.sub(r"\[\d+\]", "[]", path)
    if stripped != path and stripped in INDICATOR_METADATA:
        return INDICATOR_METADATA[stripped]

    # Leaf-only fallback: `momentum.macdHist` → `macdHist`
    if "." in path:
        leaf = path.rsplit(".", 1)[-1]
        if leaf in INDICATOR_METADATA:
            return INDICATOR_METADATA[leaf]

    return None


def all_metadata() -> dict[str, Any]:
    """Returned by `GET /metadata` — the static catalog plus a count."""
    return {
        "version": 1,
        "count": len(INDICATOR_METADATA),
        "entries": INDICATOR_METADATA,
    }
