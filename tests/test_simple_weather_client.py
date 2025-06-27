"""Tests for weather client in the simplified AccessiWeather application.

This module provides comprehensive tests for the WeatherClient in the simplified
AccessiWeather implementation, adapted from existing weather client test logic while
updating imports and ensuring tests match the simplified weather client architecture.
"""

import json
from datetime import datetime
from unittest.mock import Mock, patch

import httpx
import pytest

# Import models and weather client directly to avoid toga dependency
import sys
import os
import importlib.util

# Load models module directly
models_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'accessiweather', 'simple', 'models.py')
spec = importlib.util.spec_from_file_location("simple_models", models_path)
simple_models = importlib.util.module_from_spec(spec)
spec.loader.exec_module(simple_models)

# Load weather client module directly
weather_client_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'accessiweather', 'simple', 'weather_client.py')
spec = importlib.util.spec_from_file_location("simple_weather_client", weather_client_path)
simple_weather_client = importlib.util.module_from_spec(spec)

# Inject models into weather_client namespace
for attr in dir(simple_models):
    if not attr.startswith('_'):
        setattr(simple_weather_client, attr, getattr(simple_models, attr))

# Execute weather_client
spec.loader.exec_module(simple_weather_client)

# Extract the classes we need
CurrentConditions = simple_models.CurrentConditions
Forecast = simple_models.Forecast
ForecastPeriod = simple_models.ForecastPeriod
HourlyForecast = simple_models.HourlyForecast
HourlyForecastPeriod = simple_models.HourlyForecastPeriod
Location = simple_models.Location
WeatherAlerts = simple_models.WeatherAlerts
WeatherData = simple_models.WeatherData
WeatherClient = simple_weather_client.WeatherClient


class TestWeatherClientBasics:
    """Test basic WeatherClient functionality - adapted from existing test logic."""

    def test_weather_client_initialization(self):
        """Test WeatherClient initialization."""
        client = WeatherClient()

        assert client.user_agent == "AccessiWeather/1.0"
        assert client.nws_base_url == "https://api.weather.gov"
        assert client.openmeteo_base_url == "https://api.open-meteo.com/v1"
        assert client.timeout == 10.0
        assert client.data_source == "auto"  # Default data source

    def test_weather_client_custom_initialization(self):
        """Test WeatherClient initialization with custom parameters."""
        client = WeatherClient(user_agent="TestApp/2.0", data_source="openmeteo")

        assert client.user_agent == "TestApp/2.0"
        assert client.nws_base_url == "https://api.weather.gov"
        assert client.openmeteo_base_url == "https://api.open-meteo.com/v1"
        assert client.timeout == 10.0
        assert client.data_source == "openmeteo"

    @pytest.mark.asyncio
    async def test_get_weather_data_structure(self):
        """Test that weather data is structured correctly."""
        client = WeatherClient()
        location = Location("Test City", 40.0, -75.0)

        # Mock all HTTP requests to return empty/error responses
        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = mock_client.return_value.__aenter__.return_value
            mock_client_instance.get.side_effect = Exception("Network error")

            weather_data = await client.get_weather_data(location)

            assert isinstance(weather_data, WeatherData)
            assert weather_data.location == location
            # When individual NWS methods fail, they return None, so weather_data fields are None
            # The main try block doesn't fail because methods catch exceptions internally
            assert weather_data.current is None
            assert weather_data.forecast is None
            assert isinstance(
                weather_data.alerts, WeatherAlerts
            )  # alerts method returns empty WeatherAlerts on error
            assert isinstance(weather_data.last_updated, datetime)


class TestWeatherClientNWSAPI:
    """Test WeatherClient NWS API functionality - adapted from existing test logic."""

    @pytest.mark.asyncio
    async def test_nws_current_conditions_success(self):
        """Test successful NWS current conditions retrieval."""
        client = WeatherClient()
        location = Location("Philadelphia, PA", 39.9526, -75.1652)

        # Mock NWS API responses
        grid_response = {
            "properties": {
                "observationStations": "https://api.weather.gov/gridpoints/PHI/50,75/stations"
            }
        }

        stations_response = {"features": [{"properties": {"stationIdentifier": "KPHL"}}]}

        observation_response = {
            "properties": {
                "temperature": {"value": 20.0},  # Celsius
                "textDescription": "Clear",
                "relativeHumidity": {"value": 65},
                "windSpeed": {"value": 5.0},  # m/s
                "windDirection": {"value": 270},  # degrees
                "barometricPressure": {"value": 101325},  # Pa
            }
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = mock_client.return_value.__aenter__.return_value
            mock_client_instance.get.side_effect = [
                Mock(json=lambda: grid_response, raise_for_status=lambda: None),
                Mock(json=lambda: stations_response, raise_for_status=lambda: None),
                Mock(json=lambda: observation_response, raise_for_status=lambda: None),
            ]

            current = await client._get_nws_current_conditions(location)

            assert current is not None
            assert current.temperature_f == 68.0  # 20C = 68F
            assert current.temperature_c == 20.0
            assert current.condition == "Clear"
            assert current.humidity == 65
            assert abs(current.wind_speed_mph - 11.185) < 0.01  # 5 m/s ≈ 11.185 mph
            assert current.wind_direction == 270

    @pytest.mark.asyncio
    async def test_nws_forecast_success(self):
        """Test successful NWS forecast retrieval."""
        client = WeatherClient()
        location = Location("Philadelphia, PA", 39.9526, -75.1652)

        # Mock NWS API responses
        grid_response = {
            "properties": {"forecast": "https://api.weather.gov/gridpoints/PHI/50,75/forecast"}
        }

        forecast_response = {
            "properties": {
                "periods": [
                    {
                        "name": "Today",
                        "temperature": 75,
                        "temperatureUnit": "F",
                        "shortForecast": "Sunny",
                        "detailedForecast": "Sunny skies with light winds",
                        "windSpeed": "5 mph",
                        "windDirection": "W",
                        "icon": "https://api.weather.gov/icons/land/day/skc",
                    },
                    {
                        "name": "Tonight",
                        "temperature": 55,
                        "temperatureUnit": "F",
                        "shortForecast": "Clear",
                        "detailedForecast": "Clear skies overnight",
                        "windSpeed": "3 mph",
                        "windDirection": "SW",
                    },
                ]
            }
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = mock_client.return_value.__aenter__.return_value
            mock_client_instance.get.side_effect = [
                Mock(json=lambda: grid_response, raise_for_status=lambda: None),
                Mock(json=lambda: forecast_response, raise_for_status=lambda: None),
            ]

            forecast = await client._get_nws_forecast(location)

            assert forecast is not None
            assert len(forecast.periods) == 2

            today = forecast.periods[0]
            assert today.name == "Today"
            assert today.temperature == 75
            assert today.temperature_unit == "F"
            assert today.short_forecast == "Sunny"
            assert today.wind_speed == "5 mph"
            assert today.wind_direction == "W"

    @pytest.mark.asyncio
    async def test_nws_alerts_success(self):
        """Test successful NWS alerts retrieval."""
        client = WeatherClient()
        location = Location("Philadelphia, PA", 39.9526, -75.1652)

        # Mock NWS alerts response
        alerts_response = {
            "features": [
                {
                    "properties": {
                        "headline": "Winter Storm Warning",
                        "description": "Heavy snow expected",
                        "severity": "Severe",
                        "urgency": "Expected",
                        "certainty": "Likely",
                        "event": "Winter Storm Warning",
                        "instruction": "Avoid travel if possible",
                        "areaDesc": "Philadelphia County; Delaware County",
                    }
                }
            ]
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = mock_client.return_value.__aenter__.return_value
            mock_client_instance.get.return_value = Mock(
                json=lambda: alerts_response, raise_for_status=lambda: None
            )

            alerts = await client._get_nws_alerts(location)

            assert alerts is not None
            assert len(alerts.alerts) == 1

            alert = alerts.alerts[0]
            assert alert.title == "Winter Storm Warning"
            assert alert.description == "Heavy snow expected"
            assert alert.severity == "Severe"
            assert alert.urgency == "Expected"
            assert alert.certainty == "Likely"
            assert alert.event == "Winter Storm Warning"
            assert alert.instruction == "Avoid travel if possible"
            assert "Philadelphia County" in alert.areas
            assert "Delaware County" in alert.areas

    @pytest.mark.asyncio
    async def test_nws_api_network_error(self):
        """Test NWS API network error handling."""
        client = WeatherClient()
        location = Location("Test Location", 40.0, -75.0)

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = mock_client.return_value.__aenter__.return_value
            mock_client_instance.get.side_effect = httpx.ConnectError("Connection failed")

            current = await client._get_nws_current_conditions(location)
            assert current is None

            forecast = await client._get_nws_forecast(location)
            assert forecast is None

            alerts = await client._get_nws_alerts(location)
            assert isinstance(alerts, WeatherAlerts)
            assert len(alerts.alerts) == 0

    @pytest.mark.asyncio
    async def test_nws_api_http_error(self):
        """Test NWS API HTTP error handling."""
        client = WeatherClient()
        location = Location("Test Location", 40.0, -75.0)

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = mock_client.return_value.__aenter__.return_value
            mock_response = Mock()
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "404 Not Found", request=Mock(), response=Mock()
            )
            mock_client_instance.get.return_value = mock_response

            current = await client._get_nws_current_conditions(location)
            assert current is None

            forecast = await client._get_nws_forecast(location)
            assert forecast is None

    @pytest.mark.asyncio
    async def test_nws_api_timeout(self):
        """Test NWS API timeout handling."""
        client = WeatherClient()
        location = Location("Test Location", 40.0, -75.0)

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = mock_client.return_value.__aenter__.return_value
            mock_client_instance.get.side_effect = httpx.TimeoutException("Request timeout")

            current = await client._get_nws_current_conditions(location)
            assert current is None

            forecast = await client._get_nws_forecast(location)
            assert forecast is None

    @pytest.mark.asyncio
    async def test_nws_api_invalid_json(self):
        """Test NWS API invalid JSON response handling."""
        client = WeatherClient()
        location = Location("Test Location", 40.0, -75.0)

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = mock_client.return_value.__aenter__.return_value
            mock_response = Mock()
            mock_response.raise_for_status.return_value = None
            mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
            mock_client_instance.get.return_value = mock_response

            current = await client._get_nws_current_conditions(location)
            assert current is None

    @pytest.mark.asyncio
    async def test_nws_no_observation_stations(self):
        """Test NWS API when no observation stations are found."""
        client = WeatherClient()
        location = Location("Remote Location", 40.0, -75.0)

        # Mock responses with no stations
        grid_response = {
            "properties": {
                "observationStations": "https://api.weather.gov/gridpoints/PHI/50,75/stations"
            }
        }

        stations_response = {"features": []}  # No stations

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = mock_client.return_value.__aenter__.return_value
            mock_client_instance.get.side_effect = [
                Mock(json=lambda: grid_response, raise_for_status=lambda: None),
                Mock(json=lambda: stations_response, raise_for_status=lambda: None),
            ]

            current = await client._get_nws_current_conditions(location)
            assert current is None


class TestWeatherClientOpenMeteoIntegration:
    """Test WeatherClient Open-Meteo integration and automatic API selection."""

    def test_should_use_openmeteo_auto_mode(self):
        """Test automatic API selection based on location."""
        client = WeatherClient(data_source="auto")

        # US locations should use NWS
        us_location = Location("Philadelphia, PA", 39.9526, -75.1652)
        assert not client._should_use_openmeteo(us_location)

        # International locations should use Open-Meteo
        tokyo_location = Location("Tokyo, Japan", 35.6762, 139.6503)
        assert client._should_use_openmeteo(tokyo_location)

        london_location = Location("London, UK", 51.5074, -0.1278)
        assert client._should_use_openmeteo(london_location)

        sydney_location = Location("Sydney, Australia", -33.8688, 151.2093)
        assert client._should_use_openmeteo(sydney_location)

    def test_should_use_openmeteo_forced_modes(self):
        """Test forced API selection modes."""
        us_location = Location("Philadelphia, PA", 39.9526, -75.1652)
        tokyo_location = Location("Tokyo, Japan", 35.6762, 139.6503)

        # Force Open-Meteo mode
        client_openmeteo = WeatherClient(data_source="openmeteo")
        assert client_openmeteo._should_use_openmeteo(us_location)
        assert client_openmeteo._should_use_openmeteo(tokyo_location)

        # Force NWS mode
        client_nws = WeatherClient(data_source="nws")
        assert not client_nws._should_use_openmeteo(us_location)
        assert not client_nws._should_use_openmeteo(tokyo_location)

    def test_is_us_location(self):
        """Test US location detection."""
        client = WeatherClient()

        # US locations
        assert client._is_us_location(Location("New York, NY", 40.7128, -74.0060))
        assert client._is_us_location(Location("Los Angeles, CA", 34.0522, -118.2437))
        assert client._is_us_location(Location("Miami, FL", 25.7617, -80.1918))
        assert client._is_us_location(Location("Seattle, WA", 47.6062, -122.3321))

        # International locations
        assert not client._is_us_location(Location("Tokyo, Japan", 35.6762, 139.6503))
        assert not client._is_us_location(Location("London, UK", 51.5074, -0.1278))
        assert not client._is_us_location(Location("Sydney, Australia", -33.8688, 151.2093))
        assert not client._is_us_location(Location("Paris, France", 48.8566, 2.3522))

        # Edge cases
        assert not client._is_us_location(Location("Mexico City, Mexico", 19.4326, -99.1332))
        assert not client._is_us_location(Location("Toronto, Canada", 43.6532, -79.3832))

    def test_set_empty_weather_data(self):
        """Test setting empty weather data when APIs fail."""
        client = WeatherClient()
        location = Location("Test Location", 40.0, -75.0)
        weather_data = WeatherData(location=location, last_updated=datetime.now())

        client._set_empty_weather_data(weather_data)

        assert isinstance(weather_data.current, CurrentConditions)
        assert isinstance(weather_data.forecast, Forecast)
        assert isinstance(weather_data.hourly_forecast, HourlyForecast)
        assert isinstance(weather_data.alerts, WeatherAlerts)
        assert weather_data.discussion == "Weather data not available."
        assert len(weather_data.forecast.periods) == 0
        assert len(weather_data.alerts.alerts) == 0

    @pytest.mark.asyncio
    async def test_get_weather_data_auto_us_location(self):
        """Test automatic API selection for US location (should use NWS)."""
        client = WeatherClient(data_source="auto")
        us_location = Location("Philadelphia, PA", 39.9526, -75.1652)

        # Mock NWS success
        with (
            patch.object(client, "_get_nws_current_conditions") as mock_nws_current,
            patch.object(client, "_get_nws_forecast_and_discussion") as mock_nws_forecast,
            patch.object(client, "_get_nws_hourly_forecast") as mock_nws_hourly,
            patch.object(client, "_get_nws_alerts") as mock_nws_alerts,
        ):
            mock_nws_current.return_value = CurrentConditions(temperature_f=75.0, condition="Sunny")
            mock_nws_forecast.return_value = (
                Forecast(periods=[ForecastPeriod(name="Today", temperature=75, short_forecast="Sunny")]),
                "Sunny skies expected."
            )
            mock_nws_hourly.return_value = HourlyForecast(periods=[])
            mock_nws_alerts.return_value = WeatherAlerts(alerts=[])

            weather_data = await client.get_weather_data(us_location)

            # Should use NWS
            mock_nws_current.assert_called_once()
            mock_nws_forecast.assert_called_once()
            assert weather_data.current.temperature_f == 75.0
            assert weather_data.discussion == "Sunny skies expected."

    @pytest.mark.asyncio
    async def test_get_weather_data_auto_international_location(self):
        """Test automatic API selection for international location (should use Open-Meteo)."""
        client = WeatherClient(data_source="auto")
        tokyo_location = Location("Tokyo, Japan", 35.6762, 139.6503)

        # Mock Open-Meteo success
        with (
            patch.object(client, "_get_openmeteo_current_conditions") as mock_om_current,
            patch.object(client, "_get_openmeteo_forecast") as mock_om_forecast,
            patch.object(client, "_get_openmeteo_hourly_forecast") as mock_om_hourly,
        ):
            mock_om_current.return_value = CurrentConditions(temperature_f=72.0, condition="Partly cloudy")
            mock_om_forecast.return_value = Forecast(
                periods=[ForecastPeriod(name="Today", temperature=72, short_forecast="Partly cloudy")]
            )
            mock_om_hourly.return_value = HourlyForecast(periods=[])

            weather_data = await client.get_weather_data(tokyo_location)

            # Should use Open-Meteo
            mock_om_current.assert_called_once()
            mock_om_forecast.assert_called_once()
            assert weather_data.current.temperature_f == 72.0
            assert weather_data.discussion == "Forecast discussion not available from Open-Meteo."
            assert len(weather_data.alerts.alerts) == 0  # Open-Meteo doesn't provide alerts

    @pytest.mark.asyncio
    async def test_get_weather_data_openmeteo_fallback_for_us(self):
        """Test Open-Meteo fallback when NWS fails for US location."""
        client = WeatherClient(data_source="auto")
        us_location = Location("Philadelphia, PA", 39.9526, -75.1652)

        # Mock NWS failure and Open-Meteo success
        with (
            patch.object(client, "_get_nws_current_conditions") as mock_nws_current,
            patch.object(client, "_get_nws_forecast_and_discussion") as mock_nws_forecast,
            patch.object(client, "_get_nws_hourly_forecast") as mock_nws_hourly,
            patch.object(client, "_get_nws_alerts") as mock_nws_alerts,
            patch.object(client, "_get_openmeteo_current_conditions") as mock_om_current,
            patch.object(client, "_get_openmeteo_forecast") as mock_om_forecast,
            patch.object(client, "_get_openmeteo_hourly_forecast") as mock_om_hourly,
        ):
            # NWS fails
            mock_nws_current.side_effect = Exception("NWS API error")
            mock_nws_forecast.side_effect = Exception("NWS API error")
            mock_nws_hourly.side_effect = Exception("NWS API error")
            mock_nws_alerts.side_effect = Exception("NWS API error")

            # Open-Meteo succeeds
            mock_om_current.return_value = CurrentConditions(temperature_f=70.0, condition="Cloudy")
            mock_om_forecast.return_value = Forecast(
                periods=[ForecastPeriod(name="Today", temperature=70, short_forecast="Cloudy")]
            )
            mock_om_hourly.return_value = HourlyForecast(periods=[])

            weather_data = await client.get_weather_data(us_location)

            # Should try NWS first, then fallback to Open-Meteo
            mock_nws_current.assert_called_once()
            mock_om_current.assert_called_once()
            assert weather_data.current.temperature_f == 70.0
            assert weather_data.discussion == "Forecast discussion not available from Open-Meteo."

    @pytest.mark.asyncio
    async def test_get_weather_data_nws_fallback_for_international(self):
        """Test NWS fallback when Open-Meteo fails for international location in US."""
        client = WeatherClient(data_source="auto")
        # Use coordinates that are technically international but close to US
        border_location = Location("Vancouver, Canada", 49.2827, -123.1207)

        # Mock Open-Meteo failure and NWS success (if location were in US)
        with (
            patch.object(client, "_get_openmeteo_current_conditions") as mock_om_current,
            patch.object(client, "_get_openmeteo_forecast") as mock_om_forecast,
            patch.object(client, "_get_openmeteo_hourly_forecast") as mock_om_hourly,
        ):
            # Open-Meteo fails
            mock_om_current.side_effect = Exception("Open-Meteo API error")
            mock_om_forecast.side_effect = Exception("Open-Meteo API error")
            mock_om_hourly.side_effect = Exception("Open-Meteo API error")

            weather_data = await client.get_weather_data(border_location)

            # Should try Open-Meteo first, but since it's international and fails,
            # should set empty data (no NWS fallback for international locations)
            mock_om_current.assert_called_once()
            assert isinstance(weather_data.current, CurrentConditions)
            assert isinstance(weather_data.forecast, Forecast)
            assert len(weather_data.forecast.periods) == 0


class TestWeatherClientOpenMeteoAPI:
    """Test WeatherClient OpenMeteo API functionality - adapted from existing test logic."""

    @pytest.mark.asyncio
    async def test_openmeteo_current_conditions_success(self):
        """Test successful OpenMeteo current conditions retrieval."""
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
                "apparent_temperature": 78.0,  # Feels like
            }
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = mock_client.return_value.__aenter__.return_value
            mock_client_instance.get.return_value = Mock(
                json=lambda: openmeteo_response, raise_for_status=lambda: None
            )

            current = await client._get_openmeteo_current_conditions(location)

            assert current is not None
            assert current.temperature_f == 75.0
            assert abs(current.temperature_c - 23.89) < 0.1  # 75F ≈ 23.89C
            assert current.condition == "Mainly clear"
            assert current.humidity == 60
            assert current.wind_speed_mph == 10.0
            assert current.wind_direction == "W"  # 270 degrees = W
            assert current.pressure_mb == 1013.25
            assert current.feels_like_f == 78.0

    @pytest.mark.asyncio
    async def test_openmeteo_forecast_success(self):
        """Test successful OpenMeteo forecast retrieval."""
        client = WeatherClient()
        location = Location("Test Location", 40.0, -75.0)

        # Mock OpenMeteo forecast response
        openmeteo_response = {
            "daily": {
                "time": ["2024-01-01", "2024-01-02", "2024-01-03"],
                "temperature_2m_max": [75.0, 72.0, 68.0],
                "temperature_2m_min": [55.0, 52.0, 48.0],
                "weather_code": [1, 2, 61],  # Mainly clear, Partly cloudy, Slight rain
            }
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = mock_client.return_value.__aenter__.return_value
            mock_client_instance.get.return_value = Mock(
                json=lambda: openmeteo_response, raise_for_status=lambda: None
            )

            forecast = await client._get_openmeteo_forecast(location)

            assert forecast is not None
            assert len(forecast.periods) == 3

            today = forecast.periods[0]
            assert today.name == "Today"
            assert today.temperature == 75.0
            assert today.temperature_unit == "F"
            assert today.short_forecast == "Mainly clear"

            tomorrow = forecast.periods[1]
            assert tomorrow.name == "Tomorrow"
            assert tomorrow.temperature == 72.0
            assert tomorrow.short_forecast == "Partly cloudy"

    @pytest.mark.asyncio
    async def test_openmeteo_api_network_error(self):
        """Test OpenMeteo API network error handling."""
        client = WeatherClient()
        location = Location("Test Location", 40.0, -75.0)

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = mock_client.return_value.__aenter__.return_value
            mock_client_instance.get.side_effect = httpx.ConnectError("Connection failed")

            current = await client._get_openmeteo_current_conditions(location)
            assert current is None

            forecast = await client._get_openmeteo_forecast(location)
            assert forecast is None

    @pytest.mark.asyncio
    async def test_openmeteo_api_http_error(self):
        """Test OpenMeteo API HTTP error handling."""
        client = WeatherClient()
        location = Location("Test Location", 40.0, -75.0)

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = mock_client.return_value.__aenter__.return_value
            mock_response = Mock()
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "500 Internal Server Error", request=Mock(), response=Mock()
            )
            mock_client_instance.get.return_value = mock_response

            current = await client._get_openmeteo_current_conditions(location)
            assert current is None

            forecast = await client._get_openmeteo_forecast(location)
            assert forecast is None


class TestWeatherClientUtilityMethods:
    """Test WeatherClient utility methods - adapted from existing test logic."""

    def test_convert_mps_to_mph(self):
        """Test meters per second to miles per hour conversion."""
        client = WeatherClient()

        assert client._convert_mps_to_mph(None) is None
        assert abs(client._convert_mps_to_mph(5.0) - 11.185) < 0.01
        assert abs(client._convert_mps_to_mph(10.0) - 22.37) < 0.01
        assert client._convert_mps_to_mph(0.0) == 0.0

    def test_convert_pa_to_inches(self):
        """Test pascals to inches of mercury conversion."""
        client = WeatherClient()

        assert client._convert_pa_to_inches(None) is None
        assert abs(client._convert_pa_to_inches(101325) - 29.92) < 0.01  # Standard pressure
        assert client._convert_pa_to_inches(0.0) == 0.0

    def test_convert_f_to_c(self):
        """Test Fahrenheit to Celsius conversion."""
        client = WeatherClient()

        assert client._convert_f_to_c(None) is None
        assert abs(client._convert_f_to_c(32.0) - 0.0) < 0.01  # Freezing point
        assert abs(client._convert_f_to_c(212.0) - 100.0) < 0.01  # Boiling point
        assert abs(client._convert_f_to_c(68.0) - 20.0) < 0.01  # Room temperature

    def test_degrees_to_cardinal(self):
        """Test wind direction degrees to cardinal conversion."""
        client = WeatherClient()

        assert client._degrees_to_cardinal(None) is None
        assert client._degrees_to_cardinal(0) == "N"
        assert client._degrees_to_cardinal(90) == "E"
        assert client._degrees_to_cardinal(180) == "S"
        assert client._degrees_to_cardinal(270) == "W"
        assert client._degrees_to_cardinal(45) == "NE"
        assert client._degrees_to_cardinal(315) == "NW"
        assert client._degrees_to_cardinal(360) == "N"  # Wraps around

    def test_weather_code_to_description(self):
        """Test OpenMeteo weather code to description conversion."""
        client = WeatherClient()

        assert client._weather_code_to_description(None) is None
        assert client._weather_code_to_description(0) == "Clear sky"
        assert client._weather_code_to_description(1) == "Mainly clear"
        assert client._weather_code_to_description(2) == "Partly cloudy"
        assert client._weather_code_to_description(3) == "Overcast"
        assert client._weather_code_to_description(61) == "Slight rain"
        assert client._weather_code_to_description(95) == "Thunderstorm"
        assert client._weather_code_to_description(999) == "Weather code 999"  # Unknown code

    def test_format_date_name(self):
        """Test date string formatting to readable names."""
        client = WeatherClient()

        assert client._format_date_name("2024-01-01", 0) == "Today"
        assert client._format_date_name("2024-01-02", 1) == "Tomorrow"

        # Test fallback for invalid date
        assert client._format_date_name("invalid-date", 3) == "Day 4"


class TestWeatherClientIntegration:
    """Test WeatherClient integration scenarios - adapted from existing test logic."""

    @pytest.mark.asyncio
    async def test_get_weather_data_nws_success(self):
        """Test complete weather data retrieval with NWS success."""
        client = WeatherClient()
        location = Location("Philadelphia, PA", 39.9526, -75.1652)

        # Mock successful NWS responses
        with (
            patch.object(client, "_get_nws_current_conditions") as mock_current,
            patch.object(client, "_get_nws_forecast") as mock_forecast,
            patch.object(client, "_get_nws_alerts") as mock_alerts,
        ):
            mock_current.return_value = CurrentConditions(temperature_f=75.0, condition="Sunny")
            mock_forecast.return_value = Forecast(
                periods=[ForecastPeriod(name="Today", temperature=75, short_forecast="Sunny")]
            )
            mock_alerts.return_value = WeatherAlerts(alerts=[])

            weather_data = await client.get_weather_data(location)

            assert weather_data.location == location
            assert weather_data.current.temperature_f == 75.0
            assert weather_data.current.condition == "Sunny"
            assert len(weather_data.forecast.periods) == 1
            assert weather_data.forecast.periods[0].name == "Today"
            assert len(weather_data.alerts.alerts) == 0

    @pytest.mark.asyncio
    async def test_get_weather_data_fallback_to_openmeteo(self):
        """Test weather data retrieval with NWS failure and OpenMeteo fallback."""
        client = WeatherClient()
        location = Location("Test Location", 40.0, -75.0)

        # Mock NWS failure and OpenMeteo success
        with (
            patch.object(client, "_get_nws_current_conditions") as mock_nws_current,
            patch.object(client, "_get_nws_forecast") as mock_nws_forecast,
            patch.object(client, "_get_nws_alerts") as mock_nws_alerts,
            patch.object(client, "_get_openmeteo_current_conditions") as mock_om_current,
            patch.object(client, "_get_openmeteo_forecast") as mock_om_forecast,
        ):
            # NWS methods raise exceptions
            mock_nws_current.side_effect = Exception("NWS API error")
            mock_nws_forecast.side_effect = Exception("NWS API error")
            mock_nws_alerts.side_effect = Exception("NWS API error")

            # OpenMeteo methods succeed
            mock_om_current.return_value = CurrentConditions(
                temperature_f=72.0, condition="Partly cloudy"
            )
            mock_om_forecast.return_value = Forecast(
                periods=[
                    ForecastPeriod(name="Today", temperature=72, short_forecast="Partly cloudy")
                ]
            )

            weather_data = await client.get_weather_data(location)

            assert weather_data.location == location
            assert weather_data.current.temperature_f == 72.0
            assert weather_data.current.condition == "Partly cloudy"
            assert len(weather_data.forecast.periods) == 1
            assert weather_data.forecast.periods[0].name == "Today"
            assert len(weather_data.alerts.alerts) == 0  # OpenMeteo doesn't provide alerts

    @pytest.mark.asyncio
    async def test_get_weather_data_both_apis_fail(self):
        """Test weather data retrieval when both APIs fail."""
        client = WeatherClient()
        location = Location("Test Location", 40.0, -75.0)

        # Mock both APIs failing
        with (
            patch.object(client, "_get_nws_current_conditions") as mock_nws_current,
            patch.object(client, "_get_nws_forecast") as mock_nws_forecast,
            patch.object(client, "_get_nws_alerts") as mock_nws_alerts,
            patch.object(client, "_get_openmeteo_current_conditions") as mock_om_current,
            patch.object(client, "_get_openmeteo_forecast") as mock_om_forecast,
        ):
            # All methods raise exceptions
            mock_nws_current.side_effect = Exception("NWS API error")
            mock_nws_forecast.side_effect = Exception("NWS API error")
            mock_nws_alerts.side_effect = Exception("NWS API error")
            mock_om_current.side_effect = Exception("OpenMeteo API error")
            mock_om_forecast.side_effect = Exception("OpenMeteo API error")

            weather_data = await client.get_weather_data(location)

            assert weather_data.location == location
            assert isinstance(weather_data.current, CurrentConditions)
            assert isinstance(weather_data.forecast, Forecast)
            assert isinstance(weather_data.alerts, WeatherAlerts)
            assert len(weather_data.forecast.periods) == 0
            assert len(weather_data.alerts.alerts) == 0

    @pytest.mark.asyncio
    async def test_get_weather_data_partial_nws_failure(self):
        """Test weather data retrieval with partial NWS failure."""
        client = WeatherClient()
        location = Location("Test Location", 40.0, -75.0)

        # Mock partial NWS failure (current conditions fail, forecast succeeds)
        with (
            patch.object(client, "_get_nws_current_conditions") as mock_nws_current,
            patch.object(client, "_get_nws_forecast") as mock_nws_forecast,
            patch.object(client, "_get_nws_alerts") as mock_nws_alerts,
            patch.object(client, "_get_openmeteo_current_conditions") as mock_om_current,
            patch.object(client, "_get_openmeteo_forecast") as mock_om_forecast,
        ):
            # Current conditions fails, others succeed
            mock_nws_current.side_effect = Exception("Current conditions API error")
            mock_nws_forecast.return_value = Forecast(
                periods=[ForecastPeriod(name="Today", temperature=70, short_forecast="Cloudy")]
            )
            mock_nws_alerts.return_value = WeatherAlerts(alerts=[])

            # OpenMeteo fallback for current conditions
            mock_om_current.return_value = CurrentConditions(temperature_f=70.0, condition="Cloudy")
            mock_om_forecast.return_value = Forecast(
                periods=[ForecastPeriod(name="Today", temperature=70, short_forecast="Cloudy")]
            )

            weather_data = await client.get_weather_data(location)

            # Should fall back to OpenMeteo for everything since NWS partially failed
            assert weather_data.location == location
            assert weather_data.current.temperature_f == 70.0
            assert weather_data.current.condition == "Cloudy"
            assert len(weather_data.forecast.periods) == 1
            assert len(weather_data.alerts.alerts) == 0


class TestWeatherClientHourlyForecast:
    """Test WeatherClient hourly forecast functionality."""

    @pytest.mark.asyncio
    async def test_nws_hourly_forecast_success(self):
        """Test successful NWS hourly forecast retrieval."""
        client = WeatherClient()
        location = Location("Philadelphia, PA", 39.9526, -75.1652)

        # Mock NWS API responses
        grid_response = {
            "properties": {
                "forecastHourly": "https://api.weather.gov/gridpoints/PHI/50,75/forecast/hourly"
            }
        }

        hourly_response = {
            "properties": {
                "periods": [
                    {
                        "startTime": "2024-01-01T12:00:00-05:00",
                        "endTime": "2024-01-01T13:00:00-05:00",
                        "temperature": 75,
                        "temperatureUnit": "F",
                        "shortForecast": "Sunny",
                        "windSpeed": "5 mph",
                        "windDirection": "W",
                        "icon": "https://api.weather.gov/icons/land/day/skc",
                    },
                    {
                        "startTime": "2024-01-01T13:00:00-05:00",
                        "endTime": "2024-01-01T14:00:00-05:00",
                        "temperature": 76,
                        "temperatureUnit": "F",
                        "shortForecast": "Partly Cloudy",
                        "windSpeed": "7 mph",
                        "windDirection": "SW",
                    },
                ]
            }
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = mock_client.return_value.__aenter__.return_value
            mock_client_instance.get.side_effect = [
                Mock(json=lambda: grid_response, raise_for_status=lambda: None),
                Mock(json=lambda: hourly_response, raise_for_status=lambda: None),
            ]

            hourly_forecast = await client._get_nws_hourly_forecast(location)

            assert hourly_forecast is not None
            assert len(hourly_forecast.periods) == 2

            first_hour = hourly_forecast.periods[0]
            assert first_hour.temperature == 75
            assert first_hour.temperature_unit == "F"
            assert first_hour.short_forecast == "Sunny"
            assert first_hour.wind_speed == "5 mph"
            assert first_hour.wind_direction == "W"
            assert first_hour.start_time is not None

    @pytest.mark.asyncio
    async def test_openmeteo_hourly_forecast_success(self):
        """Test successful OpenMeteo hourly forecast retrieval."""
        client = WeatherClient()
        location = Location("Test Location", 40.0, -75.0)

        # Mock OpenMeteo hourly response
        openmeteo_response = {
            "hourly": {
                "time": [
                    "2024-01-01T12:00",
                    "2024-01-01T13:00",
                    "2024-01-01T14:00",
                ],
                "temperature_2m": [75.0, 76.0, 74.0],
                "weather_code": [1, 2, 1],  # Mainly clear, Partly cloudy, Mainly clear
                "wind_speed_10m": [5.0, 7.0, 6.0],
                "wind_direction_10m": [270, 225, 270],
            }
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = mock_client.return_value.__aenter__.return_value
            mock_client_instance.get.return_value = Mock(
                json=lambda: openmeteo_response, raise_for_status=lambda: None
            )

            hourly_forecast = await client._get_openmeteo_hourly_forecast(location)

            assert hourly_forecast is not None
            assert len(hourly_forecast.periods) == 3

            first_hour = hourly_forecast.periods[0]
            assert first_hour.temperature == 75.0
            assert first_hour.temperature_unit == "F"
            assert first_hour.short_forecast == "Mainly clear"
            assert first_hour.start_time is not None

    @pytest.mark.asyncio
    async def test_hourly_forecast_network_error(self):
        """Test hourly forecast network error handling."""
        client = WeatherClient()
        location = Location("Test Location", 40.0, -75.0)

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = mock_client.return_value.__aenter__.return_value
            mock_client_instance.get.side_effect = httpx.ConnectError("Connection failed")

            nws_hourly = await client._get_nws_hourly_forecast(location)
            assert nws_hourly is None

            openmeteo_hourly = await client._get_openmeteo_hourly_forecast(location)
            assert openmeteo_hourly is None

    @pytest.mark.asyncio
    async def test_get_weather_data_with_hourly_forecast(self):
        """Test complete weather data retrieval including hourly forecast."""
        client = WeatherClient()
        location = Location("Philadelphia, PA", 39.9526, -75.1652)

        # Mock successful responses including hourly forecast
        with (
            patch.object(client, "_get_nws_current_conditions") as mock_current,
            patch.object(client, "_get_nws_forecast") as mock_forecast,
            patch.object(client, "_get_nws_hourly_forecast") as mock_hourly,
            patch.object(client, "_get_nws_alerts") as mock_alerts,
        ):
            mock_current.return_value = CurrentConditions(temperature_f=75.0, condition="Sunny")
            mock_forecast.return_value = Forecast(
                periods=[ForecastPeriod(name="Today", temperature=75, short_forecast="Sunny")]
            )
            mock_hourly.return_value = HourlyForecast(
                periods=[
                    HourlyForecastPeriod(
                        start_time=datetime.now(),
                        temperature=75.0,
                        short_forecast="Sunny"
                    )
                ]
            )
            mock_alerts.return_value = WeatherAlerts(alerts=[])

            weather_data = await client.get_weather_data(location)

            assert weather_data.location == location
            assert weather_data.current.temperature_f == 75.0
            assert weather_data.forecast.periods[0].name == "Today"
            assert weather_data.hourly_forecast is not None
            assert len(weather_data.hourly_forecast.periods) == 1
            assert weather_data.hourly_forecast.periods[0].temperature == 75.0


class TestWeatherClientErrorHandling:
    """Test WeatherClient error handling scenarios - adapted from existing test logic."""

    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """Test timeout error handling."""
        client = WeatherClient()
        location = Location("Test Location", 40.0, -75.0)

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = mock_client.return_value.__aenter__.return_value
            mock_client_instance.get.side_effect = httpx.TimeoutException("Request timeout")

            weather_data = await client.get_weather_data(location)

            # Should return empty weather data when both APIs fail
            assert weather_data.location == location
            assert isinstance(weather_data.current, CurrentConditions)
            assert isinstance(weather_data.forecast, Forecast)
            assert isinstance(weather_data.alerts, WeatherAlerts)
            assert len(weather_data.forecast.periods) == 0
            assert len(weather_data.alerts.alerts) == 0

    @pytest.mark.asyncio
    async def test_connection_error_handling(self):
        """Test connection error handling."""
        client = WeatherClient()
        location = Location("Test Location", 40.0, -75.0)

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = mock_client.return_value.__aenter__.return_value
            mock_client_instance.get.side_effect = httpx.ConnectError("Connection failed")

            weather_data = await client.get_weather_data(location)

            # Should return empty weather data when both APIs fail
            assert weather_data.location == location
            assert isinstance(weather_data.current, CurrentConditions)
            assert isinstance(weather_data.forecast, Forecast)
            assert isinstance(weather_data.alerts, WeatherAlerts)
            assert len(weather_data.forecast.periods) == 0
            assert len(weather_data.alerts.alerts) == 0

    @pytest.mark.asyncio
    async def test_malformed_response_handling(self):
        """Test malformed response handling."""
        client = WeatherClient()
        location = Location("Test Location", 40.0, -75.0)

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = mock_client.return_value.__aenter__.return_value
            mock_response = Mock()
            mock_response.raise_for_status.return_value = None
            mock_response.json.return_value = {"invalid": "structure"}  # Malformed response
            mock_client_instance.get.return_value = mock_response

            weather_data = await client.get_weather_data(location)

            # Should return empty weather data due to parsing errors when both APIs fail
            assert weather_data.location == location
            assert isinstance(weather_data.current, CurrentConditions)
            assert isinstance(weather_data.forecast, Forecast)
            assert isinstance(weather_data.alerts, WeatherAlerts)
            assert len(weather_data.forecast.periods) == 0
            assert len(weather_data.alerts.alerts) == 0


# Smoke test functions that can be run with briefcase dev --test
def test_weather_client_can_be_imported():
    """Test that WeatherClient can be imported successfully."""
    from accessiweather.simple.models import Location
    from accessiweather.simple.weather_client import WeatherClient

    # Basic instantiation test
    client = WeatherClient()
    assert client is not None
    assert client.user_agent == "AccessiWeather/1.0"

    # Test location creation
    location = Location("Test City", 40.0, -75.0)
    assert location.name == "Test City"


def test_weather_client_basic_functionality():
    """Test basic WeatherClient functionality without network calls."""
    from accessiweather.simple.weather_client import WeatherClient

    client = WeatherClient(user_agent="TestApp/1.0")

    # Test utility methods
    assert client._convert_mps_to_mph(5.0) is not None
    assert client._convert_pa_to_inches(101325) is not None
    assert client._convert_f_to_c(75.0) is not None
    assert client._degrees_to_cardinal(270) == "W"
    assert client._weather_code_to_description(1) == "Mainly clear"
    assert client._format_date_name("2024-01-01", 0) == "Today"
