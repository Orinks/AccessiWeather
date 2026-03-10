"""
Weather data operations for NWS API wrapper.

This module handles weather data retrieval including current conditions,
forecasts, hourly forecasts, and observation stations.
"""

from __future__ import annotations

import logging
import math
from datetime import UTC, datetime
from typing import Any, cast

from accessiweather.api_client import ApiClientError, NoaaApiError
from accessiweather.weather_gov_api_client.api.default import station_observation_latest

logger = logging.getLogger(__name__)

STATION_SELECTION_STRATEGIES = {
    "nearest",
    "major_airport_preferred",
    "freshest_observation",
    "hybrid_default",
}


class NwsWeatherData:
    """Handles NWS weather data operations."""

    def __init__(self, wrapper_instance):
        """
        Initialize with reference to the main wrapper.

        Args:
        ----
            wrapper_instance: The main NwsApiWrapper instance

        """
        self.wrapper = wrapper_instance

    def get_current_conditions(self, lat: float, lon: float, **kwargs) -> dict[str, Any]:
        """
        Get current weather conditions for a location from an observation station.

        Args:
        ----
            lat: Latitude
            lon: Longitude
            **kwargs: Additional arguments including force_refresh and station_selection_strategy

        Returns:
        -------
            Current conditions data dictionary

        Raises:
        ------
            ApiClientError: For client-related errors

        """
        force_refresh = kwargs.get("force_refresh", False)
        strategy = kwargs.get("station_selection_strategy", "hybrid_default")

        try:
            logger.info(f"Getting current conditions for coordinates: ({lat}, {lon})")

            stations_data = self.get_stations(lat, lon, force_refresh=force_refresh)

            if "features" not in stations_data or not stations_data["features"]:
                logger.error("No observation stations found")
                raise ValueError("No observation stations found")

            station = self._select_station(
                lat=lat,
                lon=lon,
                stations_data=stations_data,
                strategy=strategy,
                force_refresh=force_refresh,
            )
            station_id = station["properties"]["stationIdentifier"]

            logger.info(
                f"Using station {station_id} with strategy '{strategy}' for current conditions"
            )

            observation = self._fetch_station_observation(station_id, force_refresh=force_refresh)
            return self._transform_observation_data(observation)
        except Exception as e:
            logger.error(f"Error getting current conditions: {str(e)}")
            raise ApiClientError(f"Unable to retrieve current conditions data: {str(e)}") from e

    def _fetch_station_observation(
        self, station_id: str, force_refresh: bool = False
    ) -> dict[str, Any]:
        """Fetch latest observation for a station, using wrapper cache."""
        cache_key = self.wrapper._generate_cache_key(
            f"stations/{station_id}/observations/latest", {}
        )

        def fetch_data() -> dict[str, Any]:
            self.wrapper._rate_limit()
            try:
                response = self.wrapper.core_client.make_api_request(
                    station_observation_latest.sync, station_id=station_id
                )
                return self._transform_observation_data(response)
            except NoaaApiError:
                raise
            except Exception as e:
                logger.error(f"Error getting current conditions for station {station_id}: {str(e)}")
                url = (
                    f"{self.wrapper.core_client.BASE_URL}/stations/{station_id}/observations/latest"
                )
                error_msg = f"Unexpected error getting current conditions: {e}"
                raise NoaaApiError(
                    message=error_msg, error_type=NoaaApiError.UNKNOWN_ERROR, url=url
                ) from e

        return cast(
            dict[str, Any],
            self.wrapper._get_cached_or_fetch(cache_key, fetch_data, force_refresh),
        )

    def _select_station(
        self,
        lat: float,
        lon: float,
        stations_data: dict[str, Any],
        strategy: str,
        force_refresh: bool,
    ) -> dict[str, Any]:
        """Select station according to configured strategy with resilient fallbacks."""
        features = stations_data.get("features", [])
        if not features:
            raise ValueError("No observation stations found")

        if strategy not in STATION_SELECTION_STRATEGIES:
            logger.warning(
                "Unknown station strategy '%s', falling back to hybrid_default", strategy
            )
            strategy = "hybrid_default"

        if strategy == "nearest":
            return features[0]

        top_n = features[:5]
        nearest_station = features[0]
        nearest_distance = self._distance_km(lat, lon, nearest_station)

        if strategy == "major_airport_preferred":
            preferred_radius_km = max(25.0, min(80.0, nearest_distance + 35.0))
            major_candidates = [
                st
                for st in top_n
                if self._is_major_station(st)
                and self._distance_km(lat, lon, st) <= preferred_radius_km
            ]
            if major_candidates:
                return min(major_candidates, key=lambda st: self._distance_km(lat, lon, st))
            return nearest_station

        observations = self._collect_candidate_observations(
            lat, lon, top_n, force_refresh=force_refresh
        )

        if strategy == "freshest_observation":
            freshest = self._pick_freshest(observations)
            if freshest:
                return freshest["station"]
            usable = self._pick_nearest_usable(observations)
            return usable["station"] if usable else nearest_station

        # hybrid_default: favor reliable major stations and fresh observations,
        # but keep a distance guardrail to avoid stations that are too far away.
        guardrail_km = max(20.0, min(100.0, nearest_distance + 30.0))
        guarded = [o for o in observations if o["distance_km"] <= guardrail_km and o["usable"]]

        major_fresh = [
            o
            for o in guarded
            if o["is_major"] and o["age_minutes"] is not None and o["age_minutes"] <= 90
        ]
        if major_fresh:
            return min(major_fresh, key=lambda o: (o["age_minutes"], o["distance_km"]))["station"]

        freshest_guarded = self._pick_freshest(guarded)
        if freshest_guarded:
            return freshest_guarded["station"]

        nearest_usable = self._pick_nearest_usable(observations)
        return nearest_usable["station"] if nearest_usable else nearest_station

    def _collect_candidate_observations(
        self, lat: float, lon: float, stations: list[dict[str, Any]], force_refresh: bool
    ) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        for station in stations:
            station_id = station.get("properties", {}).get("stationIdentifier")
            if not station_id:
                continue
            try:
                obs = self._fetch_station_observation(station_id, force_refresh=force_refresh)
            except Exception as exc:
                logger.warning("Failed fetching observation for station %s: %s", station_id, exc)
                obs = {}

            candidates.append(
                {
                    "station": station,
                    "observation": obs,
                    "distance_km": self._distance_km(lat, lon, station),
                    "is_major": self._is_major_station(station),
                    "usable": self._observation_has_usable_data(obs),
                    "age_minutes": self._observation_age_minutes(obs),
                }
            )
        return candidates

    def _pick_freshest(self, candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
        valid = [c for c in candidates if c.get("usable") and c.get("age_minutes") is not None]
        if not valid:
            return None
        return min(valid, key=lambda c: (c["age_minutes"], c["distance_km"]))

    def _pick_nearest_usable(self, candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
        usable = [c for c in candidates if c.get("usable")]
        if not usable:
            return None
        return min(usable, key=lambda c: c["distance_km"])

    def _distance_km(self, lat: float, lon: float, station: dict[str, Any]) -> float:
        geometry = station.get("geometry", {})
        coords = geometry.get("coordinates") or []
        if len(coords) < 2:
            return float("inf")
        station_lon, station_lat = coords[0], coords[1]

        # Haversine distance.
        r = 6371.0
        lat1 = math.radians(lat)
        lon1 = math.radians(lon)
        lat2 = math.radians(station_lat)
        lon2 = math.radians(station_lon)

        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return r * c

    def _is_major_station(self, station: dict[str, Any]) -> bool:
        props = station.get("properties", {})
        station_id = str(props.get("stationIdentifier", "")).upper()
        name = str(props.get("name", "")).lower()

        major_name_markers = (
            "international",
            "intl",
            "regional airport",
            "air force base",
            "afb",
            "asos",
            "awos",
        )
        if any(marker in name for marker in major_name_markers):
            return True

        # Common major airport station IDs are 4-letter ICAO style.
        return len(station_id) == 4 and station_id.isalpha() and station_id[:1] in {"K", "C", "P"}

    def _observation_has_usable_data(self, observation: dict[str, Any]) -> bool:
        props = observation.get("properties", {}) if isinstance(observation, dict) else {}
        if not props:
            return False

        temp = props.get("temperature", {}).get("value")
        dewpoint = props.get("dewpoint", {}).get("value")
        wind_speed = props.get("windSpeed", {}).get("value")
        text_desc = props.get("textDescription")
        return any(v is not None for v in (temp, dewpoint, wind_speed, text_desc))

    def _observation_age_minutes(self, observation: dict[str, Any]) -> float | None:
        props = observation.get("properties", {}) if isinstance(observation, dict) else {}
        timestamp = props.get("timestamp")
        if not timestamp:
            return None
        try:
            dt = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return max(0.0, (datetime.now(UTC) - dt.astimezone(UTC)).total_seconds() / 60.0)
        except Exception:
            return None

    def get_forecast(self, lat: float, lon: float, **kwargs) -> dict[str, Any]:
        """
        Get forecast for a location.

        Args:
        ----
            lat: Latitude
            lon: Longitude
            **kwargs: Additional arguments including force_refresh

        Returns:
        -------
            Forecast data dictionary

        Raises:
        ------
            ApiClientError: For client-related errors
            NoaaApiError: For API-related errors

        """
        force_refresh = kwargs.get("force_refresh", False)

        try:
            logger.info(f"Getting forecast for coordinates: ({lat}, {lon})")
            point_data = self.wrapper.point_location.get_point_data(
                lat, lon, force_refresh=force_refresh
            )

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
            cache_key = self.wrapper._generate_cache_key(
                f"gridpoints/{office_id}/{grid_x},{grid_y}/forecast", {}
            )

            def fetch_data() -> dict[str, Any]:
                self.wrapper._rate_limit()
                try:
                    response = self.wrapper._fetch_url(forecast_url)
                    return self._transform_forecast_data(response)
                except NoaaApiError:
                    raise
                except Exception as e:
                    logger.error(f"Error getting forecast for {lat},{lon}: {str(e)}")
                    error_msg = f"Unexpected error getting forecast: {e}"
                    raise NoaaApiError(
                        message=error_msg, error_type=NoaaApiError.UNKNOWN_ERROR, url=forecast_url
                    ) from e

            return cast(
                dict[str, Any],
                self.wrapper._get_cached_or_fetch(cache_key, fetch_data, force_refresh),
            )
        except NoaaApiError:
            raise
        except Exception as e:
            logger.error(f"Error getting forecast: {str(e)}")
            raise ApiClientError(f"Unable to retrieve forecast data: {str(e)}") from e

    def get_hourly_forecast(self, lat: float, lon: float, **kwargs) -> dict[str, Any]:
        """
        Get hourly forecast for a location.

        Args:
        ----
            lat: Latitude
            lon: Longitude
            **kwargs: Additional arguments including force_refresh

        Returns:
        -------
            Hourly forecast data dictionary

        Raises:
        ------
            ApiClientError: For client-related errors

        """
        force_refresh = kwargs.get("force_refresh", False)

        try:
            logger.info(f"Getting hourly forecast for coordinates: ({lat}, {lon})")
            point_data = self.wrapper.point_location.get_point_data(
                lat, lon, force_refresh=force_refresh
            )

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
            cache_key = self.wrapper._generate_cache_key(
                f"gridpoints/{office_id}/{grid_x},{grid_y}/forecast/hourly", {}
            )

            def fetch_data() -> dict[str, Any]:
                self.wrapper._rate_limit()
                try:
                    response = self.wrapper._fetch_url(forecast_hourly_url)
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
                    ) from e

            return cast(
                dict[str, Any],
                self.wrapper._get_cached_or_fetch(cache_key, fetch_data, force_refresh),
            )
        except Exception as e:
            logger.error(f"Error getting hourly forecast: {str(e)}")
            raise ApiClientError(f"Unable to retrieve hourly forecast data: {str(e)}") from e

    def get_stations(self, lat: float, lon: float, force_refresh: bool = False) -> dict[str, Any]:
        """
        Get observation stations for a location.

        Args:
        ----
            lat: Latitude
            lon: Longitude
            force_refresh: Whether to force refresh cached data

        Returns:
        -------
            Stations data dictionary

        Raises:
        ------
            ApiClientError: For client-related errors

        """
        try:
            logger.info(f"Getting observation stations for coordinates: ({lat}, {lon})")
            point_data = self.wrapper.point_location.get_point_data(
                lat, lon, force_refresh=force_refresh
            )

            stations_url = point_data.get("properties", {}).get("observationStations")

            if not stations_url:
                props = list(point_data.get("properties", {}).keys())
                logger.error(
                    f"Could not find observation stations URL in point data. Available properties: {props}"
                )
                raise ValueError("Could not find observation stations URL in point data")

            # Generate cache key for the stations
            cache_key = self.wrapper._generate_cache_key(stations_url, {})

            def fetch_data() -> dict[str, Any]:
                self.wrapper._rate_limit()
                try:
                    response = self.wrapper._fetch_url(stations_url)
                    return self._transform_stations_data(response)
                except Exception as e:
                    logger.error(f"Error getting stations for {lat},{lon}: {str(e)}")
                    raise NoaaApiError(
                        message=f"Error getting stations: {e}",
                        error_type=NoaaApiError.UNKNOWN_ERROR,
                        url=stations_url,
                    ) from e

            logger.info(f"Retrieved observation stations URL: {stations_url}")
            return cast(
                dict[str, Any],
                self.wrapper._get_cached_or_fetch(cache_key, fetch_data, force_refresh),
            )
        except Exception as e:
            logger.error(f"Error getting observation stations: {str(e)}")
            raise ApiClientError(f"Unable to retrieve observation stations data: {str(e)}") from e

    def _transform_observation_data(self, observation_data: Any) -> dict[str, Any]:
        """Transform observation data from the generated client format."""
        if isinstance(observation_data, dict):
            return observation_data
        if hasattr(observation_data, "to_dict"):
            return cast(dict[str, Any], observation_data.to_dict())
        return cast(dict[str, Any], observation_data)

    def _transform_forecast_data(self, forecast_data: Any) -> dict[str, Any]:
        """Transform forecast data from the generated client format."""
        if hasattr(forecast_data, "to_dict"):
            return cast(dict[str, Any], forecast_data.to_dict())
        return cast(dict[str, Any], forecast_data)

    def _transform_stations_data(self, stations_data: Any) -> dict[str, Any]:
        """Transform stations data from the generated client format."""
        if isinstance(stations_data, dict):
            return stations_data
        if hasattr(stations_data, "to_dict"):
            return cast(dict[str, Any], stations_data.to_dict())
        return cast(dict[str, Any], stations_data)
