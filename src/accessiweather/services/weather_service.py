"""Weather service for AccessiWeather.

This module provides a service layer for weather-related operations,
separating business logic from UI concerns.
"""

import logging
import time
from typing import Any, Dict, List, Optional, Union, cast

from accessiweather.api_client import ApiClientError, NoaaApiClient, NoaaApiError
from accessiweather.api_wrapper import NoaaApiWrapper
from accessiweather.gui.settings_dialog import (
    DATA_SOURCE_AUTO,
    DATA_SOURCE_NWS,
    DATA_SOURCE_OPENWEATHERMAP,
)
from accessiweather.services.national_discussion_scraper import NationalDiscussionScraper
from accessiweather.weatherapi_wrapper import WeatherApiError, WeatherApiWrapper

logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Exception raised for configuration errors."""

    pass


class WeatherService:
    """Service for weather-related operations."""

    def __init__(
        self,
        nws_client: Union[NoaaApiClient, NoaaApiWrapper],
        weatherapi_wrapper: Optional[WeatherApiWrapper] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        """Initialize the weather service.

        Args:
            nws_client: The NWS API client to use for weather data retrieval.
            weatherapi_wrapper: The WeatherAPI.com wrapper to use for weather data retrieval.
            config: Configuration dictionary containing settings like data_source.
        """
        self.nws_client = nws_client
        self.weatherapi_wrapper = weatherapi_wrapper
        self.config = config or {}
        self.national_scraper = NationalDiscussionScraper(request_delay=1.0)
        self.national_data_cache: Optional[Dict[str, Dict[str, str]]] = None
        self.national_data_timestamp: float = 0.0
        self.cache_expiry = 3600  # 1 hour in seconds

    def get_national_forecast_data(self, force_refresh: bool = False) -> dict:
        """Get nationwide forecast data, including national discussion summaries.

        Args:
            force_refresh: Whether to force a refresh of the data

        Returns:
            Dictionary containing national forecast data with structure:
            {
                "national_discussion_summaries": {
                    "wpc": {
                        "short_range_summary": str,
                        "short_range_full": str
                    },
                    "spc": {
                        "day1_summary": str,
                        "day1_full": str
                    },
                    "attribution": str
                }
            }

        Raises:
            ApiClientError: If there was an error retrieving the data
        """
        current_time = time.time()

        # Check if we have cached data that's still valid and not forcing refresh
        if (
            not force_refresh
            and self.national_data_cache
            and current_time - self.national_data_timestamp < self.cache_expiry
        ):
            logger.info("Using cached nationwide forecast data")
            return {"national_discussion_summaries": self.national_data_cache}

        try:
            logger.info("Getting nationwide forecast data from scraper")
            # Fetch fresh data from the scraper
            national_data = self.national_scraper.fetch_all_discussions()

            # Update cache
            self.national_data_cache = national_data
            self.national_data_timestamp = current_time

            return {"national_discussion_summaries": national_data}
        except Exception as e:
            logger.error(f"Error getting nationwide forecast data: {str(e)}")

            # If we have cached data, return it even if expired
            if self.national_data_cache:
                logger.info("Returning cached national data due to fetch error")
                return {"national_discussion_summaries": self.national_data_cache}

            # Otherwise, raise an error
            raise ApiClientError(f"Unable to retrieve nationwide forecast data: {str(e)}")

    def _get_data_source(self) -> str:
        """Get the configured data source.

        Returns:
            String indicating which data source to use ('nws' or 'weatherapi')
        """
        data_source = self.config.get("settings", {}).get("data_source", DATA_SOURCE_NWS)
        logger.debug(
            f"_get_data_source: config={self.config.get('settings', {})}, data_source={data_source}"
        )
        return str(data_source)

    def _check_weatherapi_key(self) -> str:
        """Check if WeatherAPI.com API key is configured.

        Returns:
            The API key if available

        Raises:
            ConfigurationError: If WeatherAPI.com is selected but no API key is configured
        """
        api_key = self.config.get("api_keys", {}).get("weatherapi")
        if not api_key:
            raise ConfigurationError(
                "WeatherAPI.com API key is required when using WeatherAPI.com as the data source"
            )
        return str(api_key)

    def _convert_location_for_weatherapi(self, lat: float, lon: float) -> str:
        """Convert location to WeatherAPI format.

        Args:
            lat: Latitude
            lon: Longitude

        Returns:
            Location in a format suitable for WeatherAPI.com
        """
        # WeatherAPI.com accepts lat,lon as a string in the format "lat,lon"
        return f"{lat},{lon}"

    def _is_location_in_us(self, lat: float, lon: float) -> bool:
        """Check if a location is within the United States.

        This method uses the geocoding service to determine if the given coordinates
        are within the United States.

        Args:
            lat: Latitude
            lon: Longitude

        Returns:
            True if the location is within the US, False otherwise
        """
        from accessiweather.geocoding import GeocodingService

        # Create a geocoding service instance with the correct data source
        # Using 'auto' as data source to ensure it doesn't filter based on data source
        # but only on the explicit us_only parameter
        geocoding_service = GeocodingService(
            user_agent="AccessiWeather-WeatherService", data_source="auto"
        )

        # Use the validate_coordinates method to check if the location is in the US
        # Explicitly set us_only=True to check for US location regardless of data source
        is_us = geocoding_service.validate_coordinates(lat, lon, us_only=True)
        logger.debug(f"Location ({lat}, {lon}) is {'in' if is_us else 'not in'} the US")
        return is_us

    def _is_weatherapi_available(self) -> bool:
        """Check if WeatherAPI.com is available and configured.

        Returns:
            True if WeatherAPI.com is available and configured, False otherwise
        """
        data_source = self._get_data_source()
        logger.debug(f"_is_weatherapi_available: data_source={data_source}")

        # Check if OpenWeatherMap is selected as the data source
        if data_source != DATA_SOURCE_OPENWEATHERMAP and data_source != DATA_SOURCE_AUTO:
            logger.debug(
                f"_is_weatherapi_available: data_source is not weatherapi or auto, returning False"
            )
            return False

        # Check if WeatherAPI.com wrapper is initialized
        if self.weatherapi_wrapper is None:
            logger.warning(
                "WeatherAPI.com is selected as the data source, but the wrapper is not initialized"
            )
            raise ConfigurationError("WeatherAPI.com wrapper is not initialized")

        logger.debug(f"_is_weatherapi_available: WeatherAPI.com is available, returning True")
        return True

    def _should_use_weatherapi(self, lat: float, lon: float) -> bool:
        """Determine if WeatherAPI.com should be used for the given location.

        Args:
            lat: Latitude of the location
            lon: Longitude of the location

        Returns:
            True if WeatherAPI.com should be used, False if NWS should be used
        """
        data_source = self._get_data_source()
        logger.debug(f"_should_use_weatherapi: data_source={data_source}, lat={lat}, lon={lon}")

        # If OpenWeatherMap is explicitly selected, always use it
        if data_source == DATA_SOURCE_OPENWEATHERMAP:
            logger.debug("_should_use_weatherapi: WeatherAPI.com explicitly selected")
            return True

        # If Automatic mode is selected, use WeatherAPI.com for non-US locations
        if data_source == DATA_SOURCE_AUTO:
            # Check if location is in the US
            is_us_location = self._is_location_in_us(lat, lon)
            logger.debug(f"_should_use_weatherapi: Automatic mode, is_us_location={is_us_location}")
            return not is_us_location

        # Default to NWS
        logger.debug("_should_use_weatherapi: Defaulting to NWS API")
        return False

    def get_forecast(self, lat: float, lon: float, force_refresh: bool = False) -> Dict[str, Any]:
        """Get forecast data for a location.

        Args:
            lat: Latitude of the location.
            lon: Longitude of the location.
            force_refresh: Whether to force a refresh of the data from the API
                instead of using cache.

        Returns:
            Dictionary containing forecast data.

        Raises:
            ApiClientError: If there was an error retrieving the forecast.
            ConfigurationError: If WeatherAPI.com is selected but no API key is configured.
        """
        try:
            logger.info(f"Getting forecast for coordinates: ({lat}, {lon})")

            # Get the data source directly
            data_source = self._get_data_source()

            # Determine which API to use
            use_weatherapi = False

            # If OpenWeatherMap is explicitly selected, always use it
            if data_source == DATA_SOURCE_OPENWEATHERMAP:
                use_weatherapi = True
                logger.info("Using WeatherAPI.com for forecast (explicitly selected)")
            # If Automatic mode is selected, use WeatherAPI.com for non-US locations
            elif data_source == DATA_SOURCE_AUTO:
                # Check if location is in the US
                is_us_location = self._is_location_in_us(lat, lon)
                use_weatherapi = not is_us_location
                logger.info(
                    f"Using {'WeatherAPI.com' if use_weatherapi else 'NWS API'} for forecast (automatic mode, {'non-US' if not is_us_location else 'US'} location)"
                )
            else:
                # Default to NWS
                logger.info("Using NWS API for forecast (default)")

            # Log more details for debugging
            logger.debug(
                f"get_forecast: data_source={data_source}, use_weatherapi={use_weatherapi}, lat={lat}, lon={lon}"
            )

            if use_weatherapi:
                # Check if WeatherAPI.com is available
                if self.weatherapi_wrapper is not None:
                    # Use WeatherAPI
                    weatherapi_location = self._convert_location_for_weatherapi(lat, lon)
                    wrapper = cast(WeatherApiWrapper, self.weatherapi_wrapper)
                    return wrapper.get_forecast(
                        weatherapi_location, days=7, alerts=True, force_refresh=force_refresh
                    )
                else:
                    # WeatherAPI not available, but needed
                    if data_source == DATA_SOURCE_AUTO:
                        raise ConfigurationError(
                            "WeatherAPI.com is required for non-US locations in Automatic mode"
                        )
                    else:
                        raise ConfigurationError(
                            "WeatherAPI.com is required when using WeatherAPI.com as the data source"
                        )
            else:
                # Use NWS API
                return self.nws_client.get_forecast(lat, lon, force_refresh=force_refresh)
        except ConfigurationError:
            # Re-raise configuration errors
            raise
        except WeatherApiError as e:
            # Re-raise WeatherAPI.com errors directly for specific handling
            logger.error(f"WeatherAPI.com error getting forecast: {str(e)}")
            raise
        except NoaaApiError as e:
            # Re-raise NOAA API errors directly for specific handling
            logger.error(f"NOAA API error getting forecast: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error getting forecast: {str(e)}")
            raise ApiClientError(f"Unable to retrieve forecast data: {str(e)}")

    def get_hourly_forecast(
        self, lat: float, lon: float, force_refresh: bool = False
    ) -> Dict[str, Any]:
        """Get hourly forecast data for a location.

        Args:
            lat: Latitude of the location.
            lon: Longitude of the location.
            force_refresh: Whether to force a refresh of the data from the API
                instead of using cache.

        Returns:
            Dictionary containing hourly forecast data.

        Raises:
            ApiClientError: If there was an error retrieving the hourly forecast.
            ConfigurationError: If WeatherAPI.com is selected but no API key is configured.
        """
        try:
            logger.info(f"Getting hourly forecast for coordinates: ({lat}, {lon})")

            # Get the data source directly
            data_source = self._get_data_source()

            # Determine which API to use
            use_weatherapi = False

            # If OpenWeatherMap is explicitly selected, always use it
            if data_source == DATA_SOURCE_OPENWEATHERMAP:
                use_weatherapi = True
                logger.info("Using WeatherAPI.com for hourly forecast (explicitly selected)")
            # If Automatic mode is selected, use WeatherAPI.com for non-US locations
            elif data_source == DATA_SOURCE_AUTO:
                # Check if location is in the US
                is_us_location = self._is_location_in_us(lat, lon)
                use_weatherapi = not is_us_location
                logger.info(
                    f"Using {'WeatherAPI.com' if use_weatherapi else 'NWS API'} for hourly forecast (automatic mode, {'non-US' if not is_us_location else 'US'} location)"
                )
            else:
                # Default to NWS
                logger.info("Using NWS API for hourly forecast (default)")

            # Log more details for debugging
            logger.debug(
                f"get_hourly_forecast: data_source={data_source}, use_weatherapi={use_weatherapi}, lat={lat}, lon={lon}"
            )

            if use_weatherapi:
                # Check if WeatherAPI.com is available
                if self.weatherapi_wrapper is not None:
                    # Use WeatherAPI
                    weatherapi_location = self._convert_location_for_weatherapi(lat, lon)
                    wrapper = cast(WeatherApiWrapper, self.weatherapi_wrapper)
                    hourly_data = wrapper.get_hourly_forecast(
                        weatherapi_location, days=2, force_refresh=force_refresh
                    )
                    return {"hourly": hourly_data}
                else:
                    # WeatherAPI not available, but needed
                    if data_source == DATA_SOURCE_AUTO:
                        raise ConfigurationError(
                            "WeatherAPI.com is required for non-US locations in Automatic mode"
                        )
                    else:
                        raise ConfigurationError(
                            "WeatherAPI.com is required when using WeatherAPI.com as the data source"
                        )
            else:
                # Use NWS API
                return self.nws_client.get_hourly_forecast(lat, lon, force_refresh=force_refresh)
        except ConfigurationError:
            # Re-raise configuration errors
            raise
        except WeatherApiError as e:
            # Re-raise WeatherAPI.com errors directly for specific handling
            logger.error(f"WeatherAPI.com error getting hourly forecast: {str(e)}")
            raise
        except NoaaApiError as e:
            # Re-raise NOAA API errors directly for specific handling
            logger.error(f"NOAA API error getting hourly forecast: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error getting hourly forecast: {str(e)}")
            raise ApiClientError(f"Unable to retrieve hourly forecast data: {str(e)}")

    def get_stations(self, lat: float, lon: float, force_refresh: bool = False) -> Dict[str, Any]:
        """Get observation stations for a location.

        Args:
            lat: Latitude of the location.
            lon: Longitude of the location.
            force_refresh: Whether to force a refresh of the data from the API
                instead of using cache.

        Returns:
            Dictionary containing observation stations data.

        Raises:
            ApiClientError: If there was an error retrieving the stations.
            ConfigurationError: If WeatherAPI.com is selected (not supported).
        """
        try:
            logger.info(f"Getting observation stations for coordinates: ({lat}, {lon})")

            # Stations are only available from NWS
            data_source = self._get_data_source()
            if data_source == DATA_SOURCE_OPENWEATHERMAP or data_source == DATA_SOURCE_AUTO:
                logger.warning(
                    "Observation stations are not available from WeatherAPI.com, using NWS instead"
                )

            # Always use NWS for stations
            return self.nws_client.get_stations(lat, lon, force_refresh=force_refresh)
        except Exception as e:
            logger.error(f"Error getting observation stations: {str(e)}")
            raise ApiClientError(f"Unable to retrieve observation stations data: {str(e)}")

    def get_current_conditions(
        self, lat: float, lon: float, force_refresh: bool = False
    ) -> Dict[str, Any]:
        """Get current weather conditions for a location.

        Args:
            lat: Latitude of the location.
            lon: Longitude of the location.
            force_refresh: Whether to force a refresh of the data from the API
                instead of using cache.

        Returns:
            Dictionary containing current weather conditions.

        Raises:
            ApiClientError: If there was an error retrieving the current conditions.
            ConfigurationError: If WeatherAPI.com is selected but no API key is configured.
        """
        try:
            logger.info(f"Getting current conditions for coordinates: ({lat}, {lon})")

            # Get the data source directly
            data_source = self._get_data_source()

            # Determine which API to use
            use_weatherapi = False

            # If OpenWeatherMap is explicitly selected, always use it
            if data_source == DATA_SOURCE_OPENWEATHERMAP:
                use_weatherapi = True
                logger.info("Using WeatherAPI.com for current conditions (explicitly selected)")
            # If Automatic mode is selected, use WeatherAPI.com for non-US locations
            elif data_source == DATA_SOURCE_AUTO:
                # Check if location is in the US
                is_us_location = self._is_location_in_us(lat, lon)
                use_weatherapi = not is_us_location
                logger.info(
                    f"Using {'WeatherAPI.com' if use_weatherapi else 'NWS API'} for current conditions (automatic mode, {'non-US' if not is_us_location else 'US'} location)"
                )
            else:
                # Default to NWS
                logger.info("Using NWS API for current conditions (default)")

            # Log more details for debugging
            logger.debug(
                f"get_current_conditions: data_source={data_source}, use_weatherapi={use_weatherapi}, lat={lat}, lon={lon}"
            )

            if use_weatherapi:
                # Check if WeatherAPI.com is available
                if self.weatherapi_wrapper is not None:
                    # Use WeatherAPI
                    weatherapi_location = self._convert_location_for_weatherapi(lat, lon)
                    wrapper = cast(WeatherApiWrapper, self.weatherapi_wrapper)
                    return wrapper.get_current_conditions(
                        weatherapi_location, force_refresh=force_refresh
                    )
                else:
                    # WeatherAPI not available, but needed
                    if data_source == DATA_SOURCE_AUTO:
                        raise ConfigurationError(
                            "WeatherAPI.com is required for non-US locations in Automatic mode"
                        )
                    else:
                        raise ConfigurationError(
                            "WeatherAPI.com is required when using WeatherAPI.com as the data source"
                        )
            else:
                # Use NWS API
                return self.nws_client.get_current_conditions(lat, lon, force_refresh=force_refresh)
        except ConfigurationError:
            # Re-raise configuration errors
            raise
        except WeatherApiError as e:
            # Re-raise WeatherAPI.com errors directly for specific handling
            logger.error(f"WeatherAPI.com error getting current conditions: {str(e)}")
            raise
        except NoaaApiError as e:
            # Re-raise NOAA API errors directly for specific handling
            logger.error(f"NOAA API error getting current conditions: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error getting current conditions: {str(e)}")
            raise ApiClientError(f"Unable to retrieve current conditions data: {str(e)}")

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
            lat: Latitude of the location.
            lon: Longitude of the location.
            radius: Radius in miles to search for alerts.
            precise_location: Whether to get alerts for the precise location (county/zone)
                             or for the entire state.
            force_refresh: Whether to force a refresh of the data from the API
                instead of using cache.

        Returns:
            Dictionary containing alert data.

        Raises:
            ApiClientError: If there was an error retrieving the alerts.
            ConfigurationError: If WeatherAPI.com is selected but no API key is configured.
        """
        try:
            logger.info(
                f"Getting alerts for coordinates: ({lat}, {lon}) with radius {radius} miles, "
                f"precise_location={precise_location}, force_refresh={force_refresh}"
            )

            # Get the data source directly
            data_source = self._get_data_source()

            # Determine which API to use
            use_weatherapi = False

            # If OpenWeatherMap is explicitly selected, always use it
            if data_source == DATA_SOURCE_OPENWEATHERMAP:
                use_weatherapi = True
                logger.info("Using WeatherAPI.com for alerts (explicitly selected)")
            # If Automatic mode is selected, use WeatherAPI.com for non-US locations
            elif data_source == DATA_SOURCE_AUTO:
                # Check if location is in the US
                is_us_location = self._is_location_in_us(lat, lon)
                use_weatherapi = not is_us_location
                logger.info(
                    f"Using {'WeatherAPI.com' if use_weatherapi else 'NWS API'} for alerts (automatic mode, {'non-US' if not is_us_location else 'US'} location)"
                )
            else:
                # Default to NWS
                logger.info("Using NWS API for alerts (default)")

            # Log more details for debugging
            logger.debug(
                f"get_alerts: data_source={data_source}, use_weatherapi={use_weatherapi}, lat={lat}, lon={lon}"
            )

            if use_weatherapi:
                # Check if WeatherAPI.com is available
                if self.weatherapi_wrapper is not None:
                    # Use WeatherAPI
                    weatherapi_location = self._convert_location_for_weatherapi(lat, lon)
                    wrapper = cast(WeatherApiWrapper, self.weatherapi_wrapper)
                    forecast_data = wrapper.get_forecast(
                        weatherapi_location, days=1, alerts=True, force_refresh=force_refresh
                    )
                    if "alerts" in forecast_data:
                        return {"alerts": forecast_data["alerts"]}
                    return {"alerts": []}
                else:
                    # WeatherAPI not available, but needed
                    if data_source == DATA_SOURCE_AUTO:
                        raise ConfigurationError(
                            "WeatherAPI.com is required for non-US locations in Automatic mode"
                        )
                    else:
                        raise ConfigurationError(
                            "WeatherAPI.com is required when using WeatherAPI.com as the data source"
                        )
            else:
                # Use NWS API
                return self.nws_client.get_alerts(
                    lat,
                    lon,
                    radius=radius,
                    precise_location=precise_location,
                    force_refresh=force_refresh,
                )
        except ConfigurationError:
            # Re-raise configuration errors
            raise
        except WeatherApiError as e:
            # Re-raise WeatherAPI.com errors directly for specific handling
            logger.error(f"WeatherAPI.com error getting alerts: {str(e)}")
            raise
        except NoaaApiError as e:
            # Re-raise NOAA API errors directly for specific handling
            logger.error(f"NOAA API error getting alerts: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error getting alerts: {str(e)}")
            raise ApiClientError(f"Unable to retrieve alerts data: {str(e)}")

    def get_discussion(self, lat: float, lon: float, force_refresh: bool = False) -> Optional[str]:
        """Get forecast discussion for a location.

        Args:
            lat: Latitude of the location.
            lon: Longitude of the location.
            force_refresh: Whether to force a refresh of the data from the API
                instead of using cache.

        Returns:
            Text of the forecast discussion or None if not available.

        Raises:
            ApiClientError: If there was an error retrieving the discussion.
        """
        try:
            logger.info(f"Getting forecast discussion for coordinates: ({lat}, {lon})")

            # Discussions are only available from NWS
            data_source = self._get_data_source()
            if data_source == DATA_SOURCE_OPENWEATHERMAP or data_source == DATA_SOURCE_AUTO:
                logger.warning(
                    "Forecast discussions are not available from WeatherAPI.com, using NWS instead"
                )

            # Always use NWS for discussions
            discussion = self.nws_client.get_discussion(lat, lon, force_refresh=force_refresh)
            if not discussion:
                logger.warning("No discussion available")
                return None
            return discussion
        except Exception as e:
            logger.error(f"Error getting discussion: {str(e)}")
            raise ApiClientError(f"Unable to retrieve discussion data: {str(e)}")

    def process_alerts(self, alerts_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process alerts data into a list of alert objects.

        Args:
            alerts_data: Raw alerts data from the API.

        Returns:
            List of processed alert objects.
        """
        processed_alerts = []
        features = alerts_data.get("features", [])

        for feature in features:
            properties = feature.get("properties", {})

            # Extract relevant alert information
            alert = {
                "id": feature.get("id", ""),
                "headline": properties.get("headline", "Unknown Alert"),
                "description": properties.get("description", "No description available"),
                "instruction": properties.get("instruction", ""),
                "severity": properties.get("severity", "Unknown"),
                "event": properties.get("event", "Unknown Event"),
                "effective": properties.get("effective", ""),
                "expires": properties.get("expires", ""),
                "status": properties.get("status", ""),
                "messageType": properties.get("messageType", ""),
                "areaDesc": properties.get("areaDesc", "Unknown Area"),
                "parameters": properties.get("parameters", {}),  # For NWSheadline
            }

            processed_alerts.append(alert)

        return processed_alerts
