"""
Core NOAA API client for AccessiWeather.

This module provides the base NoaaApiClient class with core functionality including
initialization, configuration, HTTP request handling, caching, and rate limiting.
"""

import hashlib
import json
import logging
import threading
import time
import traceback
from typing import Any

import requests

# For compatibility with different requests versions
try:
    from requests.exceptions import JSONDecodeError
except ImportError:
    from json import JSONDecodeError

from accessiweather.cache import Cache

from .alerts_and_products import AlertsAndProductsMixin
from .exceptions import NoaaApiError

logger = logging.getLogger(__name__)


class NoaaApiClient(AlertsAndProductsMixin):
    """Client for interacting with NOAA Weather API."""

    # NOAA Weather API base URL
    BASE_URL = "https://api.weather.gov"

    def __init__(
        self,
        user_agent: str = "AccessiWeather",
        contact_info: str | None = None,
        enable_caching: bool = False,
        cache_ttl: int = 300,
    ):
        """
        Initialize the NOAA API client.

        Args:
        ----
            user_agent: User agent string for API requests
            contact_info: Optional contact information (website or email)
                          for API identification. If None, uses the app name.
            enable_caching: Whether to enable caching of API responses
            cache_ttl: Time-to-live for cached responses in seconds (default: 5 minutes)

        """
        self.user_agent = user_agent
        # Use app name as default contact info if none provided
        self.contact_info = contact_info or user_agent

        # Build user agent string according to NOAA API recommendations
        user_agent_string = f"{user_agent} ({self.contact_info})"

        self.headers = {"User-Agent": user_agent_string, "Accept": "application/geo+json"}

        # Add request tracking for rate limiting
        self.last_request_time: float = 0.0  # Ensure float type
        # Half a second between requests to avoid rate limiting
        self.min_request_interval: float = 0.5

        # Add thread lock for thread safety
        self.request_lock = threading.RLock()

        # Initialize cache if enabled
        self.cache = Cache(default_ttl=cache_ttl) if enable_caching else None

        logger.info(f"Initialized NOAA API client with User-Agent: {user_agent_string}")
        if enable_caching:
            logger.info(f"Caching enabled with TTL of {cache_ttl} seconds")

    def get_point_data(self, lat: float, lon: float, force_refresh: bool = False) -> dict[str, Any]:
        """
        Get metadata about a specific lat/lon point.

        Args:
        ----
            lat: Latitude
            lon: Longitude
            force_refresh: If True, bypass cache and fetch fresh data

        Returns:
        -------
            Dict containing point metadata

        """
        endpoint = f"points/{lat},{lon}"
        logger.info(f"Fetching point data for coordinates: ({lat}, {lon})")
        return self._make_request(endpoint, force_refresh=force_refresh)

    def _make_request(
        self,
        endpoint_or_url: str,
        params: dict[str, Any] | None = None,
        use_full_url: bool = False,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        """
        Make a request to the NOAA API.

        Args:
        ----
            endpoint_or_url: API endpoint path or full URL if use_full_url
                             is True
            params: Query parameters
            use_full_url: Whether the endpoint_or_url is a complete URL
            force_refresh: Whether to force a refresh of the data

        Returns:
        -------
            Dict containing the API response

        Raises:
        ------
            NoaaApiError: If the API request fails

        """
        # Build the request URL
        request_url = endpoint_or_url if use_full_url else f"{self.BASE_URL}/{endpoint_or_url}"

        # Create cache key if caching is enabled
        cache_key = None
        if self.cache:
            # Create a unique cache key based on URL and params
            cache_data = {"url": request_url, "params": params or {}}
            cache_key = hashlib.md5(
                json.dumps(cache_data, sort_keys=True).encode(), usedforsecurity=False
            ).hexdigest()

            # Check cache first if not forcing refresh
            if not force_refresh:
                cached_response = self.cache.get(cache_key)
                if cached_response is not None:
                    logger.debug(f"Cache hit for {request_url}")
                    return cached_response  # type: ignore[no-any-return]

        # Make the API request with rate limiting and error handling
        try:
            with self.request_lock:
                # Rate limiting
                if self.last_request_time > 0:
                    elapsed = time.time() - self.last_request_time
                    sleep_time = max(0, self.min_request_interval - elapsed)
                    if sleep_time > 0:
                        logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f}s")
                        time.sleep(sleep_time)

                logger.debug(f"API request to: {request_url} with params: {params}")
                # Make the request - keeping this inside the lock to avoid
                # concurrent access. Added timeout.
                try:
                    logger.debug(f"Sending GET request to {request_url}")
                    response = requests.get(
                        request_url, headers=self.headers, params=params, timeout=10
                    )
                    logger.debug(
                        f"Received response from {request_url} with status code: "
                        f"{response.status_code}"
                    )
                    self.last_request_time = time.time()
                except Exception as e:
                    logger.error(f"Exception during GET request to {request_url}: {e}")
                    raise

                # Handle HTTP errors
                if response.status_code == 404:
                    error_msg = f"Resource not found (404) for {request_url}"
                    logger.error(error_msg)
                    raise NoaaApiError(
                        message=error_msg,
                        status_code=response.status_code,
                        error_type=NoaaApiError.CLIENT_ERROR,
                        url=request_url,
                    )
                if response.status_code == 429:
                    error_msg = f"Rate limit exceeded (429) for {request_url}"
                    logger.error(error_msg)
                    raise NoaaApiError(
                        message=error_msg,
                        status_code=response.status_code,
                        error_type=NoaaApiError.RATE_LIMIT_ERROR,
                        url=request_url,
                    )
                if response.status_code >= 500:
                    error_msg = f"Server error ({response.status_code}) for {request_url}"
                    logger.error(error_msg)
                    raise NoaaApiError(
                        message=error_msg,
                        status_code=response.status_code,
                        error_type=NoaaApiError.SERVER_ERROR,
                        url=request_url,
                    )
                if response.status_code >= 400:
                    error_msg = f"Client error ({response.status_code}) for {request_url}"
                    logger.error(error_msg)
                    raise NoaaApiError(
                        message=error_msg,
                        status_code=response.status_code,
                        error_type=NoaaApiError.CLIENT_ERROR,
                        url=request_url,
                    )

                # Parse JSON response
                try:
                    data = response.json()
                    logger.debug(f"Successfully parsed JSON response from {request_url}")

                    # Cache the response if caching is enabled
                    if self.cache and cache_key:
                        self.cache.set(cache_key, data)
                        logger.debug(f"Cached response for {request_url}")

                    return data  # type: ignore[no-any-return]

                except JSONDecodeError as json_err:
                    error_msg = f"Failed to parse JSON response from {request_url}: {json_err}"
                    logger.error(error_msg)
                    logger.debug(f"Response content: {response.text[:500]}...")
                    raise NoaaApiError(
                        message=error_msg,
                        status_code=response.status_code,
                        error_type=NoaaApiError.PARSE_ERROR,
                        url=request_url,
                    ) from json_err

        except requests.exceptions.Timeout as timeout_err:
            # Handle timeout errors specifically
            error_msg = f"Request timed out during API request to {request_url}: {timeout_err}"
            logger.error(error_msg)
            raise NoaaApiError(
                message=error_msg, error_type=NoaaApiError.TIMEOUT_ERROR, url=request_url
            ) from timeout_err
        except requests.exceptions.ConnectionError as conn_err:
            # Handle connection errors specifically
            error_msg = f"Connection error during API request to {request_url}: {conn_err}"
            logger.error(error_msg)
            raise NoaaApiError(
                message=error_msg, error_type=NoaaApiError.CONNECTION_ERROR, url=request_url
            ) from conn_err
        except requests.exceptions.RequestException as req_err:
            # Catch other request exceptions
            error_msg = f"Network error during API request to {request_url}: {req_err}"
            # Log without traceback to avoid cluttering logs with expected errors
            logger.error(error_msg)  # Don't include exc_info=True
            raise NoaaApiError(
                message=error_msg, error_type=NoaaApiError.NETWORK_ERROR, url=request_url
            ) from req_err
        except NoaaApiError:  # Re-raise NoaaApiErrors directly
            raise
        except Exception as e:
            # Catch any other unexpected errors
            error_msg = f"Unexpected error during API request to {request_url}: {e}"
            logger.error(error_msg, exc_info=True)  # Log with traceback
            raise NoaaApiError(
                message=error_msg, error_type=NoaaApiError.UNKNOWN_ERROR, url=request_url
            ) from e

    def get_forecast(self, lat: float, lon: float, force_refresh: bool = False) -> dict[str, Any]:
        """
        Get forecast for a location.

        Args:
        ----
            lat: Latitude
            lon: Longitude
            force_refresh: Whether to force a refresh of the data

        Returns:
        -------
            Dict containing forecast data

        """
        # First get the forecast URL from the point data
        try:
            logger.info(f"Getting forecast for coordinates: ({lat}, {lon})")
            point_data = self.get_point_data(lat, lon, force_refresh=force_refresh)

            # Debug log the point data structure
            logger.debug(f"Point data structure: {json.dumps(point_data, indent=2)}")

            forecast_url = point_data.get("properties", {}).get("forecast")

            if not forecast_url:
                props = list(point_data.get("properties", {}).keys())
                logger.error(
                    f"Could not find forecast URL in point data. Available properties: {props}"
                )
                # Keep this specific ValueError for this context
                raise ValueError("Could not find forecast URL in point data")

            logger.info(f"Retrieved forecast URL: {forecast_url}")
            return self._make_request(forecast_url, use_full_url=True, force_refresh=force_refresh)
        except Exception as e:
            logger.error(f"Error getting forecast: {str(e)}")
            logger.debug(f"Traceback: {traceback.format_exc()}")
            raise

    def get_hourly_forecast(
        self, lat: float, lon: float, force_refresh: bool = False
    ) -> dict[str, Any]:
        """
        Get hourly forecast for a location.

        Args:
        ----
            lat: Latitude
            lon: Longitude
            force_refresh: Whether to force a refresh of the data

        Returns:
        -------
            Dict containing hourly forecast data

        """
        # First get the hourly forecast URL from the point data
        try:
            logger.info(f"Getting hourly forecast for coordinates: ({lat}, {lon})")
            point_data = self.get_point_data(lat, lon, force_refresh=force_refresh)

            # Debug log the point data structure
            logger.debug(f"Point data structure: {json.dumps(point_data, indent=2)}")

            hourly_forecast_url = point_data.get("properties", {}).get("forecastHourly")

            if not hourly_forecast_url:
                props = list(point_data.get("properties", {}).keys())
                logger.error(
                    "Could not find hourly forecast URL in point data. "
                    f"Available properties: {props}"
                )
                raise ValueError("Could not find hourly forecast URL in point data")

            logger.info(f"Retrieved hourly forecast URL: {hourly_forecast_url}")
            return self._make_request(
                hourly_forecast_url, use_full_url=True, force_refresh=force_refresh
            )
        except Exception as e:
            logger.error(f"Error getting hourly forecast: {str(e)}")
            logger.debug(f"Traceback: {traceback.format_exc()}")
            raise

    def get_stations(self, lat: float, lon: float, force_refresh: bool = False) -> dict[str, Any]:
        """
        Get observation stations for a location.

        Args:
        ----
            lat: Latitude
            lon: Longitude
            force_refresh: Whether to force a refresh of the data

        Returns:
        -------
            Dict containing observation stations data

        """
        try:
            logger.info(f"Getting observation stations for coordinates: ({lat}, {lon})")
            point_data = self.get_point_data(lat, lon, force_refresh=force_refresh)

            # Debug log the point data structure
            logger.debug(f"Point data structure: {json.dumps(point_data, indent=2)}")

            stations_url = point_data.get("properties", {}).get("observationStations")

            if not stations_url:
                props = list(point_data.get("properties", {}).keys())
                logger.error(
                    "Could not find observation stations URL in point data. "
                    f"Available properties: {props}"
                )
                raise ValueError("Could not find observation stations URL in point data")

            logger.info(f"Retrieved observation stations URL: {stations_url}")
            return self._make_request(stations_url, use_full_url=True, force_refresh=force_refresh)
        except Exception as e:
            logger.error(f"Error getting observation stations: {str(e)}")
            logger.debug(f"Traceback: {traceback.format_exc()}")
            raise

    def get_current_conditions(
        self, lat: float, lon: float, force_refresh: bool = False
    ) -> dict[str, Any]:
        """
        Get current weather conditions for a location from the nearest observation station.

        Args:
        ----
            lat: Latitude
            lon: Longitude
            force_refresh: Whether to force a refresh of the data

        Returns:
        -------
            Dict containing current weather conditions

        """
        try:
            logger.info(f"Getting current conditions for coordinates: ({lat}, {lon})")

            # Get the observation stations
            stations_data = self.get_stations(lat, lon, force_refresh=force_refresh)

            # Check if we have any stations
            if not stations_data.get("features") or len(stations_data["features"]) == 0:
                logger.error("No observation stations found for the given coordinates")
                raise ValueError("No observation stations found for the given coordinates")

            # Get the first station (nearest)
            station = stations_data["features"][0]
            station_id = station["properties"]["stationIdentifier"]

            logger.info(f"Using station {station_id} for current conditions")

            # Get the latest observation from this station
            observation_url = f"{self.BASE_URL}/stations/{station_id}/observations/latest"
            logger.info(f"Fetching current conditions from: {observation_url}")

            return self._make_request(
                observation_url, use_full_url=True, force_refresh=force_refresh
            )
        except Exception as e:
            logger.error(f"Error getting current conditions: {str(e)}")
            logger.debug(f"Traceback: {traceback.format_exc()}")
            raise

    def identify_location_type(
        self, lat: float, lon: float, force_refresh: bool = False
    ) -> tuple[str | None, str | None]:
        """
        Identify the type of location (county, state, etc.) for the given coordinates.

        Args:
        ----
            lat: Latitude of the location
            lon: Longitude of the location
            force_refresh: Whether to force a refresh of the data from the API
                instead of using cache

        Returns:
        -------
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
                logger.info(f"Identified location as fire weather zone: {fire_id}")
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
