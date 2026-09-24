"""Tests for AI tool schemas and WeatherToolExecutor."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from accessiweather.ai_tools import WEATHER_TOOLS, WeatherToolExecutor


def test_selected_location_alert_lookup_keeps_displayed_warning_when_live_source_disagrees():
    weather_service = MagicMock()
    weather_service.get_alerts.return_value = {"alerts": []}
    geocoding = MagicMock()
    warning = MagicMock()
    warning.event = "Coastal Flood Warning"
    warning.severity = "Severe"
    warning.headline = "Flood warning remains on screen"
    warning.description = "Flooding is possible"
    warning.is_expired.return_value = False
    executor = WeatherToolExecutor(
        weather_service,
        geocoding,
        default_lat=39.97,
        default_lon=-74.8,
        default_name="Lumberton, NJ",
        displayed_alerts=[warning],
    )

    result = executor.execute("get_alerts", {"location": "Lumberton, NJ"})

    weather_service.get_alerts.assert_called_once_with(39.97, -74.8)
    geocoding.geocode_address.assert_not_called()
    assert "Coastal Flood Warning" in result
    assert "Live alert lookup found none" in result


def test_selected_location_alert_lookup_reports_displayed_warning_missing_from_live_point():
    weather_service = MagicMock()
    weather_service.get_alerts.return_value = {
        "features": [{"properties": {"event": "Coastal Flood Advisory", "severity": "Minor"}}]
    }
    warning = MagicMock()
    warning.event = "Coastal Flood Warning"
    warning.severity = "Severe"
    warning.headline = "Warning shown in the app"
    warning.description = "Flooding is possible"
    warning.is_expired.return_value = False
    executor = WeatherToolExecutor(
        weather_service,
        MagicMock(),
        default_lat=39.97,
        default_lon=-74.8,
        default_name="Lumberton, NJ",
        displayed_alerts=[warning],
    )

    result = executor.execute("get_alerts", {"location": "Lumberton, NJ"})

    assert "Coastal Flood Advisory" in result
    assert "Coastal Flood Warning" in result
    assert "not returned by the live point lookup" in result
    assert "do not claim they are currently verified" in result


def test_selected_location_alert_lookup_reports_unknown_when_live_source_fails():
    weather_service = MagicMock()
    weather_service.get_alerts.side_effect = RuntimeError("unavailable")
    warning = MagicMock()
    warning.event = "Coastal Flood Advisory"
    warning.severity = "Moderate"
    warning.headline = None
    warning.description = "Advisory still shown"
    warning.is_expired.return_value = False
    executor = WeatherToolExecutor(
        weather_service,
        MagicMock(),
        default_lat=39.97,
        default_lon=-74.8,
        default_name="Lumberton, NJ",
        displayed_alerts=[warning],
    )

    result = executor.execute("get_alerts", {"location": "Lumberton, NJ"})

    assert "Coastal Flood Advisory" in result
    assert "current alert status is unknown" in result


class TestWeatherToolSchemas:
    """Tests for the WEATHER_TOOLS schema definitions."""

    def test_weather_tools_has_expected_count(self):
        assert len(WEATHER_TOOLS) == 11

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

    def test_core_tool_names(self):
        names = [t["function"]["name"] for t in WEATHER_TOOLS]
        assert "get_current_weather" in names
        assert "get_forecast" in names
        assert "get_alerts" in names

    def test_extended_tool_names(self):
        names = [t["function"]["name"] for t in WEATHER_TOOLS]
        assert "get_hourly_forecast" in names
        assert "search_location" in names
        assert "add_location" in names
        assert "list_locations" in names
        assert "query_open_meteo" in names

    def test_discussion_tool_names(self):
        names = [t["function"]["name"] for t in WEATHER_TOOLS]
        assert "get_area_forecast_discussion" in names
        assert "get_wpc_discussion" in names
        assert "get_spc_outlook" in names

    def test_all_tools_have_descriptions(self):
        for tool in WEATHER_TOOLS:
            assert len(tool["function"]["description"]) > 0


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
        assert "No current weather data available" in result

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
