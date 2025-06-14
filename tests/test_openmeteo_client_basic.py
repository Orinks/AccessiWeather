"""Basic tests for the OpenMeteoApiClient class."""

from unittest.mock import MagicMock, patch

import pytest

from accessiweather.openmeteo_client import OpenMeteoApiClient

# Sample test data matching Open-Meteo API format
SAMPLE_CURRENT_WEATHER_DATA = {
    "latitude": 40.0,
    "longitude": -75.0,
    "generationtime_ms": 0.123,
    "utc_offset_seconds": -18000,
    "timezone": "America/New_York",
    "timezone_abbreviation": "EST",
    "elevation": 100.0,
    "current_units": {
        "time": "iso8601",
        "interval": "seconds",
        "temperature_2m": "°F",
        "relative_humidity_2m": "%",
        "apparent_temperature": "°F",
        "is_day": "",
        "precipitation": "inch",
        "weather_code": "wmo code",
        "cloud_cover": "%",
        "pressure_msl": "hPa",
        "surface_pressure": "hPa",
        "wind_speed_10m": "mph",
        "wind_direction_10m": "°",
        "wind_gusts_10m": "mph",
    },
    "current": {
        "time": "2024-01-01T12:00",
        "interval": 900,
        "temperature_2m": 72.0,
        "relative_humidity_2m": 65,
        "apparent_temperature": 75.0,
        "is_day": 1,
        "precipitation": 0.0,
        "weather_code": 1,
        "cloud_cover": 25,
        "pressure_msl": 1013.2,
        "surface_pressure": 1010.5,
        "wind_speed_10m": 8.5,
        "wind_direction_10m": 180,
        "wind_gusts_10m": 12.3,
    },
}

SAMPLE_FORECAST_DATA = {
    "latitude": 40.0,
    "longitude": -75.0,
    "generationtime_ms": 0.456,
    "utc_offset_seconds": -18000,
    "timezone": "America/New_York",
    "timezone_abbreviation": "EST",
    "elevation": 100.0,
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
        "temperature_2m_max": [75.0, 78.0, 72.0],
        "temperature_2m_min": [55.0, 58.0, 52.0],
        "apparent_temperature_max": [78.0, 82.0, 75.0],
        "apparent_temperature_min": [58.0, 61.0, 55.0],
        "sunrise": ["2024-01-01T07:15", "2024-01-02T07:15", "2024-01-03T07:16"],
        "sunset": ["2024-01-01T17:30", "2024-01-02T17:31", "2024-01-03T17:32"],
        "precipitation_sum": [0.0, 0.1, 0.0],
        "precipitation_probability_max": [10, 30, 5],
        "wind_speed_10m_max": [12.0, 15.0, 8.0],
        "wind_gusts_10m_max": [18.0, 22.0, 12.0],
        "wind_direction_10m_dominant": [180, 225, 270],
    },
}

SAMPLE_HOURLY_FORECAST_DATA = {
    "latitude": 40.0,
    "longitude": -75.0,
    "generationtime_ms": 0.789,
    "utc_offset_seconds": -18000,
    "timezone": "America/New_York",
    "timezone_abbreviation": "EST",
    "elevation": 100.0,
    "hourly_units": {
        "time": "iso8601",
        "temperature_2m": "°F",
        "relative_humidity_2m": "%",
        "apparent_temperature": "°F",
        "precipitation_probability": "%",
        "precipitation": "inch",
        "weather_code": "wmo code",
        "pressure_msl": "hPa",
        "surface_pressure": "hPa",
        "cloud_cover": "%",
        "wind_speed_10m": "mph",
        "wind_direction_10m": "°",
        "wind_gusts_10m": "mph",
        "is_day": "",
    },
    "hourly": {
        "time": ["2024-01-01T12:00", "2024-01-01T13:00", "2024-01-01T14:00"],
        "temperature_2m": [72.0, 74.0, 75.0],
        "relative_humidity_2m": [65, 62, 60],
        "apparent_temperature": [75.0, 77.0, 78.0],
        "precipitation_probability": [10, 15, 5],
        "precipitation": [0.0, 0.0, 0.0],
        "weather_code": [1, 1, 2],
        "pressure_msl": [1013.2, 1013.0, 1012.8],
        "surface_pressure": [1010.5, 1010.3, 1010.1],
        "cloud_cover": [25, 30, 35],
        "wind_speed_10m": [8.5, 9.0, 9.5],
        "wind_direction_10m": [180, 185, 190],
        "wind_gusts_10m": [12.3, 13.0, 13.5],
        "is_day": [1, 1, 1],
    },
}


@pytest.fixture
def openmeteo_client():
    """Create an OpenMeteoApiClient instance for testing."""
    return OpenMeteoApiClient(user_agent="TestClient", timeout=30.0, max_retries=3, retry_delay=1.0)


@pytest.mark.unit
def test_init_basic():
    """Test basic initialization."""
    client = OpenMeteoApiClient()

    assert client.user_agent == "AccessiWeather"
    assert client.timeout == 30.0
    assert client.max_retries == 3
    assert client.retry_delay == 1.0
    assert client.client is not None


@pytest.mark.unit
def test_init_custom_params():
    """Test initialization with custom parameters."""
    client = OpenMeteoApiClient(
        user_agent="CustomApp", timeout=60.0, max_retries=5, retry_delay=2.0
    )

    assert client.user_agent == "CustomApp"
    assert client.timeout == 60.0
    assert client.max_retries == 5
    assert client.retry_delay == 2.0


@pytest.mark.unit
def test_get_current_weather_success(openmeteo_client):
    """Test getting current weather successfully."""
    lat, lon = 40.0, -75.0

    with patch.object(openmeteo_client, "_make_request") as mock_request:
        mock_request.return_value = SAMPLE_CURRENT_WEATHER_DATA

        result = openmeteo_client.get_current_weather(lat, lon)

        assert result == SAMPLE_CURRENT_WEATHER_DATA
        call_args = mock_request.call_args[0][1]
        assert call_args["latitude"] == lat
        assert call_args["longitude"] == lon
        assert call_args["current"] == [
            "temperature_2m",
            "relative_humidity_2m",
            "apparent_temperature",
            "is_day",
            "precipitation",
            "weather_code",
            "cloud_cover",
            "pressure_msl",
            "surface_pressure",
            "wind_speed_10m",
            "wind_direction_10m",
            "wind_gusts_10m",
        ]
        assert call_args["temperature_unit"] == "fahrenheit"
        assert call_args["wind_speed_unit"] == "mph"
        assert call_args["precipitation_unit"] == "inch"
        assert call_args["timezone"] == "auto"


@pytest.mark.unit
def test_get_current_weather_metric_units(openmeteo_client):
    """Test getting current weather with metric units."""
    lat, lon = 40.0, -75.0

    with patch.object(openmeteo_client, "_make_request") as mock_request:
        mock_request.return_value = SAMPLE_CURRENT_WEATHER_DATA

        openmeteo_client.get_current_weather(lat, lon, temperature_unit="celsius")

        call_args = mock_request.call_args[0][1]
        assert call_args["temperature_unit"] == "celsius"
        assert call_args["wind_speed_unit"] == "kmh"
        assert call_args["precipitation_unit"] == "mm"


@pytest.mark.unit
def test_get_forecast_success(openmeteo_client):
    """Test getting forecast successfully."""
    lat, lon = 40.0, -75.0

    with patch.object(openmeteo_client, "_make_request") as mock_request:
        mock_request.return_value = SAMPLE_FORECAST_DATA

        result = openmeteo_client.get_forecast(lat, lon)

        assert result == SAMPLE_FORECAST_DATA
        call_args = mock_request.call_args[0][1]
        assert call_args["latitude"] == lat
        assert call_args["longitude"] == lon
        assert call_args["forecast_days"] == 7  # default


@pytest.mark.unit
def test_get_forecast_custom_days(openmeteo_client):
    """Test getting forecast with custom number of days."""
    lat, lon = 40.0, -75.0

    with patch.object(openmeteo_client, "_make_request") as mock_request:
        mock_request.return_value = SAMPLE_FORECAST_DATA

        openmeteo_client.get_forecast(lat, lon, days=10)

        call_args = mock_request.call_args[0][1]
        assert call_args["forecast_days"] == 10


@pytest.mark.unit
def test_get_forecast_max_days_limit(openmeteo_client):
    """Test that forecast days are limited to API maximum."""
    lat, lon = 40.0, -75.0

    with patch.object(openmeteo_client, "_make_request") as mock_request:
        mock_request.return_value = SAMPLE_FORECAST_DATA

        openmeteo_client.get_forecast(lat, lon, days=20)  # Over limit

        call_args = mock_request.call_args[0][1]
        assert call_args["forecast_days"] == 16  # API max


@pytest.mark.unit
def test_get_hourly_forecast_success(openmeteo_client):
    """Test getting hourly forecast successfully."""
    lat, lon = 40.0, -75.0

    with patch.object(openmeteo_client, "_make_request") as mock_request:
        mock_request.return_value = SAMPLE_HOURLY_FORECAST_DATA

        result = openmeteo_client.get_hourly_forecast(lat, lon)

        assert result == SAMPLE_HOURLY_FORECAST_DATA
        call_args = mock_request.call_args[0][1]
        assert call_args["latitude"] == lat
        assert call_args["longitude"] == lon
        assert call_args["forecast_hours"] == 48  # default


@pytest.mark.unit
def test_get_hourly_forecast_custom_hours(openmeteo_client):
    """Test getting hourly forecast with custom hours."""
    lat, lon = 40.0, -75.0

    with patch.object(openmeteo_client, "_make_request") as mock_request:
        mock_request.return_value = SAMPLE_HOURLY_FORECAST_DATA

        openmeteo_client.get_hourly_forecast(lat, lon, hours=72)

        call_args = mock_request.call_args[0][1]
        assert call_args["forecast_hours"] == 72


@pytest.mark.unit
def test_get_hourly_forecast_max_hours_limit(openmeteo_client):
    """Test that hourly forecast hours are limited to API maximum."""
    lat, lon = 40.0, -75.0

    with patch.object(openmeteo_client, "_make_request") as mock_request:
        mock_request.return_value = SAMPLE_HOURLY_FORECAST_DATA

        openmeteo_client.get_hourly_forecast(lat, lon, hours=500)  # Over limit

        call_args = mock_request.call_args[0][1]
        assert call_args["forecast_hours"] == 384  # API max
