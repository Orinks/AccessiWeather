"""Sample API response fixtures for testing."""

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def sample_nws_point_response():
    """Sample NWS point response."""
    return {
        "properties": {
            "gridId": "PHI",
            "gridX": 31,
            "gridY": 70,
            "forecast": "https://api.weather.gov/gridpoints/PHI/31,70/forecast",
            "forecastHourly": "https://api.weather.gov/gridpoints/PHI/31,70/forecast/hourly",
            "forecastGridData": "https://api.weather.gov/gridpoints/PHI/31,70",
            "observationStations": "https://api.weather.gov/gridpoints/PHI/31,70/stations",
            "county": "https://api.weather.gov/zones/county/PAC101",
            "fireWeatherZone": "https://api.weather.gov/zones/fire/PAZ103",
            "timeZone": "America/New_York",
            "radarStation": "KDIX",
            "relativeLocation": {"properties": {"city": "Philadelphia", "state": "PA"}},
        }
    }


@pytest.fixture
def sample_nws_forecast_response():
    """Sample NWS forecast response."""
    return {
        "properties": {
            "periods": [
                {
                    "number": 1,
                    "name": "Tonight",
                    "startTime": "2024-01-15T18:00:00-05:00",
                    "endTime": "2024-01-16T06:00:00-05:00",
                    "isDaytime": False,
                    "temperature": 45,
                    "temperatureUnit": "F",
                    "temperatureTrend": None,
                    "windSpeed": "5 mph",
                    "windDirection": "NW",
                    "icon": "https://api.weather.gov/icons/land/night/few?size=medium",
                    "shortForecast": "Mostly Clear",
                    "detailedForecast": "Mostly clear, with a low around 45.",
                },
                {
                    "number": 2,
                    "name": "Tuesday",
                    "startTime": "2024-01-16T06:00:00-05:00",
                    "endTime": "2024-01-16T18:00:00-05:00",
                    "isDaytime": True,
                    "temperature": 65,
                    "temperatureUnit": "F",
                    "temperatureTrend": None,
                    "windSpeed": "10 mph",
                    "windDirection": "S",
                    "icon": "https://api.weather.gov/icons/land/day/sct?size=medium",
                    "shortForecast": "Partly Sunny",
                    "detailedForecast": "Partly sunny, with a high near 65.",
                },
            ]
        }
    }


@pytest.fixture
def sample_nws_alerts_response():
    """Sample NWS alerts response."""
    return {
        "features": [
            {
                "id": "https://api.weather.gov/alerts/urn:oid:2.49.0.1.840.0.123456789",
                "type": "Feature",
                "properties": {
                    "id": "urn:oid:2.49.0.1.840.0.123456789",
                    "areaDesc": "Philadelphia County",
                    "geocode": {"FIPS6": ["42101"], "UGC": ["PAC101"]},
                    "affectedZones": ["https://api.weather.gov/zones/county/PAC101"],
                    "references": [],
                    "sent": "2024-01-15T12:00:00-05:00",
                    "effective": "2024-01-15T12:00:00-05:00",
                    "onset": "2024-01-15T18:00:00-05:00",
                    "expires": "2024-01-16T06:00:00-05:00",
                    "ends": "2024-01-16T06:00:00-05:00",
                    "status": "Actual",
                    "messageType": "Alert",
                    "category": "Met",
                    "severity": "Minor",
                    "certainty": "Likely",
                    "urgency": "Expected",
                    "event": "Frost Advisory",
                    "sender": "w-nws.webmaster@noaa.gov",
                    "senderName": "NWS Philadelphia PA",
                    "headline": "Frost Advisory issued January 15 at 12:00PM EST until January 16 at 6:00AM EST by NWS Philadelphia PA",
                    "description": "Frost may kill sensitive outdoor vegetation if left uncovered.",
                    "instruction": "Take steps now to protect tender plants from the cold.",
                    "response": "Prepare",
                },
            }
        ]
    }


@pytest.fixture
def sample_nws_current_response():
    """Sample NWS current conditions response."""
    return {
        "properties": {
            "timestamp": "2024-01-15T18:53:00+00:00",
            "temperature": {"value": 7.2, "unitCode": "wmoUnit:degC"},
            "textDescription": "Clear",
            "relativeHumidity": {"value": 65},
            "windSpeed": {"value": 10, "unitCode": "wmoUnit:km_h-1"},
            "windDirection": {"value": 180},
            "barometricPressure": {"value": 101325, "unitCode": "wmoUnit:Pa"},
            "visibility": {"value": 16093, "unitCode": "wmoUnit:m"},
            "dewpoint": {"value": 1.1, "unitCode": "wmoUnit:degC"},
            "windChill": {"value": None, "unitCode": "wmoUnit:degC"},
            "heatIndex": {"value": None, "unitCode": "wmoUnit:degC"},
        }
    }
    """Sample NWS alerts response."""
    return {
        "features": [
            {
                "id": "https://api.weather.gov/alerts/urn:oid:2.49.0.1.840.0.123456789",
                "type": "Feature",
                "properties": {
                    "id": "urn:oid:2.49.0.1.840.0.123456789",
                    "areaDesc": "Philadelphia County",
                    "geocode": {"FIPS6": ["42101"], "UGC": ["PAC101"]},
                    "affectedZones": ["https://api.weather.gov/zones/county/PAC101"],
                    "references": [],
                    "sent": "2024-01-15T12:00:00-05:00",
                    "effective": "2024-01-15T12:00:00-05:00",
                    "onset": "2024-01-15T18:00:00-05:00",
                    "expires": "2024-01-16T06:00:00-05:00",
                    "ends": "2024-01-16T06:00:00-05:00",
                    "status": "Actual",
                    "messageType": "Alert",
                    "category": "Met",
                    "severity": "Minor",
                    "certainty": "Likely",
                    "urgency": "Expected",
                    "event": "Frost Advisory",
                    "sender": "w-nws.webmaster@noaa.gov",
                    "senderName": "NWS Philadelphia PA",
                    "headline": "Frost Advisory issued January 15 at 12:00PM EST until January 16 at 6:00AM EST by NWS Philadelphia PA",
                    "description": "Frost may kill sensitive outdoor vegetation if left uncovered.",
                    "instruction": "Take steps now to protect tender plants from the cold.",
                    "response": "Prepare",
                },
            }
        ]
    }


@pytest.fixture
def sample_openmeteo_response():
    """Sample Open-Meteo API response."""
    return {
        "latitude": 40.7128,
        "longitude": -74.0060,
        "generationtime_ms": 0.123,
        "utc_offset_seconds": -18000,
        "timezone": "America/New_York",
        "timezone_abbreviation": "EST",
        "elevation": 10.0,
        "current_units": {
            "time": "iso8601",
            "interval": "seconds",
            "temperature_2m": "°F",
            "relative_humidity_2m": "%",
            "apparent_temperature": "°F",
            "is_day": "",
            "precipitation": "inch",
            "rain": "inch",
            "showers": "inch",
            "snowfall": "inch",
            "weather_code": "wmo code",
            "cloud_cover": "%",
            "pressure_msl": "hPa",
            "surface_pressure": "hPa",
            "wind_speed_10m": "mph",
            "wind_direction_10m": "°",
            "wind_gusts_10m": "mph",
        },
        "current": {
            "time": "2024-01-15T18:00",
            "interval": 900,
            "temperature_2m": 45.0,
            "relative_humidity_2m": 65,
            "apparent_temperature": 42.0,
            "is_day": 0,
            "precipitation": 0.0,
            "rain": 0.0,
            "showers": 0.0,
            "snowfall": 0.0,
            "weather_code": 1,
            "cloud_cover": 25,
            "pressure_msl": 1013.2,
            "surface_pressure": 1012.8,
            "wind_speed_10m": 5.2,
            "wind_direction_10m": 315,
            "wind_gusts_10m": 8.1,
        },
        "daily_units": {
            "time": "iso8601",
            "weather_code": "wmo code",
            "temperature_2m_max": "°F",
            "temperature_2m_min": "°F",
            "apparent_temperature_max": "°F",
            "apparent_temperature_min": "°F",
            "sunrise": "iso8601",
            "sunset": "iso8601",
            "daylight_duration": "seconds",
            "sunshine_duration": "seconds",
            "uv_index_max": "",
            "uv_index_clear_sky_max": "",
            "precipitation_sum": "inch",
            "rain_sum": "inch",
            "showers_sum": "inch",
            "snowfall_sum": "inch",
            "precipitation_hours": "h",
            "precipitation_probability_max": "%",
            "wind_speed_10m_max": "mph",
            "wind_gusts_10m_max": "mph",
            "wind_direction_10m_dominant": "°",
            "shortwave_radiation_sum": "MJ/m²",
        },
        "daily": {
            "time": ["2024-01-15", "2024-01-16", "2024-01-17"],
            "weather_code": [1, 2, 3],
            "temperature_2m_max": [65.0, 68.0, 70.0],
            "temperature_2m_min": [45.0, 48.0, 50.0],
            "apparent_temperature_max": [62.0, 65.0, 67.0],
            "apparent_temperature_min": [42.0, 45.0, 47.0],
            "sunrise": ["2024-01-15T07:15", "2024-01-16T07:14", "2024-01-17T07:13"],
            "sunset": ["2024-01-15T17:30", "2024-01-16T17:31", "2024-01-17T17:32"],
            "daylight_duration": [36900.0, 37020.0, 37140.0],
            "sunshine_duration": [25200.0, 28800.0, 32400.0],
            "uv_index_max": [3.2, 3.5, 3.8],
            "uv_index_clear_sky_max": [4.1, 4.3, 4.5],
            "precipitation_sum": [0.0, 0.1, 0.0],
            "rain_sum": [0.0, 0.1, 0.0],
            "showers_sum": [0.0, 0.0, 0.0],
            "snowfall_sum": [0.0, 0.0, 0.0],
            "precipitation_hours": [0.0, 2.0, 0.0],
            "precipitation_probability_max": [10, 30, 15],
            "wind_speed_10m_max": [8.5, 12.3, 6.7],
            "wind_gusts_10m_max": [15.2, 18.9, 11.4],
            "wind_direction_10m_dominant": [315, 270, 225],
            "shortwave_radiation_sum": [8.2, 12.5, 15.8],
        },
    }


@pytest.fixture
def sample_openmeteo_error_response():
    """Sample Open-Meteo error response."""
    return {"error": True, "reason": "Invalid coordinates"}


@pytest.fixture
def sample_geocoding_response():
    """Sample geocoding response."""
    return {
        "name": "New York, NY, USA",
        "lat": 40.7128,
        "lon": -74.0060,
        "country_code": "us",
    }


@pytest.fixture
def mock_http_response():
    """Create a properly configured mock HTTP response object."""

    def _create_mock_response(status_code=200, json_data=None, text_data="", headers=None):
        """Create a mock response with proper attributes."""
        mock_response = MagicMock()
        mock_response.status_code = status_code
        mock_response.headers = headers or {}
        mock_response.text = text_data

        if json_data is not None:
            mock_response.json.return_value = json_data
        else:
            mock_response.json.side_effect = ValueError("No JSON object could be decoded")

        mock_response.raise_for_status.return_value = None
        return mock_response

    return _create_mock_response
