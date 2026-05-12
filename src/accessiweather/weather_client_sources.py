"""Source-specific helper methods for WeatherClient."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from . import (
    weather_client_enrichment as enrichment,
    weather_client_nws as nws_client,
    weather_client_openmeteo as openmeteo_client,
    weather_client_parsers as parsers,
)
from .location_classification import is_us_location
from .models import (
    AviationData,
    CurrentConditions,
    Forecast,
    HourlyForecast,
    Location,
    WeatherAlerts,
    WeatherData,
)
from .pirate_weather_client import PirateWeatherClient
from .units import resolve_auto_unit_system

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class WeatherClientSourcesMixin:
    def _determine_api_choice(self, location: Location) -> str:
        """Determine which API to use for the given location."""
        # Validate data source
        valid_sources = ["auto", "nws", "openmeteo", "pirateweather"]
        if self.data_source not in valid_sources:
            logger.warning(f"Invalid data source '{self.data_source}', defaulting to 'auto'")
            self.data_source = "auto"

        if self.data_source == "pirateweather":
            if not self.pirate_weather_client:
                # The lazy key may have cached an empty result from a transient
                # keyring failure (e.g., right after an MSI update).  Reset and
                # retry once before giving up.
                lazy = self._pirate_weather_api_key
                if hasattr(lazy, "reset"):
                    lazy.reset()
                    # Force re-evaluation after reset
                    self._pirate_weather_client = None
                if not self.pirate_weather_client:
                    logger.warning(
                        "Pirate Weather selected but no API key provided, falling back to auto"
                    )
                    return "nws" if self._is_us_location(location) else "openmeteo"
            return "pirateweather"
        if self.data_source == "openmeteo":
            return "openmeteo"
        if self.data_source == "nws":
            return "nws"
        if self.data_source == "auto":
            # Use NWS for US locations, Open-Meteo for international locations
            return "nws" if self._is_us_location(location) else "openmeteo"
        # Fallback for any unexpected cases
        logger.warning(f"Unexpected data source '{self.data_source}', defaulting to auto")
        return "nws" if self._is_us_location(location) else "openmeteo"

    @staticmethod
    def _location_key(location: Location) -> str:
        """Return a stable string key for a location (used for alert caching)."""
        return f"{location.latitude:.4f},{location.longitude:.4f}"

    def _resolve_pirate_weather_units(self, location: Location) -> str:
        """Resolve the Pirate Weather unit bundle for the given location."""
        preference = (getattr(self.settings, "temperature_unit", "both") or "both").strip().lower()
        if preference == "auto":
            unit_system = resolve_auto_unit_system(location)
            return "uk" if unit_system.value == "uk" else unit_system.value
        if preference in {"c", "celsius"}:
            return "ca"
        return "us"

    def _pirate_weather_client_for_location(self, location: Location) -> PirateWeatherClient | None:
        """Return a Pirate Weather client configured for the location's effective unit system."""
        api_key = self.pirate_weather_api_key
        if not api_key:
            return None

        units = self._resolve_pirate_weather_units(location)
        client = self._pirate_weather_client
        if client is None or client.units != units:
            client = PirateWeatherClient(api_key, self.user_agent, units=units)
            self._pirate_weather_client = client
        return client

    def _is_us_location(self, location: Location) -> bool:
        """
        Check if location is within the United States.

        Uses country_code when available for accurate detection. Falls back to
        coordinate bounds only for clear-cut cases. For ambiguous regions (near US-Canada
        border), requires country_code to be set - otherwise returns False to avoid
        misclassifying Canadian cities as US locations.
        """
        result = is_us_location(location)
        if not result and getattr(location, "country_code", None) is None:
            logger.debug(
                "Location '%s' lacks country_code and is not safely classifiable as US; "
                "re-add it through geocoding to set country_code.",
                location.name,
            )
        return result

    def _set_empty_weather_data(self, weather_data: WeatherData) -> None:
        """Set empty weather data when all APIs fail."""
        weather_data.current = CurrentConditions()
        weather_data.forecast = Forecast(periods=[])
        weather_data.hourly_forecast = HourlyForecast(periods=[])
        weather_data.discussion = "Weather data not available."
        weather_data.discussion_issuance_time = None
        weather_data.alerts = WeatherAlerts(alerts=[])

    async def _get_nws_current_conditions(self, location: Location) -> CurrentConditions | None:
        """Delegate to the NWS client module."""
        return await nws_client.get_nws_current_conditions(
            location, self.nws_base_url, self.user_agent, self.timeout, self._get_http_client()
        )

    async def _get_nws_forecast_and_discussion(
        self, location: Location
    ) -> tuple[Forecast | None, str | None, datetime | None]:
        """Delegate to the NWS client module."""
        return await nws_client.get_nws_forecast_and_discussion(
            location, self.nws_base_url, self.user_agent, self.timeout, self._get_http_client()
        )

    async def _get_nws_discussion_only(
        self, location: Location
    ) -> tuple[str | None, datetime | None]:
        """Fetch only the NWS AFD discussion (no forecast). Used by the notification path."""
        return await nws_client.get_nws_discussion_only(
            location, self.nws_base_url, self.user_agent, self.timeout, self._get_http_client()
        )

    async def _get_nws_alerts(self, location: Location) -> WeatherAlerts | None:
        """Delegate to the NWS client module."""
        from . import weather_client_base as base_module

        alert_radius_type = getattr(self.settings, "alert_radius_type", "county")
        return await base_module.nws_client.get_nws_alerts(
            location,
            self.nws_base_url,
            self.user_agent,
            self.timeout,
            self._get_http_client(),
            alert_radius_type=alert_radius_type,
        )

    async def _get_nws_hourly_forecast(self, location: Location) -> HourlyForecast | None:
        """Delegate to the NWS client module."""
        return await nws_client.get_nws_hourly_forecast(
            location, self.nws_base_url, self.user_agent, self.timeout, self._get_http_client()
        )

    async def _get_openmeteo_current_conditions(
        self, location: Location
    ) -> CurrentConditions | None:
        """Delegate to the Open-Meteo client module."""
        return await openmeteo_client.get_openmeteo_current_conditions(
            location, self.openmeteo_base_url, self.timeout, self._get_http_client()
        )

    async def _get_openmeteo_forecast(self, location: Location) -> Forecast | None:
        """Delegate to the Open-Meteo client module."""
        return await openmeteo_client.get_openmeteo_forecast(
            location,
            self.openmeteo_base_url,
            self.timeout,
            self._get_http_client(),
            days=self._get_forecast_days_for_source(location, source="openmeteo"),
        )

    def _get_forecast_days_for_source(self, location: Location, source: str) -> int:
        """
        Return configured forecast days with location/source caps.

        US locations are capped at 7 days to align with NWS limitations.
        Other sources are capped by their API limits.
        """
        configured = getattr(self.settings, "forecast_duration_days", 7)
        if not isinstance(configured, int):
            configured = 7
        configured = max(3, min(configured, 16))

        source_limits = {
            "openmeteo": 16,
            "pirateweather": 8,
            "nws": 7,
        }
        return min(configured, source_limits.get(source, 16))

    async def _get_openmeteo_hourly_forecast(self, location: Location) -> HourlyForecast | None:
        """Delegate to the Open-Meteo client module."""
        return await openmeteo_client.get_openmeteo_hourly_forecast(
            location,
            self.openmeteo_base_url,
            self.timeout,
            self._get_http_client(),
            hours=self._get_hourly_hours_for_pressure_outlook(),
        )

    def _get_hourly_hours_for_pressure_outlook(self) -> int:
        """Return enough hourly data for display and pressure trend windows."""
        hourly_hours = int(getattr(self.settings, "hourly_forecast_hours", 6) or 6)
        trend_hours = int(getattr(self.settings, "trend_hours", 24) or 24)
        return max(1, min(max(hourly_hours, trend_hours), 384))

    async def _augment_current_with_openmeteo(
        self,
        current: CurrentConditions | None,
        location: Location,
    ) -> CurrentConditions | None:
        """Fill missing current-condition fields using Open-Meteo data when available."""
        if current is not None and current.has_data():
            return current

        try:
            fallback = await self._get_openmeteo_current_conditions(location)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Open-Meteo current conditions fallback failed: %s", exc)
            return current

        if fallback is None:
            return current

        if current is None:
            logger.info(
                "Using Open-Meteo current conditions for %s due to missing NWS data", location.name
            )
            # Strip model-derived snow depth — Open-Meteo uses ERA5/GFS which is
            # notoriously inaccurate for snowpack. Only station observations are reliable.
            fallback.snow_depth_in = None  # pragma: no cover
            fallback.snow_depth_cm = None  # pragma: no cover
            return fallback

        logger.info(
            "Supplementing NWS current conditions with Open-Meteo data for %s", location.name
        )
        return parsers.merge_current_conditions(current, fallback)

    async def get_aviation_weather(
        self,
        station_id: str,
        *,
        include_sigmets: bool = False,
        atsu: str | None = None,
        include_cwas: bool = False,
        cwsu_id: str | None = None,
    ) -> AviationData:
        return await enrichment.get_aviation_weather(
            self,
            station_id,
            include_sigmets=include_sigmets,
            atsu=atsu,
            include_cwas=include_cwas,
            cwsu_id=cwsu_id,
        )
