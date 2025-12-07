"""
Tests for weather data fetching in the simplified AccessiWeather application.

This module tests the weather data fetching functionality that was fixed,
including the wind direction formatting bug and API integration.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from accessiweather.display import WeatherPresenter
from accessiweather.models import (
    CurrentConditions,
    Forecast,
    HourlyForecast,
    Location,
    WeatherAlerts,
)
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
    async def test_nws_current_conditions_uses_station_with_data(self):
        """The client should walk the station list until it finds usable observations."""
        client = WeatherClient()
        location = Location("Conrad, MT", 48.1703, -111.9461)

        grid_response = {
            "properties": {
                "observationStations": "https://api.weather.gov/gridpoints/TFX/82,179/stations",
            }
        }
        stations_response = {
            "features": [
                {
                    "properties": {
                        "stationIdentifier": "COAM8",
                        "distance": {"value": 14056.0},
                    }
                },
                {
                    "properties": {
                        "stationIdentifier": "KCTB",
                        "distance": {"value": 45000.0},
                    }
                },
            ]
        }
        recent_iso = (datetime.now(UTC) - timedelta(minutes=15)).isoformat().replace("+00:00", "Z")
        empty_observation = {
            "properties": {
                "timestamp": recent_iso,
                "temperature": {"value": 2.0, "qualityControl": "Z"},
                "textDescription": "",
                "windSpeed": {"value": 3.708, "unitCode": "wmoUnit:km_h-1", "qualityControl": "V"},
            }
        }
        usable_observation = {
            "properties": {
                "timestamp": recent_iso,
                "temperature": {"value": 6.0, "unitCode": "wmoUnit:degC", "qualityControl": "V"},
                "textDescription": "Clear",
                "windSpeed": {"value": 5.544, "unitCode": "wmoUnit:km_h-1", "qualityControl": "V"},
                "windDirection": {"value": 130, "qualityControl": "V"},
                "barometricPressure": {"value": 101862.57, "qualityControl": "V"},
            }
        }

        def _make_response(payload):
            response = MagicMock()
            response.status_code = 200
            response.json = lambda: payload
            response.raise_for_status = MagicMock()
            return response

        called_urls: list[str] = []

        def _mock_get(url, *args, **kwargs):
            called_urls.append(url)
            if url.endswith("/points/48.1703,-111.9461"):
                return _make_response(grid_response)
            if url == "https://api.weather.gov/gridpoints/TFX/82,179/stations":
                return _make_response(stations_response)
            if url.endswith("/stations/COAM8/observations/latest"):
                return _make_response(empty_observation)
            if url.endswith("/stations/KCTB/observations/latest"):
                return _make_response(usable_observation)
            raise AssertionError(f"Unexpected URL requested: {url}")

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = mock_client.return_value.__aenter__.return_value
            mock_client_instance.get.side_effect = _mock_get

            current = await client._get_nws_current_conditions(location)
            await client.close()

        assert current is not None
        assert current.has_data()
        assert pytest.approx(current.temperature_c or 0.0, rel=1e-2) == 6.0
        assert current.condition == "Clear"
        assert "https://api.weather.gov/stations/KCTB/observations/latest" in called_urls
        assert "https://api.weather.gov/stations/COAM8/observations/latest" not in called_urls, (
            "Raw station should be skipped when airport data is available"
        )

    @pytest.mark.asyncio
    async def test_nws_station_selection_falls_back_after_invalid_airport(self):
        """If the preferred airport report is invalid, use the next station with good QC."""
        client = WeatherClient()
        location = Location("Fallback Town", 40.0, -105.0)

        grid_response = {
            "properties": {
                "observationStations": "https://api.weather.gov/gridpoints/DEN/42,60/stations",
            }
        }
        stations_response = {
            "features": [
                {
                    "properties": {
                        "stationIdentifier": "KDEN",
                        "distance": {"value": 31000.0},
                    }
                },
                {
                    "properties": {
                        "stationIdentifier": "BRRM8",
                        "distance": {"value": 25000.0},
                    }
                },
            ]
        }

        recent_iso = (datetime.now(UTC) - timedelta(minutes=20)).isoformat().replace("+00:00", "Z")
        invalid_airport_observation = {
            "properties": {
                "timestamp": recent_iso,
                "temperature": {"value": 18.0, "unitCode": "wmoUnit:degC", "qualityControl": "Z"},
                "textDescription": "",
                "windSpeed": {"value": 5.0, "unitCode": "wmoUnit:km_h-1", "qualityControl": "V"},
            }
        }
        valid_mesonet_observation = {
            "properties": {
                "timestamp": recent_iso,
                "temperature": {"value": 13.0, "unitCode": "wmoUnit:degC", "qualityControl": "V"},
                "textDescription": "Mostly sunny",
                "windSpeed": {"value": 10.0, "unitCode": "wmoUnit:km_h-1", "qualityControl": "V"},
                "relativeHumidity": {"value": 40.0, "qualityControl": "V"},
            }
        }

        def _make_response(payload):
            response = MagicMock()
            response.status_code = 200
            response.json = lambda: payload
            response.raise_for_status = MagicMock()
            return response

        request_log: list[str] = []

        def _mock_get(url, *args, **kwargs):
            request_log.append(url)
            if url.endswith("/points/40.0,-105.0"):
                return _make_response(grid_response)
            if url == "https://api.weather.gov/gridpoints/DEN/42,60/stations":
                return _make_response(stations_response)
            if url.endswith("/stations/KDEN/observations/latest"):
                return _make_response(invalid_airport_observation)
            if url.endswith("/stations/BRRM8/observations/latest"):
                return _make_response(valid_mesonet_observation)
            raise AssertionError(f"Unexpected URL requested: {url}")

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = mock_client.return_value.__aenter__.return_value
            mock_client_instance.get.side_effect = _mock_get

            current = await client._get_nws_current_conditions(location)
            await client.close()

        assert current is not None
        assert pytest.approx(current.temperature_c or 0.0, rel=1e-2) == 13.0
        assert "Mostly sunny" in (current.condition or "")
        assert "https://api.weather.gov/stations/KDEN/observations/latest" in request_log
        assert "https://api.weather.gov/stations/BRRM8/observations/latest" in request_log

    @pytest.mark.asyncio
    async def test_nws_station_selection_ignores_stale_reports(self):
        """Stations with stale timestamps should be skipped in favour of fresher data."""
        client = WeatherClient()
        location = Location("Stale City", 35.0, -97.0)

        grid_response = {
            "properties": {
                "observationStations": "https://api.weather.gov/gridpoints/OUN/56,80/stations",
            }
        }
        stations_response = {
            "features": [
                {
                    "properties": {
                        "stationIdentifier": "KOKC",
                        "distance": {"value": 12000.0},
                    }
                },
                {
                    "properties": {
                        "stationIdentifier": "KOUN",
                        "distance": {"value": 18000.0},
                    }
                },
            ]
        }

        stale_iso = (datetime.now(UTC) - timedelta(hours=4)).isoformat().replace("+00:00", "Z")
        fresh_iso = (datetime.now(UTC) - timedelta(minutes=10)).isoformat().replace("+00:00", "Z")
        stale_observation = {
            "properties": {
                "timestamp": stale_iso,
                "temperature": {"value": 30.0, "unitCode": "wmoUnit:degC", "qualityControl": "V"},
                "textDescription": "Hot",
                "windSpeed": {"value": 8.0, "unitCode": "wmoUnit:km_h-1", "qualityControl": "V"},
            }
        }
        fresh_observation = {
            "properties": {
                "timestamp": fresh_iso,
                "temperature": {"value": 24.0, "unitCode": "wmoUnit:degC", "qualityControl": "V"},
                "textDescription": "Warm",
                "windSpeed": {"value": 12.0, "unitCode": "wmoUnit:km_h-1", "qualityControl": "V"},
            }
        }

        def _make_response(payload):
            response = MagicMock()
            response.status_code = 200
            response.json = lambda: payload
            response.raise_for_status = MagicMock()
            return response

        def _mock_get(url, *args, **kwargs):
            if url.endswith("/points/35.0,-97.0"):
                return _make_response(grid_response)
            if url == "https://api.weather.gov/gridpoints/OUN/56,80/stations":
                return _make_response(stations_response)
            if url.endswith("/stations/KOKC/observations/latest"):
                return _make_response(stale_observation)
            if url.endswith("/stations/KOUN/observations/latest"):
                return _make_response(fresh_observation)
            raise AssertionError(f"Unexpected URL requested: {url}")

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = mock_client.return_value.__aenter__.return_value
            mock_client_instance.get.side_effect = _mock_get

            current = await client._get_nws_current_conditions(location)
            await client.close()

        assert current is not None
        assert pytest.approx(current.temperature_c or 0.0, rel=1e-2) == 24.0
        assert current.condition == "Warm"

    @pytest.mark.asyncio
    async def test_nws_explicit_source_does_not_augment_with_openmeteo(self):
        """
        When NWS is explicitly selected, missing fields are NOT filled from Open-Meteo.

        This test verifies that explicit source selection respects user preference.
        When a user explicitly selects NWS as their data source, only NWS data is used
        even if some fields are missing. No fallback or augmentation from other sources.
        """
        client = WeatherClient(data_source="nws")
        location = Location("Data Gap", 40.0, -75.0)

        # NWS returns current conditions with only wind_speed_mph (missing temperature)
        nws_current = CurrentConditions(wind_speed_mph=7.0)
        forecast = Forecast(periods=[])
        alerts = WeatherAlerts(alerts=[])
        hourly = HourlyForecast(periods=[])
        discussion = "Sample discussion"

        client._fetch_nws_data = AsyncMock(
            return_value=(nws_current, forecast, discussion, alerts, hourly)
        )
        openmeteo_current = CurrentConditions(
            temperature_f=42.0,
            temperature_c=5.5556,
            condition="Clear sky",
            humidity=51,
        )
        client._get_openmeteo_current_conditions = AsyncMock(return_value=openmeteo_current)
        client._enrich_with_sunrise_sunset = AsyncMock()
        client._enrich_with_nws_discussion = AsyncMock()
        client._enrich_with_visual_crossing_alerts = AsyncMock()
        client._populate_environmental_metrics = AsyncMock()
        client._merge_international_alerts = AsyncMock()
        client._enrich_with_aviation_data = AsyncMock()
        client._apply_trend_insights = MagicMock()
        client._persist_weather_data = MagicMock()

        weather_data = await client.get_weather_data(location)
        await client.close()

        # With explicit NWS selection, we should get NWS data only - no Open-Meteo augmentation
        assert weather_data.current is not None
        assert weather_data.current.wind_speed_mph == pytest.approx(7.0)
        # Temperature should be None since NWS didn't provide it and we don't augment
        assert weather_data.current.temperature_f is None
        assert weather_data.current.condition is None
        # Open-Meteo should NOT have been called for augmentation
        client._get_openmeteo_current_conditions.assert_not_awaited()

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
