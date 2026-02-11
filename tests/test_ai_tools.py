"""Tests for AI tool schemas and WeatherToolExecutor."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from accessiweather.ai_tools import WEATHER_TOOLS, WeatherToolExecutor


class TestWeatherToolSchemas:
    """Tests for the WEATHER_TOOLS schema definitions."""

    def test_weather_tools_has_three_tools(self):
        assert len(WEATHER_TOOLS) == 3

    def test_all_tools_have_function_type(self):
        for tool in WEATHER_TOOLS:
            assert tool["type"] == "function"

    def test_all_tools_have_required_fields(self):
        for tool in WEATHER_TOOLS:
            func = tool["function"]
            assert "name" in func
            assert "description" in func
            assert "parameters" in func

    def test_all_tools_have_json_schema_parameters(self):
        for tool in WEATHER_TOOLS:
            params = tool["function"]["parameters"]
            assert params["type"] == "object"
            assert "properties" in params
            assert "location" in params["properties"]
            assert params["properties"]["location"]["type"] == "string"
            assert "required" in params
            assert "location" in params["required"]

    def test_tool_names(self):
        names = [t["function"]["name"] for t in WEATHER_TOOLS]
        assert "get_current_weather" in names
        assert "get_forecast" in names
        assert "get_alerts" in names

    def test_all_tools_have_descriptions(self):
        for tool in WEATHER_TOOLS:
            assert len(tool["function"]["description"]) > 0
            assert len(tool["function"]["parameters"]["properties"]["location"]["description"]) > 0


class TestWeatherToolExecutor:
    """Tests for WeatherToolExecutor."""

    @pytest.fixture()
    def mock_weather_service(self):
        return MagicMock()

    @pytest.fixture()
    def mock_geocoding_service(self):
        service = MagicMock()
        service.geocode_address.return_value = (40.7128, -74.0060, "New York, NY")
        return service

    @pytest.fixture()
    def executor(self, mock_weather_service, mock_geocoding_service):
        return WeatherToolExecutor(mock_weather_service, mock_geocoding_service)

    def test_execute_unknown_tool_raises_value_error(self, executor):
        with pytest.raises(ValueError, match="Unknown tool"):
            executor.execute("unknown_tool", {"location": "NYC"})

    def test_execute_get_current_weather(
        self, executor, mock_weather_service, mock_geocoding_service
    ):
        mock_weather_service.get_current_conditions.return_value = {
            "temperature": "72°F",
            "humidity": "55%",
            "wind": "5 mph NW",
            "description": "Partly Cloudy",
        }

        result = executor.execute("get_current_weather", {"location": "New York, NY"})

        mock_geocoding_service.geocode_address.assert_called_once_with("New York, NY")
        mock_weather_service.get_current_conditions.assert_called_once_with(40.7128, -74.0060)
        assert "New York, NY" in result
        assert "72°F" in result
        assert "55%" in result

    def test_execute_get_forecast(self, executor, mock_weather_service, mock_geocoding_service):
        mock_weather_service.get_forecast.return_value = {
            "periods": [
                {
                    "name": "Tonight",
                    "detailedForecast": "Clear skies with a low of 60°F.",
                    "temperature": 60,
                    "temperatureUnit": "F",
                },
                {
                    "name": "Tomorrow",
                    "detailedForecast": "Sunny with a high of 85°F.",
                    "temperature": 85,
                    "temperatureUnit": "F",
                },
            ]
        }

        result = executor.execute("get_forecast", {"location": "New York, NY"})

        mock_weather_service.get_forecast.assert_called_once_with(40.7128, -74.0060)
        assert "Forecast for New York, NY" in result
        assert "Tonight" in result
        assert "Tomorrow" in result

    def test_execute_get_alerts_with_alerts(
        self, executor, mock_weather_service, mock_geocoding_service
    ):
        mock_weather_service.get_alerts.return_value = {
            "alerts": [
                {
                    "properties": {
                        "event": "Heat Advisory",
                        "headline": "Heat advisory in effect until 8 PM",
                    }
                }
            ]
        }

        result = executor.execute("get_alerts", {"location": "New York, NY"})

        mock_weather_service.get_alerts.assert_called_once_with(40.7128, -74.0060)
        assert "Heat Advisory" in result
        assert "Heat advisory in effect" in result

    def test_execute_get_alerts_no_alerts(
        self, executor, mock_weather_service, mock_geocoding_service
    ):
        mock_weather_service.get_alerts.return_value = {"alerts": []}

        result = executor.execute("get_alerts", {"location": "New York, NY"})

        assert "No active alerts" in result

    def test_execute_geocoding_failure(self, executor, mock_geocoding_service):
        mock_geocoding_service.geocode_address.return_value = None

        result = executor.execute("get_current_weather", {"location": "Nonexistent Place"})
        assert "Error" in result
        assert "Could not resolve location" in result

    def test_execute_current_weather_minimal_data(self, executor, mock_weather_service):
        mock_weather_service.get_current_conditions.return_value = {
            "status": "ok",
        }

        result = executor.execute("get_current_weather", {"location": "NYC"})
        assert "New York, NY" in result
        assert "status: ok" in result

    def test_execute_forecast_nested_properties(self, executor, mock_weather_service):
        mock_weather_service.get_forecast.return_value = {
            "properties": {
                "periods": [
                    {
                        "name": "Today",
                        "shortForecast": "Sunny",
                        "temperature": 80,
                        "temperatureUnit": "F",
                    }
                ]
            }
        }

        result = executor.execute("get_forecast", {"location": "NYC"})
        assert "Today" in result

    def test_execute_alerts_features_format(self, executor, mock_weather_service):
        """Test alerts with GeoJSON features format."""
        mock_weather_service.get_alerts.return_value = {
            "features": [
                {
                    "properties": {
                        "event": "Tornado Warning",
                        "headline": "Tornado warning for the area",
                    }
                }
            ]
        }

        result = executor.execute("get_alerts", {"location": "NYC"})
        assert "Tornado Warning" in result
