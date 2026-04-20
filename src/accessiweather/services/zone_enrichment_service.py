"""
Zone enrichment service for NWS /points metadata.

On save of a new US location, this service fetches the NWS /points endpoint
once and maps the response onto six zone-related fields of a ``Location``
dataclass (``timezone``, ``cwa_office``, ``forecast_zone_id``,
``county_zone_id``, ``fire_zone_id``, ``radar_station``).

Non-US locations and /points failures must never block the save: the service
returns the original ``Location`` unchanged, and no exception propagates.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from ..models import Location

logger = logging.getLogger(__name__)

NWS_API_BASE = "https://api.weather.gov"
DEFAULT_USER_AGENT = "AccessiWeather/1.0 (AccessiWeather)"
DEFAULT_TIMEOUT = 10.0


def _is_us_location(location: Location) -> bool:
    """
    Return True when the location should use NWS (US) data sources.

    Mirrors the heuristic in ``display/presentation/forecast.py`` so enrichment
    and forecast-rendering agree on what counts as a US location.
    """
    country_code = getattr(location, "country_code", None)
    if country_code:
        return country_code.upper() == "US"

    lat = location.latitude
    lon = location.longitude
    in_continental_bounds = 24.0 <= lat <= 49.0 and -125.0 <= lon <= -66.0
    in_alaska_bounds = 51.0 <= lat <= 71.5 and -172.0 <= lon <= -130.0
    in_hawaii_bounds = 18.0 <= lat <= 23.0 and -161.0 <= lon <= -154.0
    return in_continental_bounds or in_alaska_bounds or in_hawaii_bounds


def _last_path_segment(url: str | None) -> str | None:
    """
    Extract the last non-empty path segment from a URL.

    Example: ``"https://api.weather.gov/zones/forecast/PAZ106"`` -> ``"PAZ106"``.
    Returns ``None`` for falsy or non-string input.
    """
    if not url or not isinstance(url, str):
        return None
    # Strip any trailing slash, then take the final segment.
    trimmed = url.rstrip("/")
    if not trimmed:
        return None
    segment = trimmed.rsplit("/", 1)[-1]
    return segment or None


def _extract_zone_fields(properties: dict) -> dict[str, str | None]:
    """
    Map a /points ``properties`` payload to Location zone field values.

    Missing keys are returned as ``None`` so callers can cleanly merge the
    result onto a Location without clobbering fields that were not present
    in the response.
    """
    time_zone = properties.get("timeZone")
    cwa = properties.get("cwa")
    radar_station = properties.get("radarStation")

    return {
        "timezone": time_zone if isinstance(time_zone, str) and time_zone else None,
        "cwa_office": cwa if isinstance(cwa, str) and cwa else None,
        "forecast_zone_id": _last_path_segment(properties.get("forecastZone")),
        "county_zone_id": _last_path_segment(properties.get("county")),
        "fire_zone_id": _last_path_segment(properties.get("fireWeatherZone")),
        "radar_station": (
            radar_station if isinstance(radar_station, str) and radar_station else None
        ),
    }


class ZoneEnrichmentService:
    """
    Fetch NWS /points zone metadata and map it onto a Location.

    The service is intentionally minimal: constructor injection for the
    async HTTP client (so tests can substitute a mock), and a single
    ``enrich_location`` entry point that never raises.
    """

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        *,
        base_url: str = NWS_API_BASE,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        """
        Create a new enrichment service.

        Args:
            client: Optional pre-built ``httpx.AsyncClient``. When omitted,
                each ``enrich_location`` call constructs a short-lived client.
            base_url: NWS API base URL (overrideable for tests).
            user_agent: User-Agent header value required by NWS.
            timeout: Per-request timeout in seconds.

        """
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._user_agent = user_agent
        self._timeout = timeout

    async def enrich_location(self, location: Location) -> Location:
        """
        Return a new ``Location`` with zone fields populated.

        Returns the original ``location`` unchanged when:
          * the location is not in the US, or
          * the /points fetch fails for any reason (HTTP error, timeout,
            non-200 response, malformed payload).

        This method never raises.
        """
        if not _is_us_location(location):
            logger.debug("Skipping zone enrichment for non-US location: %s", location.name)
            return location

        properties = await self._fetch_points_properties(location.latitude, location.longitude)
        if properties is None:
            # Already logged at debug inside the fetch helper.
            return location

        fields = _extract_zone_fields(properties)
        # Only set fields that are actually present in the payload so we don't
        # blow away any values the caller may have pre-populated.
        updates = {key: value for key, value in fields.items() if value is not None}
        if not updates:
            logger.debug("No zone fields present in /points payload for %s", location.name)
            return location

        return replace(location, **updates)

    async def _fetch_points_properties(self, lat: float, lon: float) -> dict | None:
        """
        Fetch ``/points/{lat},{lon}`` and return the ``properties`` dict.

        Returns ``None`` on any failure. All errors are swallowed and logged
        at debug level so a transient API issue never blocks a location save.
        """
        url = f"{self._base_url}/points/{lat},{lon}"
        headers = {
            "User-Agent": self._user_agent,
            "Accept": "application/geo+json",
        }

        try:
            if self._client is not None:
                response = await self._client.get(url, headers=headers, timeout=self._timeout)
            else:
                async with httpx.AsyncClient(
                    timeout=self._timeout, follow_redirects=True
                ) as client:
                    response = await client.get(url, headers=headers)
        except httpx.HTTPError as exc:
            logger.debug("Zone enrichment /points request failed: %s", exc)
            return None
        except Exception as exc:  # noqa: BLE001 - defensive: never block save
            logger.debug("Zone enrichment /points unexpected error: %s", exc)
            return None

        if response.status_code != 200:
            logger.debug(
                "Zone enrichment /points returned status %s for (%s, %s)",
                response.status_code,
                lat,
                lon,
            )
            return None

        try:
            payload = response.json()
        except ValueError as exc:
            logger.debug("Zone enrichment /points returned invalid JSON: %s", exc)
            return None

        if not isinstance(payload, dict):
            logger.debug("Zone enrichment /points payload not a dict: %r", type(payload))
            return None

        properties = payload.get("properties")
        if not isinstance(properties, dict):
            logger.debug("Zone enrichment /points payload missing 'properties' key")
            return None

        return properties
