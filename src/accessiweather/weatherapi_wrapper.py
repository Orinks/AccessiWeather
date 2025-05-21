"""Wrapper for the WeatherAPI.com client.

This module provides a wrapper for the WeatherAPI.com client that includes
caching, rate limiting, error handling, and data mapping to the format expected
by the AccessiWeather application.
"""

import hashlib
import json
import logging
import threading
import time
from typing import Any, Dict, List, Optional, cast

import httpx

from accessiweather.api_client import ApiClientError
from accessiweather.cache import Cache
from accessiweather.weatherapi_client.client import WeatherApiClient
from accessiweather.weatherapi_mapper import (
    map_alerts,
    map_current_conditions,
    map_forecast,
    map_hourly_forecast,
    map_location,
)

logger = logging.getLogger(__name__)


class WeatherApiError(ApiClientError):
    """Custom exception for WeatherAPI.com errors."""

    # Error types
    UNKNOWN_ERROR = "unknown_error"
    INVALID_REQUEST = "invalid_request"
    API_KEY_INVALID = "api_key_invalid"
    QUOTA_EXCEEDED = "quota_exceeded"
    NOT_FOUND = "not_found"
    VALIDATION_ERROR = "validation_error"
    MAPPING_ERROR = "mapping_error"
    CONNECTION_ERROR = "connection_error"
    TIMEOUT_ERROR = "timeout_error"
    SERVER_ERROR = "server_error"

    # Error codes from WeatherAPI.com
    ERROR_CODES = {
        1002: "API key not provided",
        1003: "Parameter 'q' not provided",
        1005: "API request URL invalid",
        1006: "Location not found",
        2006: "API key provided is invalid",
        2007: "API key has exceeded calls per month quota",
        2008: "API key has been disabled",
        9999: "Internal application error",
    }

    def __init__(
        self,
        message: str,
        error_type: str = UNKNOWN_ERROR,
        url: Optional[str] = None,
        error_code: Optional[int] = None,
        response: Optional[Dict[str, Any]] = None,
    ):
        """Initialize the WeatherApiError.

        Args:
            message: Error message
            error_type: Type of error
            url: URL that caused the error
            error_code: Error code from the API
            response: Raw API response if available
        """
        super().__init__(message)
        self.error_type = error_type
        self.url = url
        self.error_code = error_code
        self.response = response

    @classmethod
    def from_api_error(
        cls, error_json: Dict[str, Any], url: Optional[str] = None
    ) -> "WeatherApiError":
        """Create an error instance from the API error response.

        Args:
            error_json: Error JSON from the API
            url: URL that caused the error

        Returns:
            WeatherApiError instance
        """
        error_code = error_json.get("error", {}).get("code")
        error_message = error_json.get("error", {}).get("message", "Unknown API error")

        # Map error code to error type
        error_type = cls.UNKNOWN_ERROR
        if error_code == 1006:
            error_type = cls.NOT_FOUND
        elif error_code in (2006, 2008):
            error_type = cls.API_KEY_INVALID
        elif error_code == 2007:
            error_type = cls.QUOTA_EXCEEDED
        elif error_code in (1002, 1003, 1005):
            error_type = cls.INVALID_REQUEST
        elif error_code == 9999:
            error_type = cls.SERVER_ERROR

        return cls(
            message=f"API Error {error_code}: {error_message}",
            error_type=error_type,
            url=url,
            error_code=error_code,
            response=error_json,
        )


class WeatherApiWrapper:
    """Wrapper for the WeatherAPI.com client that includes caching and rate limiting."""

    def __init__(
        self,
        api_key: str,
        user_agent: str = "AccessiWeather",
        enable_caching: bool = False,
        cache_ttl: int = 300,
        min_request_interval: float = 0.5,
        max_retries: int = 3,
        retry_backoff: float = 2.0,
        retry_initial_wait: float = 5.0,
    ):
        """Initialize the WeatherAPI.com wrapper.

        Args:
            api_key: WeatherAPI.com API key
            user_agent: User agent string for API requests
            enable_caching: Whether to enable caching of API responses
            cache_ttl: Time-to-live for cached responses in seconds (default: 5 minutes)
            min_request_interval: Minimum interval between requests in seconds (default: 0.5)
            max_retries: Maximum number of retries for rate-limited requests (default: 3)
            retry_backoff: Multiplier for exponential backoff between retries (default: 2.0)
            retry_initial_wait: Initial wait time in seconds after a rate limit error (default: 5.0)
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
        self.client = WeatherApiClient(
            api_key=api_key,
            user_agent=user_agent,
        )

        # Initialize caching if enabled
        self.cache = Cache() if enable_caching else None

        # Initialize rate limiting
        self.last_request_time = 0.0
        self.request_lock = threading.Lock()

    def _rate_limit(self) -> None:
        """Apply rate limiting to API requests.

        This method ensures that requests are not made too frequently.
        """
        with self.request_lock:
            # Calculate time since last request
            current_time = time.time()
            time_since_last_request = current_time - self.last_request_time

            # If we've made a request recently, wait until the minimum interval has passed
            if time_since_last_request < self.min_request_interval:
                sleep_time = self.min_request_interval - time_since_last_request
                logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
                time.sleep(sleep_time)

            # Update the last request time
            self.last_request_time = time.time()

    def _get_cache_key(self, endpoint: str, params: Dict[str, Any]) -> str:
        """Generate a cache key for the request.

        Args:
            endpoint: API endpoint
            params: Request parameters

        Returns:
            Cache key as a string
        """
        # Create a string representation of the request
        param_str = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        request_str = f"{endpoint}?{param_str}"

        # Hash the string to create a cache key
        return hashlib.md5(request_str.encode()).hexdigest()

    def _validate_response(self, endpoint: str, response: Dict[str, Any]) -> None:
        """Validate the response structure based on the endpoint.

        Args:
            endpoint: API endpoint
            response: Response data

        Raises:
            WeatherApiError: If the response structure is invalid
        """
        # Construct the URL for error reporting
        base_url = self.client.BASE_URL
        url = f"{base_url}/{endpoint}"

        # Validate based on endpoint
        if endpoint == "current.json":
            if "location" not in response:
                raise WeatherApiError(
                    message="Invalid response: missing 'location' field",
                    error_type=WeatherApiError.VALIDATION_ERROR,
                    url=url,
                )
            if "current" not in response:
                raise WeatherApiError(
                    message="Invalid response: missing 'current' field",
                    error_type=WeatherApiError.VALIDATION_ERROR,
                    url=url,
                )

        elif endpoint == "forecast.json":
            if "location" not in response:
                raise WeatherApiError(
                    message="Invalid response: missing 'location' field",
                    error_type=WeatherApiError.VALIDATION_ERROR,
                    url=url,
                )
            if "current" not in response:
                raise WeatherApiError(
                    message="Invalid response: missing 'current' field",
                    error_type=WeatherApiError.VALIDATION_ERROR,
                    url=url,
                )
            if "forecast" not in response:
                raise WeatherApiError(
                    message="Invalid response: missing 'forecast' field",
                    error_type=WeatherApiError.VALIDATION_ERROR,
                    url=url,
                )
            if "forecastday" not in response.get("forecast", {}):
                raise WeatherApiError(
                    message="Invalid response: missing 'forecast.forecastday' field",
                    error_type=WeatherApiError.VALIDATION_ERROR,
                    url=url,
                )

        elif endpoint == "search.json":
            if not isinstance(response, list):
                raise WeatherApiError(
                    message="Invalid response: expected a list of locations",
                    error_type=WeatherApiError.VALIDATION_ERROR,
                    url=url,
                )

    def _make_request(
        self, endpoint: str, params: Dict[str, Any], force_refresh: bool = False
    ) -> Dict[str, Any]:
        """Make a request to the WeatherAPI.com API with caching and rate limiting.

        Args:
            endpoint: API endpoint
            params: Request parameters
            force_refresh: Whether to force a refresh of cached data

        Returns:
            Dict containing the response data

        Raises:
            WeatherApiError: If an error occurs during the API request
        """
        # Check cache if enabled and not forcing a refresh
        if self.cache and not force_refresh:
            cache_key = self._get_cache_key(endpoint, params)
            cached_data = self.cache.get(cache_key)
            if cached_data:
                logger.debug(f"Cache hit for {endpoint}")
                return cast(Dict[str, Any], cached_data)

        # Apply rate limiting
        self._rate_limit()

        # Construct the URL for error reporting
        base_url = self.client.BASE_URL
        url = f"{base_url}/{endpoint}"

        # Make the request with retries
        retry_count = 0
        wait_time = self.retry_initial_wait

        while retry_count <= self.max_retries:
            try:
                response = self.client._request_sync(endpoint, params)

                # Check if the response contains an error
                if "error" in response:
                    # Use the from_api_error class method to create a proper error
                    raise WeatherApiError.from_api_error(response, url)

                # Validate the response structure based on the endpoint
                self._validate_response(endpoint, response)

                # Cache the response if caching is enabled
                if self.cache:
                    cache_key = self._get_cache_key(endpoint, params)
                    self.cache.set(cache_key, response, self.cache_ttl)

                return response

            except WeatherApiError as e:
                # Don't retry for certain error types
                if e.error_type in (
                    WeatherApiError.API_KEY_INVALID,
                    WeatherApiError.INVALID_REQUEST,
                    WeatherApiError.NOT_FOUND,
                    WeatherApiError.VALIDATION_ERROR,
                ):
                    logger.error(f"Non-retryable error: {str(e)}")
                    raise

                # For quota exceeded, only retry once with a longer wait
                if e.error_type == WeatherApiError.QUOTA_EXCEEDED and retry_count > 0:
                    logger.error(f"Quota exceeded and retry limit reached: {str(e)}")
                    raise

                # For other errors, retry with backoff
                if retry_count < self.max_retries:
                    logger.warning(
                        f"API request failed (attempt {retry_count + 1}/{self.max_retries + 1}): {str(e)}. "
                        f"Retrying in {wait_time} seconds..."
                    )
                    time.sleep(wait_time)
                    wait_time *= self.retry_backoff
                    retry_count += 1
                else:
                    logger.error(
                        f"API request failed after {self.max_retries + 1} attempts: {str(e)}"
                    )
                    raise

            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON response from {url}: {str(e)}")
                raise WeatherApiError(
                    message=f"Invalid JSON response: {str(e)}",
                    error_type=WeatherApiError.VALIDATION_ERROR,
                    url=url,
                )

            except httpx.ConnectError as e:
                if retry_count < self.max_retries:
                    logger.warning(
                        f"Connection error (attempt {retry_count + 1}/{self.max_retries + 1}): {str(e)}. "
                        f"Retrying in {wait_time} seconds..."
                    )
                    time.sleep(wait_time)
                    wait_time *= self.retry_backoff
                    retry_count += 1
                else:
                    logger.error(
                        f"Connection error after {self.max_retries + 1} attempts: {str(e)}"
                    )
                    raise WeatherApiError(
                        message=f"Connection error: {str(e)}",
                        error_type=WeatherApiError.CONNECTION_ERROR,
                        url=url,
                    )

            except httpx.ReadTimeout as e:
                if retry_count < self.max_retries:
                    logger.warning(
                        f"Timeout error (attempt {retry_count + 1}/{self.max_retries + 1}): {str(e)}. "
                        f"Retrying in {wait_time} seconds..."
                    )
                    time.sleep(wait_time)
                    wait_time *= self.retry_backoff
                    retry_count += 1
                else:
                    logger.error(f"Timeout error after {self.max_retries + 1} attempts: {str(e)}")
                    raise WeatherApiError(
                        message=f"Timeout error: {str(e)}",
                        error_type=WeatherApiError.TIMEOUT_ERROR,
                        url=url,
                    )

            except Exception as e:
                logger.error(f"Unexpected error making request to {url}: {str(e)}")
                raise WeatherApiError(
                    message=f"Unexpected error: {str(e)}",
                    error_type=WeatherApiError.UNKNOWN_ERROR,
                    url=url,
                )

        # If we've exhausted all retries and haven't returned or raised an exception
        raise WeatherApiError(
            message="Failed to get a valid response after all retries",
            error_type=WeatherApiError.UNKNOWN_ERROR,
            url=url,
        )

    def _format_location_for_api(self, location) -> str:
        """Format location for WeatherAPI.com API.

        WeatherAPI.com accepts various formats:
        - Latitude/longitude as a tuple (lat, lon) or string "lat,lon"
        - City name (e.g., "London")
        - ZIP code (e.g., "10001")
        - IP address (e.g., "192.168.1.1" or "auto:ip")

        Args:
            location: Location in various formats (tuple, string, etc.)

        Returns:
            String formatted for WeatherAPI.com API
        """
        if isinstance(location, tuple) and len(location) == 2:
            # Lat/Lon tuple
            return f"{location[0]},{location[1]}"
        elif isinstance(location, (int, float)):
            # Likely a ZIP code as a number
            return str(location)
        else:
            # String (city name, ZIP code as string, or already formatted lat,lon)
            return str(location)

    def get_current_conditions(self, location, force_refresh: bool = False) -> Dict[str, Any]:
        """Get current weather conditions for a location.

        Args:
            location: Location identifier (lat/lon tuple, city name, ZIP code)
            force_refresh: Whether to force a refresh of cached data

        Returns:
            Dict containing current weather conditions mapped to internal format
        """
        # For backward compatibility
        if isinstance(location, (int, float)) and isinstance(force_refresh, (int, float)):
            # Old signature: (lat, lon, force_refresh)
            lat, lon = location, force_refresh
            force_refresh = False
            location = f"{lat},{lon}"  # Use string format instead of tuple
            logger.info(f"Using deprecated signature with coordinates: ({lat}, {lon})")

        formatted_location = self._format_location_for_api(location)
        logger.info(f"Getting current conditions for location: {formatted_location}")

        try:
            response = self._make_request("current.json", {"q": formatted_location}, force_refresh)
            return map_current_conditions(response)
        except Exception as e:
            logger.error(f"Error getting current conditions: {str(e)}")
            raise

    def get_forecast(
        self,
        location,
        days: int = 1,
        aqi: bool = False,
        alerts: bool = False,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """Get weather forecast for a location.

        Args:
            location: Location identifier (lat/lon tuple, city name, ZIP code)
                     or separate lat, lon parameters
            days: Number of days of forecast (1-14)
            aqi: Include air quality data
            alerts: Include weather alerts
            force_refresh: Whether to force a refresh of cached data

        Returns:
            Dict containing forecast weather data mapped to internal format
        """
        # For backward compatibility
        if (
            isinstance(location, (int, float))
            and isinstance(days, (int, float))
            and not isinstance(days, bool)
        ):
            # Old signature: (lat, lon, days, aqi, alerts, force_refresh)
            lat, lon = location, days
            days = aqi if isinstance(aqi, int) else 1
            aqi = alerts if isinstance(alerts, bool) else False
            alerts = force_refresh if isinstance(force_refresh, bool) else False
            force_refresh = False
            location = f"{lat},{lon}"  # Use string format instead of tuple
            logger.info(f"Using deprecated signature with coordinates: ({lat}, {lon})")

        formatted_location = self._format_location_for_api(location)
        logger.info(f"Getting forecast for location: {formatted_location}")

        params = {
            "q": formatted_location,
            "days": days,
            "aqi": "yes" if aqi else "no",
            "alerts": "yes" if alerts else "no",
        }

        try:
            response = self._make_request("forecast.json", params, force_refresh)

            # Create a result dictionary with mapped data
            result = {
                "forecast": map_forecast(response),
                "location": map_location(response),
            }

            # Add hourly forecast if available
            hourly = map_hourly_forecast(response)
            if hourly:
                result["hourly"] = hourly

            # Add alerts if requested and available
            if alerts:
                result["alerts"] = map_alerts(response)

            return result
        except Exception as e:
            logger.error(f"Error getting forecast: {str(e)}")
            raise

    def get_hourly_forecast(
        self,
        location,
        days: int = 1,
        force_refresh: bool = False,
    ) -> List[Dict[str, Any]]:
        """Get hourly weather forecast for a location.

        Args:
            location: Location identifier (lat/lon tuple, city name, ZIP code)
            days: Number of days of hourly forecast (1-14)
            force_refresh: Whether to force a refresh of cached data

        Returns:
            List of dicts containing hourly forecast data mapped to internal format
        """
        # For backward compatibility
        if (
            isinstance(location, (int, float))
            and isinstance(days, (int, float))
            and not isinstance(days, bool)
        ):
            # Old signature: (lat, lon, days, force_refresh)
            lat, lon = location, days
            days = force_refresh if isinstance(force_refresh, int) else 1
            force_refresh = False
            location = f"{lat},{lon}"  # Use string format instead of tuple
            logger.info(f"Using deprecated signature with coordinates: ({lat}, {lon})")

        formatted_location = self._format_location_for_api(location)
        logger.info(f"Getting hourly forecast for location: {formatted_location}")

        params = {
            "q": formatted_location,
            "days": days,
            "aqi": "no",
            "alerts": "no",
        }

        try:
            response = self._make_request("forecast.json", params, force_refresh)
            return map_hourly_forecast(response)
        except Exception as e:
            logger.error(f"Error getting hourly forecast: {str(e)}")
            raise

    def get_alerts(
        self,
        lat: float,
        lon: float,
        force_refresh: bool = False,
    ) -> List[Dict[str, Any]]:
        """Get weather alerts for a location.

        Args:
            lat: Latitude
            lon: Longitude
            force_refresh: Whether to force a refresh of cached data

        Returns:
            List of dicts containing weather alerts mapped to internal format
        """
        logger.info(f"Getting weather alerts for coordinates: ({lat}, {lon})")
        location = f"{lat},{lon}"

        params = {
            "q": location,
            "days": 1,  # Minimum required
            "aqi": "no",
            "alerts": "yes",
        }

        try:
            response = self._make_request("forecast.json", params, force_refresh)
            return map_alerts(response)
        except Exception as e:
            logger.error(f"Error getting weather alerts: {str(e)}")
            raise

    def search_locations(self, query: str) -> Dict[str, Any]:
        """Search for locations.

        Args:
            query: Search query (city name, ZIP code, etc.)

        Returns:
            Dict containing search results
        """
        logger.info(f"Searching for locations matching: {query}")
        formatted_query = self._format_location_for_api(query)

        try:
            return self._make_request("search.json", {"q": formatted_query}, force_refresh=True)
        except Exception as e:
            logger.error(f"Error searching for locations: {str(e)}")
            raise
