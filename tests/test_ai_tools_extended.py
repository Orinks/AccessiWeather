"""Tests for extended AI tools: hourly forecast, location search/management, open-meteo, discussions."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from accessiweather.ai_tools import (
    CORE_TOOLS,
    DISCUSSION_TOOLS,
    EXTENDED_TOOLS,
    WeatherToolExecutor,
    format_hourly_forecast,
    format_location_search,
    format_open_meteo_response,
    get_tools_for_message,
)


class TestGetToolsForMessage:
    """Tests for tiered tool selection."""

    def test_simple_weather_returns_core_only(self):
        tools = get_tools_for_message("What's the weather like?")
        assert len(tools) == len(CORE_TOOLS)

    def test_hourly_trigger(self):
        tools = get_tools_for_message("Will it rain at 3pm?")
        names = [t["function"]["name"] for t in tools]
        assert "get_hourly_forecast" in names

    def test_location_trigger(self):
        tools = get_tools_for_message("Add Paris to my locations")
        names = [t["function"]["name"] for t in tools]
        assert "add_location" in names
        assert "search_location" in names

    def test_discussion_trigger_severe(self):
        tools = get_tools_for_message("Is there any severe weather risk?")
        names = [t["function"]["name"] for t in tools]
        assert "get_spc_outlook" in names

    def test_discussion_trigger_spc(self):
        tools = get_tools_for_message("Show me the SPC outlook")
        names = [t["function"]["name"] for t in tools]
        assert "get_wpc_discussion" in names

    def test_discussion_trigger_tornado(self):
        tools = get_tools_for_message("Any tornado risk today?")
        names = [t["function"]["name"] for t in tools]
        assert "get_area_forecast_discussion" in names

    def test_soil_triggers_extended(self):
        tools = get_tools_for_message("What's the soil temperature?")
        names = [t["function"]["name"] for t in tools]
        assert "query_open_meteo" in names

    def test_uv_triggers_extended(self):
        tools = get_tools_for_message("What's the UV index?")
        names = [t["function"]["name"] for t in tools]
        assert "query_open_meteo" in names

    def test_list_locations_trigger(self):
        tools = get_tools_for_message("Show my locations")
        names = [t["function"]["name"] for t in tools]
        assert "list_locations" in names

    def test_no_triggers_core_only(self):
        tools = get_tools_for_message("Is it cold outside?")
        names = [t["function"]["name"] for t in tools]
        assert "get_current_weather" in names
        assert "query_open_meteo" not in names
        assert "get_spc_outlook" not in names


class TestFormatHourlyForecast:
    """Tests for format_hourly_forecast."""

    def test_basic_periods(self):
        data = {
            "periods": [
                {
                    "name": "3 PM",
                    "temperature": 72,
                    "temperatureUnit": "F",
                    "shortForecast": "Sunny",
                    "windSpeed": "5 mph",
                }
            ]
        }
        result = format_hourly_forecast(data, "NYC")
        assert "NYC" in result
        assert "3 PM" in result
        assert "72°F" in result
        assert "Sunny" in result
        assert "Wind: 5 mph" in result

    def test_nested_properties_periods(self):
        data = {
            "properties": {
                "periods": [{"name": "Tonight", "temperature": 55, "temperatureUnit": "F"}]
            }
        }
        result = format_hourly_forecast(data)
        assert "Tonight" in result

    def test_empty_periods(self):
        data = {"periods": []}
        result = format_hourly_forecast(data)
        assert "No hourly forecast data" in result

    def test_limits_to_12_periods(self):
        data = {
            "periods": [
                {"name": f"Hour {i}", "temperature": 70 + i, "temperatureUnit": "F"}
                for i in range(20)
            ]
        }
        result = format_hourly_forecast(data)
        assert "Hour 11" in result
        assert "Hour 12" not in result

    def test_missing_fields(self):
        data = {"periods": [{"startTime": "2026-02-11T15:00"}]}
        result = format_hourly_forecast(data)
        assert "2026-02-11T15:00" in result


class TestFormatLocationSearch:
    """Tests for format_location_search."""

    def test_with_results(self):
        result = format_location_search(["New York, NY", "New York Mills, MN"], "New York")
        assert "New York" in result
        assert "1. New York, NY" in result
        assert "2. New York Mills, MN" in result

    def test_no_results(self):
        result = format_location_search([], "Nonexistent")
        assert "No locations found" in result

    def test_empty_query(self):
        result = format_location_search([], "")
        assert "No locations found" in result


class TestFormatOpenMeteoResponse:
    """Tests for format_open_meteo_response."""

    def test_current_data(self):
        data = {
            "current": {"temperature_2m": 22.5, "time": "2026-02-11T15:00", "interval": 900},
            "current_units": {"temperature_2m": "°C"},
        }
        result = format_open_meteo_response(data, "Berlin")
        assert "Berlin" in result
        assert "temperature_2m: 22.5°C" in result
        assert "time" not in result.split("Current:")[1]  # time should be excluded

    def test_hourly_data(self):
        data = {
            "hourly": {
                "time": ["2026-02-11T12:00", "2026-02-11T13:00"],
                "temperature_2m": [20.0, 21.0],
            },
            "hourly_units": {"temperature_2m": "°C"},
        }
        result = format_open_meteo_response(data)
        assert "Hourly (2 periods)" in result
        assert "20.0°C" in result

    def test_daily_data(self):
        data = {
            "daily": {
                "time": ["2026-02-11"],
                "temperature_2m_max": [25.0],
            },
            "daily_units": {"temperature_2m_max": "°C"},
        }
        result = format_open_meteo_response(data)
        assert "Daily (1 days)" in result
        assert "25.0°C" in result

    def test_empty_response(self):
        result = format_open_meteo_response({})
        assert "No data returned" in result

    def test_no_display_name(self):
        data = {"current": {"temperature_2m": 15}, "current_units": {}}
        result = format_open_meteo_response(data)
        assert "Open-Meteo data:" in result


class TestWeatherToolExecutorExtended:
    """Tests for extended WeatherToolExecutor methods."""

    @pytest.fixture()
    def mock_services(self):
        weather = MagicMock()
        geocoding = MagicMock()
        geocoding.geocode_address.return_value = (40.7, -74.0, "New York, NY")
        config = MagicMock()
        config.get_location_names.return_value = ["Home"]
        config.get_all_locations.return_value = []
        config.get_current_location.return_value = None
        config.add_location.return_value = True
        return weather, geocoding, config

    @pytest.fixture()
    def executor(self, mock_services):
        weather, geocoding, config = mock_services
        return WeatherToolExecutor(weather, geocoding, config_manager=config)

    def test_get_hourly_forecast(self, executor, mock_services):
        weather, _, _ = mock_services
        weather.get_hourly_forecast.return_value = {
            "periods": [
                {
                    "name": "3 PM",
                    "temperature": 72,
                    "temperatureUnit": "F",
                    "shortForecast": "Clear",
                }
            ]
        }
        result = executor.execute("get_hourly_forecast", {"location": "New York"})
        assert "3 PM" in result
        weather.get_hourly_forecast.assert_called_once_with(40.7, -74.0)

    def test_search_location(self, executor, mock_services):
        _, geocoding, _ = mock_services
        geocoding.suggest_locations.return_value = ["Paris, France", "Paris, TX"]
        result = executor.execute("search_location", {"query": "Paris"})
        assert "Paris, France" in result
        geocoding.suggest_locations.assert_called_once_with("Paris", limit=5)

    def test_add_location_success(self, executor, mock_services):
        _, _, config = mock_services
        result = executor.execute(
            "add_location", {"name": "NYC", "latitude": 40.7, "longitude": -74.0}
        )
        assert "Added" in result
        config.add_location.assert_called_once_with("NYC", 40.7, -74.0)

    def test_add_location_already_exists(self, executor, mock_services):
        _, _, config = mock_services
        config.get_location_names.return_value = ["NYC"]
        result = executor.execute(
            "add_location", {"name": "NYC", "latitude": 40.7, "longitude": -74.0}
        )
        assert "already" in result

    def test_add_location_no_config_manager(self, mock_services):
        weather, geocoding, _ = mock_services
        executor = WeatherToolExecutor(weather, geocoding, config_manager=None)
        result = executor.execute(
            "add_location", {"name": "NYC", "latitude": 40.7, "longitude": -74.0}
        )
        assert "unavailable" in result

    def test_list_locations_empty(self, executor):
        result = executor.execute("list_locations", {})
        assert "No saved locations" in result

    def test_list_locations_with_data(self, mock_services):
        weather, geocoding, config = mock_services
        loc = MagicMock()
        loc.name = "Home"
        loc.latitude = 40.7
        loc.longitude = -74.0
        config.get_all_locations.return_value = [loc]
        current = MagicMock()
        current.name = "Home"
        config.get_current_location.return_value = current
        executor = WeatherToolExecutor(weather, geocoding, config_manager=config)
        result = executor.execute("list_locations", {})
        assert "Home" in result
        assert "(current)" in result

    def test_list_locations_no_config_manager(self, mock_services):
        weather, geocoding, _ = mock_services
        executor = WeatherToolExecutor(weather, geocoding, config_manager=None)
        result = executor.execute("list_locations", {})
        assert "unavailable" in result

    def test_get_afd(self, executor, mock_services):
        weather, _, _ = mock_services
        weather.get_discussion.return_value = "This is the AFD text for testing."
        result = executor.execute("get_area_forecast_discussion", {"location": "NYC"})
        assert "Area Forecast Discussion" in result
        assert "AFD text" in result

    def test_get_afd_none(self, executor, mock_services):
        weather, _, _ = mock_services
        weather.get_discussion.return_value = None
        result = executor.execute("get_area_forecast_discussion", {"location": "NYC"})
        assert "No Area Forecast Discussion" in result

    def test_get_afd_truncates_long_text(self, executor, mock_services):
        weather, _, _ = mock_services
        weather.get_discussion.return_value = "x" * 5000
        result = executor.execute("get_area_forecast_discussion", {"location": "NYC"})
        assert "[Truncated" in result

    def test_get_wpc_discussion(self, executor):
        with patch(
            "accessiweather.services.national_discussion_scraper.NationalDiscussionScraper"
        ) as MockScraper:
            instance = MockScraper.return_value
            instance.fetch_wpc_discussion.return_value = {"full": "WPC discussion text here."}
            result = executor.execute("get_wpc_discussion", {})
        assert "WPC" in result

    def test_get_spc_outlook(self, executor):
        with patch(
            "accessiweather.services.national_discussion_scraper.NationalDiscussionScraper"
        ) as MockScraper:
            instance = MockScraper.return_value
            instance.fetch_spc_discussion.return_value = {"full": "SPC outlook text here."}
            result = executor.execute("get_spc_outlook", {})
        assert "SPC" in result

    def test_query_open_meteo(self, executor):
        with patch("accessiweather.openmeteo_client.OpenMeteoApiClient") as MockClient:
            instance = MockClient.return_value
            instance._make_request.return_value = {
                "current": {"temperature_2m": 22.5},
                "current_units": {"temperature_2m": "°C"},
            }
            result = executor.execute(
                "query_open_meteo",
                {"location": "NYC", "current": ["temperature_2m"]},
            )
        assert "22.5" in result

    def test_query_open_meteo_no_variables(self, executor):
        result = executor.execute("query_open_meteo", {"location": "NYC"})
        assert "specify at least one" in result

    def test_query_open_meteo_error(self, executor):
        with patch("accessiweather.openmeteo_client.OpenMeteoApiClient") as MockClient:
            MockClient.side_effect = Exception("API down")
            result = executor.execute(
                "query_open_meteo",
                {"location": "NYC", "current": ["temperature_2m"]},
            )
        assert "Error" in result


class TestToolListIntegrity:
    """Tests for tool list structure."""

    def test_core_tools_count(self):
        assert len(CORE_TOOLS) == 3

    def test_extended_tools_count(self):
        assert len(EXTENDED_TOOLS) == 5

    def test_discussion_tools_count(self):
        assert len(DISCUSSION_TOOLS) == 3

    def test_no_duplicate_names(self):
        from accessiweather.ai_tools import WEATHER_TOOLS

        names = [t["function"]["name"] for t in WEATHER_TOOLS]
        assert len(names) == len(set(names))
