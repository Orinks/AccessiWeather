"""Wrapper for the generated NWS API client.

This module provides a wrapper for the generated NWS API client that preserves
the functionality of the original NoaaApiClient, including caching, rate limiting,
and error handling.
"""

import hashlib
import logging
import threading
import time
from typing import Any, Callable, Dict, Optional, cast

import httpx

from accessiweather.api_client import ApiClientError, NoaaApiError
from accessiweather.cache import Cache
from accessiweather.weather_gov_api_client.api.default import (
    alerts_active,
    alerts_active_zone,
    point,
    station_observation_latest,
)
from accessiweather.weather_gov_api_client.client import Client
from accessiweather.weather_gov_api_client.errors import UnexpectedStatus

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
                          for API identification
            enable_caching: Whether to enable caching of API responses
            cache_ttl: Time-to-live for cached responses in seconds (default: 5 minutes)
            min_request_interval: Minimum interval between requests in seconds (default: 0.5)
            max_retries: Maximum number of retries for rate-limited requests (default: 3)
            retry_backoff: Multiplier for exponential backoff between retries (default: 2.0)
            retry_initial_wait: Initial wait time in seconds after a rate limit error (default: 5.0)
        """
        self.user_agent = user_agent
        self.contact_info = contact_info

        # Build user agent string according to NOAA API recommendations
        if contact_info:
            user_agent_string = f"{user_agent} ({contact_info})"
        else:
            user_agent_string = user_agent

        # Initialize the generated client
        self.client = Client(
            base_url=self.BASE_URL,
            headers={"User-Agent": user_agent_string, "Accept": "application/geo+json"},
            timeout=httpx.Timeout(10.0),  # 10 seconds timeout
            follow_redirects=True,
        )

        # Add request tracking for rate limiting
        self.last_request_time: float = 0.0
        self.min_request_interval: float = min_request_interval
        self.max_retries: int = max_retries
        self.retry_backoff: float = retry_backoff
        self.retry_initial_wait: float = retry_initial_wait

        # Add thread lock for thread safety
        self.request_lock = threading.RLock()

        # Initialize cache if enabled
        self.cache = Cache(default_ttl=cache_ttl) if enable_caching else None

        logger.info(f"Initialized NOAA API wrapper with User-Agent: {user_agent_string}")
        logger.info(
            f"Rate limiting: {self.min_request_interval}s between requests, "
            f"max {self.max_retries} retries with {self.retry_backoff}x backoff"
        )
        if enable_caching:
            logger.info(f"Caching enabled with TTL of {cache_ttl} seconds")

    def _generate_cache_key(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> str:
        """Generate a cache key for the given endpoint and parameters.

        Args:
            endpoint: The API endpoint
            params: Optional parameters for the request

        Returns:
            A cache key string
        """
        # Create a unique key based on the endpoint and parameters
        key_parts = [endpoint]
        if params:
            # Sort params to ensure consistent keys
            sorted_params = sorted(params.items())
            key_parts.extend([f"{k}={v}" for k, v in sorted_params])

        # Create a hash of the key parts
        key_string = "|".join(key_parts)
        return hashlib.md5(key_string.encode(), usedforsecurity=False).hexdigest()

    def _rate_limit(self) -> None:
        """Apply rate limiting to avoid overwhelming the API.

        This method ensures that requests are spaced at least min_request_interval
        seconds apart to comply with the NWS API rate limits.
        """
        with self.request_lock:
            if self.last_request_time is not None:
                elapsed = time.time() - self.last_request_time
                sleep_time = max(0, self.min_request_interval - elapsed)
                if sleep_time > 0:
                    logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f}s")
                    time.sleep(sleep_time)
            self.last_request_time = time.time()

    def _fetch_url(self, url: str) -> Dict[str, Any]:
        """Fetch data from a URL.

        Args:
            url: The URL to fetch

        Returns:
            Dict containing the response data
        """
        self._rate_limit()
        try:
            # Create a request with the appropriate headers
            headers = {"User-Agent": self.user_agent, "Accept": "application/geo+json"}
            response = httpx.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            return cast(Dict[str, Any], response.json())
        except Exception as e:
            logger.error(f"Error fetching URL {url}: {str(e)}")
            raise ApiClientError(f"Error fetching URL {url}: {str(e)}")

    def _handle_rate_limit(self, url: str, retry_count: int = 0) -> None:
        """Handle rate limit errors with exponential backoff.

        Args:
            url: The URL that triggered the rate limit
            retry_count: Current retry attempt (0-based)

        Raises:
            NoaaApiError: If max retries are exceeded
        """
        if retry_count >= self.max_retries:
            error_msg = (
                f"Rate limit exceeded for {url} after {self.max_retries} retries. "
                f"Please try again later."
            )
            logger.error(error_msg)
            raise NoaaApiError(message=error_msg, error_type=NoaaApiError.RATE_LIMIT_ERROR, url=url)

        # Calculate backoff delay with exponential increase
        wait_time = self.retry_initial_wait * (self.retry_backoff**retry_count)

        logger.warning(
            f"Rate limit exceeded for {url}. "
            f"Retrying in {wait_time:.1f}s (attempt {retry_count + 1}/{self.max_retries})"
        )

        # Sleep with the lock released to allow other threads to proceed
        with self.request_lock:
            self.last_request_time = time.time() + wait_time

        time.sleep(wait_time)

    def _get_cached_or_fetch(
        self,
        cache_key: str,
        fetch_func: Callable[[], Any],
        force_refresh: bool = False,
    ) -> Any:
        """Get data from cache or fetch it if not available.

        Args:
            cache_key: Cache key for the data
            fetch_func: Function to call to fetch the data if not in cache
            force_refresh: Whether to force a refresh of the data

        Returns:
            The data from cache or freshly fetched
        """
        # If caching is disabled or force refresh is requested, fetch directly
        if self.cache is None or force_refresh:
            return fetch_func()

        # Try to get from cache
        cached_data = self.cache.get(cache_key)
        if cached_data is not None:
            logger.debug(f"Using cached data for {cache_key}")
            return cached_data

        # Fetch and cache
        data = fetch_func()
        self.cache.set(cache_key, data)
        return data

    def _make_api_request(self, module_func: Callable, **kwargs) -> Any:
        """Call a function from the generated client modules and handle exceptions.

        Args:
            module_func: Function from the generated client modules (e.g., point.sync)
            **kwargs: Keyword arguments to pass to the function

        Returns:
            The result of the function call

        Raises:
            NoaaApiError: If an error occurs during the API request
        """
        # Always add the client to kwargs
        kwargs["client"] = self.client

        try:
            # Call the function
            return module_func(**kwargs)
        except UnexpectedStatus as e:
            # Map UnexpectedStatus to NoaaApiError
            status_code = e.status_code
            url = kwargs.get("url", self.BASE_URL)

            if status_code == 404:
                error_msg = f"Resource not found: {e}"
                logger.warning(error_msg)
                raise NoaaApiError(
                    message=error_msg,
                    status_code=status_code,
                    error_type=NoaaApiError.CLIENT_ERROR,
                    url=url,
                )
            elif status_code == 429:
                error_msg = f"Rate limit exceeded: {e}"
                logger.warning(error_msg)
                # For tests, we need to include the exact phrase "Rate limit exceeded" in the message
                raise NoaaApiError(
                    message=f"Rate limit exceeded: {e}",
                    status_code=status_code,
                    error_type=NoaaApiError.RATE_LIMIT_ERROR,
                    url=url,
                )
            elif 400 <= status_code < 500:
                error_msg = f"Client error ({status_code}): {e}"
                logger.error(error_msg)
                raise NoaaApiError(
                    message=error_msg,
                    status_code=status_code,
                    error_type=NoaaApiError.CLIENT_ERROR,
                    url=url,
                )
            elif 500 <= status_code < 600:
                error_msg = f"Server error ({status_code}): {e}"
                logger.error(error_msg)
                # For tests, we need to include the exact phrase "Server error" in the message
                raise NoaaApiError(
                    message=f"Server error ({status_code}): {e}",
                    status_code=status_code,
                    error_type=NoaaApiError.SERVER_ERROR,
                    url=url,
                )
            else:
                error_msg = f"Unexpected status code ({status_code}): {e}"
                logger.error(error_msg)
                raise NoaaApiError(
                    message=error_msg,
                    status_code=status_code,
                    error_type=NoaaApiError.UNKNOWN_ERROR,
                    url=url,
                )
        except httpx.TimeoutException as e:
            url = kwargs.get("url", self.BASE_URL)
            error_msg = f"Request timed out: {e}"
            logger.error(error_msg)
            raise NoaaApiError(message=error_msg, error_type=NoaaApiError.TIMEOUT_ERROR, url=url)
        except httpx.ConnectError as e:
            url = kwargs.get("url", self.BASE_URL)
            error_msg = f"Connection error: {e}"
            logger.error(error_msg)
            raise NoaaApiError(message=error_msg, error_type=NoaaApiError.CONNECTION_ERROR, url=url)
        except httpx.RequestError as e:
            url = kwargs.get("url", self.BASE_URL)
            error_msg = f"Network error: {e}"
            logger.error(error_msg)
            raise NoaaApiError(message=error_msg, error_type=NoaaApiError.NETWORK_ERROR, url=url)
        except Exception as e:
            url = kwargs.get("url", self.BASE_URL)
            error_msg = f"Unexpected error: {e}"
            logger.error(error_msg, exc_info=True)
            raise NoaaApiError(message=error_msg, error_type=NoaaApiError.UNKNOWN_ERROR, url=url)

    def _handle_client_error(
        self, error: Exception, url: str, retry_count: int = 0
    ) -> NoaaApiError:
        """Map client errors to NoaaApiError types.

        Args:
            error: The original error
            url: The URL that caused the error
            retry_count: Current retry attempt (0-based)

        Returns:
            A NoaaApiError instance

        Note:
            This method will handle rate limiting (HTTP 429) errors by implementing
            exponential backoff and retrying the request if retry_count is less than
            max_retries.
        """
        if isinstance(error, UnexpectedStatus):
            status_code = error.status_code

            if status_code == 429:
                # Handle rate limiting with exponential backoff
                try:
                    self._handle_rate_limit(url, retry_count)
                    # If _handle_rate_limit doesn't raise an exception, it means
                    # we should retry the request, so we return a special error type
                    return NoaaApiError(
                        message="Rate limit retry",
                        status_code=status_code,
                        error_type="retry",  # Special error type to indicate retry
                        url=url,
                    )
                except NoaaApiError as rate_error:
                    # If _handle_rate_limit raises an exception, it means we've
                    # exceeded max retries, so we return that error
                    return rate_error
            elif 400 <= status_code < 500:
                error_type = NoaaApiError.CLIENT_ERROR
                error_msg = f"Client error ({status_code}): {error}"
            elif 500 <= status_code < 600:
                error_type = NoaaApiError.SERVER_ERROR
                error_msg = f"Server error ({status_code}): {error}"
            else:
                error_type = NoaaApiError.UNKNOWN_ERROR
                error_msg = f"Unexpected status code ({status_code}): {error}"

            return NoaaApiError(
                message=error_msg, status_code=status_code, error_type=error_type, url=url
            )
        elif isinstance(error, httpx.TimeoutException):
            error_msg = f"Request timed out during API request to {url}: {error}"
            return NoaaApiError(message=error_msg, error_type=NoaaApiError.TIMEOUT_ERROR, url=url)
        elif isinstance(error, httpx.ConnectError):
            error_msg = f"Connection error during API request to {url}: {error}"
            return NoaaApiError(
                message=error_msg, error_type=NoaaApiError.CONNECTION_ERROR, url=url
            )
        elif isinstance(error, httpx.RequestError):
            error_msg = f"Network error during API request to {url}: {error}"
            return NoaaApiError(message=error_msg, error_type=NoaaApiError.NETWORK_ERROR, url=url)
        else:
            error_msg = f"Unexpected error during API request to {url}: {error}"
            return NoaaApiError(message=error_msg, error_type=NoaaApiError.UNKNOWN_ERROR, url=url)

    def get_point_data(self, lat: float, lon: float, force_refresh: bool = False) -> Dict[str, Any]:
        """Get metadata about a specific lat/lon point.

        Args:
            lat: Latitude
            lon: Longitude
            force_refresh: Whether to force a refresh of the data

        Returns:
            Dict containing point metadata
        """
        endpoint = f"points/{lat},{lon}"
        cache_key = self._generate_cache_key(endpoint)
        logger.info(f"Fetching point data for coordinates: ({lat}, {lon})")

        def fetch_data() -> Dict[str, Any]:
            self._rate_limit()
            try:
                point_str = f"{lat},{lon}"
                # Use the new _make_api_request method to handle errors consistently
                response = self._make_api_request(point.sync, point=point_str)
                # Transform the response to match the format expected by the application
                return self._transform_point_data(response)
            except NoaaApiError:
                # Re-raise NoaaApiErrors directly
                raise
            except Exception as e:
                # For any other exceptions, wrap them in a NoaaApiError
                logger.error(f"Error getting point data for {lat},{lon}: {str(e)}")
                url = f"{self.BASE_URL}/{endpoint}"
                error_msg = f"Unexpected error getting point data: {e}"
                raise NoaaApiError(
                    message=error_msg, error_type=NoaaApiError.UNKNOWN_ERROR, url=url
                )

        return cast(Dict[str, Any], self._get_cached_or_fetch(cache_key, fetch_data, force_refresh))

    # _fetch_url is already defined above, so we'll remove this duplicate

    def _transform_point_data(self, point_data: Any) -> Dict[str, Any]:
        """Transform point data from the generated client format to the format expected by WeatherService.

        Args:
            point_data: Point data from the generated client

        Returns:
            Transformed point data
        """
        # Extract and transform the data to match the format expected by the application
        # Handle both dictionary and object access
        if isinstance(point_data, dict):
            properties = point_data.get("properties", {})
            transformed = {
                "properties": {
                    "forecast": properties.get("forecast"),
                    "forecastHourly": properties.get("forecastHourly"),
                    "forecastGridData": properties.get("forecastGridData"),
                    "observationStations": properties.get("observationStations"),
                    "county": properties.get("county"),
                    "fireWeatherZone": properties.get("fireWeatherZone"),
                    "timeZone": properties.get("timeZone"),
                    "radarStation": properties.get("radarStation"),
                }
            }
        else:
            # Assume it's an object with properties attribute
            properties_obj = getattr(point_data, "properties", None)
            if properties_obj:
                if hasattr(properties_obj, "additional_properties"):
                    properties = properties_obj.additional_properties
                else:
                    properties = {}
                    for attr in [
                        "forecast",
                        "forecast_hourly",
                        "forecast_grid_data",
                        "observation_stations",
                        "county",
                        "fire_weather_zone",
                        "time_zone",
                        "radar_station",
                    ]:
                        if hasattr(properties_obj, attr):
                            properties[attr] = getattr(properties_obj, attr)

                transformed = {
                    "properties": {
                        "forecast": properties.get("forecast"),
                        "forecastHourly": properties.get("forecastHourly")
                        or properties.get("forecast_hourly"),
                        "forecastGridData": properties.get("forecastGridData")
                        or properties.get("forecast_grid_data"),
                        "observationStations": properties.get("observationStations")
                        or properties.get("observation_stations"),
                        "county": properties.get("county"),
                        "fireWeatherZone": properties.get("fireWeatherZone")
                        or properties.get("fire_weather_zone"),
                        "timeZone": properties.get("timeZone") or properties.get("time_zone"),
                        "radarStation": properties.get("radarStation")
                        or properties.get("radar_station"),
                    }
                }
            else:
                # Fallback to empty structure
                transformed = {"properties": {}}

        return transformed

    def get_forecast(self, lat: float, lon: float, force_refresh: bool = False) -> Dict[str, Any]:
        """Get forecast for a location.

        Args:
            lat: Latitude
            lon: Longitude
            force_refresh: Whether to force a refresh of the data

        Returns:
            Dict containing forecast data
        """
        # First get the forecast URL from the point data
        try:
            logger.info(f"Getting forecast for coordinates: ({lat}, {lon})")
            point_data = self.get_point_data(lat, lon, force_refresh=force_refresh)

            # Debug log the point data structure
            logger.debug(f"Point data structure keys: {list(point_data.keys())}")

            forecast_url = point_data.get("properties", {}).get("forecast")

            if not forecast_url:
                props = list(point_data.get("properties", {}).keys())
                logger.error(
                    "Could not find forecast URL in point data. " f"Available properties: {props}"
                )
                # Keep this specific ValueError for this context
                raise ValueError("Could not find forecast URL in point data")

            # Extract the forecast office ID and grid coordinates from the URL
            # Example URL: https://api.weather.gov/gridpoints/PHI/31,70/forecast
            parts = forecast_url.split("/")
            office_id = parts[-3]
            grid_x, grid_y = parts[-2].split(",")

            # Generate cache key for the forecast
            cache_key = self._generate_cache_key(
                f"gridpoints/{office_id}/{grid_x},{grid_y}/forecast"
            )

            def fetch_data() -> Dict[str, Any]:
                self._rate_limit()
                try:
                    # Use direct URL fetch instead of gridpoint.sync to get formatted forecast data
                    response = self._fetch_url(forecast_url)
                    # Transform the response to match the format expected by the application
                    return self._transform_forecast_data(response)
                except NoaaApiError:
                    # Re-raise NoaaApiErrors directly
                    raise
                except Exception as e:
                    # For any other exceptions, wrap them in a NoaaApiError
                    logger.error(f"Error getting forecast for {lat},{lon}: {str(e)}")
                    error_msg = f"Unexpected error getting forecast: {e}"
                    raise NoaaApiError(
                        message=error_msg, error_type=NoaaApiError.UNKNOWN_ERROR, url=forecast_url
                    )

            return cast(
                Dict[str, Any], self._get_cached_or_fetch(cache_key, fetch_data, force_refresh)
            )
        except NoaaApiError:
            # Re-raise NoaaApiErrors directly
            raise
        except Exception as e:
            logger.error(f"Error getting forecast: {str(e)}")
            raise ApiClientError(f"Unable to retrieve forecast data: {str(e)}")

    def _transform_forecast_data(self, forecast_data: Any) -> Dict[str, Any]:
        """Transform forecast data from the generated client format to the format expected by WeatherService.

        Args:
            forecast_data: Forecast data from the generated client

        Returns:
            Transformed forecast data
        """
        # Convert the forecast data to a dict
        if hasattr(forecast_data, "to_dict"):
            return cast(Dict[str, Any], forecast_data.to_dict())
        return cast(Dict[str, Any], forecast_data)

    def get_hourly_forecast(
        self, lat: float, lon: float, force_refresh: bool = False
    ) -> Dict[str, Any]:
        """Get hourly forecast for a location.

        Args:
            lat: Latitude
            lon: Longitude
            force_refresh: Whether to force a refresh of the data

        Returns:
            Dict containing hourly forecast data
        """
        # First get the forecast URL from the point data
        try:
            logger.info(f"Getting hourly forecast for coordinates: ({lat}, {lon})")
            point_data = self.get_point_data(lat, lon, force_refresh=force_refresh)

            forecast_hourly_url = point_data.get("properties", {}).get("forecastHourly")

            if not forecast_hourly_url:
                props = list(point_data.get("properties", {}).keys())
                logger.error(
                    "Could not find hourly forecast URL in point data. "
                    f"Available properties: {props}"
                )
                raise ValueError("Could not find hourly forecast URL in point data")

            # Extract the forecast office ID and grid coordinates from the URL
            # Example URL: https://api.weather.gov/gridpoints/PHI/31,70/forecast/hourly
            parts = forecast_hourly_url.split("/")
            office_id = parts[-4]
            grid_x, grid_y = parts[-3].split(",")

            # Generate cache key for the hourly forecast
            cache_key = self._generate_cache_key(
                f"gridpoints/{office_id}/{grid_x},{grid_y}/forecast/hourly"
            )

            def fetch_data() -> Dict[str, Any]:
                self._rate_limit()
                try:
                    # Use direct URL fetch instead of gridpoint.sync to get formatted hourly forecast data
                    response = self._fetch_url(forecast_hourly_url)
                    # Transform the response to match the format expected by the application
                    return self._transform_forecast_data(response)
                except NoaaApiError:
                    # Re-raise NoaaApiErrors directly
                    raise
                except Exception as e:
                    # For any other exceptions, wrap them in a NoaaApiError
                    logger.error(f"Error getting hourly forecast for {lat},{lon}: {str(e)}")
                    error_msg = f"Unexpected error getting hourly forecast: {e}"
                    raise NoaaApiError(
                        message=error_msg,
                        error_type=NoaaApiError.UNKNOWN_ERROR,
                        url=forecast_hourly_url,
                    )

            return cast(
                Dict[str, Any], self._get_cached_or_fetch(cache_key, fetch_data, force_refresh)
            )
        except Exception as e:
            logger.error(f"Error getting hourly forecast: {str(e)}")
            raise ApiClientError(f"Unable to retrieve hourly forecast data: {str(e)}")

    def get_stations(self, lat: float, lon: float, force_refresh: bool = False) -> Dict[str, Any]:
        """Get observation stations for a location.

        Args:
            lat: Latitude
            lon: Longitude
            force_refresh: Whether to force a refresh of the data

        Returns:
            Dict containing observation stations data
        """
        try:
            logger.info(f"Getting observation stations for coordinates: ({lat}, {lon})")
            point_data = self.get_point_data(lat, lon, force_refresh=force_refresh)

            stations_url = point_data.get("properties", {}).get("observationStations")

            if not stations_url:
                props = list(point_data.get("properties", {}).keys())
                logger.error(
                    "Could not find observation stations URL in point data. "
                    f"Available properties: {props}"
                )
                raise ValueError("Could not find observation stations URL in point data")

            # Generate cache key for the stations
            cache_key = self._generate_cache_key(stations_url)

            def fetch_data() -> Dict[str, Any]:
                self._rate_limit()
                try:
                    # Use direct API call instead of the generated client
                    response = self._fetch_url(stations_url)
                    # Transform the response to match the format expected by the application
                    return self._transform_stations_data(response)
                except Exception as e:
                    logger.error(f"Error getting stations for {lat},{lon}: {str(e)}")
                    raise self._handle_client_error(e, stations_url)

            logger.info(f"Retrieved observation stations URL: {stations_url}")
            return cast(
                Dict[str, Any], self._get_cached_or_fetch(cache_key, fetch_data, force_refresh)
            )
        except Exception as e:
            logger.error(f"Error getting observation stations: {str(e)}")
            raise ApiClientError(f"Unable to retrieve observation stations data: {str(e)}")

    def _transform_stations_data(self, stations_data: Any) -> Dict[str, Any]:
        """Transform stations data from the generated client format to the format expected by WeatherService.

        Args:
            stations_data: Stations data from the generated client

        Returns:
            Transformed stations data
        """
        # If it's already a dict, return it
        if isinstance(stations_data, dict):
            return stations_data
        # Otherwise, convert it to a dict if possible
        if hasattr(stations_data, "to_dict"):
            return cast(Dict[str, Any], stations_data.to_dict())
        return cast(Dict[str, Any], stations_data)

    def get_current_conditions(
        self, lat: float, lon: float, force_refresh: bool = False
    ) -> Dict[str, Any]:
        """Get current weather conditions for a location from the nearest observation station.

        Args:
            lat: Latitude
            lon: Longitude
            force_refresh: Whether to force a refresh of the data

        Returns:
            Dict containing current weather conditions
        """
        try:
            logger.info(f"Getting current conditions for coordinates: ({lat}, {lon})")

            # Get the observation stations
            stations_data = self.get_stations(lat, lon, force_refresh=force_refresh)

            if "features" not in stations_data or not stations_data["features"]:
                logger.error("No observation stations found")
                raise ValueError("No observation stations found")

            # Get the first station (nearest)
            station = stations_data["features"][0]
            station_id = station["properties"]["stationIdentifier"]

            logger.info(f"Using station {station_id} for current conditions")

            # Generate cache key for the current conditions
            cache_key = self._generate_cache_key(f"stations/{station_id}/observations/latest")

            def fetch_data() -> Dict[str, Any]:
                self._rate_limit()
                try:
                    # Use the new _make_api_request method to handle errors consistently
                    response = self._make_api_request(
                        station_observation_latest.sync, station_id=station_id
                    )
                    # Transform the response to match the format expected by the application
                    return self._transform_observation_data(response)
                except NoaaApiError:
                    # Re-raise NoaaApiErrors directly
                    raise
                except Exception as e:
                    # For any other exceptions, wrap them in a NoaaApiError
                    logger.error(
                        f"Error getting current conditions for station {station_id}: {str(e)}"
                    )
                    url = f"{self.BASE_URL}/stations/{station_id}/observations/latest"
                    error_msg = f"Unexpected error getting current conditions: {e}"
                    raise NoaaApiError(
                        message=error_msg, error_type=NoaaApiError.UNKNOWN_ERROR, url=url
                    )

            return cast(
                Dict[str, Any], self._get_cached_or_fetch(cache_key, fetch_data, force_refresh)
            )
        except Exception as e:
            logger.error(f"Error getting current conditions: {str(e)}")
            raise ApiClientError(f"Unable to retrieve current conditions data: {str(e)}")

    def _transform_observation_data(self, observation_data: Any) -> Dict[str, Any]:
        """Transform observation data from the generated client format to the format expected by WeatherService.

        Args:
            observation_data: Observation data from the generated client

        Returns:
            Transformed observation data
        """
        # If it's already a dict, return it
        if isinstance(observation_data, dict):
            return observation_data
        # Otherwise, convert it to a dict if possible
        if hasattr(observation_data, "to_dict"):
            return cast(Dict[str, Any], observation_data.to_dict())
        return cast(Dict[str, Any], observation_data)

    def identify_location_type(
        self, lat: float, lon: float, force_refresh: bool = False
    ) -> tuple[Optional[str], Optional[str]]:
        """Identify the type of location (county, state, etc.) for the given coordinates.

        Args:
            lat: Latitude of the location
            lon: Longitude of the location
            force_refresh: Whether to force a refresh of the data from the API
                instead of using cache

        Returns:
            Tuple of (location_type, location_id) where location_type is one of
            'county', 'forecast', 'fire', or None if the type cannot be determined.
            location_id is the UGC code for the location or None.
        """
        try:
            # Get point data for the coordinates
            point_data = self.get_point_data(lat, lon, force_refresh=force_refresh)
            properties = point_data.get("properties", {})

            # Check for county zone
            county_url = properties.get("county")
            if county_url and isinstance(county_url, str) and "/county/" in county_url:
                # Extract county code (format: .../zones/county/XXC###)
                county_id = county_url.split("/county/")[1]
                logger.info(f"Identified location as county: {county_id}")
                return "county", county_id

            # Check for forecast zone
            forecast_zone_url = properties.get("forecastZone")
            if (
                forecast_zone_url
                and isinstance(forecast_zone_url, str)
                and "/forecast/" in forecast_zone_url
            ):
                # Extract forecast zone code (format: .../zones/forecast/XXZ###)
                forecast_id = forecast_zone_url.split("/forecast/")[1]
                logger.info(f"Identified location as forecast zone: {forecast_id}")
                return "forecast", forecast_id

            # Check for fire weather zone
            fire_zone_url = properties.get("fireWeatherZone")
            if fire_zone_url and isinstance(fire_zone_url, str) and "/fire/" in fire_zone_url:
                # Extract fire zone code (format: .../zones/fire/XXZ###)
                fire_id = fire_zone_url.split("/fire/")[1]
                logger.info(f"Identified location as fire zone: {fire_id}")
                return "fire", fire_id

            # If we can't determine a specific zone, try to get the state
            try:
                state = properties.get("relativeLocation", {}).get("properties", {}).get("state")
                if state:
                    logger.info(f"Could only identify location at state level: {state}")
                    return "state", state
            except (KeyError, TypeError):
                pass

            logger.warning(f"Could not identify location type for coordinates: ({lat}, {lon})")
            return None, None

        except Exception as e:
            logger.error(f"Error identifying location type: {str(e)}")
            return None, None

    def get_alerts(
        self,
        lat: float,
        lon: float,
        radius: float = 50,
        precise_location: bool = True,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """Get alerts for a location.

        Args:
            lat: Latitude
            lon: Longitude
            radius: Radius in miles to search for alerts
            precise_location: Whether to get alerts for the precise location (county/zone)
                             or for the entire state
            force_refresh: Whether to force a refresh of the data

        Returns:
            Dictionary containing alert data
        """
        try:
            logger.info(
                f"Getting alerts for coordinates: ({lat}, {lon}) with radius {radius} miles, "
                f"precise_location={precise_location}, force_refresh={force_refresh}"
            )

            # Identify the location type
            location_type, location_id = self.identify_location_type(
                lat, lon, force_refresh=force_refresh
            )

            if precise_location and location_type in ("county", "forecast", "fire") and location_id:
                # Get alerts for the specific zone
                logger.info(f"Fetching alerts for {location_type} zone: {location_id}")
                cache_key = self._generate_cache_key("alerts_zone", {"zone_id": location_id})

                def fetch_data() -> Dict[str, Any]:
                    self._rate_limit()
                    try:
                        # Use the new _make_api_request method to handle errors consistently
                        response = self._make_api_request(
                            alerts_active_zone.sync, zone_id=location_id
                        )
                        # Transform the response to match the format expected by the application
                        return self._transform_alerts_data(response)
                    except NoaaApiError:
                        # Re-raise NoaaApiErrors directly
                        raise
                    except Exception as e:
                        # For any other exceptions, wrap them in a NoaaApiError
                        logger.error(f"Error getting alerts for zone {location_id}: {str(e)}")
                        url = f"{self.BASE_URL}/alerts/active/zone/{location_id}"
                        error_msg = f"Unexpected error getting alerts for zone: {e}"
                        raise NoaaApiError(
                            message=error_msg, error_type=NoaaApiError.UNKNOWN_ERROR, url=url
                        )

                return cast(
                    Dict[str, Any], self._get_cached_or_fetch(cache_key, fetch_data, force_refresh)
                )

            # If we have a state but not precise location, get state alerts
            if not precise_location and location_type == "state" and location_id:
                logger.info(f"Fetching alerts for state: {location_id}")
                cache_key = self._generate_cache_key("alerts_state", {"state": location_id})

                def fetch_data() -> Dict[str, Any]:
                    self._rate_limit()
                    try:
                        # Use _fetch_url for state-based alerts
                        url = f"{self.BASE_URL}/alerts/active?area={location_id}"
                        response = self._fetch_url(url)
                        return self._transform_alerts_data(response)
                    except Exception as e:
                        logger.error(f"Error getting alerts for state {location_id}: {str(e)}")
                        error_msg = f"Unexpected error getting alerts for state: {e}"
                        raise NoaaApiError(
                            message=error_msg, error_type=NoaaApiError.UNKNOWN_ERROR, url=url
                        )

                return cast(
                    Dict[str, Any], self._get_cached_or_fetch(cache_key, fetch_data, force_refresh)
                )

            # If we couldn't determine location or state, fall back to point-radius search
            if location_type is None or location_id is None:
                logger.info(
                    "Using point-radius search for alerts since location could not "
                    f"be determined: ({lat}, {lon}) with radius {radius} miles"
                )
                cache_key = self._generate_cache_key(
                    "alerts_point", {"lat": lat, "lon": lon, "radius": radius}
                )

                def fetch_data() -> Dict[str, Any]:
                    self._rate_limit()
                    try:
                        # Use _fetch_url for point-radius alerts
                        url = f"{self.BASE_URL}/alerts/active?point={lat},{lon}&radius={radius}"
                        response = self._fetch_url(url)
                        return self._transform_alerts_data(response)
                    except Exception as e:
                        logger.error(f"Error getting alerts for point ({lat}, {lon}): {str(e)}")
                        error_msg = f"Unexpected error getting alerts for point: {e}"
                        raise NoaaApiError(
                            message=error_msg, error_type=NoaaApiError.UNKNOWN_ERROR, url=url
                        )

                return cast(
                    Dict[str, Any], self._get_cached_or_fetch(cache_key, fetch_data, force_refresh)
                )

            # Final fallback: get all active alerts
            logger.info("Falling back to all active alerts")
            cache_key = self._generate_cache_key("alerts_all", {})

            def fetch_data() -> Dict[str, Any]:
                self._rate_limit()
                try:
                    # Use the new _make_api_request method to handle errors consistently
                    response = self._make_api_request(alerts_active.sync)
                    # Transform the response to match the format expected by the application
                    return self._transform_alerts_data(response)
                except NoaaApiError:
                    # Re-raise NoaaApiErrors directly
                    raise
                except Exception as e:
                    # For any other exceptions, wrap them in a NoaaApiError
                    logger.error(f"Error getting all alerts: {str(e)}")
                    url = f"{self.BASE_URL}/alerts/active"
                    error_msg = f"Unexpected error getting all alerts: {e}"
                    raise NoaaApiError(
                        message=error_msg, error_type=NoaaApiError.UNKNOWN_ERROR, url=url
                    )

            return cast(
                Dict[str, Any], self._get_cached_or_fetch(cache_key, fetch_data, force_refresh)
            )
        except Exception as e:
            logger.error(f"Error getting alerts: {str(e)}")
            raise ApiClientError(f"Unable to retrieve alerts data: {str(e)}")

    def _transform_alerts_data(self, alerts_data: Any) -> Dict[str, Any]:
        """Transform alerts data from the generated client format to the format expected by WeatherService.

        Args:
            alerts_data: Alerts data from the generated client

        Returns:
            Transformed alerts data
        """
        # If it's already a dict, return it
        if isinstance(alerts_data, dict):
            return alerts_data
        # Otherwise, convert it to a dict if possible
        if hasattr(alerts_data, "to_dict"):
            return cast(Dict[str, Any], alerts_data.to_dict())
        return cast(Dict[str, Any], alerts_data)

    def get_alerts_direct(self, url: str, force_refresh: bool = False) -> Dict[str, Any]:
        """Get active weather alerts directly from a provided URL.

        Args:
            url: Full URL to the alerts endpoint
            force_refresh: Whether to force a refresh of the data

        Returns:
            Dictionary containing alert data
        """
        try:
            logger.info(f"Fetching alerts directly from URL: {url}")

            # Generate cache key for the URL
            cache_key = self._generate_cache_key("alerts_direct", {"url": url})

            def fetch_data() -> Dict[str, Any]:
                self._rate_limit()
                try:
                    # Use _fetch_url for direct URL access
                    response = self._fetch_url(url)
                    # Transform the response to match the format expected by the application
                    return self._transform_alerts_data(response)
                except Exception as e:
                    # For any exceptions, wrap them in a NoaaApiError
                    logger.error(f"Error getting alerts from URL {url}: {str(e)}")
                    error_msg = f"Unexpected error getting alerts from URL: {e}"
                    raise NoaaApiError(
                        message=error_msg, error_type=NoaaApiError.UNKNOWN_ERROR, url=url
                    )

            return cast(
                Dict[str, Any], self._get_cached_or_fetch(cache_key, fetch_data, force_refresh)
            )
        except Exception as e:
            logger.error(f"Error getting alerts from URL: {str(e)}")
            raise ApiClientError(f"Unable to retrieve alerts from URL: {str(e)}")

    def get_discussion(self, lat: float, lon: float, force_refresh: bool = False) -> Optional[str]:
        """Get forecast discussion for a location.

        Args:
            lat: Latitude
            lon: Longitude
            force_refresh: Whether to force a refresh of the data

        Returns:
            Text of the forecast discussion or None if not available
        """
        try:
            logger.info(f"Getting forecast discussion for coordinates: ({lat}, {lon})")

            # Get the point data to find the forecast office
            point_data = self.get_point_data(lat, lon, force_refresh=force_refresh)

            # Extract the forecast office ID from the forecast URL
            # Example URL: https://api.weather.gov/gridpoints/PHI/31,70/forecast
            forecast_url = point_data.get("properties", {}).get("forecast")

            if not forecast_url:
                logger.warning("No forecast URL found in point data")
                return None

            parts = forecast_url.split("/")
            office_id = parts[-3]

            # Generate cache key for the discussion
            cache_key = self._generate_cache_key(f"products/types/AFD/locations/{office_id}")

            def fetch_data() -> Optional[str]:
                self._rate_limit()
                try:
                    # Get the list of products
                    # Since product_locations doesn't support these parameters, use a direct API call
                    products_url = f"{self.BASE_URL}/products/types/AFD/locations/{office_id}"
                    products_response = self._fetch_url(products_url)

                    # Check if the response has a @graph property
                    if not products_response.get("@graph") or not products_response["@graph"]:
                        logger.warning(f"No AFD products found for {office_id}")
                        return None

                    # Get the latest product
                    latest_product = products_response["@graph"][0]
                    latest_product_id = latest_product.get("id")

                    # Get the product text
                    # Since product module is not available, we'll use a direct API call
                    product_url = f"{self.BASE_URL}/products/{latest_product_id}"
                    product_response = self._get_cached_or_fetch(
                        f"products/{latest_product_id}",
                        lambda: self._fetch_url(product_url),
                        force_refresh=False,
                    )

                    if not product_response.get("productText"):
                        logger.warning(f"No product text found for {latest_product_id}")
                        return None

                    return cast(Optional[str], product_response.get("productText"))
                except Exception as e:
                    logger.error(f"Error getting discussion for {office_id}: {str(e)}")
                    # Return None instead of raising an error for discussions
                    return None

            return cast(
                Optional[str], self._get_cached_or_fetch(cache_key, fetch_data, force_refresh)
            )
        except Exception as e:
            logger.error(f"Error getting discussion: {str(e)}")
            return None

    def get_national_product(
        self, product_type: str, location: str, force_refresh: bool = False
    ) -> Optional[str]:
        """Get a national product from a specific center.

        Args:
            product_type: Product type code (e.g., "FXUS01")
            location: Location code (e.g., "KWNH")
            force_refresh: Whether to force a refresh of the data

        Returns:
            Text of the product or None if not available
        """
        try:
            endpoint = f"products/types/{product_type}/locations/{location}"
            logger.debug(
                f"Requesting national product: type={product_type}, "
                f"location={location}, endpoint={endpoint}"
            )

            # Generate cache key for the product
            cache_key = self._generate_cache_key(endpoint)

            def fetch_data() -> Optional[str]:
                self._rate_limit()
                try:
                    # Get the list of products
                    # Since product_locations doesn't support these parameters, use a direct API call
                    products_url = (
                        f"{self.BASE_URL}/products/types/{product_type}/locations/{location}"
                    )
                    products_response = self._fetch_url(products_url)

                    # Check if the response has a @graph property
                    if not products_response.get("@graph") or not products_response["@graph"]:
                        logger.warning(f"No products found for {product_type}/{location}")
                        return None

                    # Get the latest product
                    latest_product = products_response["@graph"][0]
                    latest_product_id = latest_product.get("id")

                    # Get the product text
                    # Since product module is not available, we'll use a direct API call
                    product_url = f"{self.BASE_URL}/products/{latest_product_id}"
                    product_response = self._get_cached_or_fetch(
                        f"products/{latest_product_id}",
                        lambda: self._fetch_url(product_url),
                        force_refresh=False,
                    )

                    if not product_response.get("productText"):
                        logger.warning(f"No product text found for {latest_product_id}")
                        return None

                    return cast(Optional[str], product_response.get("productText"))
                except Exception as e:
                    logger.error(
                        f"Error getting national product {product_type} from {location}: {str(e)}"
                    )
                    return None

            return cast(
                Optional[str], self._get_cached_or_fetch(cache_key, fetch_data, force_refresh)
            )
        except Exception as e:
            logger.error(f"Error getting national product {product_type} from {location}: {str(e)}")
            return None

    def get_national_forecast_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Get national forecast data from various centers.

        Args:
            force_refresh: Whether to force a refresh of the data

        Returns:
            Dictionary containing national forecast data
        """
        result = {
            "wpc": {
                "short_range": self.get_national_product("FXUS01", "KWNH", force_refresh),
                "medium_range": self.get_national_product("FXUS06", "KWNH", force_refresh),
                "extended": self.get_national_product("FXUS07", "KWNH", force_refresh),
                "qpf": self.get_national_product("FXUS02", "KWNH", force_refresh),
            },
            "spc": {
                "day1": self.get_national_product("ACUS01", "KWNS", force_refresh),
                "day2": self.get_national_product("ACUS02", "KWNS", force_refresh),
            },
            "nhc": {
                "atlantic": self.get_national_product("MIATWOAT", "KNHC", force_refresh),
                "east_pacific": self.get_national_product("MIATWOEP", "KNHC", force_refresh),
            },
        }
        return result
