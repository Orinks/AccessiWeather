"""Tests for LocationResolver and updated WeatherToolExecutor location handling."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from accessiweather.ai_tools import LocationResolver, WeatherToolExecutor


class TestLocationResolver:
    """Tests for the LocationResolver class."""

    def _make_resolver(
        self,
        geocoding_service: MagicMock | None = None,
        default_lat: float | None = 40.7,
        default_lon: float | None = -74.0,
        default_name: str | None = "New York, NY",
    ) -> LocationResolver:
        if geocoding_service is None:
            geocoding_service = MagicMock()
        return LocationResolver(
            geocoding_service=geocoding_service,
            default_lat=default_lat,
            default_lon=default_lon,
            default_name=default_name,
        )

    def test_resolve_returns_tuple(self):
        resolver = self._make_resolver()
        result = resolver.resolve("New York, NY")
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_resolve_matches_default_exact(self):
        geo = MagicMock()
        resolver = self._make_resolver(geocoding_service=geo)
        lat, lon, name = resolver.resolve("New York, NY")
        assert lat == 40.7
        assert lon == -74.0
        assert name == "New York, NY"
        geo.geocode_address.assert_not_called()

    def test_resolve_matches_default_case_insensitive(self):
        geo = MagicMock()
        resolver = self._make_resolver(geocoding_service=geo)
        lat, lon, name = resolver.resolve("new york, ny")
        assert lat == 40.7
        assert lon == -74.0
        geo.geocode_address.assert_not_called()

    def test_resolve_matches_default_with_whitespace(self):
        geo = MagicMock()
        resolver = self._make_resolver(geocoding_service=geo)
        lat, lon, _name = resolver.resolve("  New York, NY  ")
        assert lat == 40.7
        assert lon == -74.0
        geo.geocode_address.assert_not_called()

    def test_resolve_falls_back_to_geocoding(self):
        geo = MagicMock()
        geo.geocode_address.return_value = (48.8566, 2.3522, "Paris, France")
        resolver = self._make_resolver(geocoding_service=geo)
        lat, lon, name = resolver.resolve("Paris")
        assert lat == 48.8566
        assert lon == 2.3522
        assert name == "Paris, France"
        geo.geocode_address.assert_called_once_with("Paris")

    def test_resolve_geocoding_failure_raises_valueerror(self):
        geo = MagicMock()
        geo.geocode_address.return_value = None
        resolver = self._make_resolver(geocoding_service=geo)
        with pytest.raises(ValueError, match="Could not resolve location"):
            resolver.resolve("Nonexistent Place XYZ")

    def test_resolve_no_default_set(self):
        """When no default location is configured, always use geocoding."""
        geo = MagicMock()
        geo.geocode_address.return_value = (40.7, -74.0, "New York, NY")
        resolver = self._make_resolver(
            geocoding_service=geo,
            default_lat=None,
            default_lon=None,
            default_name=None,
        )
        resolver.resolve("New York, NY")
        geo.geocode_address.assert_called_once()

    def test_resolve_partial_default_does_not_match(self):
        """If only name is set but not coords, don't match."""
        geo = MagicMock()
        geo.geocode_address.return_value = (40.7, -74.0, "New York, NY")
        resolver = self._make_resolver(
            geocoding_service=geo,
            default_lat=None,
            default_lon=None,
            default_name="New York, NY",
        )
        resolver.resolve("New York, NY")
        geo.geocode_address.assert_called_once()


class TestWeatherToolExecutorWithLocationResolver:
    """Tests for WeatherToolExecutor using LocationResolver."""

    def _make_executor(self) -> tuple[WeatherToolExecutor, MagicMock, MagicMock]:
        weather_svc = MagicMock()
        geo_svc = MagicMock()
        executor = WeatherToolExecutor(
            weather_service=weather_svc,
            geocoding_service=geo_svc,
            default_lat=40.7,
            default_lon=-74.0,
            default_name="New York, NY",
        )
        return executor, weather_svc, geo_svc

    def test_execute_uses_default_location(self):
        executor, weather_svc, geo_svc = self._make_executor()
        weather_svc.get_current_conditions.return_value = {"temperature": "72°F"}
        result = executor.execute("get_current_weather", {"location": "New York, NY"})
        geo_svc.geocode_address.assert_not_called()
        weather_svc.get_current_conditions.assert_called_once_with(40.7, -74.0)
        assert "72°F" in result

    def test_execute_geocodes_other_location(self):
        executor, weather_svc, geo_svc = self._make_executor()
        geo_svc.geocode_address.return_value = (48.85, 2.35, "Paris, France")
        weather_svc.get_forecast.return_value = {"periods": []}
        executor.execute("get_forecast", {"location": "Paris"})
        geo_svc.geocode_address.assert_called_once_with("Paris")
        weather_svc.get_forecast.assert_called_once_with(48.85, 2.35)

    def test_execute_returns_error_on_geocoding_failure(self):
        executor, weather_svc, geo_svc = self._make_executor()
        geo_svc.geocode_address.return_value = None
        result = executor.execute("get_current_weather", {"location": "Nowhere XYZ"})
        assert "Error" in result
        assert "Could not resolve location" in result
        weather_svc.get_current_conditions.assert_not_called()

    def test_execute_returns_error_on_weather_service_failure(self):
        executor, weather_svc, geo_svc = self._make_executor()
        weather_svc.get_alerts.side_effect = Exception("API down")
        result = executor.execute("get_alerts", {"location": "New York, NY"})
        assert "Error" in result

    def test_unknown_tool_raises(self):
        executor, _, _ = self._make_executor()
        with pytest.raises(ValueError, match="Unknown tool"):
            executor.execute("nonexistent_tool", {})
