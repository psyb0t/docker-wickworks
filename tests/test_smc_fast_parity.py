"""Parity tests: smc_fast (numba ports) must match upstream smartmoneyconcepts.

If upstream changes shape or fixes a bug, these tests catch the drift.
"""

from __future__ import annotations

import importlib
import math
import sys

import numpy as np
import pandas as pd
import pytest


def _bars_df(n: int = 300, seed: int = 0) -> pd.DataFrame:
    """Synthetic OHLCV with enough swings/gaps to exercise all 4 primitives."""
    rng = np.random.default_rng(seed)
    closes = []
    price = 100.0
    for i in range(n):
        # multi-frequency wave + noise → swings, FVGs, OBs all show up
        price += math.sin(i / 7.0) * 0.8 + math.cos(i / 13.0) * 0.5
        price += rng.normal(0, 0.3)
        closes.append(price)

    closes_arr = np.array(closes)
    opens = np.roll(closes_arr, 1)
    opens[0] = closes_arr[0]
    spread = np.abs(rng.normal(0, 0.4, n)) + 0.2
    highs = np.maximum(opens, closes_arr) + spread
    lows = np.minimum(opens, closes_arr) - spread
    vol = (1000 + rng.integers(0, 500, n)).astype(float)

    return pd.DataFrame(
        {
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes_arr,
            "volume": vol,
        }
    )


@pytest.fixture(scope="module")
def upstream_smc():
    """Reload smartmoneyconcepts WITHOUT the fast patch applied.

    Run AFTER capturing patched output, so a freshly-reloaded class has the
    original methods.
    """
    # Drop any patched module so reimport gives us the original class.
    for mod in list(sys.modules):
        if mod.startswith("smartmoneyconcepts"):
            del sys.modules[mod]
    smc_mod = importlib.import_module("smartmoneyconcepts.smc")
    return smc_mod.smc


@pytest.fixture(scope="module")
def fast_outputs():
    """Run all 4 fast primitives once on the shared fixture."""
    from wickworks import smc_fast

    df = _bars_df()
    sh = smc_fast.fast_swing_highs_lows(df, swing_length=15)
    ob = smc_fast.fast_ob(df, sh, close_mitigation=False)
    fvg = smc_fast.fast_fvg(df, join_consecutive=False)
    bosc = smc_fast.fast_bos_choch(df, sh, close_break=True)
    return {"df": df, "sh": sh, "ob": ob, "fvg": fvg, "bosc": bosc}


def _frames_equal(
    a: pd.DataFrame, b: pd.DataFrame, atol: float = 1e-9
) -> None:
    assert list(a.columns) == list(b.columns), (
        f"column mismatch: {list(a.columns)} vs {list(b.columns)}"
    )
    assert len(a) == len(b), f"length mismatch: {len(a)} vs {len(b)}"
    for col in a.columns:
        av = a[col].to_numpy(dtype=float)
        bv = b[col].to_numpy(dtype=float)
        nan_a = np.isnan(av)
        nan_b = np.isnan(bv)
        assert np.array_equal(nan_a, nan_b), f"NaN pattern differs in {col}"
        mask = ~nan_a
        if mask.any():
            assert np.allclose(av[mask], bv[mask], atol=atol), (
                f"values differ in {col}"
            )


def test_swing_highs_lows_parity(fast_outputs, upstream_smc):
    expected = upstream_smc.swing_highs_lows(
        fast_outputs["df"], swing_length=15
    )
    _frames_equal(fast_outputs["sh"], expected)


def test_fvg_parity(fast_outputs, upstream_smc):
    expected = upstream_smc.fvg(fast_outputs["df"], join_consecutive=False)
    _frames_equal(fast_outputs["fvg"], expected)


def test_fvg_join_consecutive_parity(upstream_smc):
    from wickworks import smc_fast

    df = _bars_df(seed=1)
    fast = smc_fast.fast_fvg(df, join_consecutive=True)
    expected = upstream_smc.fvg(df, join_consecutive=True)
    _frames_equal(fast, expected)


def test_ob_parity(fast_outputs, upstream_smc):
    expected = upstream_smc.ob(
        fast_outputs["df"], fast_outputs["sh"], close_mitigation=False
    )
    _frames_equal(fast_outputs["ob"], expected)


def test_ob_close_mitigation_parity(upstream_smc):
    from wickworks import smc_fast

    df = _bars_df(seed=2)
    sh = smc_fast.fast_swing_highs_lows(df, swing_length=15)
    fast = smc_fast.fast_ob(df, sh, close_mitigation=True)
    expected = upstream_smc.ob(df, sh, close_mitigation=True)
    _frames_equal(fast, expected)


def test_bos_choch_parity_close_break(fast_outputs, upstream_smc):
    expected = upstream_smc.bos_choch(
        fast_outputs["df"], fast_outputs["sh"], close_break=True
    )
    _frames_equal(fast_outputs["bosc"], expected)


def test_patch_is_idempotent():
    """Calling patch() twice must not double-wrap or break the class.

    The upstream_smc fixture above reloads smartmoneyconcepts to get the
    original class — that strips the previously-applied patches but leaves
    _patched=True (module-level guard). Reset it here so patch() actually
    runs and we can assert the post-state.
    """
    from wickworks import smc_fast

    smc_fast._patched = False  # force fresh patch after fixture reload
    smc_fast.patch()
    smc_fast.patch()  # second call must be a no-op via the _patched guard
    assert smc_fast._patched is True

    from smartmoneyconcepts.smc import smc as patched_smc

    assert patched_smc.swing_highs_lows is smc_fast.fast_swing_highs_lows
    assert patched_smc.fvg is smc_fast.fast_fvg
    assert patched_smc.bos_choch is smc_fast.fast_bos_choch
    assert patched_smc.ob is smc_fast.fast_ob
