"""Wrapper for the OpenWeatherMap API client.

This module provides a wrapper for the OpenWeatherMap client that includes
caching, rate limiting, error handling, and data mapping to the format expected
by the AccessiWeather application.
"""

import hashlib
import json
import logging
import threading
import time
from typing import Any, Dict, List, Optional

from accessiweather.api_client import ApiClientError
from accessiweather.cache import Cache
from accessiweather.openweathermap_client import (
    AuthenticationError,
    NotFoundError,
    OpenWeatherMapClient,
    OpenWeatherMapError,
    RateLimitError,
    ValidationError,
)
from accessiweather.openweathermap_mapper import (
    map_alerts,
    map_current_conditions,
    map_forecast,
    map_hourly_forecast,
)

logger = logging.getLogger(__name__)


class OpenWeatherMapWrapper:
    """Wrapper for the OpenWeatherMap client that includes caching and rate limiting."""

    def __init__(
        self,
        api_key: str,
        user_agent: str = "AccessiWeather",
        enable_caching: bool = False,
        cache_ttl: int = 300,
        min_request_interval: float = 1.0,  # OpenWeatherMap free tier: 60 calls/minute
        max_retries: int = 3,
        retry_backoff: float = 2.0,
        retry_initial_wait: float = 5.0,
        units: str = "imperial",
        language: str = "en",
    ):
        """Initialize the OpenWeatherMap wrapper.

        Args:
            api_key: OpenWeatherMap API key
            user_agent: User agent string for API requests
            enable_caching: Whether to enable response caching
            cache_ttl: Cache time-to-live in seconds
            min_request_interval: Minimum interval between requests in seconds
            max_retries: Maximum number of retry attempts
            retry_backoff: Backoff multiplier for retries
            retry_initial_wait: Initial wait time for retries in seconds
            units: Units for temperature and other measurements
            language: Language for weather descriptions
        """
        self.api_key = api_key
        self.user_agent = user_agent
        self.enable_caching = enable_caching
        self.cache_ttl = cache_ttl
        self.min_request_interval = min_request_interval
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self.retry_initial_wait = retry_initial_wait

        # Initialize the client
        self.client = OpenWeatherMapClient(
            api_key=api_key,
            user_agent=user_agent,
            units=units,
            language=language,
        )

        # Initialize caching if enabled
        self.cache = Cache() if enable_caching else None

        # Initialize rate limiting
        self.last_request_time = 0.0
        self.request_lock = threading.Lock()

    def _rate_limit(self):
        """Implement rate limiting to respect API limits."""
        with self.request_lock:
            current_time = time.time()
            time_since_last_request = current_time - self.last_request_time
            
            if time_since_last_request < self.min_request_interval:
                sleep_time = self.min_request_interval - time_since_last_request
                logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
                time.sleep(sleep_time)
            
            self.last_request_time = time.time()

    def _get_cache_key(self, method: str, **kwargs) -> str:
        """Generate a cache key for the given method and parameters.

        Args:
            method: The method name
            **kwargs: Method parameters

        Returns:
            A unique cache key string
        """
        # Create a deterministic cache key from method and parameters
        key_data = {"method": method, "params": kwargs}
        key_string = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_string.encode()).hexdigest()

    def _cached_request(self, cache_key: str, request_func, *args, **kwargs):
        """Make a cached request if caching is enabled.

        Args:
            cache_key: Cache key for the request
            request_func: Function to call if cache miss
            *args: Arguments to pass to request_func
            **kwargs: Keyword arguments to pass to request_func

        Returns:
            The result of the request (from cache or fresh)
        """
        # Check cache first if enabled
        if self.cache:
            cached_result = self.cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for key: {cache_key}")
                return cached_result

        # Apply rate limiting
        self._rate_limit()

        # Make the request with retry logic
        result = self._make_request_with_retry(request_func, *args, **kwargs)

        # Cache the result if caching is enabled
        if self.cache:
            logger.debug(f"Caching result for key: {cache_key}")
            self.cache.set(cache_key, result, ttl=self.cache_ttl)

        return result

    def _make_request_with_retry(self, request_func, *args, **kwargs):
        """Make a request with retry logic.

        Args:
            request_func: Function to call
            *args: Arguments to pass to request_func
            **kwargs: Keyword arguments to pass to request_func

        Returns:
            The result of the request

        Raises:
            OpenWeatherMapError: If all retry attempts fail
        """
        last_exception = None
        wait_time = self.retry_initial_wait

        for attempt in range(self.max_retries + 1):
            try:
                return request_func(*args, **kwargs)
            except (AuthenticationError, ValidationError, NotFoundError):
                # Don't retry for these error types
                raise
            except (RateLimitError, OpenWeatherMapError) as e:
                last_exception = e
                
                if attempt < self.max_retries:
                    logger.warning(
                        f"Request failed (attempt {attempt + 1}/{self.max_retries + 1}): {str(e)}. "
                        f"Retrying in {wait_time} seconds..."
                    )
                    time.sleep(wait_time)
                    wait_time *= self.retry_backoff
                else:
                    logger.error(f"Request failed after {self.max_retries + 1} attempts: {str(e)}")
                    raise

        # This should never be reached, but just in case
        if last_exception:
            raise last_exception
        else:
            raise OpenWeatherMapError("Request failed for unknown reason")

    def get_current_conditions(
        self, lat: float, lon: float, force_refresh: bool = False
    ) -> Dict[str, Any]:
        """Get current weather conditions for a location.

        Args:
            lat: Latitude of the location
            lon: Longitude of the location
            force_refresh: Whether to force a refresh bypassing cache

        Returns:
            Dictionary containing current weather conditions in AccessiWeather format

        Raises:
            OpenWeatherMapError: If there was an error retrieving the data
        """
        cache_key = self._get_cache_key("current_conditions", lat=lat, lon=lon)
        
        if force_refresh and self.cache:
            logger.debug(f"Force refresh: invalidating cache for key {cache_key}")
            self.cache.invalidate(cache_key)

        def request_func():
            raw_data = self.client.get_current_weather(lat, lon)
            return map_current_conditions(raw_data)

        return self._cached_request(cache_key, request_func)

    def get_forecast(
        self, lat: float, lon: float, days: int = 7, force_refresh: bool = False
    ) -> Dict[str, Any]:
        """Get forecast data for a location.

        Args:
            lat: Latitude of the location
            lon: Longitude of the location
            days: Number of days to forecast (max 8 for One Call API)
            force_refresh: Whether to force a refresh bypassing cache

        Returns:
            Dictionary containing forecast data in AccessiWeather format

        Raises:
            OpenWeatherMapError: If there was an error retrieving the data
        """
        cache_key = self._get_cache_key("forecast", lat=lat, lon=lon, days=days)
        
        if force_refresh and self.cache:
            logger.debug(f"Force refresh: invalidating cache for key {cache_key}")
            self.cache.invalidate(cache_key)

        def request_func():
            # Use One Call API to get daily forecast
            raw_data = self.client.get_one_call_data(lat, lon, exclude="minutely")
            return map_forecast(raw_data, days)

        return self._cached_request(cache_key, request_func)

    def get_hourly_forecast(
        self, lat: float, lon: float, hours: int = 48, force_refresh: bool = False
    ) -> Dict[str, Any]:
        """Get hourly forecast data for a location.

        Args:
            lat: Latitude of the location
            lon: Longitude of the location
            hours: Number of hours to forecast (max 48 for One Call API)
            force_refresh: Whether to force a refresh bypassing cache

        Returns:
            Dictionary containing hourly forecast data in AccessiWeather format

        Raises:
            OpenWeatherMapError: If there was an error retrieving the data
        """
        cache_key = self._get_cache_key("hourly_forecast", lat=lat, lon=lon, hours=hours)

        if force_refresh and self.cache:
            logger.debug(f"Force refresh: invalidating cache for key {cache_key}")
            self.cache.invalidate(cache_key)

        def request_func():
            # Use One Call API to get hourly forecast
            raw_data = self.client.get_one_call_data(lat, lon, exclude="minutely,daily")
            return map_hourly_forecast(raw_data, hours)

        return self._cached_request(cache_key, request_func)

    def get_alerts(
        self, lat: float, lon: float, force_refresh: bool = False
    ) -> List[Dict[str, Any]]:
        """Get weather alerts for a location.

        Args:
            lat: Latitude of the location
            lon: Longitude of the location
            force_refresh: Whether to force a refresh bypassing cache

        Returns:
            List of dictionaries containing weather alerts in AccessiWeather format

        Raises:
            OpenWeatherMapError: If there was an error retrieving the data
        """
        cache_key = self._get_cache_key("alerts", lat=lat, lon=lon)

        if force_refresh and self.cache:
            logger.debug(f"Force refresh: invalidating cache for key {cache_key}")
            self.cache.invalidate(cache_key)

        def request_func():
            # Use One Call API to get alerts
            raw_data = self.client.get_one_call_data(lat, lon, exclude="minutely,hourly,daily,current")
            return map_alerts(raw_data)

        return self._cached_request(cache_key, request_func)

    def validate_api_key(self) -> bool:
        """Validate the API key by making a test request.

        Returns:
            True if the API key is valid, False otherwise
        """
        try:
            # Make a simple request to validate the key
            # Use London coordinates as a test location
            self.client.get_current_weather(51.5074, -0.1278)
            return True
        except AuthenticationError:
            return False
        except Exception as e:
            logger.warning(f"API key validation failed with unexpected error: {str(e)}")
            return False

    def clear_cache(self):
        """Clear all cached data."""
        if self.cache:
            logger.info("Clearing OpenWeatherMap cache")
            self.cache.clear()

    def get_cache_stats(self) -> Optional[Dict[str, Any]]:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics or None if caching is disabled
        """
        if self.cache:
            return {
                "enabled": True,
                "ttl": self.cache_ttl,
                "size": len(self.cache.data) if hasattr(self.cache, 'data') else 0,
            }
        return {"enabled": False}
