# tests/test_priority_engine.py
"""Tests for the priority ordering engine."""

from accessiweather.display.priority_engine import PriorityEngine, WeatherCategory
from accessiweather.models import WeatherAlert, WeatherAlerts


class TestWeatherCategory:
    """Test WeatherCategory enum."""

    def test_all_categories_defined(self):
        """All expected categories should be defined."""
        expected = [
            "temperature",
            "precipitation",
            "wind",
            "humidity_pressure",
            "visibility_clouds",
            "uv_index",
        ]
        for cat in expected:
            assert hasattr(WeatherCategory, cat.upper())


class TestPriorityEngine:
    """Test PriorityEngine class."""

    def test_default_order_with_no_alerts(self):
        """Without alerts, use default category order."""
        engine = PriorityEngine()
        order = engine.get_category_order(alerts=None)
        assert order[0] == WeatherCategory.TEMPERATURE

    def test_wind_alert_prioritizes_wind(self):
        """Wind warning should move wind category to top."""
        engine = PriorityEngine()
        alert = WeatherAlert(
            title="Wind Advisory",
            description="High winds expected",
            event="Wind Advisory",
            severity="Moderate",
        )
        alerts = WeatherAlerts(alerts=[alert])
        order = engine.get_category_order(alerts=alerts)
        assert order[0] == WeatherCategory.WIND

    def test_heat_alert_prioritizes_temperature_and_uv(self):
        """Heat advisory should prioritize temperature and UV."""
        engine = PriorityEngine()
        alert = WeatherAlert(
            title="Heat Advisory",
            description="Extreme heat expected",
            event="Heat Advisory",
            severity="Severe",
        )
        alerts = WeatherAlerts(alerts=[alert])
        order = engine.get_category_order(alerts=alerts)
        assert order[0] == WeatherCategory.TEMPERATURE
        assert WeatherCategory.UV_INDEX in order[:3]

    def test_flood_alert_prioritizes_precipitation(self):
        """Flood watch should move precipitation to top."""
        engine = PriorityEngine()
        alert = WeatherAlert(
            title="Flash Flood Watch",
            description="Flooding possible",
            event="Flash Flood Watch",
            severity="Severe",
        )
        alerts = WeatherAlerts(alerts=[alert])
        order = engine.get_category_order(alerts=alerts)
        assert order[0] == WeatherCategory.PRECIPITATION

    def test_winter_alert_prioritizes_precipitation_and_temperature(self):
        """Winter storm should prioritize precipitation and temperature."""
        engine = PriorityEngine()
        alert = WeatherAlert(
            title="Winter Storm Warning",
            description="Heavy snow expected",
            event="Winter Storm Warning",
            severity="Severe",
        )
        alerts = WeatherAlerts(alerts=[alert])
        order = engine.get_category_order(alerts=alerts)
        assert order[0] == WeatherCategory.PRECIPITATION
        assert order[1] == WeatherCategory.TEMPERATURE

    def test_custom_order_respected(self):
        """Custom category order should be respected when no alerts."""
        custom_order = ["wind", "temperature", "precipitation"]
        engine = PriorityEngine(category_order=custom_order)
        order = engine.get_category_order(alerts=None)
        assert order[0] == WeatherCategory.WIND
        assert order[1] == WeatherCategory.TEMPERATURE

    def test_override_disabled_uses_user_order(self):
        """When override is disabled, always use user's order."""
        custom_order = ["wind", "temperature"]
        engine = PriorityEngine(
            category_order=custom_order,
            severe_weather_override=False,
        )
        alert = WeatherAlert(
            title="Heat Advisory",
            description="Heat",
            event="Heat Advisory",
            severity="Severe",
        )
        alerts = WeatherAlerts(alerts=[alert])
        order = engine.get_category_order(alerts=alerts)
        assert order[0] == WeatherCategory.WIND  # User order respected

    def test_verbosity_minimal_fields(self):
        """Minimal verbosity should return limited fields."""
        engine = PriorityEngine(verbosity_level="minimal")
        fields = engine.get_fields_for_category(WeatherCategory.TEMPERATURE)
        assert "temperature" in fields
        assert "feels_like" not in fields

    def test_verbosity_standard_fields(self):
        """Standard verbosity should return normal fields."""
        engine = PriorityEngine(verbosity_level="standard")
        fields = engine.get_fields_for_category(WeatherCategory.TEMPERATURE)
        assert "temperature" in fields
        assert "feels_like" in fields

    def test_verbosity_detailed_fields(self):
        """Detailed verbosity should return all fields."""
        engine = PriorityEngine(verbosity_level="detailed")
        fields = engine.get_fields_for_category(WeatherCategory.TEMPERATURE)
        assert "temperature" in fields
        assert "feels_like" in fields
        assert "dewpoint" in fields
