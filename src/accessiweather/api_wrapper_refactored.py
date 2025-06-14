"""Refactored wrapper for the generated NWS API client.

This module provides a wrapper for the generated NWS API client that preserves
the functionality of the original NoaaApiClient, including caching, rate limiting,
and error handling. The implementation has been refactored into smaller, focused modules.
"""

import logging
from typing import Any, Dict, Optional, Tuple

import httpx

# Import the refactored modules
from accessiweather.api.alert_fetchers import ApiAlertFetchers
from accessiweather.api.data_transformers import ApiDataTransformers
from accessiweather.api.location_services import ApiLocationServices
from accessiweather.api.product_services import ApiProductServices
from accessiweather.api.request_manager import ApiRequestManager
from accessiweather.api.weather_fetchers import ApiWeatherFetchers
from accessiweather.cache import Cache
from accessiweather.weather_gov_api_client.client import Client

logger = logging.getLogger(__name__)


class NoaaApiWrapper:
    """Wrapper for the generated NWS API client that preserves the functionality of NoaaApiClient."""

    BASE_URL = "https://api.weather.gov"

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
    ):
        """Initialize the NOAA API wrapper.

        Args:
            user_agent: User agent string for API requests
            contact_info: Optional contact information (website or email)
                          for API identification. If None, uses the app name.
            enable_caching: Whether to enable caching of API responses
            cache_ttl: Time-to-live for cached responses in seconds (default: 5 minutes)
            min_request_interval: Minimum interval between requests in seconds (default: 0.5)
            max_retries: Maximum number of retries for rate-limited requests (default: 3)
            retry_backoff: Multiplier for exponential backoff between retries (default: 2.0)
            retry_initial_wait: Initial wait time in seconds after a rate limit error (default: 5.0)
        """
        self.user_agent = user_agent
        # Use app name as default contact info if none provided
        self.contact_info = contact_info or user_agent

        # Build user agent string according to NOAA API recommendations
        user_agent_string = f"{user_agent} ({self.contact_info})"

        # Initialize the generated client
        self.client = Client(
            base_url=self.BASE_URL,
            headers={"User-Agent": user_agent_string, "Accept": "application/geo+json"},
            timeout=httpx.Timeout(10.0),  # 10 seconds timeout
            follow_redirects=True,
        )

        # Initialize cache if enabled
        cache = Cache(default_ttl=cache_ttl) if enable_caching else None

        # Initialize the request manager
        self.request_manager = ApiRequestManager(
            client=self.client,
            base_url=self.BASE_URL,
            user_agent=user_agent_string,
            cache=cache,
            min_request_interval=min_request_interval,
            max_retries=max_retries,
            retry_backoff=retry_backoff,
            retry_initial_wait=retry_initial_wait,
        )

        # Initialize data transformers
        self.data_transformers = ApiDataTransformers()

        # Initialize location services
        self.location_services = ApiLocationServices(
            request_manager=self.request_manager,
            data_transformers=self.data_transformers,
            base_url=self.BASE_URL,
        )

        # Initialize weather fetchers
        self.weather_fetchers = ApiWeatherFetchers(
            request_manager=self.request_manager,
            data_transformers=self.data_transformers,
            location_services=self.location_services,
            base_url=self.BASE_URL,
        )

        # Initialize alert fetchers
        self.alert_fetchers = ApiAlertFetchers(
            request_manager=self.request_manager,
            data_transformers=self.data_transformers,
            location_services=self.location_services,
            base_url=self.BASE_URL,
        )

        # Initialize product services
        self.product_services = ApiProductServices(
            request_manager=self.request_manager,
            location_services=self.location_services,
            base_url=self.BASE_URL,
        )

        logger.info(f"Initialized NOAA API wrapper with User-Agent: {user_agent_string}")
        logger.info(
            f"Rate limiting: {min_request_interval}s between requests, "
            f"max {max_retries} retries with {retry_backoff}x backoff"
        )
        if enable_caching:
            logger.info(f"Caching enabled with TTL of {cache_ttl} seconds")

    # Delegate methods to the appropriate service modules

    def get_point_data(self, lat: float, lon: float, force_refresh: bool = False) -> Dict[str, Any]:
        """Get metadata about a specific lat/lon point."""
        return self.location_services.get_point_data(lat, lon, force_refresh)

    def identify_location_type(
        self, lat: float, lon: float, force_refresh: bool = False
    ) -> Tuple[Optional[str], Optional[str]]:
        """Identify the type of location (county, state, etc.) for the given coordinates."""
        return self.location_services.identify_location_type(lat, lon, force_refresh)

    def get_stations(self, lat: float, lon: float, force_refresh: bool = False) -> Dict[str, Any]:
        """Get observation stations for a location."""
        return self.location_services.get_stations(lat, lon, force_refresh)

    def get_forecast(self, lat: float, lon: float, force_refresh: bool = False) -> Dict[str, Any]:
        """Get forecast for a location."""
        return self.weather_fetchers.get_forecast(lat, lon, force_refresh)

    def get_hourly_forecast(
        self, lat: float, lon: float, force_refresh: bool = False
    ) -> Dict[str, Any]:
        """Get hourly forecast for a location."""
        return self.weather_fetchers.get_hourly_forecast(lat, lon, force_refresh)

    def get_current_conditions(
        self, lat: float, lon: float, force_refresh: bool = False
    ) -> Dict[str, Any]:
        """Get current weather conditions for a location from the nearest observation station."""
        return self.weather_fetchers.get_current_conditions(lat, lon, force_refresh)

    def get_alerts(
        self,
        lat: float,
        lon: float,
        radius: float = 50,
        precise_location: bool = True,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """Get alerts for a location."""
        return self.alert_fetchers.get_alerts(lat, lon, radius, precise_location, force_refresh)

    def get_alerts_direct(self, url: str, force_refresh: bool = False) -> Dict[str, Any]:
        """Get active weather alerts directly from a provided URL."""
        return self.alert_fetchers.get_alerts_direct(url, force_refresh)

    def get_discussion(self, lat: float, lon: float, force_refresh: bool = False) -> Optional[str]:
        """Get forecast discussion for a location."""
        return self.product_services.get_discussion(lat, lon, force_refresh)

    def get_national_product(
        self, product_type: str, location: str, force_refresh: bool = False
    ) -> Optional[str]:
        """Get a national product from a specific center."""
        return self.product_services.get_national_product(product_type, location, force_refresh)

    def get_national_forecast_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Get national forecast data from various centers."""
        return self.product_services.get_national_forecast_data(force_refresh)

    # Legacy methods for backward compatibility (delegate to request manager)
    def _generate_cache_key(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> str:
        """Generate a cache key for the given endpoint and parameters."""
        return self.request_manager.generate_cache_key(endpoint, params)

    def _rate_limit(self) -> None:
        """Apply rate limiting to avoid overwhelming the API."""
        self.request_manager.rate_limit()

    def _fetch_url(self, url: str) -> Dict[str, Any]:
        """Fetch data from a URL."""
        return self.request_manager.fetch_url(url)

    def _handle_rate_limit(self, url: str, retry_count: int = 0) -> None:
        """Handle rate limit errors with exponential backoff."""
        self.request_manager.handle_rate_limit(url, retry_count)

    def _get_cached_or_fetch(
        self,
        cache_key: str,
        fetch_func: Any,
        force_refresh: bool = False,
    ) -> Any:
        """Get data from cache or fetch it if not available."""
        return self.request_manager.get_cached_or_fetch(cache_key, fetch_func, force_refresh)

    def _make_api_request(self, module_func: Any, **kwargs) -> Any:
        """Call a function from the generated client modules and handle exceptions."""
        return self.request_manager.make_api_request(module_func, **kwargs)

    def _handle_client_error(self, error: Exception, url: str, retry_count: int = 0) -> Any:
        """Map client errors to NoaaApiError types."""
        return self.request_manager.handle_client_error(error, url, retry_count)

    # Data transformation methods (delegate to data transformers)
    def _transform_point_data(self, point_data: Any) -> Dict[str, Any]:
        """Transform point data from the generated client format."""
        return self.data_transformers.transform_point_data(point_data)

    def _transform_forecast_data(self, forecast_data: Any) -> Dict[str, Any]:
        """Transform forecast data from the generated client format."""
        return self.data_transformers.transform_forecast_data(forecast_data)

    def _transform_stations_data(self, stations_data: Any) -> Dict[str, Any]:
        """Transform stations data from the generated client format."""
        return self.data_transformers.transform_stations_data(stations_data)

    def _transform_observation_data(self, observation_data: Any) -> Dict[str, Any]:
        """Transform observation data from the generated client format."""
        return self.data_transformers.transform_observation_data(observation_data)

    def _transform_alerts_data(self, alerts_data: Any) -> Dict[str, Any]:
        """Transform alerts data from the generated client format."""
        return self.data_transformers.transform_alerts_data(alerts_data)
