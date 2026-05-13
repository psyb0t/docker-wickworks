"""Pydantic request/response schemas."""

from __future__ import annotations

from typing import Any, Union

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

# Per-indicator spec: either `true` (use defaults; key doubles as `type`) or a
# free-form params object. If the params object contains "type", that's the
# indicator name; otherwise the request-dict key is used as the type.
IndicatorSpec = Union[bool, dict[str, Any]]


class Bar(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    time: int = Field(..., description="UTC unix seconds")
    open: float
    high: float
    low: float
    close: float
    tick_volume: int = Field(
        default=0,
        ge=0,
        validation_alias=AliasChoices("tickVolume", "tick_volume"),
    )
    real_volume: int = Field(
        default=0,
        ge=0,
        validation_alias=AliasChoices("realVolume", "real_volume"),
    )


class ComputeRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    symbol: str = Field(default="", description="Echoed back in the response.")
    timeframe: str = Field(default="", description="Echoed back in the response.")
    recent_bars: int = Field(
        default=10,
        ge=1,
        validation_alias=AliasChoices("recentBars", "recent_bars"),
        description="Signal-like outputs within this many bars from end get isRecent=true.",
    )
    bars: list[Bar]
    indicators: dict[str, IndicatorSpec] = Field(
        default_factory=dict,
        description=(
            "Map of output-name -> spec. spec=true uses indicator with defaults "
            "(key doubles as type). spec is a params object; include 'type' to "
            "run a known indicator under a different output name."
        ),
    )


class HealthResponse(BaseModel):
    ok: bool
    version: str
