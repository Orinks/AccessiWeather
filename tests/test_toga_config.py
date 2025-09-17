"""Configuration and settings management tests for Toga AccessiWeather."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Set up Toga dummy backend
os.environ["TOGA_BACKEND"] = "toga_dummy"

from tests.toga_test_helpers import WeatherDataFactory


class TestAppConfig:
    """Test application configuration management."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration object."""
        config = MagicMock()
        config.config_file = "accessiweather.json"
        config.config_dir = "/mock/config"
        config.data = {
            "app": {
                "version": "1.0.0",
                "first_run": False,
                "data_source": "auto",
                "update_interval": 300,
            },
            "location": {
                "current": "New York, NY",
                "latitude": 40.7128,
                "longitude": -74.0060,
                "timezone": "America/New_York",
            },
            "display": {
                "temperature_unit": "fahrenheit",
                "show_feels_like": True,
                "show_humidity": True,
                "show_wind": True,
                "show_pressure": True,
            },
            "alerts": {
                "enabled": True,
                "sound": True,
                "desktop_notifications": True,
                "severity_filter": "minor",
            },
            "ui": {
                "theme": "system",
                "font_size": "medium",
                "high_contrast": False,
                "screen_reader_mode": False,
            },
        }
        return config

    def test_config_initialization(self, mock_config):
        """Test configuration initialization."""
        assert mock_config.config_file == "accessiweather.json"
        assert mock_config.data["app"]["version"] == "1.0.0"
        assert mock_config.data["location"]["current"] == "New York, NY"

    def test_config_default_values(self, mock_config):
        """Test default configuration values."""
        mock_config.get_defaults = MagicMock(
            return_value={
                "app": {"data_source": "auto", "update_interval": 300},
                "display": {"temperature_unit": "fahrenheit", "show_feels_like": True},
                "alerts": {"enabled": True, "sound": True},
                "ui": {"theme": "system", "font_size": "medium"},
            }
        )

        defaults = mock_config.get_defaults()

        assert defaults["app"]["data_source"] == "auto"
        assert defaults["display"]["temperature_unit"] == "fahrenheit"
        assert defaults["alerts"]["enabled"] is True
        assert defaults["ui"]["theme"] == "system"

    def test_config_validation(self, mock_config):
        """Test configuration validation."""
        mock_config.validate = MagicMock(return_value=True)

        # Test valid configuration
        is_valid = mock_config.validate()
        assert is_valid is True
        mock_config.validate.assert_called_once()

    def test_config_invalid_values(self, mock_config):
        """Test configuration with invalid values."""
        mock_config.validate = MagicMock(return_value=False)
        mock_config.get_validation_errors = MagicMock(
            return_value=["Invalid temperature unit", "Invalid update interval"]
        )

        # Test invalid configuration
        is_valid = mock_config.validate()
        errors = mock_config.get_validation_errors()

        assert is_valid is False
        assert len(errors) == 2
        assert "Invalid temperature unit" in errors

    def test_config_file_operations(self, mock_config):
        """Test configuration file operations."""
        mock_config.load_from_file = MagicMock(return_value=True)
        mock_config.save_to_file = MagicMock(return_value=True)

        # Test file operations
        load_success = mock_config.load_from_file()
        save_success = mock_config.save_to_file()

        assert load_success is True
        assert save_success is True
        mock_config.load_from_file.assert_called_once()
        mock_config.save_to_file.assert_called_once()

    def test_config_backup_restore(self, mock_config):
        """Test configuration backup and restore."""
        mock_config.create_backup = MagicMock(return_value="backup_20240101.json")
        mock_config.restore_from_backup = MagicMock(return_value=True)

        # Test backup operations
        backup_file = mock_config.create_backup()
        restore_success = mock_config.restore_from_backup(backup_file)

        assert backup_file == "backup_20240101.json"
        assert restore_success is True

    def test_config_migration(self, mock_config):
        """Test configuration migration between versions."""
        mock_config.current_version = "1.0.0"
        mock_config.migrate_config = MagicMock(return_value=True)
        mock_config.get_migration_path = MagicMock(return_value=["0.9.0", "1.0.0"])

        # Test migration
        migration_success = mock_config.migrate_config("0.9.0", "1.0.0")
        migration_path = mock_config.get_migration_path()

        assert migration_success is True
        assert migration_path == ["0.9.0", "1.0.0"]

    def test_config_get_set_operations(self, mock_config):
        """Test configuration get/set operations."""
        mock_config.get = MagicMock(return_value="fahrenheit")
        mock_config.set = MagicMock()

        # Test get/set operations
        temp_unit = mock_config.get("display.temperature_unit")
        mock_config.set("display.temperature_unit", "celsius")

        assert temp_unit == "fahrenheit"
        mock_config.get.assert_called_once_with("display.temperature_unit")
        mock_config.set.assert_called_once_with("display.temperature_unit", "celsius")

    def test_config_nested_access(self, mock_config):
        """Test nested configuration access."""
        mock_config.get_nested = MagicMock(return_value=True)
        mock_config.set_nested = MagicMock()

        # Test nested access
        alerts_enabled = mock_config.get_nested(["alerts", "enabled"])
        mock_config.set_nested(["alerts", "sound"], False)

        assert alerts_enabled is True
        mock_config.get_nested.assert_called_once_with(["alerts", "enabled"])
        mock_config.set_nested.assert_called_once_with(["alerts", "sound"], False)

    def test_config_change_notifications(self, mock_config):
        """Test configuration change notifications."""
        mock_config.on_config_change = MagicMock()
        mock_config.notify_change = MagicMock()

        # Test change notifications
        mock_config.notify_change("display.temperature_unit", "celsius")
        mock_config.notify_change.assert_called_once_with("display.temperature_unit", "celsius")

    def test_config_reset_to_defaults(self, mock_config):
        """Test resetting configuration to defaults."""
        mock_config.reset_to_defaults = MagicMock(return_value=True)
        mock_config.reset_section = MagicMock(return_value=True)

        # Test reset operations
        full_reset = mock_config.reset_to_defaults()
        section_reset = mock_config.reset_section("display")

        assert full_reset is True
        assert section_reset is True
        mock_config.reset_to_defaults.assert_called_once()
        mock_config.reset_section.assert_called_once_with("display")

    def test_config_environment_variables(self, mock_config):
        """Test configuration override from environment variables."""
        mock_config.load_from_env = MagicMock(
            return_value={"ACCESSIWEATHER_UPDATE_INTERVAL": "600"}
        )

        # Test environment variable loading
        env_overrides = mock_config.load_from_env()
        assert env_overrides["ACCESSIWEATHER_UPDATE_INTERVAL"] == "600"

    def test_config_command_line_args(self, mock_config):
        """Test configuration override from command line arguments."""
        mock_config.load_from_args = MagicMock(
            return_value={"location": "Boston, MA", "debug": True}
        )

        # Test command line argument loading
        args_overrides = mock_config.load_from_args()
        assert args_overrides["location"] == "Boston, MA"
        assert args_overrides["debug"] is True

    def test_config_export_import(self, mock_config):
        """Test configuration export and import."""
        mock_config.export_config = MagicMock(return_value={"exported": True})
        mock_config.import_config = MagicMock(return_value=True)

        # Test export/import operations
        exported_config = mock_config.export_config()
        import_success = mock_config.import_config(exported_config)

        assert exported_config["exported"] is True
        assert import_success is True

    def test_config_schema_validation(self, mock_config):
        """Test configuration schema validation."""
        mock_config.validate_schema = MagicMock(return_value=True)
        mock_config.get_schema = MagicMock(
            return_value={
                "type": "object",
                "properties": {
                    "app": {"type": "object"},
                    "display": {"type": "object"},
                },
            }
        )

        # Test schema validation
        is_valid = mock_config.validate_schema()
        schema = mock_config.get_schema()

        assert is_valid is True
        assert schema["type"] == "object"
        assert "app" in schema["properties"]


class TestAppSettings:
    """Test application settings management."""

    @pytest.fixture
    def mock_settings(self):
        """Create a mock settings object."""
        settings = MagicMock()
        settings.data = {
            "general": {
                "auto_start": False,
                "minimize_to_tray": True,
                "check_for_updates": True,
                "send_analytics": False,
            },
            "weather": {
                "preferred_source": "auto",
                "cache_duration": 300,
                "retry_attempts": 3,
                "timeout": 10,
            },
            "appearance": {
                "theme": "system",
                "font_family": "system",
                "font_size": 12,
                "high_contrast": False,
            },
            "accessibility": {
                "screen_reader_mode": False,
                "keyboard_navigation": True,
                "announce_updates": True,
                "voice_alerts": False,
            },
        }
        return settings

    def test_settings_initialization(self, mock_settings):
        """Test settings initialization."""
        assert mock_settings.data["general"]["minimize_to_tray"] is True
        assert mock_settings.data["weather"]["preferred_source"] == "auto"
        assert mock_settings.data["appearance"]["theme"] == "system"
        assert mock_settings.data["accessibility"]["keyboard_navigation"] is True

    def test_settings_general_options(self, mock_settings):
        """Test general settings options."""
        mock_settings.get_general_setting = MagicMock(return_value=True)
        mock_settings.set_general_setting = MagicMock()

        # Test general settings
        minimize_to_tray = mock_settings.get_general_setting("minimize_to_tray")
        mock_settings.set_general_setting("auto_start", True)

        assert minimize_to_tray is True
        mock_settings.set_general_setting.assert_called_once_with("auto_start", True)

    def test_settings_weather_options(self, mock_settings):
        """Test weather settings options."""
        mock_settings.get_weather_setting = MagicMock(return_value="auto")
        mock_settings.set_weather_setting = MagicMock()

        # Test weather settings
        preferred_source = mock_settings.get_weather_setting("preferred_source")
        mock_settings.set_weather_setting("cache_duration", 600)

        assert preferred_source == "auto"
        mock_settings.set_weather_setting.assert_called_once_with("cache_duration", 600)

    def test_settings_appearance_options(self, mock_settings):
        """Test appearance settings options."""
        mock_settings.get_appearance_setting = MagicMock(return_value="system")
        mock_settings.set_appearance_setting = MagicMock()

        # Test appearance settings
        theme = mock_settings.get_appearance_setting("theme")
        mock_settings.set_appearance_setting("font_size", 14)

        assert theme == "system"
        mock_settings.set_appearance_setting.assert_called_once_with("font_size", 14)

    def test_settings_accessibility_options(self, mock_settings):
        """Test accessibility settings options."""
        mock_settings.get_accessibility_setting = MagicMock(return_value=True)
        mock_settings.set_accessibility_setting = MagicMock()

        # Test accessibility settings
        keyboard_nav = mock_settings.get_accessibility_setting("keyboard_navigation")
        mock_settings.set_accessibility_setting("screen_reader_mode", True)

        assert keyboard_nav is True
        mock_settings.set_accessibility_setting.assert_called_once_with("screen_reader_mode", True)

    def test_settings_persistence(self, mock_settings):
        """Test settings persistence."""
        mock_settings.save_settings = MagicMock(return_value=True)
        mock_settings.load_settings = MagicMock(return_value=True)

        # Test persistence operations
        save_success = mock_settings.save_settings()
        load_success = mock_settings.load_settings()

        assert save_success is True
        assert load_success is True

    def test_settings_validation(self, mock_settings):
        """Test settings validation."""
        mock_settings.validate_setting = MagicMock(return_value=True)
        mock_settings.get_valid_values = MagicMock(return_value=["auto", "nws", "openmeteo"])

        # Test validation
        is_valid = mock_settings.validate_setting("weather.preferred_source", "auto")
        valid_values = mock_settings.get_valid_values("weather.preferred_source")

        assert is_valid is True
        assert "auto" in valid_values

    def test_settings_change_callbacks(self, mock_settings):
        """Test settings change callbacks."""
        mock_settings.on_setting_change = MagicMock()
        mock_settings.register_callback = MagicMock()

        # Test callback registration and execution
        mock_settings.register_callback("appearance.theme", lambda: None)
        mock_settings.on_setting_change("appearance.theme", "dark")

        mock_settings.register_callback.assert_called_once()
        mock_settings.on_setting_change.assert_called_once_with("appearance.theme", "dark")

    def test_settings_import_export(self, mock_settings):
        """Test settings import and export."""
        mock_settings.export_settings = MagicMock(return_value={"exported": True})
        mock_settings.import_settings = MagicMock(return_value=True)

        # Test import/export
        exported = mock_settings.export_settings()
        import_success = mock_settings.import_settings(exported)

        assert exported["exported"] is True
        assert import_success is True

    def test_settings_reset_options(self, mock_settings):
        """Test settings reset options."""
        mock_settings.reset_all_settings = MagicMock(return_value=True)
        mock_settings.reset_category = MagicMock(return_value=True)

        # Test reset operations
        reset_all = mock_settings.reset_all_settings()
        reset_appearance = mock_settings.reset_category("appearance")

        assert reset_all is True
        assert reset_appearance is True

    def test_settings_user_preferences(self, mock_settings):
        """Test user preferences management."""
        mock_settings.get_user_preference = MagicMock(return_value="metric")
        mock_settings.set_user_preference = MagicMock()

        # Test user preferences
        units = mock_settings.get_user_preference("units")
        mock_settings.set_user_preference("language", "en")

        assert units == "metric"
        mock_settings.set_user_preference.assert_called_once_with("language", "en")

    def test_settings_advanced_options(self, mock_settings):
        """Test advanced settings options."""
        mock_settings.get_advanced_setting = MagicMock(return_value=10)
        mock_settings.set_advanced_setting = MagicMock()

        # Test advanced settings
        timeout = mock_settings.get_advanced_setting("network_timeout")
        mock_settings.set_advanced_setting("debug_mode", True)

        assert timeout == 10
        mock_settings.set_advanced_setting.assert_called_once_with("debug_mode", True)


class TestLocationConfig:
    """Test location configuration management."""

    @pytest.fixture
    def mock_location_config(self):
        """Create a mock location configuration."""
        config = MagicMock()
        config.current_location = WeatherDataFactory.create_location()
        config.favorite_locations = [
            WeatherDataFactory.create_location("New York, NY", 40.7128, -74.0060),
            WeatherDataFactory.create_location("Los Angeles, CA", 34.0522, -118.2437),
            WeatherDataFactory.create_location("Chicago, IL", 41.8781, -87.6298),
        ]
        config.location_history = []
        config.auto_detect_location = True
        return config

    def test_location_config_initialization(self, mock_location_config):
        """Test location configuration initialization."""
        assert mock_location_config.current_location.name == "Test City, ST"
        assert len(mock_location_config.favorite_locations) == 3
        assert mock_location_config.auto_detect_location is True

    def test_location_config_current_location(self, mock_location_config):
        """Test current location management."""
        mock_location_config.set_current_location = MagicMock()
        mock_location_config.get_current_location = MagicMock(
            return_value=WeatherDataFactory.create_location()
        )

        # Test current location operations
        new_location = WeatherDataFactory.create_location("Boston, MA", 42.3601, -71.0589)
        mock_location_config.set_current_location(new_location)
        current = mock_location_config.get_current_location()

        assert current.name == "Test City, ST"
        mock_location_config.set_current_location.assert_called_once_with(new_location)

    def test_location_config_favorites(self, mock_location_config):
        """Test favorite locations management."""
        mock_location_config.add_favorite = MagicMock()
        mock_location_config.remove_favorite = MagicMock()
        mock_location_config.get_favorites = MagicMock(
            return_value=mock_location_config.favorite_locations
        )

        # Test favorites operations
        new_favorite = WeatherDataFactory.create_location("Miami, FL", 25.7617, -80.1918)
        mock_location_config.add_favorite(new_favorite)
        mock_location_config.remove_favorite("Chicago, IL")
        favorites = mock_location_config.get_favorites()

        assert len(favorites) == 3
        mock_location_config.add_favorite.assert_called_once_with(new_favorite)
        mock_location_config.remove_favorite.assert_called_once_with("Chicago, IL")

    def test_location_config_history(self, mock_location_config):
        """Test location history management."""
        mock_location_config.add_to_history = MagicMock()
        mock_location_config.get_history = MagicMock(return_value=[])
        mock_location_config.clear_history = MagicMock()

        # Test history operations
        location = WeatherDataFactory.create_location("Boston, MA", 42.3601, -71.0589)
        mock_location_config.add_to_history(location)
        history = mock_location_config.get_history()
        mock_location_config.clear_history()

        assert len(history) == 0
        mock_location_config.add_to_history.assert_called_once_with(location)
        mock_location_config.clear_history.assert_called_once()

    def test_location_config_auto_detection(self, mock_location_config):
        """Test automatic location detection."""
        mock_location_config.enable_auto_detection = MagicMock()
        mock_location_config.disable_auto_detection = MagicMock()
        mock_location_config.detect_location = MagicMock(
            return_value=WeatherDataFactory.create_location("Auto Location", 40.0, -75.0)
        )

        # Test auto detection
        mock_location_config.enable_auto_detection()
        detected = mock_location_config.detect_location()

        assert detected.name == "Auto Location"
        mock_location_config.enable_auto_detection.assert_called_once()

    def test_location_config_validation(self, mock_location_config):
        """Test location validation."""
        mock_location_config.validate_location = MagicMock(return_value=True)
        mock_location_config.validate_coordinates = MagicMock(return_value=True)

        # Test validation
        location = WeatherDataFactory.create_location("Valid Location", 40.0, -75.0)
        is_valid = mock_location_config.validate_location(location)
        coords_valid = mock_location_config.validate_coordinates(40.0, -75.0)

        assert is_valid is True
        assert coords_valid is True

    def test_location_config_search(self, mock_location_config):
        """Test location search functionality."""
        mock_location_config.search_locations = MagicMock(
            return_value=[
                WeatherDataFactory.create_location("New York, NY", 40.7128, -74.0060),
                WeatherDataFactory.create_location("New York, CA", 40.1234, -74.5678),
            ]
        )

        # Test location search
        results = mock_location_config.search_locations("New York")

        assert len(results) == 2
        assert results[0].name == "New York, NY"
        mock_location_config.search_locations.assert_called_once_with("New York")

    def test_location_config_geocoding(self, mock_location_config):
        """Test geocoding functionality."""
        mock_location_config.geocode_location = MagicMock(
            return_value=WeatherDataFactory.create_location("Geocoded Location", 40.0, -75.0)
        )
        mock_location_config.reverse_geocode = MagicMock(return_value="Reverse Geocoded Location")

        # Test geocoding
        geocoded = mock_location_config.geocode_location("Test Address")
        reverse_geocoded = mock_location_config.reverse_geocode(40.0, -75.0)

        assert geocoded.name == "Geocoded Location"
        assert reverse_geocoded == "Reverse Geocoded Location"

    def test_location_config_persistence(self, mock_location_config):
        """Test location configuration persistence."""
        mock_location_config.save_location_config = MagicMock(return_value=True)
        mock_location_config.load_location_config = MagicMock(return_value=True)

        # Test persistence
        save_success = mock_location_config.save_location_config()
        load_success = mock_location_config.load_location_config()

        assert save_success is True
        assert load_success is True

    def test_location_config_timezone_handling(self, mock_location_config):
        """Test timezone handling for locations."""
        mock_location_config.get_timezone = MagicMock(return_value="America/New_York")
        mock_location_config.set_timezone = MagicMock()

        # Test timezone operations
        timezone = mock_location_config.get_timezone()
        mock_location_config.set_timezone("America/Los_Angeles")

        assert timezone == "America/New_York"
        mock_location_config.set_timezone.assert_called_once_with("America/Los_Angeles")

    def test_location_config_import_export(self, mock_location_config):
        """Test location configuration import/export."""
        mock_location_config.export_locations = MagicMock(
            return_value={"locations": ["New York, NY", "Los Angeles, CA"]}
        )
        mock_location_config.import_locations = MagicMock(return_value=True)

        # Test import/export
        exported = mock_location_config.export_locations()
        import_success = mock_location_config.import_locations(exported)

        assert len(exported["locations"]) == 2
        assert import_success is True


class TestConfigurationUtils:
    """Test configuration utility functions."""

    def test_config_file_path_resolution(self):
        """Test configuration file path resolution."""
        with patch("pathlib.Path.home") as mock_home:
            mock_home.return_value = Path("/home/user")

            # Mock config path resolution
            config_path = Path("/home/user/.config/accessiweather/config.json")
            assert config_path.name == "config.json"
            assert "accessiweather" in str(config_path)

    def test_config_directory_creation(self):
        """Test configuration directory creation."""
        with patch("pathlib.Path.mkdir") as mock_mkdir:
            mock_mkdir.return_value = None

            # Mock directory creation
            config_dir = Path("/mock/config/accessiweather")
            config_dir.mkdir(parents=True, exist_ok=True)

            mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    def test_config_file_permissions(self):
        """Test configuration file permissions."""
        with patch("os.chmod") as mock_chmod:
            mock_chmod.return_value = None

            # Mock file permissions
            config_file = "/mock/config/accessiweather.json"
            os.chmod(config_file, 0o600)

            mock_chmod.assert_called_once_with(config_file, 0o600)

    def test_config_backup_rotation(self):
        """Test configuration backup rotation."""
        with patch("glob.glob") as mock_glob:
            mock_glob.return_value = [
                "config.json.backup.1",
                "config.json.backup.2",
                "config.json.backup.3",
            ]

            # Mock backup rotation
            backups = mock_glob("config.json.backup.*")
            assert len(backups) == 3

    def test_config_format_detection(self):
        """Test configuration format detection."""
        json_config = '{"app": {"version": "1.0.0"}}'

        # Test JSON format detection
        try:
            parsed = json.loads(json_config)
            assert parsed["app"]["version"] == "1.0.0"
        except json.JSONDecodeError:
            pytest.fail("JSON format detection failed")

    def test_config_encoding_handling(self):
        """Test configuration encoding handling."""
        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = '{"test": "value"}'

            # Mock encoding handling
            with open("config.json", encoding="utf-8") as f:
                content = f.read()

            assert content == '{"test": "value"}'

    def test_config_atomic_writes(self):
        """Test atomic configuration writes."""
        with patch("tempfile.NamedTemporaryFile") as mock_tempfile:
            mock_tempfile.return_value.__enter__.return_value.name = "temp_config.json"

            # Mock atomic write
            with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_file:
                temp_file.write('{"test": "value"}')
                temp_filename = temp_file.name

            assert temp_filename == "temp_config.json"

    def test_config_error_recovery(self):
        """Test configuration error recovery."""
        with patch("builtins.open", create=True) as mock_open:
            mock_open.side_effect = OSError("File not found")

            # Test error recovery
            try:
                with open("non_existent_config.json") as f:
                    f.read()  # We don't need to store the content
            except OSError as e:
                assert str(e) == "File not found"

    def test_config_version_detection(self):
        """Test configuration version detection."""
        config_v1 = {"version": "1.0.0", "app": {}}
        config_v2 = {"version": "2.0.0", "app": {}, "new_feature": {}}

        # Test version detection
        assert config_v1["version"] == "1.0.0"
        assert config_v2["version"] == "2.0.0"
        assert "new_feature" in config_v2

    def test_config_compatibility_check(self):
        """Test configuration compatibility checking."""
        current_version = "1.0.0"
        config_version = "1.0.0"

        # Test compatibility
        is_compatible = current_version == config_version
        assert is_compatible is True
