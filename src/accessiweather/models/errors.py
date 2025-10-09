"""Error models for AccessiWeather."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class ApiError:
    """API error information."""

    message: str
    code: str | None = None
    details: str | None = None
    timestamp: datetime | None = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
