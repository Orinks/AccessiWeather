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
from accessiweather.geocoding import GeocodingService  # noqa: E402
from accessiweather.location import LocationManager  # noqa: E402
from accessiweather.notifications import WeatherNotifier  # noqa: E402
from accessiweather.openmeteo_client import OpenMeteoApiClient  # noqa: E402
from accessiweather.services.weather_service import WeatherService  # noqa: E402
from accessiweather.utils.temperature_utils import TemperatureUnit  # noqa: E402

# Import mock data - using relative imports
try:
    from .mock_data import (  # noqa: E402
        MOCK_NWS_ALERTS_DATA,
        MOCK_NWS_CURRENT_CONDITIONS,
        MOCK_NWS_FORECAST_DATA,
        MOCK_NWS_POINT_DATA,
        MOCK_OPENMETEO_CURRENT_WEATHER,
        MOCK_OPENMETEO_FORECAST,
    )
except ImportError:
    # Fallback to inline mock data if import fails
    MOCK_NWS_CURRENT_CONDITIONS = {
        "properties": {
            "temperature": {"value": 20.0, "unitCode": "wmoUnit:degC"},
            "textDescription": "Partly Cloudy",
            "relativeHumidity": {"value": 65},
            "windSpeed": {"value": 10, "unitCode": "wmoUnit:km_h-1"},
            "windDirection": {"value": 180},
            "barometricPressure": {"value": 101325, "unitCode": "wmoUnit:Pa"},
        }
    }

    MOCK_NWS_FORECAST_DATA = {
        "properties": {
            "periods": [
                {
                    "name": "Today",
                    "temperature": 75,
                    "temperatureUnit": "F",
                    "shortForecast": "Sunny",
                    "detailedForecast": "Sunny with a high near 75.",
                    "windSpeed": "10 mph",
                    "windDirection": "SW",
                }
            ]
        }
    }

    MOCK_NWS_ALERTS_DATA = {
        "features": [
            {
                "properties": {
                    "headline": "Heat Advisory",
                    "description": "Dangerous heat conditions expected.",
                    "instruction": "Stay hydrated and avoid prolonged sun exposure.",
                    "severity": "Moderate",
                    "event": "Heat Advisory",
                    "urgency": "Expected",
                    "certainty": "Likely",
                }
            }
        ]
    }

    MOCK_NWS_POINT_DATA = {
        "properties": {
            "gridId": "PHI",
            "gridX": 50,
            "gridY": 75,
            "forecast": "https://api.weather.gov/gridpoints/PHI/50,75/forecast",
            "county": "https://api.weather.gov/zones/county/PAC091",
        }
    }

    MOCK_OPENMETEO_CURRENT_WEATHER = {
        "current": {
            "temperature_2m": 68.0,
            "weather_code": 2,
            "relative_humidity_2m": 65,
            "wind_speed_10m": 8.5,
            "wind_direction_10m": 180,
            "pressure_msl": 1013.2,
        }
    }

    MOCK_OPENMETEO_FORECAST = {
        "daily": {
            "time": ["2024-01-01", "2024-01-02", "2024-01-03"],
            "weather_code": [1, 2, 3],
            "temperature_2m_max": [75.0, 78.0, 72.0],
            "temperature_2m_min": [55.0, 58.0, 52.0],
        }
    }


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
def mock_geocoding_location():
    """Create a mock location object for geocoding responses."""
    location = MagicMock()
    location.latitude = 40.7128
    location.longitude = -74.0060
    location.address = "New York, NY, USA"
    location.raw = {"address": {"country_code": "us"}}
    return location


@pytest.fixture
def mock_geocoding_service():
    """Mock GeocodingService with common responses."""
    mock_service = MagicMock(spec=GeocodingService)

    # Mock geocode_address to return US coordinates
    mock_service.geocode_address.return_value = (40.7128, -74.0060, "New York, NY, USA")

    # Mock validate_coordinates to return True for US locations, False for others
    def validate_coordinates_side_effect(lat, lon, us_only=None):
        # US coordinates (rough bounds)
        if 24.0 <= lat <= 49.0 and -125.0 <= lon <= -66.0:
            return True
        # Special case for test coordinates
        if lat == 40.7128 and lon == -74.0060:  # NYC
            return True
        if lat == 34.0522 and lon == -118.2437:  # LA
            return True
        return False

    mock_service.validate_coordinates.side_effect = validate_coordinates_side_effect

    # Mock suggest_locations to return sample suggestions
    mock_service.suggest_locations.return_value = [
        "New York, NY, USA",
        "Newark, NJ, USA",
        "New Haven, CT, USA",
    ]

    # Mock utility methods
    mock_service.is_zip_code.return_value = False
    mock_service.format_zip_code.return_value = "12345, USA"

    return mock_service


@pytest.fixture
def mock_nominatim():
    """Mock Nominatim geocoder for direct usage."""
    mock_nominatim = MagicMock()

    # Create a mock location for geocode responses
    mock_location = MagicMock()
    mock_location.latitude = 40.7128
    mock_location.longitude = -74.0060
    mock_location.address = "New York, NY, USA"
    mock_location.raw = {"address": {"country_code": "us"}}

    mock_nominatim.geocode.return_value = mock_location
    mock_nominatim.reverse.return_value = mock_location

    return mock_nominatim


@pytest.fixture(autouse=True)
def mock_all_geocoding():
    """Automatically mock all geocoding API calls across all tests."""
    with patch("accessiweather.geocoding.Nominatim") as mock_nominatim_class:
        # Create mock instance
        mock_nominatim_instance = MagicMock()
        mock_nominatim_class.return_value = mock_nominatim_instance

        # Create mock location response
        mock_location = MagicMock()
        mock_location.latitude = 40.7128
        mock_location.longitude = -74.0060
        mock_location.address = "New York, NY, USA"
        mock_location.raw = {"address": {"country_code": "us"}}

        # Configure geocode method
        mock_nominatim_instance.geocode.return_value = mock_location

        # Configure reverse method for coordinate validation
        def reverse_side_effect(coords, **kwargs):
            lat, lon = coords
            # Return US location for US coordinates, non-US for others
            if 24.0 <= lat <= 49.0 and -125.0 <= lon <= -66.0:
                mock_us_location = MagicMock()
                mock_us_location.raw = {"address": {"country_code": "us"}}
                return mock_us_location
            else:
                mock_intl_location = MagicMock()
                mock_intl_location.raw = {"address": {"country_code": "gb"}}
                return mock_intl_location

        mock_nominatim_instance.reverse.side_effect = reverse_side_effect

        yield mock_nominatim_instance


@pytest.fixture
def location_manager(temp_config_dir):
    """Create a LocationManager with temp config directory and mocked geocoding."""
    # The geocoding is already mocked by the autouse fixture
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


# Test to verify geocoding is mocked
@pytest.fixture
def verify_no_real_geocoding_calls():
    """Verify that no real geocoding API calls are made during tests."""
    # This fixture can be used to ensure tests don't make real API calls
    # The autouse mock_all_geocoding fixture should prevent any real calls
    pass


@pytest.fixture
def mock_weather_apis():
    """Mock all weather API calls for unit tests with comprehensive responses."""
    with (
        patch("accessiweather.api_wrapper.NoaaApiWrapper") as mock_nws,
        patch("accessiweather.openmeteo_client.OpenMeteoApiClient") as mock_openmeteo,
        patch("accessiweather.api_client.NoaaApiClient") as mock_nws_client,
    ):
        # Configure NWS wrapper mock
        nws_instance = MagicMock()
        mock_nws.return_value = nws_instance

        # Configure NWS client mock
        nws_client_instance = MagicMock()
        mock_nws_client.return_value = nws_client_instance

        # Configure Open-Meteo mock
        openmeteo_instance = MagicMock()
        mock_openmeteo.return_value = openmeteo_instance

        # Set up comprehensive NWS responses using mock data
        nws_instance.get_current_conditions.return_value = MOCK_NWS_CURRENT_CONDITIONS
        nws_instance.get_forecast.return_value = MOCK_NWS_FORECAST_DATA
        nws_instance.get_alerts.return_value = MOCK_NWS_ALERTS_DATA
        nws_instance.get_point_data.return_value = MOCK_NWS_POINT_DATA

        # Set up NWS client responses
        nws_client_instance.get_current_conditions.return_value = MOCK_NWS_CURRENT_CONDITIONS
        nws_client_instance.get_forecast.return_value = MOCK_NWS_FORECAST_DATA
        nws_client_instance.get_alerts.return_value = MOCK_NWS_ALERTS_DATA
        nws_client_instance.get_point_data.return_value = MOCK_NWS_POINT_DATA

        # Set up comprehensive Open-Meteo responses using mock data
        openmeteo_instance.get_current_weather.return_value = MOCK_OPENMETEO_CURRENT_WEATHER
        openmeteo_instance.get_forecast.return_value = MOCK_OPENMETEO_FORECAST

        yield {
            "nws": nws_instance,
            "nws_client": nws_client_instance,
            "openmeteo": openmeteo_instance,
        }


@pytest.fixture
def mock_web_scraping():
    """Mock web scraping for national discussion data."""
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>Mock weather discussion</body></html>"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        yield mock_get


@pytest.fixture
def mock_weather_apis_error():
    """Mock weather APIs to simulate error conditions."""
    with (
        patch("accessiweather.api_wrapper.NoaaApiWrapper") as mock_nws,
        patch("accessiweather.openmeteo_client.OpenMeteoApiClient") as mock_openmeteo,
    ):
        # Configure NWS mock to raise errors
        nws_instance = MagicMock()
        mock_nws.return_value = nws_instance
        nws_instance.get_current_conditions.side_effect = Exception("NWS API Error")
        nws_instance.get_forecast.side_effect = Exception("NWS API Error")
        nws_instance.get_alerts.side_effect = Exception("NWS API Error")

        # Configure Open-Meteo mock to raise errors
        openmeteo_instance = MagicMock()
        mock_openmeteo.return_value = openmeteo_instance
        openmeteo_instance.get_current_weather.side_effect = Exception("Open-Meteo API Error")
        openmeteo_instance.get_forecast.side_effect = Exception("Open-Meteo API Error")

        yield {"nws": nws_instance, "openmeteo": openmeteo_instance}


@pytest.fixture
def mock_weather_apis_timeout():
    """Mock weather APIs to simulate timeout conditions."""
    with (
        patch("accessiweather.api_wrapper.NoaaApiWrapper") as mock_nws,
        patch("accessiweather.openmeteo_client.OpenMeteoApiClient") as mock_openmeteo,
    ):
        from requests.exceptions import Timeout

        from accessiweather.openmeteo_client import OpenMeteoNetworkError

        # Configure NWS mock to raise timeout
        nws_instance = MagicMock()
        mock_nws.return_value = nws_instance
        nws_instance.get_current_conditions.side_effect = Timeout("Request timed out")
        nws_instance.get_forecast.side_effect = Timeout("Request timed out")
        nws_instance.get_alerts.side_effect = Timeout("Request timed out")

        # Configure Open-Meteo mock to raise timeout
        openmeteo_instance = MagicMock()
        mock_openmeteo.return_value = openmeteo_instance
        openmeteo_instance.get_current_weather.side_effect = OpenMeteoNetworkError(
            "Request timed out"
        )
        openmeteo_instance.get_forecast.side_effect = OpenMeteoNetworkError("Request timed out")

        yield {"nws": nws_instance, "openmeteo": openmeteo_instance}


@pytest.fixture
def verify_no_real_api_calls():
    """Verify that no real API calls are made during tests."""
    with (
        patch("requests.get") as mock_requests_get,
        patch("httpx.get") as mock_httpx_get,
        patch("httpx.Client.get") as mock_httpx_client_get,
    ):
        # Configure mocks to raise if called
        mock_requests_get.side_effect = AssertionError("Real requests.get call detected!")
        mock_httpx_get.side_effect = AssertionError("Real httpx.get call detected!")
        mock_httpx_client_get.side_effect = AssertionError("Real httpx.Client.get call detected!")

        yield {
            "requests_get": mock_requests_get,
            "httpx_get": mock_httpx_get,
            "httpx_client_get": mock_httpx_client_get,
        }
