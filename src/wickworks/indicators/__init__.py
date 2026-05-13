"""Technical indicator calculations package.

Each module adds indicator columns to a DataFrame with OHLCV data.
Expected input columns (lowercase):
    time, open, high, low, close, tick_volume (or volume)
"""

import os

import pandas as pd

if not os.environ.get("DISABLE_SMC_FAST"):
    from ..smc_fast import patch as _patch_smc

    _patch_smc()

from . import (  # noqa: E402
    momentum_adx,
    momentum_macd,
    momentum_mfi,
    momentum_rsi,
    momentum_stochastic,
    overextension,
    price_action_donchian,
    price_action_swing_structure,
    price_action_vwap,
    smc,
    trend_moving_averages,
    volatility_atr,
    volatility_bollinger,
    volume_analysis,
)

__all__ = ["add_all"]


def add_all(df: pd.DataFrame) -> pd.DataFrame:
    """Add all indicators to the DataFrame."""
    df = trend_moving_averages.add(df)
    df = volatility_atr.add(df)
    df = momentum_rsi.add(df)
    df = momentum_macd.add(df)
    df = volatility_bollinger.add(df)
    df = momentum_mfi.add(df)
    df = momentum_stochastic.add(df)
    df = momentum_adx.add(df)
    df = price_action_vwap.add(df)
    df = price_action_donchian.add(df)
    df = volume_analysis.add(df)
    df = smc.add(df)
    df = price_action_swing_structure.add(df)
    df = overextension.add(df)
    return df
