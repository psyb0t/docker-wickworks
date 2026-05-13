"""Fair-value gap detection — 3-bar imbalance pattern."""

from __future__ import annotations

from typing import Any

from _helpers import post  # type: ignore[import-not-found]


def test_fvg_detects_bullish_gap() -> None:
    """Hand-crafted 3-bar bullish gap: bar 102 low > bar 100 high."""
    bars: list[dict[str, Any]] = []
    t0 = 1_700_000_000
    for i in range(100):
        bars.append(
            {
                "time": t0 + i * 3600,
                "open": 100.0,
                "high": 100.5,
                "low": 99.5,
                "close": 100.0,
                "tickVolume": 1000,
            }
        )
    bars.append(
        {
            "time": t0 + 100 * 3600,
            "open": 100.0,
            "high": 101.0,
            "low": 100.0,
            "close": 101.0,
            "tickVolume": 1000,
        }
    )
    bars.append(
        {
            "time": t0 + 101 * 3600,
            "open": 101.0,
            "high": 106.0,
            "low": 101.0,
            "close": 106.0,
            "tickVolume": 5000,
        }
    )
    bars.append(
        {
            "time": t0 + 102 * 3600,
            "open": 106.0,
            "high": 107.0,
            "low": 105.0,
            "close": 106.5,
            "tickVolume": 1000,
        }
    )
    for i in range(50):
        bars.append(
            {
                "time": t0 + (103 + i) * 3600,
                "open": 106.5,
                "high": 107.0,
                "low": 106.0,
                "close": 106.5,
                "tickVolume": 1000,
            }
        )

    out = post(bars, {"fvg": True})
    fvgs = out["fvg"]
    assert isinstance(fvgs, list)
    bullish = [f for f in fvgs if f.get("type") == "bullish"]
    assert len(bullish) >= 1, f"expected >=1 bullish FVG, got {fvgs}"


def test_fvg_list_shape_on_real_data(eurusd_h1_fixture: dict[str, Any]) -> None:
    out = post(eurusd_h1_fixture["bars"], {"fvg": True})
    assert isinstance(out["fvg"], list)
    for fvg in out["fvg"]:
        assert "type" in fvg and fvg["type"] in ("bullish", "bearish")
