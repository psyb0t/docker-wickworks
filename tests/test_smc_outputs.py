"""SMC list outputs — orderBlocks, bosChoch, swingLevels, srLevels.

Math/golden coverage for these structures lives in test_smc_analyze.py and
test_smc_fast_parity.py. This file pins their end-to-end shape against the
real EURUSD fixture.
"""

from __future__ import annotations

from typing import Any

import pytest

from _helpers import post  # type: ignore[import-not-found]


_SMC_INDICATORS = ["orderBlocks", "fvg", "bosChoch", "swingLevels", "srLevels"]


@pytest.fixture(scope="module")
def smc_response(eurusd_h1_fixture: dict[str, Any]) -> dict[str, Any]:
    return post(
        eurusd_h1_fixture["bars"], {ind: True for ind in _SMC_INDICATORS}
    )


@pytest.mark.parametrize("indicator", _SMC_INDICATORS)
def test_smc_output_is_list(smc_response: dict[str, Any], indicator: str) -> None:
    assert isinstance(smc_response[indicator], list)
