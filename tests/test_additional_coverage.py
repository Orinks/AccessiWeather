"""Additional coverage tests for various utility and helper modules."""


class TestWeatherServiceImports:
    """Test weather service imports."""

    def test_weather_service_imports(self):
        """Test that WeatherService can be imported."""
        from accessiweather.services.weather_service import ConfigurationError, WeatherService

        assert WeatherService is not None
        assert ConfigurationError is not None


class TestUtilsInit:
    """Test utils package init."""

    def test_utils_imports(self):
        """Test that utils exports are accessible."""
        from accessiweather.utils import (
            TemperatureUnit,
            convert_wind_direction_to_cardinal,
            format_pressure,
            format_temperature,
            format_wind_speed,
        )

        assert TemperatureUnit is not None
        assert callable(convert_wind_direction_to_cardinal)
        assert callable(format_pressure)
        assert callable(format_temperature)
        assert callable(format_wind_speed)


class TestDialogSoundpackCommunity:
    """Test soundpack community dialog integration."""

    def test_community_integration_import(self):
        """Test that CommunityIntegration class is importable."""
        from accessiweather.dialogs.soundpack_manager.community import (
            CommunityIntegration,
        )

        assert CommunityIntegration is not None


class TestModelHelpers:
    """Test model helper methods."""

    def test_weather_alert_get_unique_id(self):
        """Test WeatherAlert unique ID generation includes areas."""
        from accessiweather.models.alerts import WeatherAlert

        alert = WeatherAlert(
            title="Test Alert",
            description="Test description",
            event="Thunderstorm Warning",
            severity="Severe",
            headline="Severe Thunderstorm Warning",
            areas=["County B", "County A"],  # Test areas are sorted alphabetically
        )

        unique_id = alert.get_unique_id()
        assert isinstance(unique_id, str)
        assert len(unique_id) > 0
        assert "thunderstorm_warning" in unique_id.lower()
        # Areas should be included (sorted: County A, County B)
        assert "county_a,county_b" in unique_id.lower()

    def test_weather_alert_get_unique_id_different_areas(self):
        """Test that alerts with same event/severity/headline but different areas produce different IDs."""
        from accessiweather.models.alerts import WeatherAlert

        alert1 = WeatherAlert(
            title="Test Alert",
            description="Test description",
            event="Thunderstorm Warning",
            severity="Severe",
            headline="Severe Thunderstorm Warning",
            areas=["County A"],
        )

        alert2 = WeatherAlert(
            title="Test Alert",
            description="Test description",
            event="Thunderstorm Warning",
            severity="Severe",
            headline="Severe Thunderstorm Warning",
            areas=["County B"],
        )

        unique_id1 = alert1.get_unique_id()
        unique_id2 = alert2.get_unique_id()

        assert unique_id1 != unique_id2
        assert "county_a" in unique_id1.lower()
        assert "county_b" in unique_id2.lower()

    def test_weather_alert_get_unique_id_with_id(self):
        """Test WeatherAlert unique ID when ID is provided."""
        from accessiweather.models.alerts import WeatherAlert

        alert = WeatherAlert(
            title="Test Alert",
            description="Test description",
            id="custom-alert-123",
        )

        unique_id = alert.get_unique_id()
        assert unique_id == "custom-alert-123"

    def test_weather_alert_content_hash(self):
        """Test WeatherAlert content hash generation."""
        from accessiweather.models.alerts import WeatherAlert

        alert = WeatherAlert(
            title="Test Alert",
            description="Test description",
            severity="Moderate",
        )

        content_hash = alert.get_content_hash()
        assert isinstance(content_hash, str)
        assert len(content_hash) == 32  # MD5 hash length

    def test_weather_alert_is_expired_no_expiry(self):
        """Test WeatherAlert expiration when no expiry is set."""
        from accessiweather.models.alerts import WeatherAlert

        alert = WeatherAlert(title="Test", description="Test")
        assert alert.is_expired() is False

    def test_weather_alert_is_expired_future(self):
        """Test WeatherAlert expiration with future date."""
        from datetime import UTC, datetime, timedelta

        from accessiweather.models.alerts import WeatherAlert

        future = datetime.now(UTC) + timedelta(hours=2)
        alert = WeatherAlert(title="Test", description="Test", expires=future)
        assert alert.is_expired() is False

    def test_weather_alert_is_expired_past(self):
        """Test WeatherAlert expiration with past date."""
        from datetime import UTC, datetime, timedelta

        from accessiweather.models.alerts import WeatherAlert

        past = datetime.now(UTC) - timedelta(hours=2)
        alert = WeatherAlert(title="Test", description="Test", expires=past)
        assert alert.is_expired() is True

    def test_weather_alert_severity_priority(self):
        """Test WeatherAlert severity priority levels."""
        from accessiweather.models.alerts import WeatherAlert

        extreme = WeatherAlert(title="T", description="T", severity="Extreme")
        severe = WeatherAlert(title="T", description="T", severity="Severe")
        moderate = WeatherAlert(title="T", description="T", severity="Moderate")
        minor = WeatherAlert(title="T", description="T", severity="Minor")
        unknown = WeatherAlert(title="T", description="T", severity="Unknown")

        assert extreme.get_severity_priority() == 5
        assert severe.get_severity_priority() == 4
        assert moderate.get_severity_priority() == 3
        assert minor.get_severity_priority() == 2
        assert unknown.get_severity_priority() == 1

    def test_app_settings_as_bool(self):
        """Test AppSettings _as_bool helper."""
        from accessiweather.models.config import AppSettings

        assert AppSettings._as_bool(True, False) is True
        assert AppSettings._as_bool(False, True) is False
        assert AppSettings._as_bool(None, True) is True
        assert AppSettings._as_bool("true", False) is True
        assert AppSettings._as_bool("false", True) is False
        assert AppSettings._as_bool("yes", False) is True
        assert AppSettings._as_bool("no", True) is False
        assert AppSettings._as_bool("1", False) is True
        assert AppSettings._as_bool("0", True) is False
        assert AppSettings._as_bool(1, False) is True
        assert AppSettings._as_bool(0, True) is False

    def test_app_settings_to_dict(self):
        """Test AppSettings to_dict method."""
        from accessiweather.models.config import AppSettings

        settings = AppSettings(
            temperature_unit="fahrenheit",
            update_interval_minutes=15,
            enable_alerts=True,
        )

        settings_dict = settings.to_dict()
        assert isinstance(settings_dict, dict)
        assert settings_dict["temperature_unit"] == "fahrenheit"
        assert settings_dict["update_interval_minutes"] == 15
        assert settings_dict["enable_alerts"] is True

    def test_app_config_to_dict(self):
        """Test AppConfig to_dict method."""
        from accessiweather.models.config import AppConfig, AppSettings
        from accessiweather.models.weather import Location

        config = AppConfig(
            settings=AppSettings(),
            locations=[Location(name="Test", latitude=40.0, longitude=-74.0)],
            current_location=None,
        )

        config_dict = config.to_dict()
        assert isinstance(config_dict, dict)
        assert "settings" in config_dict
        assert "locations" in config_dict
        assert len(config_dict["locations"]) == 1

    def test_app_settings_from_dict(self):
        """Test AppSettings from_dict classmethod."""
        from accessiweather.models.config import AppSettings

        data = {
            "temperature_unit": "celsius",
            "update_interval_minutes": 20,
            "enable_alerts": False,
        }

        settings = AppSettings.from_dict(data)
        assert settings.temperature_unit == "celsius"
        assert settings.update_interval_minutes == 20
        assert settings.enable_alerts is False

    def test_app_settings_to_alert_settings(self):
        """Test AppSettings to_alert_settings conversion."""
        from accessiweather.models.config import AppSettings

        settings = AppSettings(
            alert_notifications_enabled=True,
            sound_enabled=True,
            alert_global_cooldown_minutes=10,
            alert_notify_severe=True,
        )

        alert_settings = settings.to_alert_settings()
        assert alert_settings.notifications_enabled is True
        assert alert_settings.sound_enabled is True
        assert alert_settings.global_cooldown == 10


class TestConfigUtilsModule:
    """Test config utils module."""

    def test_is_portable_mode(self):
        """Test is_portable_mode function."""
        from accessiweather.config_utils import is_portable_mode

        result = is_portable_mode()
        assert isinstance(result, bool)
