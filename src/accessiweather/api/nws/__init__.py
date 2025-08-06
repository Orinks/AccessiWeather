"""NWS API wrapper package for AccessiWeather.

This package provides a modular NWS API wrapper that delegates operations
to specialized modules while maintaining backward compatibility.
"""

import logging
from typing import Any, Optional

from accessiweather.api.base_wrapper import BaseApiWrapper

from .alerts_discussions import NwsAlertsDiscussions
from .core_client import NwsCoreClient
from .point_location import NwsPointLocation
from .weather_data import NwsWeatherData

logger = logging.getLogger(__name__)


class NwsApiWrapper(BaseApiWrapper):
    """NWS-specific API wrapper that handles National Weather Service operations.

    This class delegates operations to specialized modules for better maintainability
    while preserving the exact same public interface for backward compatibility.
    """

    def __init__(self, **kwargs):
        """Initialize the NWS API wrapper.

        Args:
            **kwargs: Arguments passed to BaseApiWrapper

        """
        super().__init__(**kwargs)

        # Initialize specialized modules
        self.core_client = NwsCoreClient(self)
        self.point_location = NwsPointLocation(self)
        self.weather_data = NwsWeatherData(self)
        self.alerts_discussions = NwsAlertsDiscussions(self)

        logger.info("Initialized modular NWS API wrapper")

    # Expose BASE_URL for backward compatibility
    @property
    def BASE_URL(self) -> str:
        """Get the base URL for the NWS API."""
        return self.core_client.BASE_URL

    @property
    def client(self):
        """Get the HTTP client for backward compatibility."""
        return self.core_client.client

    def _make_api_request(self, module_func, **kwargs) -> Any:
        """Call a function from the generated NWS client modules and handle exceptions.

        Delegates to the core client module.
        """
        return self.core_client.make_api_request(module_func, **kwargs)

    # Point and location operations
    def get_point_data(self, lat: float, lon: float, force_refresh: bool = False) -> dict[str, Any]:
        """Get metadata about a specific lat/lon point."""
        return self.point_location.get_point_data(lat, lon, force_refresh)

    def _transform_point_data(self, point_data: Any) -> dict[str, Any]:
        """Transform point data from the generated client format."""
        return self.point_location._transform_point_data(point_data)

    def identify_location_type(
        self, lat: float, lon: float, force_refresh: bool = False
    ) -> tuple[str | None, str | None]:
        """Identify the type of location (county, state, etc.) for the given coordinates."""
        return self.point_location.identify_location_type(lat, lon, force_refresh)

    # Weather data operations
    def get_current_conditions(self, lat: float, lon: float, **kwargs) -> dict[str, Any]:
        """Get current weather conditions for a location from the nearest observation station."""
        return self.weather_data.get_current_conditions(lat, lon, **kwargs)

    def get_forecast(self, lat: float, lon: float, **kwargs) -> dict[str, Any]:
        """Get forecast for a location."""
        return self.weather_data.get_forecast(lat, lon, **kwargs)

    def get_hourly_forecast(self, lat: float, lon: float, **kwargs) -> dict[str, Any]:
        """Get hourly forecast for a location."""
        return self.weather_data.get_hourly_forecast(lat, lon, **kwargs)

    def get_stations(self, lat: float, lon: float, force_refresh: bool = False) -> dict[str, Any]:
        """Get observation stations for a location."""
        return self.weather_data.get_stations(lat, lon, force_refresh)

    def _transform_observation_data(self, observation_data: Any) -> dict[str, Any]:
        """Transform observation data from the generated client format."""
        return self.weather_data._transform_observation_data(observation_data)

    def _transform_forecast_data(self, forecast_data: Any) -> dict[str, Any]:
        """Transform forecast data from the generated client format."""
        return self.weather_data._transform_forecast_data(forecast_data)

    def _transform_stations_data(self, stations_data: Any) -> dict[str, Any]:
        """Transform stations data from the generated client format."""
        return self.weather_data._transform_stations_data(stations_data)

    # Alerts and discussions operations
    def get_alerts(
        self,
        lat: float,
        lon: float,
        radius: float = 50,
        precise_location: bool = True,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        """Get alerts for a location."""
        return self.alerts_discussions.get_alerts(lat, lon, radius, precise_location, force_refresh)

    def get_discussion(self, lat: float, lon: float, force_refresh: bool = False) -> str | None:
        """Get forecast discussion for a location."""
        return self.alerts_discussions.get_discussion(lat, lon, force_refresh)

    def get_national_product(
        self, product_type: str, location: str, force_refresh: bool = False
    ) -> str | None:
        """Get a national product from a specific center."""
        return self.alerts_discussions.get_national_product(product_type, location, force_refresh)

    def get_national_forecast_data(self, force_refresh: bool = False) -> dict[str, Any]:
        """Get national forecast data from various centers."""
        return self.alerts_discussions.get_national_forecast_data(force_refresh)

    def _transform_alerts_data(self, alerts_data: Any) -> dict[str, Any]:
        """Transform alerts data from the generated client format."""
        return self.alerts_discussions._transform_alerts_data(alerts_data)
