"""Shared test fixtures for AccessiWeather integration tests."""

import json
import os

# Add src to path for imports
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add src to path before importing project modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from accessiweather.api_client import NoaaApiClient  # noqa: E402
from accessiweather.api_wrapper import NoaaApiWrapper  # noqa: E402
from accessiweather.location import LocationManager  # noqa: E402
from accessiweather.notifications import WeatherNotifier  # noqa: E402
from accessiweather.openmeteo_client import OpenMeteoApiClient  # noqa: E402
from accessiweather.services.weather_service import WeatherService  # noqa: E402
from accessiweather.utils.temperature_utils import TemperatureUnit  # noqa: E402


@pytest.fixture
def temp_config_dir():
    """Create a temporary configuration directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def sample_config():
    """Sample configuration for testing."""
    return {
        "location": {"name": "Test City", "lat": 40.7128, "lon": -74.0060},
        "settings": {
            "update_interval": 30,
            "temperature_unit": TemperatureUnit.FAHRENHEIT.value,
            "data_source": "auto",
            "minimize_to_tray": False,
            "show_nationwide_location": True,
            "alert_radius": 50,
            "precise_location_alerts": False,
        },
        "api_settings": {"contact_info": "test@example.com"},
    }


@pytest.fixture
def config_file(temp_config_dir, sample_config):
    """Create a configuration file in temp directory."""
    config_path = os.path.join(temp_config_dir, "config.json")
    os.makedirs(temp_config_dir, exist_ok=True)

    with open(config_path, "w") as f:
        json.dump(sample_config, f)

    return config_path


@pytest.fixture
def mock_nws_client():
    """Mock NWS API client."""
    return MagicMock(spec=NoaaApiClient)


@pytest.fixture
def mock_nws_wrapper():
    """Mock NWS API wrapper."""
    return MagicMock(spec=NoaaApiWrapper)


@pytest.fixture
def mock_openmeteo_client():
    """Mock Open-Meteo API client."""
    return MagicMock(spec=OpenMeteoApiClient)


@pytest.fixture
def location_manager(temp_config_dir):
    """Create a LocationManager with temp config directory."""
    return LocationManager(config_dir=temp_config_dir)


@pytest.fixture
def weather_notifier(temp_config_dir):
    """Create a WeatherNotifier with temp config directory."""
    return WeatherNotifier(config_dir=temp_config_dir, enable_persistence=True)


@pytest.fixture
def weather_service(mock_nws_wrapper, mock_openmeteo_client, sample_config):
    """Create a WeatherService with mocked clients."""
    return WeatherService(
        nws_client=mock_nws_wrapper, openmeteo_client=mock_openmeteo_client, config=sample_config
    )


@pytest.fixture
def sample_nws_point_response():
    """Sample NWS point API response."""
    return {
        "properties": {
            "forecast": "https://api.weather.gov/gridpoints/PHI/50,75/forecast",
            "forecastHourly": "https://api.weather.gov/gridpoints/PHI/50,75/forecast/hourly",
            "forecastGridData": "https://api.weather.gov/gridpoints/PHI/50,75",
            "observationStations": "https://api.weather.gov/gridpoints/PHI/50,75/stations",
            "relativeLocation": {"properties": {"city": "Test City", "state": "PA"}},
            "gridId": "PHI",
            "gridX": 50,
            "gridY": 75,
        }
    }


@pytest.fixture
def sample_nws_forecast_response():
    """Sample NWS forecast API response."""
    return {
        "properties": {
            "periods": [
                {
                    "number": 1,
                    "name": "Today",
                    "startTime": "2024-01-01T12:00:00-05:00",
                    "endTime": "2024-01-01T18:00:00-05:00",
                    "isDaytime": True,
                    "temperature": 72,
                    "temperatureUnit": "F",
                    "temperatureTrend": None,
                    "windSpeed": "10 mph",
                    "windDirection": "SW",
                    "icon": "https://api.weather.gov/icons/land/day/few?size=medium",
                    "shortForecast": "Sunny",
                    "detailedForecast": "Sunny skies with light winds.",
                },
                {
                    "number": 2,
                    "name": "Tonight",
                    "startTime": "2024-01-01T18:00:00-05:00",
                    "endTime": "2024-01-02T06:00:00-05:00",
                    "isDaytime": False,
                    "temperature": 45,
                    "temperatureUnit": "F",
                    "temperatureTrend": None,
                    "windSpeed": "5 mph",
                    "windDirection": "W",
                    "icon": "https://api.weather.gov/icons/land/night/few?size=medium",
                    "shortForecast": "Clear",
                    "detailedForecast": "Clear skies overnight.",
                },
            ]
        }
    }


@pytest.fixture
def sample_nws_current_response():
    """Sample NWS current conditions response."""
    return {
        "properties": {
            "timestamp": "2024-01-01T12:00:00Z",
            "textDescription": "Sunny",
            "icon": "https://api.weather.gov/icons/land/day/few?size=medium",
            "presentWeather": [],
            "temperature": {"value": 22.2, "unitCode": "wmoUnit:degC"},
            "dewpoint": {"value": 10.0, "unitCode": "wmoUnit:degC"},
            "windDirection": {"value": 225, "unitCode": "wmoUnit:degree_(angle)"},
            "windSpeed": {"value": 4.47, "unitCode": "wmoUnit:m_s-1"},
            "barometricPressure": {"value": 101325, "unitCode": "wmoUnit:Pa"},
            "relativeHumidity": {"value": 65, "unitCode": "wmoUnit:percent"},
            "visibility": {"value": 16093, "unitCode": "wmoUnit:m"},
        }
    }


@pytest.fixture
def sample_nws_alerts_response():
    """Sample NWS alerts response."""
    return {
        "features": [
            {
                "properties": {
                    "id": "urn:oid:2.49.0.1.840.0.123456789",
                    "areaDesc": "Test County",
                    "geocode": {"FIPS6": ["42101"], "UGC": ["PAC101"]},
                    "affectedZones": ["https://api.weather.gov/zones/county/PAC101"],
                    "references": [],
                    "sent": "2024-01-01T12:00:00-05:00",
                    "effective": "2024-01-01T12:00:00-05:00",
                    "onset": "2024-01-01T15:00:00-05:00",
                    "expires": "2024-01-01T21:00:00-05:00",
                    "ends": "2024-01-01T21:00:00-05:00",
                    "status": "Actual",
                    "messageType": "Alert",
                    "category": "Met",
                    "severity": "Minor",
                    "certainty": "Likely",
                    "urgency": "Expected",
                    "event": "Winter Weather Advisory",
                    "sender": "w-nws.webmaster@noaa.gov",
                    "senderName": "NWS Philadelphia PA",
                    "headline": "Winter Weather Advisory issued January 1 at 12:00PM EST until January 1 at 9:00PM EST by NWS Philadelphia PA",
                    "description": "Light snow expected this afternoon and evening.",
                    "instruction": "Use caution while traveling.",
                    "response": "Prepare",
                    "parameters": {
                        "AWIPSidentifier": ["WSUPHI"],
                        "WMOidentifier": ["WWUS51 KPHI 011700"],
                        "NWSheadline": [
                            "WINTER WEATHER ADVISORY IN EFFECT FROM 3 PM THIS AFTERNOON TO 9 PM EST THIS EVENING"
                        ],
                        "BLOCKCHANNEL": ["EAS", "NWEM", "CMAS"],
                        "VTEC": ["/O.NEW.KPHI.WW.Y.0001.240101T2000Z-240102T0200Z/"],
                        "eventEndingTime": ["2024-01-01T21:00:00-05:00"],
                    },
                }
            }
        ]
    }


@pytest.fixture
def sample_openmeteo_current_response():
    """Sample Open-Meteo current weather response."""
    return {
        "latitude": 51.5074,
        "longitude": -0.1278,
        "generationtime_ms": 0.123,
        "utc_offset_seconds": 0,
        "timezone": "GMT",
        "timezone_abbreviation": "GMT",
        "elevation": 25.0,
        "current_units": {
            "time": "iso8601",
            "interval": "seconds",
            "temperature_2m": "°F",
            "relative_humidity_2m": "%",
            "apparent_temperature": "°F",
            "is_day": "",
            "precipitation": "inch",
            "weather_code": "wmo code",
            "pressure_msl": "hPa",
            "wind_speed_10m": "mph",
            "wind_direction_10m": "°",
        },
        "current": {
            "time": "2024-01-01T12:00",
            "interval": 900,
            "temperature_2m": 59.0,
            "relative_humidity_2m": 70,
            "apparent_temperature": 57.2,
            "is_day": 1,
            "precipitation": 0.0,
            "weather_code": 2,
            "pressure_msl": 1013.2,
            "wind_speed_10m": 6.2,
            "wind_direction_10m": 225,
        },
    }


@pytest.fixture
def sample_openmeteo_forecast_response():
    """Sample Open-Meteo forecast response."""
    return {
        "latitude": 51.5074,
        "longitude": -0.1278,
        "generationtime_ms": 0.456,
        "utc_offset_seconds": 0,
        "timezone": "GMT",
        "timezone_abbreviation": "GMT",
        "elevation": 25.0,
        "daily_units": {
            "time": "iso8601",
            "weather_code": "wmo code",
            "temperature_2m_max": "°F",
            "temperature_2m_min": "°F",
            "apparent_temperature_max": "°F",
            "apparent_temperature_min": "°F",
            "sunrise": "iso8601",
            "sunset": "iso8601",
            "precipitation_sum": "inch",
            "precipitation_probability_max": "%",
            "wind_speed_10m_max": "mph",
            "wind_gusts_10m_max": "mph",
            "wind_direction_10m_dominant": "°",
        },
        "daily": {
            "time": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "weather_code": [1, 2, 3],
            "temperature_2m_max": [64.4, 66.2, 59.0],
            "temperature_2m_min": [46.4, 48.2, 41.0],
            "apparent_temperature_max": [62.6, 64.4, 57.2],
            "apparent_temperature_min": [44.6, 46.4, 39.2],
            "sunrise": ["2024-01-01T07:30:00", "2024-01-02T07:30:00", "2024-01-03T07:31:00"],
            "sunset": ["2024-01-01T17:30:00", "2024-01-02T17:31:00", "2024-01-03T17:32:00"],
            "precipitation_sum": [0.0, 0.1, 0.3],
            "precipitation_probability_max": [0, 20, 60],
            "wind_speed_10m_max": [8.1, 10.3, 12.4],
            "wind_gusts_10m_max": [15.7, 18.6, 22.4],
            "wind_direction_10m_dominant": [225, 180, 270],
        },
    }


# Test coordinates for different scenarios
@pytest.fixture
def us_coordinates():
    """US coordinates (New York City)."""
    return (40.7128, -74.0060)


@pytest.fixture
def international_coordinates():
    """International coordinates (London, UK)."""
    return (51.5074, -0.1278)


@pytest.fixture
def edge_case_coordinates():
    """Edge case coordinates (near US border)."""
    return (49.0, -125.0)  # Near US-Canada border


# GUI testing fixtures
@pytest.fixture
def headless_environment():
    """Set up headless environment for GUI testing."""
    original_display = os.environ.get("DISPLAY")
    os.environ["DISPLAY"] = ""
    yield
    if original_display is not None:
        os.environ["DISPLAY"] = original_display
    elif "DISPLAY" in os.environ:
        del os.environ["DISPLAY"]


@pytest.fixture
def mock_wx_app():
    """Mock wxPython App for GUI testing."""
    with patch("wx.App") as mock_app:
        yield mock_app


# Performance testing fixtures
@pytest.fixture
def performance_timer():
    """Timer for performance testing."""
    import time

    class Timer:
        def __init__(self):
            self.start_time = None
            self.end_time = None

        def start(self):
            self.start_time = time.time()

        def stop(self):
            self.end_time = time.time()

        @property
        def elapsed(self):
            if self.start_time and self.end_time:
                return self.end_time - self.start_time
            return None

    return Timer()
