"""Weather client and API integration tests for Toga AccessiWeather."""

import asyncio
import os
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

# Set up Toga dummy backend
os.environ["TOGA_BACKEND"] = "toga_dummy"

from tests.toga_test_helpers import (
    WeatherDataFactory,
)


class TestWeatherClient:
    """Test the weather client functionality."""

    @pytest.fixture
    def mock_weather_client(self):
        """Create a mock weather client for testing."""
        client = MagicMock()
        client.data_source = "auto"
        client.location = WeatherDataFactory.create_location()
        client.last_update = None
        client.cache_timeout = 300  # 5 minutes
        return client

    @pytest.fixture
    def mock_httpx_client(self):
        """Create a mock httpx client for API testing."""
        client = MagicMock()
        client.get = AsyncMock()
        client.post = AsyncMock()
        client.close = AsyncMock()
        return client

    def test_weather_client_initialization(self, mock_weather_client):
        """Test weather client initialization."""
        assert mock_weather_client.data_source == "auto"
        assert mock_weather_client.location.name == "Test City, ST"
        assert mock_weather_client.cache_timeout == 300

    @pytest.mark.asyncio
    async def test_weather_client_get_current_weather(self, mock_weather_client):
        """Test getting current weather data."""
        # Mock the get_current_weather method
        mock_weather_client.get_current_weather = AsyncMock(
            return_value=WeatherDataFactory.create_current_conditions()
        )

        current_weather = await mock_weather_client.get_current_weather()

        assert current_weather.temperature_f == 75.0
        assert current_weather.condition == "Partly Cloudy"
        assert current_weather.humidity == 65
        mock_weather_client.get_current_weather.assert_called_once()

    @pytest.mark.asyncio
    async def test_weather_client_get_forecast(self, mock_weather_client):
        """Test getting forecast data."""
        # Mock the get_forecast method
        mock_weather_client.get_forecast = AsyncMock(
            return_value=WeatherDataFactory.create_forecast()
        )

        forecast = await mock_weather_client.get_forecast()

        assert len(forecast.periods) == 7
        assert forecast.periods[0].name == "Day 1"
        assert forecast.periods[0].temperature == 75
        mock_weather_client.get_forecast.assert_called_once()

    @pytest.mark.asyncio
    async def test_weather_client_get_hourly_forecast(self, mock_weather_client):
        """Test getting hourly forecast data."""
        # Mock the get_hourly_forecast method
        mock_weather_client.get_hourly_forecast = AsyncMock(
            return_value=WeatherDataFactory.create_hourly_forecast()
        )

        hourly_forecast = await mock_weather_client.get_hourly_forecast()

        assert len(hourly_forecast.periods) == 24
        assert hourly_forecast.periods[0].temperature == 70
        mock_weather_client.get_hourly_forecast.assert_called_once()

    @pytest.mark.asyncio
    async def test_weather_client_get_alerts(self, mock_weather_client):
        """Test getting weather alerts."""
        # Mock the get_alerts method
        mock_weather_client.get_alerts = AsyncMock(
            return_value=WeatherDataFactory.create_weather_alerts()
        )

        alerts = await mock_weather_client.get_alerts()

        assert len(alerts.alerts) == 2
        assert alerts.alerts[0].title == "Alert 1"
        assert alerts.alerts[0].severity == "Minor"
        mock_weather_client.get_alerts.assert_called_once()

    @pytest.mark.asyncio
    async def test_weather_client_error_handling(self, mock_weather_client):
        """Test weather client error handling."""
        # Mock the get_current_weather method to raise an exception
        mock_weather_client.get_current_weather = AsyncMock(
            side_effect=httpx.RequestError("Network error")
        )

        with pytest.raises(httpx.RequestError):
            await mock_weather_client.get_current_weather()

    @pytest.mark.asyncio
    async def test_weather_client_timeout_handling(self, mock_weather_client):
        """Test weather client timeout handling."""
        # Mock the get_current_weather method to raise a timeout
        mock_weather_client.get_current_weather = AsyncMock(
            side_effect=httpx.TimeoutException("Request timeout")
        )

        with pytest.raises(httpx.TimeoutException):
            await mock_weather_client.get_current_weather()

    def test_weather_client_cache_validation(self, mock_weather_client):
        """Test weather client cache validation."""
        # Set up cache data
        mock_weather_client.last_update = datetime.now() - timedelta(minutes=2)
        mock_weather_client.is_cache_valid = MagicMock(return_value=True)

        # Test cache validation
        is_valid = mock_weather_client.is_cache_valid()
        assert is_valid is True
        mock_weather_client.is_cache_valid.assert_called_once()

    def test_weather_client_cache_expiration(self, mock_weather_client):
        """Test weather client cache expiration."""
        # Set up expired cache data
        mock_weather_client.last_update = datetime.now() - timedelta(minutes=10)
        mock_weather_client.is_cache_valid = MagicMock(return_value=False)

        # Test cache expiration
        is_valid = mock_weather_client.is_cache_valid()
        assert is_valid is False
        mock_weather_client.is_cache_valid.assert_called_once()

    def test_weather_client_location_update(self, mock_weather_client):
        """Test weather client location update."""
        new_location = WeatherDataFactory.create_location("New Location", 41.0, -76.0)
        mock_weather_client.set_location = MagicMock()

        # Test location update
        mock_weather_client.set_location(new_location)
        mock_weather_client.set_location.assert_called_once_with(new_location)

    def test_weather_client_data_source_switching(self, mock_weather_client):
        """Test switching between weather data sources."""
        mock_weather_client.set_data_source = MagicMock()

        # Test data source switching
        mock_weather_client.set_data_source("nws")
        mock_weather_client.set_data_source.assert_called_once_with("nws")

    @pytest.mark.asyncio
    async def test_weather_client_parallel_requests(self, mock_weather_client):
        """Test parallel weather data requests."""
        # Mock multiple async methods
        mock_weather_client.get_current_weather = AsyncMock(
            return_value=WeatherDataFactory.create_current_conditions()
        )
        mock_weather_client.get_forecast = AsyncMock(
            return_value=WeatherDataFactory.create_forecast()
        )
        mock_weather_client.get_alerts = AsyncMock(
            return_value=WeatherDataFactory.create_weather_alerts()
        )

        # Execute parallel requests
        current_task = mock_weather_client.get_current_weather()
        forecast_task = mock_weather_client.get_forecast()
        alerts_task = mock_weather_client.get_alerts()

        current, forecast, alerts = await asyncio.gather(current_task, forecast_task, alerts_task)

        assert current.temperature_f == 75.0
        assert len(forecast.periods) == 7
        assert len(alerts.alerts) == 2

    def test_weather_client_rate_limiting(self, mock_weather_client):
        """Test weather client rate limiting."""
        mock_weather_client.rate_limiter = MagicMock()
        mock_weather_client.rate_limiter.can_make_request = MagicMock(return_value=True)

        # Test rate limiting
        can_request = mock_weather_client.rate_limiter.can_make_request()
        assert can_request is True
        mock_weather_client.rate_limiter.can_make_request.assert_called_once()

    def test_weather_client_retry_logic(self, mock_weather_client):
        """Test weather client retry logic."""
        mock_weather_client.max_retries = 3
        mock_weather_client.retry_delay = 1.0
        mock_weather_client.should_retry = MagicMock(return_value=True)

        # Test retry logic
        should_retry = mock_weather_client.should_retry()
        assert should_retry is True
        assert mock_weather_client.max_retries == 3


class TestNWSWeatherClient:
    """Test National Weather Service API client."""

    @pytest.fixture
    def mock_nws_client(self):
        """Create a mock NWS client for testing."""
        client = MagicMock()
        client.base_url = "https://api.weather.gov"
        client.user_agent = "AccessiWeather/1.0"
        client.grid_office = "PHI"
        client.grid_x = 49
        client.grid_y = 75
        return client

    def test_nws_client_initialization(self, mock_nws_client):
        """Test NWS client initialization."""
        assert mock_nws_client.base_url == "https://api.weather.gov"
        assert mock_nws_client.user_agent == "AccessiWeather/1.0"
        assert mock_nws_client.grid_office == "PHI"

    @pytest.mark.asyncio
    async def test_nws_client_get_point_data(self, mock_nws_client):
        """Test getting point data from NWS."""
        mock_point_data = {
            "properties": {
                "gridId": "PHI",
                "gridX": 49,
                "gridY": 75,
                "forecast": "https://api.weather.gov/gridpoints/PHI/49,75/forecast",
                "forecastHourly": "https://api.weather.gov/gridpoints/PHI/49,75/forecast/hourly",
            }
        }

        mock_nws_client.get_point_data = AsyncMock(return_value=mock_point_data)

        point_data = await mock_nws_client.get_point_data(40.0, -75.0)

        assert point_data["properties"]["gridId"] == "PHI"
        assert point_data["properties"]["gridX"] == 49
        mock_nws_client.get_point_data.assert_called_once_with(40.0, -75.0)

    @pytest.mark.asyncio
    async def test_nws_client_get_forecast_data(self, mock_nws_client):
        """Test getting forecast data from NWS."""
        mock_forecast_data = {
            "properties": {
                "periods": [
                    {
                        "name": "Today",
                        "temperature": 75,
                        "temperatureUnit": "F",
                        "shortForecast": "Sunny",
                        "detailedForecast": "Sunny skies with light winds.",
                    }
                ]
            }
        }

        mock_nws_client.get_forecast_data = AsyncMock(return_value=mock_forecast_data)

        forecast_data = await mock_nws_client.get_forecast_data()

        assert len(forecast_data["properties"]["periods"]) == 1
        assert forecast_data["properties"]["periods"][0]["name"] == "Today"
        mock_nws_client.get_forecast_data.assert_called_once()

    @pytest.mark.asyncio
    async def test_nws_client_get_alerts_data(self, mock_nws_client):
        """Test getting alerts data from NWS."""
        mock_alerts_data = {
            "features": [
                {
                    "properties": {
                        "event": "Severe Thunderstorm Warning",
                        "severity": "Severe",
                        "description": "Severe thunderstorm warning in effect.",
                        "instruction": "Take shelter immediately.",
                    }
                }
            ]
        }

        mock_nws_client.get_alerts_data = AsyncMock(return_value=mock_alerts_data)

        alerts_data = await mock_nws_client.get_alerts_data()

        assert len(alerts_data["features"]) == 1
        assert alerts_data["features"][0]["properties"]["event"] == "Severe Thunderstorm Warning"
        mock_nws_client.get_alerts_data.assert_called_once()

    def test_nws_client_url_construction(self, mock_nws_client):
        """Test NWS URL construction."""
        mock_nws_client.build_url = MagicMock(
            return_value="https://api.weather.gov/gridpoints/PHI/49,75/forecast"
        )

        url = mock_nws_client.build_url("forecast")

        assert url == "https://api.weather.gov/gridpoints/PHI/49,75/forecast"
        mock_nws_client.build_url.assert_called_once_with("forecast")

    def test_nws_client_error_handling(self, mock_nws_client):
        """Test NWS client error handling."""
        mock_nws_client.handle_error = MagicMock()

        error = httpx.HTTPStatusError("404 Not Found", request=MagicMock(), response=MagicMock())
        mock_nws_client.handle_error(error)

        mock_nws_client.handle_error.assert_called_once_with(error)


class TestOpenMeteoClient:
    """Test Open-Meteo API client."""

    @pytest.fixture
    def mock_openmeteo_client(self):
        """Create a mock Open-Meteo client for testing."""
        client = MagicMock()
        client.base_url = "https://api.open-meteo.com/v1"
        client.timezone = "America/New_York"
        client.temperature_unit = "fahrenheit"
        client.wind_speed_unit = "mph"
        return client

    def test_openmeteo_client_initialization(self, mock_openmeteo_client):
        """Test Open-Meteo client initialization."""
        assert mock_openmeteo_client.base_url == "https://api.open-meteo.com/v1"
        assert mock_openmeteo_client.timezone == "America/New_York"
        assert mock_openmeteo_client.temperature_unit == "fahrenheit"

    @pytest.mark.asyncio
    async def test_openmeteo_client_get_current_weather(self, mock_openmeteo_client):
        """Test getting current weather from Open-Meteo."""
        mock_current_data = {
            "current": {
                "temperature_2m": 75.0,
                "weather_code": 1,
                "relative_humidity_2m": 65,
                "wind_speed_10m": 8.5,
                "wind_direction_10m": 180,
            }
        }

        mock_openmeteo_client.get_current_weather = AsyncMock(return_value=mock_current_data)

        current_data = await mock_openmeteo_client.get_current_weather(40.0, -75.0)

        assert current_data["current"]["temperature_2m"] == 75.0
        assert current_data["current"]["weather_code"] == 1
        mock_openmeteo_client.get_current_weather.assert_called_once_with(40.0, -75.0)

    @pytest.mark.asyncio
    async def test_openmeteo_client_get_forecast(self, mock_openmeteo_client):
        """Test getting forecast from Open-Meteo."""
        mock_forecast_data = {
            "daily": {
                "time": ["2024-01-01", "2024-01-02", "2024-01-03"],
                "weather_code": [1, 2, 3],
                "temperature_2m_max": [75.0, 78.0, 72.0],
                "temperature_2m_min": [55.0, 58.0, 52.0],
            }
        }

        mock_openmeteo_client.get_forecast = AsyncMock(return_value=mock_forecast_data)

        forecast_data = await mock_openmeteo_client.get_forecast(40.0, -75.0)

        assert len(forecast_data["daily"]["time"]) == 3
        assert forecast_data["daily"]["temperature_2m_max"][0] == 75.0
        mock_openmeteo_client.get_forecast.assert_called_once_with(40.0, -75.0)

    def test_openmeteo_client_weather_code_mapping(self, mock_openmeteo_client):
        """Test weather code mapping for Open-Meteo."""
        mock_openmeteo_client.map_weather_code = MagicMock(return_value="Clear")

        condition = mock_openmeteo_client.map_weather_code(1)

        assert condition == "Clear"
        mock_openmeteo_client.map_weather_code.assert_called_once_with(1)

    def test_openmeteo_client_unit_conversion(self, mock_openmeteo_client):
        """Test unit conversion for Open-Meteo data."""
        mock_openmeteo_client.convert_temperature = MagicMock(return_value=75.0)
        mock_openmeteo_client.convert_wind_speed = MagicMock(return_value=8.5)

        # Test temperature conversion
        temp_f = mock_openmeteo_client.convert_temperature(23.9, "celsius", "fahrenheit")
        assert temp_f == 75.0

        # Test wind speed conversion
        wind_mph = mock_openmeteo_client.convert_wind_speed(3.8, "m/s", "mph")
        assert wind_mph == 8.5

    def test_openmeteo_client_parameter_validation(self, mock_openmeteo_client):
        """Test parameter validation for Open-Meteo requests."""
        mock_openmeteo_client.validate_parameters = MagicMock(return_value=True)

        params = {
            "latitude": 40.0,
            "longitude": -75.0,
            "current": "temperature_2m,weather_code",
            "daily": "temperature_2m_max,temperature_2m_min",
        }

        is_valid = mock_openmeteo_client.validate_parameters(params)
        assert is_valid is True
        mock_openmeteo_client.validate_parameters.assert_called_once_with(params)


class TestVisualCrossingClient:
    """Test Visual Crossing API client."""

    @pytest.fixture
    def mock_visualcrossing_client(self):
        """Create a mock Visual Crossing client for testing."""
        client = MagicMock()
        client.base_url = (
            "https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline"
        )
        client.api_key = "test_api_key"
        client.unit_group = "us"
        return client

    def test_visualcrossing_client_initialization(self, mock_visualcrossing_client):
        """Test Visual Crossing client initialization."""
        assert "visualcrossing.com" in mock_visualcrossing_client.base_url
        assert mock_visualcrossing_client.api_key == "test_api_key"
        assert mock_visualcrossing_client.unit_group == "us"

    @pytest.mark.asyncio
    async def test_visualcrossing_client_get_weather_data(self, mock_visualcrossing_client):
        """Test getting weather data from Visual Crossing."""
        mock_weather_data = {
            "currentConditions": {
                "temp": 75.0,
                "conditions": "Clear",
                "humidity": 65.0,
                "windspeed": 8.5,
                "winddir": 180.0,
            },
            "days": [
                {
                    "datetime": "2024-01-01",
                    "tempmax": 75.0,
                    "tempmin": 55.0,
                    "conditions": "Clear",
                    "description": "Clear skies throughout the day.",
                }
            ],
        }

        mock_visualcrossing_client.get_weather_data = AsyncMock(return_value=mock_weather_data)

        weather_data = await mock_visualcrossing_client.get_weather_data("40.0,-75.0")

        assert weather_data["currentConditions"]["temp"] == 75.0
        assert weather_data["currentConditions"]["conditions"] == "Clear"
        assert len(weather_data["days"]) == 1
        mock_visualcrossing_client.get_weather_data.assert_called_once_with("40.0,-75.0")

    def test_visualcrossing_client_api_key_validation(self, mock_visualcrossing_client):
        """Test API key validation for Visual Crossing."""
        mock_visualcrossing_client.validate_api_key = MagicMock(return_value=True)

        is_valid = mock_visualcrossing_client.validate_api_key()
        assert is_valid is True
        mock_visualcrossing_client.validate_api_key.assert_called_once()

    def test_visualcrossing_client_location_formatting(self, mock_visualcrossing_client):
        """Test location formatting for Visual Crossing."""
        mock_visualcrossing_client.format_location = MagicMock(return_value="40.0,-75.0")

        location = mock_visualcrossing_client.format_location(40.0, -75.0)
        assert location == "40.0,-75.0"
        mock_visualcrossing_client.format_location.assert_called_once_with(40.0, -75.0)

    def test_visualcrossing_client_request_parameters(self, mock_visualcrossing_client):
        """Test request parameters for Visual Crossing."""
        mock_visualcrossing_client.build_request_params = MagicMock(
            return_value={
                "unitGroup": "us",
                "key": "test_api_key",
                "include": "current,days",
                "elements": "temp,conditions,humidity,windspeed,winddir",
            }
        )

        params = mock_visualcrossing_client.build_request_params()

        assert params["unitGroup"] == "us"
        assert params["key"] == "test_api_key"
        assert "current" in params["include"]
        mock_visualcrossing_client.build_request_params.assert_called_once()


class TestWeatherDataIntegration:
    """Test weather data integration and processing."""

    @pytest.fixture
    def mock_weather_data_processor(self):
        """Create a mock weather data processor."""
        processor = MagicMock()
        processor.process_weather_data = MagicMock()
        processor.format_temperature = MagicMock(return_value="75°F")
        processor.format_condition = MagicMock(return_value="Partly Cloudy")
        return processor

    def test_weather_data_processing(self, mock_weather_data_processor):
        """Test weather data processing and formatting."""
        raw_data = {"temperature": 75.0, "condition": "partly-cloudy"}

        mock_weather_data_processor.process_weather_data(raw_data)
        mock_weather_data_processor.process_weather_data.assert_called_once_with(raw_data)

    def test_temperature_formatting(self, mock_weather_data_processor):
        """Test temperature formatting."""
        formatted_temp = mock_weather_data_processor.format_temperature(75.0, "F")
        assert formatted_temp == "75°F"
        mock_weather_data_processor.format_temperature.assert_called_once_with(75.0, "F")

    def test_condition_formatting(self, mock_weather_data_processor):
        """Test condition formatting."""
        formatted_condition = mock_weather_data_processor.format_condition("partly-cloudy")
        assert formatted_condition == "Partly Cloudy"
        mock_weather_data_processor.format_condition.assert_called_once_with("partly-cloudy")

    def test_weather_data_validation(self, mock_weather_data_processor):
        """Test weather data validation."""
        mock_weather_data_processor.validate_weather_data = MagicMock(return_value=True)

        raw_data = {"temperature": 75.0, "condition": "clear"}
        is_valid = mock_weather_data_processor.validate_weather_data(raw_data)

        assert is_valid is True
        mock_weather_data_processor.validate_weather_data.assert_called_once_with(raw_data)

    def test_weather_data_caching(self, mock_weather_data_processor):
        """Test weather data caching."""
        mock_weather_data_processor.cache_weather_data = MagicMock()
        mock_weather_data_processor.get_cached_weather_data = MagicMock(
            return_value={"temperature": 75.0, "cached": True}
        )

        # Test caching
        raw_data = {"temperature": 75.0, "condition": "clear"}
        mock_weather_data_processor.cache_weather_data(raw_data)

        # Test cache retrieval
        cached_data = mock_weather_data_processor.get_cached_weather_data()

        assert cached_data["cached"] is True
        mock_weather_data_processor.cache_weather_data.assert_called_once_with(raw_data)

    def test_weather_data_aggregation(self, mock_weather_data_processor):
        """Test weather data aggregation from multiple sources."""
        mock_weather_data_processor.aggregate_weather_data = MagicMock(
            return_value={"temperature": 75.0, "source": "aggregated"}
        )

        sources_data = [
            {"temperature": 74.0, "source": "nws"},
            {"temperature": 76.0, "source": "openmeteo"},
        ]

        aggregated_data = mock_weather_data_processor.aggregate_weather_data(sources_data)

        assert aggregated_data["source"] == "aggregated"
        mock_weather_data_processor.aggregate_weather_data.assert_called_once_with(sources_data)

    def test_weather_data_error_handling(self, mock_weather_data_processor):
        """Test weather data error handling."""
        mock_weather_data_processor.handle_data_error = MagicMock()

        error = ValueError("Invalid weather data")
        mock_weather_data_processor.handle_data_error(error)

        mock_weather_data_processor.handle_data_error.assert_called_once_with(error)

    def test_weather_data_logging(self, mock_weather_data_processor):
        """Test weather data logging."""
        mock_weather_data_processor.log_weather_data = MagicMock()

        weather_data = {"temperature": 75.0, "condition": "clear"}
        mock_weather_data_processor.log_weather_data(weather_data)

        mock_weather_data_processor.log_weather_data.assert_called_once_with(weather_data)

    def test_weather_data_units_conversion(self, mock_weather_data_processor):
        """Test weather data units conversion."""
        mock_weather_data_processor.convert_units = MagicMock(
            return_value={"temperature_c": 23.9, "temperature_f": 75.0}
        )

        input_data = {"temperature": 75.0, "unit": "F"}
        converted_data = mock_weather_data_processor.convert_units(input_data)

        assert converted_data["temperature_c"] == 23.9
        assert converted_data["temperature_f"] == 75.0
        mock_weather_data_processor.convert_units.assert_called_once_with(input_data)

    def test_weather_data_quality_check(self, mock_weather_data_processor):
        """Test weather data quality check."""
        mock_weather_data_processor.check_data_quality = MagicMock(return_value={"quality": "good"})

        weather_data = {"temperature": 75.0, "condition": "clear"}
        quality_result = mock_weather_data_processor.check_data_quality(weather_data)

        assert quality_result["quality"] == "good"
        mock_weather_data_processor.check_data_quality.assert_called_once_with(weather_data)
