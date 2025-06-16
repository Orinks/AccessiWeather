"""NWS API wrapper for AccessiWeather.

This module provides the NwsApiWrapper class that handles NWS-specific
weather API operations, inheriting from BaseApiWrapper for shared functionality.
"""

import logging
from typing import Any, Dict, Optional, cast

from accessiweather.api_client import ApiClientError, NoaaApiError
from accessiweather.weather_gov_api_client.api.default import (
    alerts_active,
    alerts_active_zone,
    point,
    station_observation_latest,
)
from accessiweather.weather_gov_api_client.client import Client
from accessiweather.weather_gov_api_client.errors import UnexpectedStatus

from .base_wrapper import BaseApiWrapper

logger = logging.getLogger(__name__)


class NwsApiWrapper(BaseApiWrapper):
    """NWS-specific API wrapper that handles National Weather Service operations."""

    BASE_URL = "https://api.weather.gov"

    def __init__(self, **kwargs):
        """Initialize the NWS API wrapper.

        Args:
            **kwargs: Arguments passed to BaseApiWrapper
        """
        super().__init__(**kwargs)

        # Build user agent string according to NOAA API recommendations
        user_agent_string = f"{self.user_agent} ({self.contact_info})"

        # Initialize the generated NWS client
        self.client = Client(
            base_url=self.BASE_URL,
            headers={"User-Agent": user_agent_string, "Accept": "application/geo+json"},
            timeout=10.0,
            follow_redirects=True,
        )

        logger.info(f"Initialized NWS API wrapper with User-Agent: {user_agent_string}")

    def _make_api_request(self, module_func, **kwargs) -> Any:
        """Call a function from the generated NWS client modules and handle exceptions."""
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
                error_msg = f"Resource not found (404) at {url}"
                raise NoaaApiError(
                    message=error_msg,
                    error_type=NoaaApiError.NOT_FOUND_ERROR,
                    url=url,
                    status_code=status_code,
                )
            elif status_code == 429:
                error_msg = f"Rate limit exceeded (429) for {url}"
                raise NoaaApiError(
                    message=error_msg,
                    error_type=NoaaApiError.RATE_LIMIT_ERROR,
                    url=url,
                    status_code=status_code,
                )
            elif status_code >= 500:
                error_msg = f"Server error ({status_code}) at {url}"
                raise NoaaApiError(
                    message=error_msg,
                    error_type=NoaaApiError.SERVER_ERROR,
                    url=url,
                    status_code=status_code,
                )
            else:
                error_msg = f"HTTP {status_code} error at {url}: {e.content}"
                raise NoaaApiError(
                    message=error_msg,
                    error_type=NoaaApiError.HTTP_ERROR,
                    url=url,
                    status_code=status_code,
                )
        except Exception as e:
            # Handle other exceptions
            url = kwargs.get("url", self.BASE_URL)
            error_msg = f"Unexpected error during NWS API request to {url}: {e}"
            logger.error(error_msg)
            raise NoaaApiError(message=error_msg, error_type=NoaaApiError.UNKNOWN_ERROR, url=url)

    def get_point_data(self, lat: float, lon: float, force_refresh: bool = False) -> Dict[str, Any]:
        """Get metadata about a specific lat/lon point."""
        endpoint = f"points/{lat},{lon}"
        cache_key = self._generate_cache_key(endpoint, {})
        logger.info(f"Fetching point data for coordinates: ({lat}, {lon})")

        def fetch_data() -> Dict[str, Any]:
            self._rate_limit()
            try:
                point_str = f"{lat},{lon}"
                response = self._make_api_request(point.sync, point=point_str)
                return self._transform_point_data(response)
            except NoaaApiError:
                raise
            except Exception as e:
                logger.error(f"Error getting point data for {lat},{lon}: {str(e)}")
                url = f"{self.BASE_URL}/{endpoint}"
                error_msg = f"Unexpected error getting point data: {e}"
                raise NoaaApiError(
                    message=error_msg, error_type=NoaaApiError.UNKNOWN_ERROR, url=url
                )

        return cast(Dict[str, Any], self._get_cached_or_fetch(cache_key, fetch_data, force_refresh))

    def _transform_point_data(self, point_data: Any) -> Dict[str, Any]:
        """Transform point data from the generated client format."""
        # Extract and transform the data to match the format expected by the application
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
            # Handle object with properties attribute
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
                transformed = {"properties": {}}

        return transformed

    # Implementation of abstract methods from BaseApiWrapper
    def get_current_conditions(self, lat: float, lon: float, **kwargs) -> Dict[str, Any]:
        """Get current weather conditions for a location from the nearest observation station."""
        force_refresh = kwargs.get("force_refresh", False)

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
            cache_key = self._generate_cache_key(f"stations/{station_id}/observations/latest", {})

            def fetch_data() -> Dict[str, Any]:
                self._rate_limit()
                try:
                    response = self._make_api_request(
                        station_observation_latest.sync, station_id=station_id
                    )
                    return self._transform_observation_data(response)
                except NoaaApiError:
                    raise
                except Exception as e:
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
        """Transform observation data from the generated client format."""
        if isinstance(observation_data, dict):
            return observation_data
        if hasattr(observation_data, "to_dict"):
            return cast(Dict[str, Any], observation_data.to_dict())
        return cast(Dict[str, Any], observation_data)

    def get_forecast(self, lat: float, lon: float, **kwargs) -> Dict[str, Any]:
        """Get forecast for a location."""
        force_refresh = kwargs.get("force_refresh", False)

        try:
            logger.info(f"Getting forecast for coordinates: ({lat}, {lon})")
            point_data = self.get_point_data(lat, lon, force_refresh=force_refresh)

            forecast_url = point_data.get("properties", {}).get("forecast")

            if not forecast_url:
                props = list(point_data.get("properties", {}).keys())
                logger.error(
                    f"Could not find forecast URL in point data. Available properties: {props}"
                )
                raise ValueError("Could not find forecast URL in point data")

            # Extract the forecast office ID and grid coordinates from the URL
            parts = forecast_url.split("/")
            office_id = parts[-3]
            grid_x, grid_y = parts[-2].split(",")

            # Generate cache key for the forecast
            cache_key = self._generate_cache_key(
                f"gridpoints/{office_id}/{grid_x},{grid_y}/forecast", {}
            )

            def fetch_data() -> Dict[str, Any]:
                self._rate_limit()
                try:
                    response = self._fetch_url(forecast_url)
                    return self._transform_forecast_data(response)
                except NoaaApiError:
                    raise
                except Exception as e:
                    logger.error(f"Error getting forecast for {lat},{lon}: {str(e)}")
                    error_msg = f"Unexpected error getting forecast: {e}"
                    raise NoaaApiError(
                        message=error_msg, error_type=NoaaApiError.UNKNOWN_ERROR, url=forecast_url
                    )

            return cast(
                Dict[str, Any], self._get_cached_or_fetch(cache_key, fetch_data, force_refresh)
            )
        except NoaaApiError:
            raise
        except Exception as e:
            logger.error(f"Error getting forecast: {str(e)}")
            raise ApiClientError(f"Unable to retrieve forecast data: {str(e)}")

    def get_hourly_forecast(self, lat: float, lon: float, **kwargs) -> Dict[str, Any]:
        """Get hourly forecast for a location."""
        force_refresh = kwargs.get("force_refresh", False)

        try:
            logger.info(f"Getting hourly forecast for coordinates: ({lat}, {lon})")
            point_data = self.get_point_data(lat, lon, force_refresh=force_refresh)

            forecast_hourly_url = point_data.get("properties", {}).get("forecastHourly")

            if not forecast_hourly_url:
                props = list(point_data.get("properties", {}).keys())
                logger.error(
                    f"Could not find hourly forecast URL in point data. Available properties: {props}"
                )
                raise ValueError("Could not find hourly forecast URL in point data")

            # Extract the forecast office ID and grid coordinates from the URL
            parts = forecast_hourly_url.split("/")
            office_id = parts[-4]
            grid_x, grid_y = parts[-3].split(",")

            # Generate cache key for the hourly forecast
            cache_key = self._generate_cache_key(
                f"gridpoints/{office_id}/{grid_x},{grid_y}/forecast/hourly", {}
            )

            def fetch_data() -> Dict[str, Any]:
                self._rate_limit()
                try:
                    response = self._fetch_url(forecast_hourly_url)
                    return self._transform_forecast_data(response)
                except NoaaApiError:
                    raise
                except Exception as e:
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

    def _transform_forecast_data(self, forecast_data: Any) -> Dict[str, Any]:
        """Transform forecast data from the generated client format."""
        if hasattr(forecast_data, "to_dict"):
            return cast(Dict[str, Any], forecast_data.to_dict())
        return cast(Dict[str, Any], forecast_data)

    def get_stations(self, lat: float, lon: float, force_refresh: bool = False) -> Dict[str, Any]:
        """Get observation stations for a location."""
        try:
            logger.info(f"Getting observation stations for coordinates: ({lat}, {lon})")
            point_data = self.get_point_data(lat, lon, force_refresh=force_refresh)

            stations_url = point_data.get("properties", {}).get("observationStations")

            if not stations_url:
                props = list(point_data.get("properties", {}).keys())
                logger.error(
                    f"Could not find observation stations URL in point data. Available properties: {props}"
                )
                raise ValueError("Could not find observation stations URL in point data")

            # Generate cache key for the stations
            cache_key = self._generate_cache_key(stations_url, {})

            def fetch_data() -> Dict[str, Any]:
                self._rate_limit()
                try:
                    response = self._fetch_url(stations_url)
                    return self._transform_stations_data(response)
                except Exception as e:
                    logger.error(f"Error getting stations for {lat},{lon}: {str(e)}")
                    raise NoaaApiError(
                        message=f"Error getting stations: {e}",
                        error_type=NoaaApiError.UNKNOWN_ERROR,
                        url=stations_url,
                    )

            logger.info(f"Retrieved observation stations URL: {stations_url}")
            return cast(
                Dict[str, Any], self._get_cached_or_fetch(cache_key, fetch_data, force_refresh)
            )
        except Exception as e:
            logger.error(f"Error getting observation stations: {str(e)}")
            raise ApiClientError(f"Unable to retrieve observation stations data: {str(e)}")

    def _transform_stations_data(self, stations_data: Any) -> Dict[str, Any]:
        """Transform stations data from the generated client format."""
        if isinstance(stations_data, dict):
            return stations_data
        if hasattr(stations_data, "to_dict"):
            return cast(Dict[str, Any], stations_data.to_dict())
        return cast(Dict[str, Any], stations_data)

    def identify_location_type(
        self, lat: float, lon: float, force_refresh: bool = False
    ) -> tuple[Optional[str], Optional[str]]:
        """Identify the type of location (county, state, etc.) for the given coordinates."""
        try:
            point_data = self.get_point_data(lat, lon, force_refresh=force_refresh)
            properties = point_data.get("properties", {})

            # Check for county zone
            county_url = properties.get("county")
            if county_url and isinstance(county_url, str) and "/county/" in county_url:
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
                forecast_id = forecast_zone_url.split("/forecast/")[1]
                logger.info(f"Identified location as forecast zone: {forecast_id}")
                return "forecast", forecast_id

            # Check for fire weather zone
            fire_zone_url = properties.get("fireWeatherZone")
            if fire_zone_url and isinstance(fire_zone_url, str) and "/fire/" in fire_zone_url:
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
        """Get alerts for a location."""
        try:
            logger.info(
                f"Getting alerts for coordinates: ({lat}, {lon}) with radius {radius} miles, precise_location={precise_location}"
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
                        response = self._make_api_request(
                            alerts_active_zone.sync, zone_id=location_id
                        )
                        return self._transform_alerts_data(response)
                    except NoaaApiError:
                        raise
                    except Exception as e:
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
                    f"Using point-radius search for alerts since location could not be determined: ({lat}, {lon}) with radius {radius} miles"
                )
                cache_key = self._generate_cache_key(
                    "alerts_point", {"lat": lat, "lon": lon, "radius": radius}
                )

                def fetch_data() -> Dict[str, Any]:
                    self._rate_limit()
                    try:
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
                    response = self._make_api_request(alerts_active.sync)
                    return self._transform_alerts_data(response)
                except NoaaApiError:
                    raise
                except Exception as e:
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
        """Transform alerts data from the generated client format."""
        if isinstance(alerts_data, dict):
            return alerts_data
        if hasattr(alerts_data, "to_dict"):
            return cast(Dict[str, Any], alerts_data.to_dict())
        return cast(Dict[str, Any], alerts_data)

    def get_discussion(self, lat: float, lon: float, force_refresh: bool = False) -> Optional[str]:
        """Get forecast discussion for a location."""
        try:
            logger.info(f"Getting forecast discussion for coordinates: ({lat}, {lon})")
            point_data = self.get_point_data(lat, lon, force_refresh=force_refresh)
            forecast_url = point_data.get("properties", {}).get("forecast")

            if not forecast_url:
                logger.warning("No forecast URL found in point data")
                return None

            parts = forecast_url.split("/")
            office_id = parts[-3]
            cache_key = self._generate_cache_key(f"products/types/AFD/locations/{office_id}", {})

            def fetch_data() -> Optional[str]:
                self._rate_limit()
                try:
                    products_url = f"{self.BASE_URL}/products/types/AFD/locations/{office_id}"
                    products_response = self._fetch_url(products_url)

                    if not products_response.get("@graph") or not products_response["@graph"]:
                        logger.warning(f"No AFD products found for {office_id}")
                        return None

                    latest_product = products_response["@graph"][0]
                    latest_product_id = latest_product.get("id")

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
        """Get a national product from a specific center."""
        try:
            endpoint = f"products/types/{product_type}/locations/{location}"
            cache_key = self._generate_cache_key(endpoint, {})

            def fetch_data() -> Optional[str]:
                self._rate_limit()
                try:
                    products_url = (
                        f"{self.BASE_URL}/products/types/{product_type}/locations/{location}"
                    )
                    products_response = self._fetch_url(products_url)

                    if not products_response.get("@graph") or not products_response["@graph"]:
                        logger.warning(f"No products found for {product_type}/{location}")
                        return None

                    latest_product = products_response["@graph"][0]
                    latest_product_id = latest_product.get("id")

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
        """Get national forecast data from various centers."""
        return {
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
