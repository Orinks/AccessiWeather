"""Tests for priority ordering in taskbar tooltip."""

from accessiweather.models import CurrentConditions, Location, WeatherData
from accessiweather.taskbar_icon_updater import TaskbarIconUpdater


class TestTaskbarPriority:
    """Test taskbar tooltip uses priority ordering."""

    def test_tooltip_respects_verbosity_minimal(self):
        """Minimal verbosity should produce short tooltip with only location and temp."""
        updater = TaskbarIconUpdater(
            text_enabled=True,
            dynamic_enabled=True,
            verbosity_level="minimal",
        )
        current = CurrentConditions(
            temperature_f=75.0,
            humidity=65,
            wind_speed=15,
            condition="Sunny",
        )
        location = Location(name="Test", latitude=40.0, longitude=-75.0)
        weather_data = WeatherData(location=location, current=current)

        tooltip = updater.format_tooltip(weather_data, "Test")
        # Minimal should be: "Test: 75F" (just location + temp)
        assert "75" in tooltip
        assert "Sunny" not in tooltip  # Condition excluded at minimal
        assert "Humidity" not in tooltip  # Humidity excluded at minimal
        assert len(tooltip) < 20  # Very short

    def test_tooltip_respects_verbosity_detailed(self):
        """Detailed verbosity should include all available info."""
        updater = TaskbarIconUpdater(
            text_enabled=True,
            dynamic_enabled=True,
            verbosity_level="detailed",
        )
        current = CurrentConditions(
            temperature_f=75.0,
            feels_like_f=78.0,
            humidity=65,
            wind_speed=15,
            wind_direction="NW",
            condition="Sunny",
        )
        location = Location(name="Test", latitude=40.0, longitude=-75.0)
        weather_data = WeatherData(location=location, current=current)

        tooltip = updater.format_tooltip(weather_data, "Test")
        # Detailed should include temp, condition, feels like, humidity, wind
        assert "75" in tooltip  # Temperature
        assert "Sunny" in tooltip  # Condition
        assert "Feels" in tooltip  # Feels like label
        assert "78" in tooltip  # Feels like value
        assert "Humidity" in tooltip  # Humidity label
        assert "65" in tooltip  # Humidity value
        assert "Wind" in tooltip  # Wind label

    def test_minimal_produces_shorter_output_than_detailed(self):
        """Minimal verbosity produces significantly shorter output than detailed."""
        current = CurrentConditions(
            temperature_f=75.0,
            feels_like_f=78.0,
            humidity=65,
            wind_speed=15,
            wind_direction="NW",
            condition="Sunny",
        )
        location = Location(name="Test", latitude=40.0, longitude=-75.0)
        weather_data = WeatherData(location=location, current=current)

        minimal_updater = TaskbarIconUpdater(
            text_enabled=True,
            dynamic_enabled=True,
            verbosity_level="minimal",
        )
        detailed_updater = TaskbarIconUpdater(
            text_enabled=True,
            dynamic_enabled=True,
            verbosity_level="detailed",
        )

        minimal_tooltip = minimal_updater.format_tooltip(weather_data, "Test")
        detailed_tooltip = detailed_updater.format_tooltip(weather_data, "Test")

        # Minimal should be significantly shorter than detailed
        assert len(minimal_tooltip) < len(detailed_tooltip)
        # The difference should be substantial (at least 20 chars)
        assert len(detailed_tooltip) - len(minimal_tooltip) > 20

    def test_verbosity_level_default_is_standard(self):
        """Default verbosity level should be 'standard'."""
        updater = TaskbarIconUpdater(text_enabled=True, dynamic_enabled=True)
        assert updater.verbosity_level == "standard"

    def test_update_settings_with_verbosity_level(self):
        """Should update verbosity level via update_settings."""
        updater = TaskbarIconUpdater(text_enabled=True, dynamic_enabled=True)
        updater.update_settings(verbosity_level="detailed")
        assert updater.verbosity_level == "detailed"

    def test_minimal_verbosity_excludes_humidity(self):
        """Minimal verbosity should not include humidity."""
        updater = TaskbarIconUpdater(
            text_enabled=True,
            dynamic_enabled=True,
            verbosity_level="minimal",
        )
        current = CurrentConditions(
            temperature_f=75.0,
            humidity=65,
            condition="Sunny",
        )
        location = Location(name="Test", latitude=40.0, longitude=-75.0)
        weather_data = WeatherData(location=location, current=current)

        tooltip = updater.format_tooltip(weather_data, "Test")
        # In minimal mode, humidity should be excluded
        assert "65" not in tooltip  # Humidity value not present
        assert "Humidity" not in tooltip  # Humidity label not present
        # Temperature should still be present
        assert "75" in tooltip

    def test_minimal_verbosity_excludes_condition(self):
        """Minimal verbosity should not include weather condition."""
        updater = TaskbarIconUpdater(
            text_enabled=True,
            dynamic_enabled=True,
            verbosity_level="minimal",
        )
        current = CurrentConditions(
            temperature_f=75.0,
            condition="Sunny",
        )
        location = Location(name="Test", latitude=40.0, longitude=-75.0)
        weather_data = WeatherData(location=location, current=current)

        tooltip = updater.format_tooltip(weather_data, "Test")
        # In minimal mode, condition should be excluded
        assert "Sunny" not in tooltip
        # Temperature should still be present
        assert "75" in tooltip

    def test_detailed_verbosity_includes_feels_like(self):
        """Detailed verbosity should include feels-like temperature."""
        updater = TaskbarIconUpdater(
            text_enabled=True,
            dynamic_enabled=True,
            verbosity_level="detailed",
        )
        current = CurrentConditions(
            temperature_f=75.0,
            feels_like_f=78.0,
            condition="Sunny",
        )
        location = Location(name="Test", latitude=40.0, longitude=-75.0)
        weather_data = WeatherData(location=location, current=current)

        tooltip = updater.format_tooltip(weather_data, "Test")
        # Detailed mode should show feels-like
        assert "78" in tooltip
        assert "Feels" in tooltip

    def test_detailed_verbosity_includes_humidity(self):
        """Detailed verbosity should include humidity when available."""
        updater = TaskbarIconUpdater(
            text_enabled=True,
            dynamic_enabled=True,
            verbosity_level="detailed",
        )
        current = CurrentConditions(
            temperature_f=75.0,
            humidity=65,
            condition="Sunny",
        )
        location = Location(name="Test", latitude=40.0, longitude=-75.0)
        weather_data = WeatherData(location=location, current=current)

        tooltip = updater.format_tooltip(weather_data, "Test")
        # Detailed mode should show humidity
        assert "65" in tooltip
        assert "Humidity" in tooltip

    def test_detailed_verbosity_includes_wind(self):
        """Detailed verbosity should include wind when available."""
        updater = TaskbarIconUpdater(
            text_enabled=True,
            dynamic_enabled=True,
            verbosity_level="detailed",
        )
        current = CurrentConditions(
            temperature_f=75.0,
            wind_speed=15,
            wind_direction="NW",
            condition="Sunny",
        )
        location = Location(name="Test", latitude=40.0, longitude=-75.0)
        weather_data = WeatherData(location=location, current=current)

        tooltip = updater.format_tooltip(weather_data, "Test")
        # Detailed mode should show wind
        assert "Wind" in tooltip
        assert "15" in tooltip

    def test_standard_verbosity_includes_basic_info(self):
        """Standard verbosity should include temperature and condition."""
        updater = TaskbarIconUpdater(
            text_enabled=True,
            dynamic_enabled=True,
            verbosity_level="standard",
        )
        current = CurrentConditions(
            temperature_f=75.0,
            humidity=65,
            wind_speed=15,
            condition="Sunny",
        )
        location = Location(name="Test", latitude=40.0, longitude=-75.0)
        weather_data = WeatherData(location=location, current=current)

        tooltip = updater.format_tooltip(weather_data, "Test")
        # Standard mode should include temperature and condition
        assert "75" in tooltip
        assert "Sunny" in tooltip

    def test_standard_verbosity_excludes_detailed_info(self):
        """Standard verbosity should not include feels_like, humidity labels."""
        updater = TaskbarIconUpdater(
            text_enabled=True,
            dynamic_enabled=True,
            verbosity_level="standard",
        )
        current = CurrentConditions(
            temperature_f=75.0,
            feels_like_f=78.0,
            humidity=65,
            wind_speed=15,
            condition="Sunny",
        )
        location = Location(name="Test", latitude=40.0, longitude=-75.0)
        weather_data = WeatherData(location=location, current=current)

        tooltip = updater.format_tooltip(weather_data, "Test")
        # Standard mode should NOT include detailed labels
        assert "Feels" not in tooltip
        assert "Humidity" not in tooltip
        assert "Wind" not in tooltip


class TestTaskbarVerbosityInit:
    """Test verbosity_level initialization and settings."""

    def test_verbosity_level_init_minimal(self):
        """Should accept 'minimal' verbosity level."""
        updater = TaskbarIconUpdater(
            text_enabled=True,
            verbosity_level="minimal",
        )
        assert updater.verbosity_level == "minimal"

    def test_verbosity_level_init_standard(self):
        """Should accept 'standard' verbosity level."""
        updater = TaskbarIconUpdater(
            text_enabled=True,
            verbosity_level="standard",
        )
        assert updater.verbosity_level == "standard"

    def test_verbosity_level_init_detailed(self):
        """Should accept 'detailed' verbosity level."""
        updater = TaskbarIconUpdater(
            text_enabled=True,
            verbosity_level="detailed",
        )
        assert updater.verbosity_level == "detailed"

    def test_update_settings_preserves_verbosity(self):
        """update_settings should preserve verbosity when not explicitly set."""
        updater = TaskbarIconUpdater(
            text_enabled=True,
            verbosity_level="detailed",
        )
        updater.update_settings(text_enabled=False)
        assert updater.verbosity_level == "detailed"
