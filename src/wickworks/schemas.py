"""Pydantic request/response schemas."""

from __future__ import annotations

from typing import Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Per-indicator spec: either `true` (use defaults; key doubles as `type`) or a
# free-form params object. If the params object contains "type", that's the
# indicator name; otherwise the request-dict key is used as the type.
IndicatorSpec = Union[Literal[True], dict[str, Any]]


class Bar(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    time: int = Field(..., ge=0, description="UTC unix seconds")
    open: float = Field(..., gt=0, allow_inf_nan=False)
    high: float = Field(..., gt=0, allow_inf_nan=False)
    low: float = Field(..., gt=0, allow_inf_nan=False)
    close: float = Field(..., gt=0, allow_inf_nan=False)
    volume: float = Field(
        ...,
        ge=0,
        allow_inf_nan=False,
        description=(
            "Caller-selected per-bar activity or volume measure. Wickworks "
            "treats it as one numeric series and does not interpret "
            "vendor-specific volume types."
        ),
    )

    @model_validator(mode="after")
    def validate_geometry(self) -> Bar:
        if self.high < self.low:
            raise ValueError("high must be greater than or equal to low")
        if not self.low <= self.open <= self.high:
            raise ValueError("open must be between low and high")
        if not self.low <= self.close <= self.high:
            raise ValueError("close must be between low and high")
        return self


class ComputeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    symbol: str = Field(
        default="",
        max_length=128,
        description="Caller-supplied instrument label, echoed unchanged in the response.",
    )
    timeframe: str = Field(
        default="",
        max_length=32,
        title="Chart interval label only",
        description=(
            "Top-level ComputeRequest.timeframe is an opaque caller-supplied "
            "chart interval label, such as H4. Wickworks echoes it and attaches "
            "it to analysis summaries, but does not parse it or use it to "
            "bucket bars. Calculations use the submitted bar values and timestamps."
        ),
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

    @field_validator("indicators", mode="before")
    @classmethod
    def validate_indicator_specs(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        for output_key, spec in value.items():
            if spec is True or isinstance(spec, dict):
                continue
            raise ValueError(f"indicator {output_key!r} must be true or an object")
        return value

    @model_validator(mode="after")
    def validate_bar_times(self) -> ComputeRequest:
        times = [bar.time for bar in self.bars]
        if any(current <= previous for previous, current in zip(times, times[1:])):
            raise ValueError("bar times must be strictly increasing and unique")
        return self


class HealthResponse(BaseModel):
    ok: bool
    version: str
