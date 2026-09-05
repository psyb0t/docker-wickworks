"""Domain errors raised by the compute boundary."""

from __future__ import annotations

from typing import Any


class WickworksError(Exception):
    """Base class for errors safe to classify at the HTTP boundary."""


class InvalidIndicatorSpecError(WickworksError, ValueError):
    """Raised when an indicator spec contains invalid parameters."""


class UnknownIndicatorError(WickworksError, ValueError):
    """Raised when a request references an unregistered indicator."""


class InsufficientBarsError(WickworksError, ValueError):
    """Raised when requested indicators need more bars than supplied."""

    def __init__(self, available: int, deficits: list[dict[str, Any]]) -> None:
        self.available = available
        self.deficits = deficits
        summary = ", ".join(
            f"{deficit['outputKey']} (type={deficit['type']}) needs {deficit['required']}"
            for deficit in deficits
        )
        super().__init__(f"insufficient bars: have {available}, but: {summary}")
