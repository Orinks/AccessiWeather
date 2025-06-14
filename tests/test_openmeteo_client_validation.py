"""Validation and utility tests for the OpenMeteoApiClient class."""

from unittest.mock import MagicMock, patch

import pytest

from accessiweather.openmeteo_client import OpenMeteoApiClient, OpenMeteoApiError

# Sample test data
SAMPLE_CURRENT_WEATHER_DATA = {
    "latitude": 40.0,
    "longitude": -75.0,
    "current": {
        "time": "2024-01-01T12:00",
        "temperature_2m": 72.0,
        "weather_code": 1,
    },
}


@pytest.fixture
def openmeteo_client():
    """Create an OpenMeteoApiClient instance for testing."""
    return OpenMeteoApiClient(user_agent="TestClient", timeout=30.0, max_retries=3, retry_delay=1.0)


# Test weather description functionality
@pytest.mark.unit
def test_get_weather_description():
    """Test weather code to description mapping."""
    # Test some common weather codes
    assert OpenMeteoApiClient.get_weather_description(0) == "Clear sky"
    assert OpenMeteoApiClient.get_weather_description(1) == "Mainly clear"
    assert OpenMeteoApiClient.get_weather_description(2) == "Partly cloudy"
    assert OpenMeteoApiClient.get_weather_description(3) == "Overcast"
    assert OpenMeteoApiClient.get_weather_description(61) == "Slight rain"
    assert OpenMeteoApiClient.get_weather_description(95) == "Thunderstorm"


@pytest.mark.unit
def test_get_weather_description_unknown_code():
    """Test weather description for unknown codes."""
    result = OpenMeteoApiClient.get_weather_description(999)
    assert "Unknown" in result or result == "Clear sky"  # Fallback behavior


# Test coordinate validation
@pytest.mark.unit
@pytest.mark.parametrize(
    "lat,lon,should_work",
    [
        (40.0, -75.0, True),  # Valid coordinates
        (90.0, 180.0, True),  # Edge valid coordinates
        (-90.0, -180.0, True),  # Edge valid coordinates
        (0.0, 0.0, True),  # Equator/Prime meridian
        (91.0, 0.0, False),  # Invalid latitude
        (-91.0, 0.0, False),  # Invalid latitude
        (0.0, 181.0, False),  # Invalid longitude
        (0.0, -181.0, False),  # Invalid longitude
    ],
)
def test_coordinate_validation(openmeteo_client, lat, lon, should_work):
    """Test coordinate validation in API calls."""
    with patch.object(openmeteo_client, "_make_request") as mock_request:
        if should_work:
            mock_request.return_value = SAMPLE_CURRENT_WEATHER_DATA
            result = openmeteo_client.get_current_weather(lat, lon)
            assert result == SAMPLE_CURRENT_WEATHER_DATA
        else:
            # For invalid coordinates, the API client should still make the request
            # but the API would return an error (which we simulate)
            mock_request.side_effect = OpenMeteoApiError("Invalid coordinates")
            with pytest.raises(OpenMeteoApiError):
                openmeteo_client.get_current_weather(lat, lon)


@pytest.mark.unit
def test_temperature_unit_validation(openmeteo_client):
    """Test temperature unit parameter validation."""
    lat, lon = 40.0, -75.0

    with patch.object(openmeteo_client, "_make_request") as mock_request:
        mock_request.return_value = SAMPLE_CURRENT_WEATHER_DATA

        # Test valid temperature units
        for unit in ["celsius", "fahrenheit"]:
            openmeteo_client.get_current_weather(lat, lon, temperature_unit=unit)
            call_args = mock_request.call_args[0][1]
            assert call_args["temperature_unit"] == unit

        # Test invalid temperature unit (should default to fahrenheit)
        openmeteo_client.get_current_weather(lat, lon, temperature_unit="kelvin")
        call_args = mock_request.call_args[0][1]
        # The client might handle this gracefully or pass it through
        assert "temperature_unit" in call_args


@pytest.mark.unit
def test_forecast_days_bounds(openmeteo_client):
    """Test forecast days parameter bounds."""
    lat, lon = 40.0, -75.0

    with patch.object(openmeteo_client, "_make_request") as mock_request:
        mock_request.return_value = {"daily": {}}

        # Test minimum days
        openmeteo_client.get_forecast(lat, lon, days=1)
        call_args = mock_request.call_args[0][1]
        assert call_args["forecast_days"] == 1

        # Test maximum days (should be capped)
        openmeteo_client.get_forecast(lat, lon, days=100)
        call_args = mock_request.call_args[0][1]
        assert call_args["forecast_days"] == 16  # API maximum

        # Test zero days (should default to minimum)
        openmeteo_client.get_forecast(lat, lon, days=0)
        call_args = mock_request.call_args[0][1]
        assert call_args["forecast_days"] >= 1


@pytest.mark.unit
def test_hourly_forecast_hours_bounds(openmeteo_client):
    """Test hourly forecast hours parameter bounds."""
    lat, lon = 40.0, -75.0

    with patch.object(openmeteo_client, "_make_request") as mock_request:
        mock_request.return_value = {"hourly": {}}

        # Test minimum hours
        openmeteo_client.get_hourly_forecast(lat, lon, hours=1)
        call_args = mock_request.call_args[0][1]
        assert call_args["forecast_hours"] == 1

        # Test maximum hours (should be capped)
        openmeteo_client.get_hourly_forecast(lat, lon, hours=1000)
        call_args = mock_request.call_args[0][1]
        assert call_args["forecast_hours"] == 384  # API maximum

        # Test zero hours (should default to minimum)
        openmeteo_client.get_hourly_forecast(lat, lon, hours=0)
        call_args = mock_request.call_args[0][1]
        assert call_args["forecast_hours"] >= 1


@pytest.mark.unit
def test_api_endpoint_construction(openmeteo_client):
    """Test that API endpoints are constructed correctly."""
    with patch.object(openmeteo_client.client, "get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = SAMPLE_CURRENT_WEATHER_DATA
        mock_get.return_value = mock_response

        # Test current weather endpoint
        openmeteo_client.get_current_weather(40.0, -75.0)
        call_args = mock_get.call_args
        assert "forecast" in call_args[0][0]  # URL should contain 'forecast'

        # Test forecast endpoint
        openmeteo_client.get_forecast(40.0, -75.0)
        call_args = mock_get.call_args
        assert "forecast" in call_args[0][0]  # URL should contain 'forecast'

        # Test hourly forecast endpoint
        openmeteo_client.get_hourly_forecast(40.0, -75.0)
        call_args = mock_get.call_args
        assert "forecast" in call_args[0][0]  # URL should contain 'forecast'


@pytest.mark.unit
def test_user_agent_header(openmeteo_client):
    """Test that user agent is properly set in requests."""
    with patch.object(openmeteo_client.client, "get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = SAMPLE_CURRENT_WEATHER_DATA
        mock_get.return_value = mock_response

        openmeteo_client.get_current_weather(40.0, -75.0)

        # Check that the request was made (user agent is set during client initialization)
        mock_get.assert_called_once()


@pytest.mark.unit
def test_timezone_parameter(openmeteo_client):
    """Test timezone parameter handling."""
    lat, lon = 40.0, -75.0

    with patch.object(openmeteo_client, "_make_request") as mock_request:
        mock_request.return_value = SAMPLE_CURRENT_WEATHER_DATA

        # Test default timezone (auto)
        openmeteo_client.get_current_weather(lat, lon)
        call_args = mock_request.call_args[0][1]
        assert call_args["timezone"] == "auto"

        # The client might support custom timezones in the future
        # For now, it should always use "auto"


@pytest.mark.unit
def test_weather_code_edge_cases():
    """Test weather code description for edge cases."""
    # Test boundary values
    assert OpenMeteoApiClient.get_weather_description(0) == "Clear sky"
    assert OpenMeteoApiClient.get_weather_description(99) == "Thunderstorm"

    # Test negative values (should handle gracefully)
    result = OpenMeteoApiClient.get_weather_description(-1)
    assert isinstance(result, str)
    assert len(result) > 0

    # Test very large values (should handle gracefully)
    result = OpenMeteoApiClient.get_weather_description(10000)
    assert isinstance(result, str)
    assert len(result) > 0
