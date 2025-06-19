"""Provider coordinator for weather API operations.

This module provides the NoaaApiWrapper class that coordinates between different
weather API providers (NWS and Open-Meteo) while maintaining backward compatibility
with the original interface.
"""

import logging
from typing import Any, Dict, Optional

from accessiweather.api.nws import NwsApiWrapper
from accessiweather.api.openmeteo_wrapper import OpenMeteoApiWrapper
from accessiweather.api_client import ApiClientError, NoaaApiError

logger = logging.getLogger(__name__)


class NoaaApiWrapper:
    """Provider coordinator for weather API operations.

    This class coordinates between different weather API providers (NWS and Open-Meteo)
    while maintaining backward compatibility with the original NoaaApiWrapper interface.
    """

    def __init__(
        self,
        user_agent: str = "AccessiWeather",
        contact_info: Optional[str] = None,
        enable_caching: bool = False,
        cache_ttl: int = 300,
        min_request_interval: float = 0.5,
        max_retries: int = 3,
        retry_backoff: float = 2.0,
        retry_initial_wait: float = 5.0,
        preferred_provider: str = "auto",
    ):
        """Initialize the weather API coordinator.

        Args:
            user_agent: User agent string for API requests
            contact_info: Optional contact information for API identification
            enable_caching: Whether to enable caching of API responses
            cache_ttl: Time-to-live for cached responses in seconds
            min_request_interval: Minimum interval between requests in seconds
            max_retries: Maximum number of retries for rate-limited requests
            retry_backoff: Multiplier for exponential backoff between retries
            retry_initial_wait: Initial wait time after a rate limit error
            preferred_provider: Preferred weather provider ("nws", "openmeteo", "auto")
        """
        self.user_agent = user_agent
        self.contact_info = contact_info or user_agent
        self.preferred_provider = preferred_provider

        # Common configuration for all providers
        provider_config = {
            "user_agent": user_agent,
            "contact_info": self.contact_info,
            "enable_caching": enable_caching,
            "cache_ttl": cache_ttl,
            "min_request_interval": min_request_interval,
            "max_retries": max_retries,
            "retry_backoff": retry_backoff,
            "retry_initial_wait": retry_initial_wait,
        }

        # Initialize provider wrappers
        self.nws_wrapper = NwsApiWrapper(**provider_config)
        self.openmeteo_wrapper = OpenMeteoApiWrapper(**provider_config)

        logger.info(
            f"Initialized weather API coordinator with preferred provider: {preferred_provider}"
        )
        logger.info(f"Available providers: NWS, Open-Meteo")

    def _select_provider(self, lat: float, lon: float) -> str:
        """Select the appropriate weather provider based on location and configuration.

        Args:
            lat: Latitude
            lon: Longitude

        Returns:
            Provider name ("nws" or "openmeteo")
        """
        if self.preferred_provider == "nws":
            return "nws"
        elif self.preferred_provider == "openmeteo":
            return "openmeteo"
        elif self.preferred_provider == "auto":
            # Auto-selection logic: Use NWS for US locations, Open-Meteo for international
            # US boundaries (approximate): lat 24-49, lon -125 to -66
            if 24.0 <= lat <= 49.0 and -125.0 <= lon <= -66.0:
                logger.debug(f"Auto-selected NWS for US location: ({lat}, {lon})")
                return "nws"
            else:
                logger.debug(f"Auto-selected Open-Meteo for international location: ({lat}, {lon})")
                return "openmeteo"
        else:
            logger.warning(
                f"Unknown preferred provider '{self.preferred_provider}', defaulting to NWS"
            )
            return "nws"

    def _get_provider_wrapper(self, provider: str):
        """Get the wrapper instance for the specified provider.

        Args:
            provider: Provider name ("nws" or "openmeteo")

        Returns:
            Provider wrapper instance
        """
        if provider == "nws":
            return self.nws_wrapper
        elif provider == "openmeteo":
            return self.openmeteo_wrapper
        else:
            raise ValueError(f"Unknown provider: {provider}")

    def _execute_with_fallback(
        self, method_name: str, lat: float, lon: float, **kwargs
    ) -> Dict[str, Any]:
        """Execute a method with provider fallback logic.

        Args:
            method_name: Name of the method to call
            lat: Latitude
            lon: Longitude
            **kwargs: Additional arguments for the method

        Returns:
            Result from the successful provider
        """
        primary_provider = self._select_provider(lat, lon)
        fallback_provider = "openmeteo" if primary_provider == "nws" else "nws"

        # Try primary provider first
        try:
            wrapper = self._get_provider_wrapper(primary_provider)
            method = getattr(wrapper, method_name)
            logger.debug(f"Calling {method_name} on {primary_provider} provider")
            return method(lat, lon, **kwargs)
        except Exception as e:
            logger.warning(f"Primary provider {primary_provider} failed for {method_name}: {e}")

            # Try fallback provider
            try:
                wrapper = self._get_provider_wrapper(fallback_provider)
                method = getattr(wrapper, method_name)
                logger.info(f"Falling back to {fallback_provider} provider for {method_name}")
                return method(lat, lon, **kwargs)
            except Exception as fallback_error:
                logger.error(
                    f"Fallback provider {fallback_provider} also failed for {method_name}: {fallback_error}"
                )
                # Re-raise the original error from the primary provider
                raise e

    # Core weather data methods - delegate to appropriate provider
    def get_current_conditions(self, lat: float, lon: float, **kwargs) -> Dict[str, Any]:
        """Get current weather conditions for a location.

        Args:
            lat: Latitude
            lon: Longitude
            **kwargs: Additional arguments (force_refresh, etc.)

        Returns:
            Current weather conditions data
        """
        return self._execute_with_fallback("get_current_conditions", lat, lon, **kwargs)

    def get_forecast(self, lat: float, lon: float, **kwargs) -> Dict[str, Any]:
        """Get forecast for a location.

        Args:
            lat: Latitude
            lon: Longitude
            **kwargs: Additional arguments (force_refresh, etc.)

        Returns:
            Forecast data
        """
        return self._execute_with_fallback("get_forecast", lat, lon, **kwargs)

    def get_hourly_forecast(self, lat: float, lon: float, **kwargs) -> Dict[str, Any]:
        """Get hourly forecast for a location.

        Args:
            lat: Latitude
            lon: Longitude
            **kwargs: Additional arguments (force_refresh, etc.)

        Returns:
            Hourly forecast data
        """
        return self._execute_with_fallback("get_hourly_forecast", lat, lon, **kwargs)

    # NWS-specific methods - delegate to NWS wrapper
    def get_point_data(self, lat: float, lon: float, force_refresh: bool = False) -> Dict[str, Any]:
        """Get metadata about a specific lat/lon point (NWS-specific)."""
        return self.nws_wrapper.get_point_data(lat, lon, force_refresh=force_refresh)

    def get_stations(self, lat: float, lon: float, force_refresh: bool = False) -> Dict[str, Any]:
        """Get observation stations for a location (NWS-specific)."""
        return self.nws_wrapper.get_stations(lat, lon, force_refresh=force_refresh)

    def get_alerts(
        self,
        lat: float,
        lon: float,
        radius: float = 50,
        precise_location: bool = True,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """Get alerts for a location (NWS-specific)."""
        return self.nws_wrapper.get_alerts(
            lat, lon, radius=radius, precise_location=precise_location, force_refresh=force_refresh
        )

    def get_discussion(self, lat: float, lon: float, force_refresh: bool = False) -> Optional[str]:
        """Get forecast discussion for a location (NWS-specific)."""
        return self.nws_wrapper.get_discussion(lat, lon, force_refresh=force_refresh)

    def get_national_product(
        self, product_type: str, location: str, force_refresh: bool = False
    ) -> Optional[str]:
        """Get a national product from a specific center (NWS-specific)."""
        return self.nws_wrapper.get_national_product(
            product_type, location, force_refresh=force_refresh
        )

    def get_national_forecast_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Get national forecast data from various centers (NWS-specific)."""
        return self.nws_wrapper.get_national_forecast_data(force_refresh=force_refresh)

    def identify_location_type(
        self, lat: float, lon: float, force_refresh: bool = False
    ) -> tuple[Optional[str], Optional[str]]:
        """Identify the type of location for the given coordinates (NWS-specific)."""
        return self.nws_wrapper.identify_location_type(lat, lon, force_refresh=force_refresh)

    # Open-Meteo specific methods - delegate to Open-Meteo wrapper
    def get_weather_description(self, weather_code: int) -> str:
        """Get weather description from Open-Meteo weather code."""
        return self.openmeteo_wrapper.get_weather_description(weather_code)

    # Provider management methods
    def get_active_provider(self, lat: float, lon: float) -> str:
        """Get the active provider that would be used for the given location."""
        return self._select_provider(lat, lon)

    def set_preferred_provider(self, provider: str) -> None:
        """Set the preferred provider.

        Args:
            provider: Provider name ("nws", "openmeteo", "auto")
        """
        if provider not in ["nws", "openmeteo", "auto"]:
            raise ValueError(f"Invalid provider: {provider}. Must be 'nws', 'openmeteo', or 'auto'")

        self.preferred_provider = provider
        logger.info(f"Preferred provider set to: {provider}")

    def get_provider_status(self) -> Dict[str, Any]:
        """Get status information about available providers."""
        return {
            "preferred_provider": self.preferred_provider,
            "available_providers": ["nws", "openmeteo"],
            "nws_wrapper": "initialized",
            "openmeteo_wrapper": "initialized",
        }
