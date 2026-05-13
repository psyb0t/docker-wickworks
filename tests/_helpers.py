"""Shared test helpers — bar generators, HTTP client, reference math.

Reference math is implemented with pure numpy/pandas (no pandas_ta) so it
catches drift between the spec and the backing library. Tolerances are
chosen for FX-tick prices around 1.0–200.0.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from wickworks.server import app

client = TestClient(app)


# -----------------------------------------------------------------------------
# Bar fixtures with known mathematical properties.
# -----------------------------------------------------------------------------


def flat_bars(n: int, price: float = 100.0) -> list[dict[str, Any]]:
    """All bars identical → atr=0, rsi=NaN/50, slope=0, std=0."""
    return [
        {
            "time": 1_700_000_000 + i * 3600,
            "open": price,
            "high": price,
            "low": price,
            "close": price,
            "tickVolume": 1000,
        }
        for i in range(n)
    ]


def monotone_up_bars(
    n: int, start: float = 100.0, step: float = 1.0
) -> list[dict[str, Any]]:
    """Strictly increasing close → rsi=100 at tail, all returns positive."""
    bars = []
    for i in range(n):
        c = start + i * step
        bars.append(
            {
                "time": 1_700_000_000 + i * 3600,
                "open": c - step / 2,
                "high": c + step / 4,
                "low": c - step,
                "close": c,
                "tickVolume": 1000,
            }
        )
    return bars


def monotone_down_bars(
    n: int, start: float = 200.0, step: float = 1.0
) -> list[dict[str, Any]]:
    """Strictly decreasing close → rsi=0 at tail."""
    bars = []
    for i in range(n):
        c = start - i * step
        bars.append(
            {
                "time": 1_700_000_000 + i * 3600,
                "open": c + step / 2,
                "high": c + step,
                "low": c - step / 4,
                "close": c,
                "tickVolume": 1000,
            }
        )
    return bars


def post(
    bars: list[dict[str, Any]], indicators: dict[str, Any], **extra: Any
) -> dict[str, Any]:
    """POST / and return the parsed JSON, asserting 200."""
    body = {"bars": bars, "indicators": indicators, **extra}
    r = client.post("/", json=body)
    assert r.status_code == 200, r.text
    return r.json()


# -----------------------------------------------------------------------------
# eurusd fixture → pandas DataFrame for closed-form reference math.
# -----------------------------------------------------------------------------


def bars_to_df(bars: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": [b["open"] for b in bars],
            "high": [b["high"] for b in bars],
            "low": [b["low"] for b in bars],
            "close": [b["close"] for b in bars],
            "volume": [b.get("tickVolume", b.get("realVolume", 0)) for b in bars],
        }
    )


# -----------------------------------------------------------------------------
# Closed-form reference implementations — these match pandas_ta's specific
# defaults (ddof, Wilder seeding, etc.) so the assertions are exact at the
# last bar where pandas_ta is past its warmup.
# -----------------------------------------------------------------------------


def ref_sma(close: pd.Series, length: int) -> pd.Series:
    return close.rolling(length).mean()


def ref_ema(close: pd.Series, length: int) -> pd.Series:
    """pandas_ta EMA: seeded with SMA of first N closes, then recursive.

    EMA[N-1] = mean(close[0..N-1]); EMA[i] = alpha*close[i] + (1-alpha)*EMA[i-1]
    where alpha = 2/(N+1). NaN before index N-1.
    """
    alpha = 2.0 / (length + 1.0)
    out = pd.Series(np.nan, index=close.index, dtype=float)
    if len(close) < length:
        return out
    out.iloc[length - 1] = close.iloc[:length].mean()
    for i in range(length, len(close)):
        out.iloc[i] = alpha * close.iloc[i] + (1 - alpha) * out.iloc[i - 1]
    return out


def ref_wilder(series: pd.Series, length: int) -> pd.Series:
    """Wilder RMA: seed at index `length` with SMA of first `length` values
    starting at index 1 (Wilder skips the first diff). EMA-like with
    alpha = 1/length thereafter.
    """
    out = pd.Series(np.nan, index=series.index, dtype=float)
    if len(series) <= length:
        return out
    out.iloc[length] = series.iloc[1 : length + 1].mean()
    for i in range(length + 1, len(series)):
        out.iloc[i] = (out.iloc[i - 1] * (length - 1) + series.iloc[i]) / length
    return out


def ref_rsi(close: pd.Series, length: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = ref_wilder(gain, length)
    avg_loss = ref_wilder(loss, length)
    rs = avg_gain / avg_loss
    return 100 - 100 / (1 + rs)


def ref_true_range(
    high: pd.Series, low: pd.Series, close: pd.Series
) -> pd.Series:
    prev_close = close.shift(1)
    return pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)


def ref_atr(
    high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14
) -> pd.Series:
    return ref_wilder(ref_true_range(high, low, close), length)


def ref_macd(
    close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> dict[str, pd.Series]:
    macd = ref_ema(close, fast) - ref_ema(close, slow)
    sig = ref_ema(macd.dropna(), signal).reindex(close.index)
    hist = macd - sig
    return {"macd": macd, "signal": sig, "hist": hist}


def ref_bbands(
    close: pd.Series, length: int = 20, std: float = 2.0
) -> dict[str, pd.Series]:
    """pandas_ta BBands uses ddof=1 (sample stddev)."""
    middle = close.rolling(length).mean()
    sd = close.rolling(length).std(ddof=1)
    return {
        "upper": middle + std * sd,
        "middle": middle,
        "lower": middle - std * sd,
    }


def ref_donchian(
    high: pd.Series, low: pd.Series, length: int = 20
) -> dict[str, pd.Series]:
    """pandas_ta donchian: rolling max/min over HIGH/LOW, including current bar."""
    upper = high.rolling(length).max()
    lower = low.rolling(length).min()
    return {"upper": upper, "middle": (upper + lower) / 2, "lower": lower}


def ref_williams_r(
    high: pd.Series, low: pd.Series, close: pd.Series, length: int = 14
) -> pd.Series:
    hh = high.rolling(length).max()
    ll = low.rolling(length).min()
    return -100 * (hh - close) / (hh - ll)


def ref_roc(close: pd.Series, length: int = 10) -> pd.Series:
    return 100 * (close - close.shift(length)) / close.shift(length)


def ref_mom(close: pd.Series, length: int = 10) -> pd.Series:
    return close - close.shift(length)


def ref_obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    direction = np.sign(close.diff()).fillna(0)
    return (direction * volume).cumsum()


def ref_stoch_basic(
    high: pd.Series, low: pd.Series, close: pd.Series, k: int = 14
) -> pd.Series:
    """Raw %K (no smoothing): 100 * (close - min_low) / (max_high - min_low)."""
    ll = low.rolling(k).min()
    hh = high.rolling(k).max()
    return 100 * (close - ll) / (hh - ll)


def ref_stoch(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    k: int = 14,
    d: int = 3,
    smooth_k: int = 3,
) -> dict[str, pd.Series]:
    """pandas_ta stoch: smooth raw %K by SMA(smooth_k), then %D = SMA(%K, d)."""
    raw = ref_stoch_basic(high, low, close, k)
    smoothed_k = raw.rolling(smooth_k).mean()
    d_line = smoothed_k.rolling(d).mean()
    return {"k": smoothed_k, "d": d_line}


def ref_aroon(
    high: pd.Series, low: pd.Series, length: int = 14
) -> dict[str, pd.Series]:
    """Aroon up/down: 100 * (length - bars_since_extreme) / length.

    pandas_ta uses window of (length+1) and looks back including the current
    bar (argmax in window of length+1).
    """
    w = length + 1
    up = high.rolling(w).apply(lambda x: 100 * x.argmax() / length, raw=True)
    dn = low.rolling(w).apply(lambda x: 100 * x.argmin() / length, raw=True)
    return {"up": up, "down": dn, "oscillator": up - dn}


def ref_cci(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    length: int = 14,
    c: float = 0.015,
) -> pd.Series:
    """Patched CCI (matches wickworks' fixed implementation)."""
    tp = (high + low + close) / 3.0
    mean = tp.rolling(length).mean()
    mad = tp.rolling(length).apply(
        lambda x: np.fabs(x - x.mean()).mean(), raw=True
    )
    return (tp - mean) / (c * mad)


def ref_vwma(close: pd.Series, volume: pd.Series, length: int = 10) -> pd.Series:
    pv = (close * volume).rolling(length).sum()
    v = volume.rolling(length).sum()
    return pv / v


# -----------------------------------------------------------------------------
# Comparison helper — strip Nones, compare last-bar value within tolerance.
# -----------------------------------------------------------------------------


def assert_last_bar_matches(
    response_series: list[float | None],
    expected: pd.Series,
    rtol: float = 1e-5,
    atol: float = 1e-8,
) -> None:
    actual = response_series[-1]
    expected_val = expected.iloc[-1]
    assert actual is not None, "response tail is None — wickworks returned NaN"
    assert not pd.isna(expected_val), (
        "reference tail is NaN — fixture too short or formula warmup not met"
    )
    assert abs(actual - expected_val) <= atol + rtol * abs(expected_val), (
        f"mismatch: wickworks={actual} reference={expected_val} "
        f"diff={actual - expected_val}"
    )
