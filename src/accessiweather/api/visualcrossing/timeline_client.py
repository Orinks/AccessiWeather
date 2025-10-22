"""
Thin wrapper around the generated Visual Crossing timeline client.

This helper keeps the rest of the code base from importing the generated package
directly while we evaluate whether an OpenAPI-driven client is maintainable.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

import httpx

from accessiweather.visual_crossing_api_client.visual_crossing_timeline_api_accessi_weather_sketch_client import (
    Client as GeneratedClient,
)
from accessiweather.visual_crossing_api_client.visual_crossing_timeline_api_accessi_weather_sketch_client.api.default import (
    get_timeline,
)
from accessiweather.visual_crossing_api_client.visual_crossing_timeline_api_accessi_weather_sketch_client.models.error_response import (
    ErrorResponse,
)
from accessiweather.visual_crossing_api_client.visual_crossing_timeline_api_accessi_weather_sketch_client.models.get_timeline_unit_group import (
    GetTimelineUnitGroup,
)
from accessiweather.visual_crossing_api_client.visual_crossing_timeline_api_accessi_weather_sketch_client.models.timeline_response import (
    TimelineResponse,
)
from accessiweather.visual_crossing_api_client.visual_crossing_timeline_api_accessi_weather_sketch_client.types import (
    UNSET,
)

logger = logging.getLogger(__name__)

VISUAL_CROSSING_BASE_URL = (
    "https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services"
)


@dataclass(slots=True)
class VisualCrossingTimelineRequest:
    """Configuration for a timeline lookup."""

    location: str
    include: str | None = None
    elements: str | None = None
    start_iso: str | None = None
    end_iso: str | None = None


@dataclass(slots=True)
class VisualCrossingTimelineClient:
    """Coordinates calls to the generated timeline client."""

    api_key: str
    user_agent: str = "AccessiWeather/1.0"
    unit_group: GetTimelineUnitGroup = GetTimelineUnitGroup.US
    default_include: str = "current,days,hours,alerts"
    default_elements: str | None = None
    timeout_seconds: float = 15.0

    def _build_client(self) -> GeneratedClient:
        """Create a generated client instance with project defaults."""
        client = GeneratedClient(
            base_url=VISUAL_CROSSING_BASE_URL,
            timeout=httpx.Timeout(self.timeout_seconds),
            follow_redirects=True,
        )
        if self.user_agent:
            client = client.with_headers({"User-Agent": self.user_agent})
        return client

    async def fetch(self, request: VisualCrossingTimelineRequest) -> TimelineResponse | None:
        """Execute the timeline request asynchronously."""
        include = request.include if request.include is not None else self.default_include
        elements = request.elements if request.elements is not None else self.default_elements

        start_dt = self._safe_from_iso(request.start_iso)
        end_dt = self._safe_from_iso(request.end_iso)

        try:
            async with self._build_client() as client:
                response = await get_timeline.asyncio(
                    location=request.location,
                    client=client,
                    key=self.api_key,
                    unit_group=self.unit_group,
                    include=include if include is not None else UNSET,
                    elements=elements if elements is not None else UNSET,
                    start_date_time=start_dt if start_dt is not None else UNSET,
                    end_date_time=end_dt if end_dt is not None else UNSET,
                )
        except Exception as exc:  # pragma: no cover - spike branch logging
            logger.debug("Visual Crossing timeline request failed: %s", exc)
            return None

        if response is None or isinstance(response, ErrorResponse):
            # Bubble up None for now; a real integration would map errors.
            return None

        if isinstance(response, TimelineResponse):
            return response

        # Unexpected shape; let callers decide whether to log or raise.
        logger.debug("Unexpected Visual Crossing timeline response type: %s", type(response))
        return None

    @staticmethod
    def _safe_from_iso(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            logger.debug("Unable to parse iso datetime: %s", value)
            return None
