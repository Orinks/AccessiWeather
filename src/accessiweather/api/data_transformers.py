"""Data transformation utilities for NOAA API responses.

This module contains methods for transforming API responses from the generated
client format to the format expected by the application.
"""

from typing import Any, Dict, cast


class ApiDataTransformers:
    """Transforms API response data to application-expected formats."""

    @staticmethod
    def transform_point_data(point_data: Any) -> Dict[str, Any]:
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

    @staticmethod
    def transform_forecast_data(forecast_data: Any) -> Dict[str, Any]:
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

    @staticmethod
    def transform_stations_data(stations_data: Any) -> Dict[str, Any]:
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

    @staticmethod
    def transform_observation_data(observation_data: Any) -> Dict[str, Any]:
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

    @staticmethod
    def transform_alerts_data(alerts_data: Any) -> Dict[str, Any]:
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
