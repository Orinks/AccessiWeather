"""
Tests for weather data fetching in the simplified AccessiWeather application.

This module tests the weather data fetching functionality that was fixed,
including the wind direction formatting bug and API integration.
"""

from unittest.mock import MagicMock, patch

import pytest

from accessiweather.display import WeatherPresenter
from accessiweather.models import Location
from accessiweather.utils import convert_wind_direction_to_cardinal
from accessiweather.weather_client import WeatherClient
from accessiweather.weather_client_parsers import (
    OPEN_METEO_WEATHER_CODE_DESCRIPTIONS,
    weather_code_to_description,
)


class TestWeatherDataFetching:
    """Test weather data fetching functionality."""

    @pytest.mark.asyncio
    async def test_nws_api_response_parsing(self):
        """Test parsing of NWS API responses."""
        client = WeatherClient()
        location = Location("Philadelphia, PA", 39.9526, -75.1652)

        # Mock NWS API responses
        grid_response = {
            "properties": {
                "observationStations": "https://api.weather.gov/gridpoints/PHI/49,75/stations",
                "forecast": "https://api.weather.gov/gridpoints/PHI/49,75/forecast",
            }
        }

        stations_response = {"features": [{"properties": {"stationIdentifier": "KPHL"}}]}

        observation_response = {
            "properties": {
                "temperature": {"value": 23.9},  # Celsius
                "textDescription": "Partly Cloudy",
                "relativeHumidity": {"value": 65},
                "windSpeed": {"value": 4.47},  # m/s
                "windDirection": {"value": 330},  # degrees
                "barometricPressure": {"value": 101325},  # pascals
            }
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = mock_client.return_value.__aenter__.return_value

            # Set up the mock responses in order
            mock_client_instance.get.side_effect = [
                # Grid point response
                MagicMock(status_code=200, json=lambda: grid_response),
                # Stations response
                MagicMock(status_code=200, json=lambda: stations_response),
                # Observation response
                MagicMock(status_code=200, json=lambda: observation_response),
            ]

            # Test current conditions parsing
            current = await client._get_nws_current_conditions(location)

            assert current is not None
            assert current.temperature_c == 23.9
            assert abs(current.temperature_f - 75.0) < 0.1  # Should be ~75°F
            assert current.condition == "Partly Cloudy"
            assert current.humidity == 65
            assert current.wind_direction == 330  # Should be numeric

    def test_wind_direction_formatting_fix(self):
        """Test the wind direction formatting fix."""
        # Test the utility function directly
        assert convert_wind_direction_to_cardinal(330) == "NNW"
        assert convert_wind_direction_to_cardinal(270) == "W"
        assert convert_wind_direction_to_cardinal(90) == "E"
        assert convert_wind_direction_to_cardinal(0) == "N"

        # Test edge cases
        assert convert_wind_direction_to_cardinal(None) == "N/A"
        assert convert_wind_direction_to_cardinal(360) == "N"  # Should wrap around

    def test_presenter_handles_numeric_wind_direction(self):
        """Test that the presenter correctly handles numeric wind directions."""
        from accessiweather.models import AppSettings, CurrentConditions

        settings = AppSettings()
        presenter = WeatherPresenter(settings)
        location = Location("Test City", 40.0, -75.0)

        # Create conditions with numeric wind direction (the bug we fixed)
        conditions = CurrentConditions(
            temperature_f=75.0,
            condition="Clear",
            humidity=50,
            wind_speed_mph=15.0,
            wind_direction=330,  # This is numeric, not string
        )

        presentation = presenter.present_current(conditions, location)

        assert presentation is not None
        wind_metric = next((m for m in presentation.metrics if m.label == "Wind"), None)
        assert wind_metric is not None
        assert "NNW" in wind_metric.value
        assert "15" in wind_metric.value
        assert presentation.description == "Clear"

    @pytest.mark.asyncio
    async def test_openmeteo_fallback(self):
        """Test OpenMeteo API fallback functionality."""
        client = WeatherClient()
        location = Location("Test Location", 40.0, -75.0)

        # Mock OpenMeteo response
        openmeteo_response = {
            "current": {
                "temperature_2m": 75.0,  # Fahrenheit
                "relative_humidity_2m": 60,
                "weather_code": 1,  # Mainly clear
                "wind_speed_10m": 10.0,  # mph
                "wind_direction_10m": 270,  # degrees
                "pressure_msl": 1013.25,  # hPa
            }
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = mock_client.return_value.__aenter__.return_value
            mock_client_instance.get.return_value = MagicMock(
                status_code=200, json=lambda: openmeteo_response
            )

            current = await client._get_openmeteo_current_conditions(location)

            assert current is not None
            assert current.temperature_f == 75.0
            assert current.humidity == 60
            assert current.wind_speed_mph == 10.0
            assert current.wind_direction == "W"
            assert "Mainly clear" in current.condition

    @pytest.mark.asyncio
    async def test_weather_client_error_handling(self):
        """Test weather client error handling."""
        client = WeatherClient()
        location = Location("Test Location", 40.0, -75.0)

        with patch("httpx.AsyncClient") as mock_client:
            # Simulate network error
            mock_client_instance = mock_client.return_value.__aenter__.return_value
            mock_client_instance.get.side_effect = Exception("Network error")

            # Should not crash, should return weather data with empty fields
            weather_data = await client.get_weather_data(location)

            assert weather_data is not None
            assert weather_data.location == location
            # Should have empty/default data due to error
            assert weather_data.current is not None
            assert weather_data.forecast is not None
            assert weather_data.alerts is not None

    def test_weather_code_conversion(self):
        """Test OpenMeteo weather code conversion."""
        client = WeatherClient()

        # Test various weather codes
        assert client._weather_code_to_description(0) == "Clear sky"
        assert client._weather_code_to_description(1) == "Mainly clear"
        assert client._weather_code_to_description(61) == "Slight rain"
        assert client._weather_code_to_description(80) == "Slight rain showers"
        assert client._weather_code_to_description(81) == "Moderate rain showers"
        assert client._weather_code_to_description(82) == "Violent rain showers"
        assert client._weather_code_to_description(85) == "Slight snow showers"
        assert client._weather_code_to_description(86) == "Heavy snow showers"
        assert client._weather_code_to_description(95) == "Thunderstorm"
        assert "Weather code" in client._weather_code_to_description(999)  # Unknown code

    @pytest.mark.parametrize(
        ("code", "expected"), tuple(OPEN_METEO_WEATHER_CODE_DESCRIPTIONS.items())
    )
    def test_weather_code_conversion_covers_all_known_codes(self, code, expected):
        """Ensure every known Open-Meteo weather code has a friendly description."""
        assert weather_code_to_description(code) == expected
        # API sometimes delivers codes as strings; ensure those work too.
        assert weather_code_to_description(str(code)) == expected

    def test_weather_code_conversion_accepts_string_input(self):
        """WeatherClient helper should gracefully handle string weather codes."""
        client = WeatherClient()
        assert client._weather_code_to_description("80") == "Slight rain showers"

    def test_unit_conversions(self):
        """Test unit conversion utilities in weather client."""
        client = WeatherClient()

        # Test m/s to mph conversion
        assert abs(client._convert_mps_to_mph(10.0) - 22.37) < 0.1
        assert client._convert_mps_to_mph(None) is None

        # Test pascals to inches conversion
        assert abs(client._convert_pa_to_inches(101325) - 29.92) < 0.1
        assert client._convert_pa_to_inches(None) is None

        # Test F to C conversion
        assert abs(client._convert_f_to_c(75.0) - 23.89) < 0.1
        assert client._convert_f_to_c(None) is None

    @pytest.mark.asyncio
    async def test_full_weather_data_integration(self):
        """Test full weather data fetching integration."""
        client = WeatherClient()
        location = Location("Philadelphia, PA", 39.9526, -75.1652)

        # Mock successful NWS responses
        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = mock_client.return_value.__aenter__.return_value

            # Mock grid, stations, observation, forecast, and alerts responses
            mock_responses = [
                # Grid response
                MagicMock(
                    status_code=200,
                    json=lambda: {
                        "properties": {
                            "observationStations": "https://api.weather.gov/stations",
                            "forecast": "https://api.weather.gov/forecast",
                        }
                    },
                ),
                # Stations response
                MagicMock(
                    status_code=200,
                    json=lambda: {"features": [{"properties": {"stationIdentifier": "KPHL"}}]},
                ),
                # Observation response
                MagicMock(
                    status_code=200,
                    json=lambda: {
                        "properties": {
                            "temperature": {"value": 23.9},
                            "textDescription": "Clear",
                            "windDirection": {"value": 330},
                        }
                    },
                ),
                # Forecast response (for grid lookup)
                MagicMock(
                    status_code=200,
                    json=lambda: {
                        "properties": {
                            "observationStations": "https://api.weather.gov/stations",
                            "forecast": "https://api.weather.gov/forecast",
                        }
                    },
                ),
                # Actual forecast response
                MagicMock(
                    status_code=200,
                    json=lambda: {
                        "properties": {
                            "periods": [
                                {
                                    "name": "Today",
                                    "temperature": 75,
                                    "temperatureUnit": "F",
                                    "shortForecast": "Sunny",
                                }
                            ]
                        }
                    },
                ),
                # Alerts response
                MagicMock(status_code=200, json=lambda: {"features": []}),
            ]

            mock_client_instance.get.side_effect = mock_responses

            # Test full weather data fetch
            weather_data = await client.get_weather_data(location)

            assert weather_data is not None
            assert weather_data.location == location
            assert weather_data.has_any_data()

            # Test that current conditions were parsed
            if weather_data.current:
                assert weather_data.current.condition == "Clear"
                assert weather_data.current.wind_direction == 330


# Test that can be run with briefcase dev --test
def test_weather_fetching_components_available():
    """Test that all weather fetching components are available."""
    # Test imports
    from accessiweather.utils import convert_wind_direction_to_cardinal
    from accessiweather.weather_client import WeatherClient

    # Test instantiation
    client = WeatherClient()
    assert client is not None

    # Test utility function
    direction = convert_wind_direction_to_cardinal(330)
    assert direction == "NNW"


def test_wind_direction_bug_is_fixed():
    """Test that the wind direction formatting bug is fixed."""
    from accessiweather.display import WeatherPresenter
    from accessiweather.models import AppSettings, CurrentConditions, Location

    # This test verifies the specific bug that was causing crashes
    settings = AppSettings()
    presenter = WeatherPresenter(settings)
    location = Location("Test", 40.0, -75.0)

    # Create conditions with numeric wind direction (the problematic case)
    conditions = CurrentConditions(
        temperature_f=75.0,
        condition="Clear",
        wind_direction=330,  # This is an int, not a string
    )

    # This should not crash (it used to crash before the fix)
    try:
        presentation = presenter.present_current(conditions, location)
        assert presentation is not None
        wind_metric = next((m for m in presentation.metrics if m.label == "Wind"), None)
        assert wind_metric is not None
        assert "NNW" in wind_metric.value or "W at" in wind_metric.value
        success = True
    except Exception:
        success = False

    assert success, "Wind direction presentation should not fail with numeric input"
