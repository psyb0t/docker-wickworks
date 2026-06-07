"""Golden-value tests for the SMC analyze() projection layer.

analyze() reads pre-populated indicator columns and projects them into the
JSON summary returned via the registry. These tests validate the projection
math (distance_pct sign convention, sort order, top-N truncation, position,
slope) — NOT the underlying indicators themselves.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


def _empty_smc_cols(n: int) -> dict:
    """All SMC/indicator columns analyze() expects, zeroed/NaN."""
    return {
        "swing_type": np.zeros(n, dtype=int),
        "swing_level": np.full(n, np.nan),
        "sw7_hl": np.full(n, np.nan),
        "sw7_level": np.full(n, np.nan),
        "ob_type": np.zeros(n, dtype=int),
        "ob_top": np.full(n, np.nan),
        "ob_bottom": np.full(n, np.nan),
        "ob_mitigated": np.full(n, np.nan),
        "fvg_type": np.zeros(n, dtype=int),
        "fvg_top": np.full(n, np.nan),
        "fvg_bottom": np.full(n, np.nan),
        "fvg_mitigated": np.full(n, np.nan),
        "bos": np.zeros(n, dtype=int),
        "choch": np.zeros(n, dtype=int),
        "bos_choch_level": np.full(n, np.nan),
        "ema_21": np.full(n, np.nan),
        "sma_50": np.full(n, np.nan),
        "sma_100": np.full(n, np.nan),
        "sma_200": np.full(n, np.nan),
        "atr": np.full(n, np.nan),
        "vwap": np.full(n, np.nan),
        "vol_ratio": np.full(n, np.nan),
        "obv": np.full(n, np.nan),
        "rsi": np.full(n, np.nan),
        "mfi": np.full(n, np.nan),
    }


def _base_df(n: int = 100, price_close: float = 100.0) -> pd.DataFrame:
    """Minimal OHLCV df + all SMC cols pre-populated empty."""
    cols = _empty_smc_cols(n)
    cols["time"] = np.arange(1_700_000_000, 1_700_000_000 + n * 3600, 3600)
    cols["open"] = np.full(n, price_close)
    cols["high"] = np.full(n, price_close + 1.0)
    cols["low"] = np.full(n, price_close - 1.0)
    cols["close"] = np.full(n, price_close)
    cols["tick_volume"] = np.full(n, 1000)
    return pd.DataFrame(cols)


def test_analyze_no_smc_events_yields_empty_lists():
    from wickworks.smc import analyze

    df = _base_df()
    out = analyze(df, "H1")

    assert out["timeframe"] == "H1"
    assert out["candles"] == 100
    assert out["order_blocks"] == []
    assert out["fvgs"] == []
    assert out["bos_choch"] == []
    assert out["swing_levels"] == []
    assert out["sr_levels"] == []


def test_analyze_bullish_ob_distance_sign():
    """Bullish OB below price → positive distance_pct."""
    from wickworks.smc import analyze

    df = _base_df(price_close=100.0)
    df.loc[10, "ob_type"] = 1
    df.loc[10, "ob_top"] = 95.0
    df.loc[10, "ob_bottom"] = 90.0
    # ob_mitigated stays NaN → "active" OB

    out = analyze(df, "H1")
    assert len(out["order_blocks"]) == 1
    ob = out["order_blocks"][0]
    assert ob["type"] == "bullish"
    assert ob["top"] == 95.0
    assert ob["bottom"] == 90.0
    # (100 - 95) / 100 * 100 = 5.0
    assert ob["distance_pct"] == pytest.approx(5.0)


def test_analyze_bearish_ob_distance_sign():
    """Bearish OB above price → positive distance_pct."""
    from wickworks.smc import analyze

    df = _base_df(price_close=100.0)
    df.loc[10, "ob_type"] = -1
    df.loc[10, "ob_top"] = 110.0
    df.loc[10, "ob_bottom"] = 105.0

    out = analyze(df, "H1")
    ob = out["order_blocks"][0]
    assert ob["type"] == "bearish"
    # (105 - 100) / 100 * 100 = 5.0
    assert ob["distance_pct"] == pytest.approx(5.0)


def test_analyze_ob_mitigation_flags_round_trip():
    # As of v0.5.0 the OB extractor stops dropping mitigated entries —
    # consumers now receive every OB plus per-row `mitigated_wick` /
    # `mitigated_close` flags so they can pick their freshness criterion.
    # This test verifies both OBs round-trip and the wick-criterion flag
    # mirrors the legacy `ob_mitigated` column.
    from wickworks.smc import analyze

    df = _base_df()
    df.loc[10, "ob_type"] = 1
    df.loc[10, "ob_top"] = 95.0
    df.loc[10, "ob_bottom"] = 90.0
    df.loc[10, "ob_mitigated"] = 50  # wick-mitigated at bar 50
    df.loc[20, "ob_type"] = 1
    df.loc[20, "ob_top"] = 92.0
    df.loc[20, "ob_bottom"] = 88.0
    # bar 20 stays fully fresh — both flags should be false

    out = analyze(df, "H1")
    obs = out["order_blocks"]
    assert len(obs) == 2
    by_bottom = {ob["bottom"]: ob for ob in obs}
    assert by_bottom[90.0]["mitigated_wick"] is True
    assert by_bottom[90.0]["mitigated_close"] is False
    assert by_bottom[88.0]["mitigated_wick"] is False
    assert by_bottom[88.0]["mitigated_close"] is False


def test_analyze_ob_sorted_by_distance_ascending():
    from wickworks.smc import analyze

    df = _base_df(price_close=100.0)
    # closer OB
    df.loc[10, ["ob_type", "ob_top", "ob_bottom"]] = [1, 98.0, 97.0]
    # farther OB
    df.loc[20, ["ob_type", "ob_top", "ob_bottom"]] = [1, 90.0, 89.0]

    out = analyze(df, "H1")
    obs = out["order_blocks"]
    assert obs[0]["top"] == 98.0  # closer comes first
    assert obs[1]["top"] == 90.0


def test_analyze_ob_top_40_truncation():
    # Cap raised 20 → 40 in v0.5.0 to compensate for no longer dropping
    # mitigated OBs at the source — a 20-cap would silently lose signal
    # since the cap now applies to live + mitigated combined.
    from wickworks.smc import analyze

    df = _base_df(n=200, price_close=100.0)
    # 50 OBs at descending distances — sorted ascending by distance
    # before truncation, so the closest 40 should survive.
    for i in range(50):
        df.loc[10 + i, "ob_type"] = 1
        df.loc[10 + i, "ob_top"] = 99.0 - i * 0.1
        df.loc[10 + i, "ob_bottom"] = 98.0 - i * 0.1

    out = analyze(df, "H1")
    assert len(out["order_blocks"]) == 40


def test_analyze_fvg_distance_uses_midpoint():
    from wickworks.smc import analyze

    df = _base_df(price_close=100.0)
    df.loc[10, "fvg_type"] = 1
    df.loc[10, "fvg_top"] = 96.0
    df.loc[10, "fvg_bottom"] = 94.0

    out = analyze(df, "H1")
    fvg = out["fvgs"][0]
    # midpoint=95, |100-95|/100*100 = 5.0
    assert fvg["distance_pct"] == pytest.approx(5.0)
    assert fvg["type"] == "bullish"


def test_analyze_fvg_top_15_truncation():
    from wickworks.smc import analyze

    df = _base_df(n=200)
    for i in range(20):
        df.loc[10 + i, "fvg_type"] = 1
        df.loc[10 + i, "fvg_top"] = 99.0 - i * 0.1
        df.loc[10 + i, "fvg_bottom"] = 98.0 - i * 0.1

    out = analyze(df, "H1")
    assert len(out["fvgs"]) == 15


def test_analyze_bos_choch_last_10():
    from wickworks.smc import analyze

    df = _base_df()
    # 12 BOS events at indices 80..91 → only last 10 kept
    for i in range(12):
        df.loc[80 + i, "bos"] = 1
        df.loc[80 + i, "bos_choch_level"] = 100.0 + i

    out = analyze(df, "H1")
    events = out["bos_choch"]
    assert len(events) == 10
    assert events[0]["level"] == pytest.approx(102.0)  # event from bar 82
    assert events[-1]["level"] == pytest.approx(111.0)
    assert all(e["event"] == "BOS" for e in events)
    assert all(e["direction"] == "bullish" for e in events)


def test_analyze_bos_choch_only_last_50_bars_scanned():
    from wickworks.smc import analyze

    df = _base_df(n=100)
    df.loc[10, "bos"] = 1  # outside last 50 → ignored
    df.loc[10, "bos_choch_level"] = 99.0
    df.loc[60, "choch"] = -1
    df.loc[60, "bos_choch_level"] = 105.0

    out = analyze(df, "H1")
    assert len(out["bos_choch"]) == 1
    e = out["bos_choch"][0]
    assert e["event"] == "CHoCH"
    assert e["direction"] == "bearish"
    assert e["level"] == pytest.approx(105.0)


def test_analyze_swing_levels_high_vs_low_mapping():
    from wickworks.smc import analyze

    df = _base_df()
    df.loc[60, "swing_type"] = 1
    df.loc[60, "swing_level"] = 110.0
    df.loc[70, "swing_type"] = -1
    df.loc[70, "swing_level"] = 90.0

    out = analyze(df, "H1")
    swings = out["swing_levels"]
    assert len(swings) == 2
    assert swings[0]["type"] == "high"
    assert swings[0]["level"] == 110.0
    assert swings[1]["type"] == "low"
    assert swings[1]["level"] == 90.0


def test_analyze_position_above_below():
    from wickworks.smc import analyze

    df = _base_df(price_close=100.0)
    df.loc[df.index[-1], "ema_21"] = 95.0  # price > ema → above
    df.loc[df.index[-1], "sma_50"] = 105.0  # price < sma → below
    df.loc[df.index[-1], "vwap"] = 99.0  # price > vwap → above

    out = analyze(df, "H1")
    pos = out["position"]
    assert pos["ema_21"] == "above"
    assert pos["sma_50"] == "below"
    assert pos["vwap"] == "above"
    # sma_100/sma_200 stayed NaN → not in dict
    assert "sma_100" not in pos
    assert "sma_200" not in pos


def test_analyze_slope_up_down():
    from wickworks.smc import analyze

    df = _base_df(n=100, price_close=100.0)
    # Slope lookback is 10 bars: compare iloc[-1] vs iloc[-11]
    df.loc[df.index[-1], "ema_21"] = 105.0
    df.loc[df.index[-11], "ema_21"] = 100.0  # up
    df.loc[df.index[-1], "sma_50"] = 100.0
    df.loc[df.index[-11], "sma_50"] = 105.0  # down
    df.loc[df.index[-1], "sma_100"] = 100.0
    df.loc[df.index[-11], "sma_100"] = 100.0  # flat → omitted

    out = analyze(df, "H1")
    slope = out["slope"]
    assert slope["ema_21"] == "up"
    assert slope["sma_50"] == "down"
    assert "sma_100" not in slope


def test_analyze_recent_range_uses_tail_20():
    from wickworks.smc import analyze

    df = _base_df(n=100, price_close=100.0)
    # Boost a high outside the last 20 bars and inside it.
    df.loc[10, "high"] = 200.0   # outside → period_high, NOT recent
    df.loc[90, "high"] = 150.0   # inside → recent.high
    df.loc[5, "low"] = 50.0      # outside → period_low
    df.loc[95, "low"] = 70.0     # inside → recent.low

    out = analyze(df, "H1")
    rng = out["recent_range"]
    assert rng["high"] == 150.0
    assert rng["low"] == 70.0
    assert rng["period_high"] == 200.0
    assert rng["period_low"] == 50.0


def test_analyze_momentum_uses_prefix_lookup():
    """Custom MACD lengths should still be discoverable via prefix."""
    from wickworks.smc import analyze

    df = _base_df()
    # Non-default lengths — exact-name lookup would fail here.
    df["MACDh_5_13_4"] = np.full(len(df), np.nan)
    df.loc[df.index[-1], "MACDh_5_13_4"] = 0.42
    df["ADX_21"] = np.full(len(df), np.nan)
    df.loc[df.index[-1], "ADX_21"] = 33.3

    out = analyze(df, "H1")
    assert out["momentum"]["macd_hist"] == pytest.approx(0.42)
    assert out["momentum"]["adx"] == pytest.approx(33.3)


def test_analyze_volume_spike_flag():
    from wickworks.smc import analyze

    df = _base_df()
    df.loc[df.index[-1], "vol_ratio"] = 2.5  # > 2.0 → spike
    out = analyze(df, "H1")
    assert out["volume"]["is_spike"] is True
    assert out["volume"]["vol_ratio"] == pytest.approx(2.5)

    df.loc[df.index[-1], "vol_ratio"] = 1.5  # < 2.0 → no spike
    out = analyze(df, "H1")
    assert out["volume"]["is_spike"] is False


# ---------------------------------------------------------------------------
# Degenerate-price guards. analyze() used to leak ±Inf into the response
# whenever (price - x) / price divided by a zero/NaN price, crashing
# FastAPI's JSON encoder with: "Out of range float values are not JSON
# compliant: -inf". The fix bails with an empty-but-typed stub in that
# case AND keeps full precision for sub-1e-6 crypto prices.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_close",
    [0.0, -1.0, np.nan],
    ids=["zero", "negative", "nan"],
)
def test_analyze_degenerate_price_bails_with_stub(bad_close: float):
    """All three degenerate cases (0, negative, NaN) hit the same guard at
    the top of analyze() and return an empty-but-typed dict. Critical: no
    ±Inf anywhere — the response must round-trip through strict JSON."""
    import json

    from wickworks.smc import analyze

    df = _base_df()
    df.loc[df.index[-1], "close"] = bad_close
    out = analyze(df, "H1")

    # Strict JSON would raise on Inf/NaN — proves the response is clean.
    json.dumps(out, allow_nan=False)

    # Empty-but-typed stub — frontend renders nothing, no crash.
    assert out["order_blocks"] == []
    assert out["fvgs"] == []
    assert out["sr_levels"] == []
    assert out["swing_levels"] == []
    assert out["recent_range"] == {}
    assert out["levels"] == {}
    assert out["momentum"] == {}


@pytest.mark.parametrize(
    "tiny_price",
    [1e-7, 1e-8, 1e-12, 1e-15],
    ids=["1e-7", "1e-8", "1e-12", "1e-15"],
)
def test_analyze_tiny_crypto_price_preserves_precision(tiny_price: float):
    """SHIB / PEPE / micro-cap launches trade well below 1e-6. The price
    guard must not round these to 0, and the price stored in the result
    must preserve the actual magnitude for the frontend chart."""
    import json

    from wickworks.smc import analyze

    df = _base_df(price_close=tiny_price)
    out = analyze(df, "H1")

    # Did NOT hit the bail-stub.
    assert out["price"] == tiny_price
    assert out["recent_range"] != {}
    # And serializes cleanly with no Inf/NaN.
    json.dumps(out, allow_nan=False)


@pytest.mark.parametrize(
    "series_in,expected",
    [
        # CCI mad=0 path produces ±Inf — must become None
        ([1.0, np.inf, 2.0], [1.0, None, 2.0]),
        ([1.0, -np.inf, 2.0], [1.0, None, 2.0]),
        # NaN already handled before this fix, kept to lock behavior
        ([1.0, np.nan, 2.0], [1.0, None, 2.0]),
        # Mixed
        ([np.inf, np.nan, -np.inf, 3.0], [None, None, None, 3.0]),
        # Empty/passthrough
        ([], []),
        ([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]),
    ],
    ids=["plus_inf", "minus_inf", "nan", "all_invalid_mix", "empty", "all_valid"],
)
def test_series_sanitizes_indicator_output(
    series_in: list, expected: list
):
    """_series is the JSON projection for every series indicator. CCI on a
    flat window produces ±Inf from (tp-mean)/(c*mad) when mad=0; pandas_ta
    primitives can also emit Inf from divide-by-zero edge cases. This lock
    proves _series replaces every non-finite value with None."""
    import json

    import pandas as pd

    from wickworks.registry import _series

    out = _series(pd.Series(series_in, dtype=float))
    assert out == expected
    # Result must round-trip through strict JSON.
    json.dumps(out, allow_nan=False)
