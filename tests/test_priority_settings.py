"""Tests for priority ordering settings."""

from accessiweather.models.config import AppSettings


class TestPrioritySettings:
    """Test priority ordering settings in AppSettings."""

    def test_default_verbosity_level(self):
        """Default verbosity should be 'standard'."""
        settings = AppSettings()
        assert settings.verbosity_level == "standard"

    def test_default_category_order(self):
        """Default category order should be temperature first."""
        settings = AppSettings()
        expected = [
            "temperature",
            "precipitation",
            "wind",
            "humidity_pressure",
            "visibility_clouds",
            "uv_index",
        ]
        assert settings.category_order == expected

    def test_default_severe_weather_override(self):
        """Severe weather override should be enabled by default."""
        settings = AppSettings()
        assert settings.severe_weather_override is True

    def test_verbosity_level_options(self):
        """Verbosity level should accept valid options."""
        for level in ["minimal", "standard", "detailed"]:
            settings = AppSettings(verbosity_level=level)
            assert settings.verbosity_level == level

    def test_settings_to_dict_includes_priority_fields(self):
        """to_dict should include priority ordering fields."""
        settings = AppSettings()
        data = settings.to_dict()
        assert "verbosity_level" in data
        assert "category_order" in data
        assert "severe_weather_override" in data

    def test_settings_from_dict_loads_priority_fields(self):
        """from_dict should load priority ordering fields."""
        data = {
            "verbosity_level": "minimal",
            "category_order": ["wind", "temperature"],
            "severe_weather_override": False,
        }
        settings = AppSettings.from_dict(data)
        assert settings.verbosity_level == "minimal"
        assert settings.category_order == ["wind", "temperature"]
        assert settings.severe_weather_override is False
