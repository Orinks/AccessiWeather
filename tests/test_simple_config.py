"""
Tests for configuration management in the simplified AccessiWeather application.

This module provides comprehensive tests for the ConfigManager in the simplified
AccessiWeather implementation, adapted from existing configuration test logic while
updating imports and ensuring tests match the simplified configuration architecture.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Import simplified app configuration components
from accessiweather.config import ConfigManager
from accessiweather.models import AppConfig, AppSettings


class TestConfigManagerBasics:
    """Test basic ConfigManager functionality - adapted from existing test logic."""

    @pytest.fixture
    def mock_app(self):
        """Create a mock Toga app for testing."""
        app = Mock()
        app.paths = Mock()

        # Create a temporary directory for config
        temp_dir = Path(tempfile.mkdtemp())
        app.paths.config = temp_dir

        return app

    @pytest.fixture
    def config_manager(self, mock_app):
        """Create a ConfigManager instance for testing."""
        return ConfigManager(mock_app)

    def test_config_manager_initialization(self, mock_app):
        """Test ConfigManager initialization."""
        config_manager = ConfigManager(mock_app)

        assert config_manager.app == mock_app
        assert config_manager.config_file == mock_app.paths.config / "accessiweather.json"
        assert config_manager._config is None

        # Check that config directory is created
        assert config_manager.config_file.parent.exists()

    def test_load_config_creates_default_when_no_file(self, config_manager):
        """Test loading config creates default when no file exists."""
        config = config_manager.load_config()

        assert isinstance(config, AppConfig)
        assert isinstance(config.settings, AppSettings)
        assert config.locations == []
        assert config.current_location is None

        # Should save default config
        assert config_manager.config_file.exists()

    def test_load_config_from_existing_file(self, config_manager):
        """Test loading config from existing file."""
        # Create a test config file
        test_config_data = {
            "settings": {
                "temperature_unit": "f",
                "update_interval_minutes": 15,
                "data_source": "nws",
            },
            "locations": [{"name": "Philadelphia, PA", "latitude": 39.9526, "longitude": -75.1652}],
            "current_location": {
                "name": "Philadelphia, PA",
                "latitude": 39.9526,
                "longitude": -75.1652,
            },
        }

        with open(config_manager.config_file, "w") as f:
            json.dump(test_config_data, f)

        config = config_manager.load_config()

        assert config.settings.temperature_unit == "f"
        assert config.settings.update_interval_minutes == 15
        assert config.settings.data_source == "nws"
        assert len(config.locations) == 1
        assert config.locations[0].name == "Philadelphia, PA"
        assert config.current_location.name == "Philadelphia, PA"

    def test_load_config_handles_corrupted_file(self, config_manager):
        """Test loading config handles corrupted JSON file gracefully."""
        # Create corrupted config file
        with open(config_manager.config_file, "w") as f:
            f.write("invalid json content")

        config = config_manager.load_config()

        # Should fall back to default config
        assert isinstance(config, AppConfig)
        assert config.settings.temperature_unit == "both"  # Default value
        assert config.locations == []

    def test_save_config_success(self, config_manager):
        """Test successful config saving."""
        # Load config first to initialize
        config = config_manager.load_config()
        config.settings.temperature_unit = "c"

        result = config_manager.save_config()

        assert result is True
        assert config_manager.config_file.exists()

        # Verify saved content
        with open(config_manager.config_file) as f:
            saved_data = json.load(f)

        assert saved_data["settings"]["temperature_unit"] == "c"

    def test_save_config_no_config_to_save(self, config_manager):
        """Test save_config when no config is loaded."""
        result = config_manager.save_config()

        assert result is False

    def test_get_config_loads_if_not_cached(self, config_manager):
        """Test get_config loads config if not already cached."""
        assert config_manager._config is None

        config = config_manager.get_config()

        assert config_manager._config is not None
        assert config == config_manager._config

    def test_get_config_returns_cached_config(self, config_manager):
        """Test get_config returns cached config if available."""
        # Load config first
        first_config = config_manager.get_config()

        # Get config again
        second_config = config_manager.get_config()

        # Should be the same instance
        assert first_config is second_config

    def test_critical_config_fast_load(self, mock_app):
        """
        Test that critical settings load without keyring access.

        This test verifies the lazy keyring access optimization:
        - Critical config (temperature_unit, data_source, update_interval_minutes)
          should load synchronously without touching the keyring
        - SecureStorage.get_password should NOT be called during load_config()
        - LazySecureStorage objects should be created but not accessed
        """
        # Create a config file with critical settings
        test_config_data = {
            "settings": {
                "temperature_unit": "f",
                "update_interval_minutes": 15,
                "data_source": "nws",
            },
            "locations": [{"name": "Test City", "latitude": 40.0, "longitude": -75.0}],
            "current_location": {"name": "Test City", "latitude": 40.0, "longitude": -75.0},
        }

        config_dir = mock_app.paths.config
        config_file = config_dir / "accessiweather.json"
        with open(config_file, "w") as f:
            json.dump(test_config_data, f)

        # Mock SecureStorage.get_password to ensure it's NOT called during load
        with patch(
            "accessiweather.config.secure_storage.SecureStorage.get_password"
        ) as mock_get_password:
            # Create ConfigManager and load config
            config_manager = ConfigManager(mock_app)
            config = config_manager.load_config()

            # Verify keyring was NOT accessed during load_config()
            assert mock_get_password.call_count == 0, (
                f"SecureStorage.get_password should not be called during load_config(), "
                f"but was called {mock_get_password.call_count} time(s)"
            )

        # Verify critical settings are loaded correctly
        assert config.settings.temperature_unit == "f"
        assert config.settings.update_interval_minutes == 15
        assert config.settings.data_source == "nws"

        # Verify location is loaded
        assert config.current_location is not None
        assert config.current_location.name == "Test City"

        # Verify LazySecureStorage objects were created for secure keys
        # These should exist but NOT have been accessed (._loaded should be False)
        from accessiweather.config.secure_storage import LazySecureStorage

        secure_keys = [
            "visual_crossing_api_key",
            "openrouter_api_key",
            "github_app_id",
            "github_app_private_key",
            "github_app_installation_id",
        ]
        for key in secure_keys:
            attr = getattr(config.settings, key, None)
            assert isinstance(attr, LazySecureStorage), (
                f"Setting '{key}' should be a LazySecureStorage instance"
            )
            assert not attr._loaded, f"LazySecureStorage for '{key}' should not be loaded yet"

    def test_lazy_keyring_access(self, mock_app):
        """
        Test that keyring is only accessed when API key property is actually read.

        This test verifies the lazy keyring access pattern:
        1. Loading config should NOT trigger keyring access
        2. Accessing the .value property of a LazySecureStorage SHOULD trigger keyring access
        3. Subsequent accesses should use cached value (no additional keyring calls)
        """
        from accessiweather.config.secure_storage import LazySecureStorage

        # Create a config file
        test_config_data = {
            "settings": {
                "temperature_unit": "f",
                "update_interval_minutes": 15,
                "data_source": "nws",
            },
            "locations": [],
            "current_location": None,
        }

        config_dir = mock_app.paths.config
        config_file = config_dir / "accessiweather.json"
        with open(config_file, "w") as f:
            json.dump(test_config_data, f)

        with patch(
            "accessiweather.config.secure_storage.SecureStorage.get_password"
        ) as mock_get_password:
            # Return a test API key when keyring is accessed
            mock_get_password.return_value = "test-api-key-12345"

            # Step 1: Load config - keyring should NOT be accessed
            config_manager = ConfigManager(mock_app)
            config = config_manager.load_config()

            assert mock_get_password.call_count == 0, (
                f"Keyring should not be accessed during load_config(), "
                f"but was called {mock_get_password.call_count} time(s)"
            )

            # Verify LazySecureStorage is in place
            api_key_lazy = config.settings.visual_crossing_api_key
            assert isinstance(api_key_lazy, LazySecureStorage), (
                "visual_crossing_api_key should be a LazySecureStorage instance"
            )
            assert not api_key_lazy._loaded, (
                "LazySecureStorage should not be loaded before value access"
            )

            # Step 2: Access the .value property - keyring SHOULD be accessed now
            api_key_value = api_key_lazy.value

            assert mock_get_password.call_count == 1, (
                f"Keyring should be accessed exactly once when reading .value, "
                f"but was called {mock_get_password.call_count} time(s)"
            )
            assert api_key_value == "test-api-key-12345", (
                f"Expected 'test-api-key-12345', got '{api_key_value}'"
            )
            assert api_key_lazy._loaded, (
                "LazySecureStorage should be marked as loaded after value access"
            )

            # Step 3: Access value again - should use cached value, no additional keyring call
            api_key_value_again = api_key_lazy.value

            assert mock_get_password.call_count == 1, (
                f"Keyring should not be called again on subsequent accesses, "
                f"but call count increased to {mock_get_password.call_count}"
            )
            assert api_key_value_again == "test-api-key-12345", (
                "Cached value should be returned on subsequent access"
            )

    def test_deferred_validation(self, mock_app):
        """
        Test that non-critical settings are validated on first access, not at load time.

        This test verifies the deferred validation pattern:
        1. Invalid values for non-critical settings are NOT corrected during load_config()
        2. Calling validate_on_access() validates and corrects invalid values
        3. Critical settings are validated immediately (already tested elsewhere)
        """
        from accessiweather.models.config import NON_CRITICAL_SETTINGS

        # Create a config file with invalid values for non-critical settings
        test_config_data = {
            "settings": {
                # Critical settings (valid)
                "temperature_unit": "f",
                "update_interval_minutes": 15,
                "data_source": "nws",
                # Non-critical settings with INVALID values
                "ai_explanation_style": "invalid_style",  # Should be brief/standard/detailed
                "update_channel": "invalid_channel",  # Should be stable/beta/dev
                "time_display_mode": "invalid_mode",  # Should be local/utc/both
                "sound_pack": "",  # Should be non-empty string
                "alert_global_cooldown_minutes": -5,  # Should be >= 0
                "alert_max_notifications_per_hour": 0,  # Should be >= 1
                "trend_hours": 500,  # Should be 1-168
            },
            "locations": [],
            "current_location": None,
        }

        config_dir = mock_app.paths.config
        config_file = config_dir / "accessiweather.json"
        with open(config_file, "w") as f:
            json.dump(test_config_data, f)

        # Load config - invalid values should be loaded as-is (deferred validation)
        config_manager = ConfigManager(mock_app)
        config = config_manager.load_config()

        # Verify critical settings are loaded correctly
        assert config.settings.temperature_unit == "f"
        assert config.settings.update_interval_minutes == 15
        assert config.settings.data_source == "nws"

        # Verify non-critical settings still have invalid values before validation
        # (they were loaded from file but not yet validated)
        assert config.settings.ai_explanation_style == "invalid_style"
        assert config.settings.update_channel == "invalid_channel"
        assert config.settings.time_display_mode == "invalid_mode"
        assert config.settings.sound_pack == ""
        assert config.settings.alert_global_cooldown_minutes == -5
        assert config.settings.alert_max_notifications_per_hour == 0
        assert config.settings.trend_hours == 500

        # Now trigger deferred validation for each non-critical setting
        # This simulates "first access" validation

        # Validate ai_explanation_style - should correct to "standard"
        result = config.settings.validate_on_access("ai_explanation_style")
        assert result is True
        assert config.settings.ai_explanation_style == "standard"

        # Validate update_channel - should correct to "stable"
        result = config.settings.validate_on_access("update_channel")
        assert result is True
        assert config.settings.update_channel == "stable"

        # Validate time_display_mode - should correct to "local"
        result = config.settings.validate_on_access("time_display_mode")
        assert result is True
        assert config.settings.time_display_mode == "local"

        # Validate sound_pack - should correct to "default"
        result = config.settings.validate_on_access("sound_pack")
        assert result is True
        assert config.settings.sound_pack == "default"

        # Validate alert_global_cooldown_minutes - should correct to 5
        result = config.settings.validate_on_access("alert_global_cooldown_minutes")
        assert result is True
        assert config.settings.alert_global_cooldown_minutes == 5

        # Validate alert_max_notifications_per_hour - should correct to 10
        result = config.settings.validate_on_access("alert_max_notifications_per_hour")
        assert result is True
        assert config.settings.alert_max_notifications_per_hour == 10

        # Validate trend_hours - should correct to 24 (out of valid range)
        result = config.settings.validate_on_access("trend_hours")
        assert result is True
        assert config.settings.trend_hours == 24

        # Verify validate_on_access returns False for unknown settings
        result = config.settings.validate_on_access("unknown_setting_name")
        assert result is False

        # Verify that a valid non-critical setting passes validation unchanged
        config.settings.ai_cache_ttl = 600  # Valid value
        result = config.settings.validate_on_access("ai_cache_ttl")
        assert result is True
        assert config.settings.ai_cache_ttl == 600  # Should remain unchanged

        # Verify that the NON_CRITICAL_SETTINGS constant contains expected settings
        assert "ai_explanation_style" in NON_CRITICAL_SETTINGS
        assert "update_channel" in NON_CRITICAL_SETTINGS
        assert "time_display_mode" in NON_CRITICAL_SETTINGS
        assert "sound_pack" in NON_CRITICAL_SETTINGS


class TestConfigManagerSettings:
    """Test ConfigManager settings management - adapted from existing test logic."""

    @pytest.fixture
    def mock_app(self):
        """Create a mock Toga app for testing."""
        app = Mock()
        app.paths = Mock()
        temp_dir = Path(tempfile.mkdtemp())
        app.paths.config = temp_dir
        return app

    @pytest.fixture
    def config_manager(self, mock_app):
        """Create a ConfigManager instance for testing."""
        return ConfigManager(mock_app)

    def test_update_settings_valid_attributes(self, config_manager):
        """Test updating valid settings attributes."""
        result = config_manager.update_settings(
            temperature_unit="f", update_interval_minutes=20, data_source="openmeteo"
        )

        assert result is True

        config = config_manager.get_config()
        assert config.settings.temperature_unit == "f"
        assert config.settings.update_interval_minutes == 20
        assert config.settings.data_source == "openmeteo"

    def test_update_settings_invalid_attribute(self, config_manager):
        """Test updating invalid settings attribute."""
        with patch("accessiweather.config.logger") as mock_logger:
            result = config_manager.update_settings(temperature_unit="c", invalid_setting="value")

            assert result is True  # Should still save valid settings
            mock_logger.warning.assert_called_with("Unknown setting: invalid_setting")

        config = config_manager.get_config()
        assert config.settings.temperature_unit == "c"

    def test_get_settings(self, config_manager):
        """Test getting application settings."""
        settings = config_manager.get_settings()

        assert isinstance(settings, AppSettings)
        assert settings.temperature_unit == "both"  # Default value
        assert settings.update_interval_minutes == 10  # Default value

    def test_reset_to_defaults(self, config_manager):
        """Test resetting configuration to defaults."""
        # Modify config first
        config_manager.update_settings(temperature_unit="f", update_interval_minutes=30)
        config_manager.add_location("Test City", 40.0, -75.0)

        result = config_manager.reset_to_defaults()

        assert result is True

        config = config_manager.get_config()
        assert config.settings.temperature_unit == "both"  # Default
        assert config.settings.update_interval_minutes == 10  # Default
        assert config.locations == []  # Default
        assert config.current_location is None  # Default


class TestConfigManagerLocations:
    """Test ConfigManager location management - adapted from existing test logic."""

    @pytest.fixture
    def mock_app(self):
        """Create a mock Toga app for testing."""
        app = Mock()
        app.paths = Mock()
        temp_dir = Path(tempfile.mkdtemp())
        app.paths.config = temp_dir
        return app

    @pytest.fixture
    def config_manager(self, mock_app):
        """Create a ConfigManager instance for testing."""
        return ConfigManager(mock_app)

    def test_add_location_success(self, config_manager):
        """Test successfully adding a new location."""
        result = config_manager.add_location("Philadelphia, PA", 39.9526, -75.1652)

        assert result is True

        locations = config_manager.get_all_locations()
        assert len(locations) == 1
        assert locations[0].name == "Philadelphia, PA"
        assert locations[0].latitude == 39.9526
        assert locations[0].longitude == -75.1652

        # Should be set as current location (first location)
        current = config_manager.get_current_location()
        assert current.name == "Philadelphia, PA"

    def test_add_location_duplicate_name(self, config_manager):
        """Test adding location with duplicate name."""
        # Add first location
        config_manager.add_location("Test City", 40.0, -75.0)

        # Try to add duplicate
        result = config_manager.add_location("Test City", 41.0, -76.0)

        assert result is False

        locations = config_manager.get_all_locations()
        assert len(locations) == 1  # Should still be only one
        assert locations[0].latitude == 40.0  # Original coordinates

    def test_add_location_with_country_code(self, config_manager):
        """Locations should persist country codes when provided."""
        result = config_manager.add_location(
            "Toronto, Ontario", 43.6535, -79.3839, country_code="ca"
        )

        assert result is True

        current = config_manager.get_current_location()
        assert current is not None
        assert current.country_code == "CA"

        reloaded = ConfigManager(config_manager.app)
        reloaded.load_config()
        reloaded_locations = reloaded.get_all_locations()
        assert reloaded_locations[0].country_code == "CA"

    def test_add_multiple_locations(self, config_manager):
        """Test adding multiple locations."""
        config_manager.add_location("Philadelphia, PA", 39.9526, -75.1652)
        config_manager.add_location("New York, NY", 40.7128, -74.0060)

        locations = config_manager.get_all_locations()
        assert len(locations) == 2

        location_names = config_manager.get_location_names()
        assert "Philadelphia, PA" in location_names
        assert "New York, NY" in location_names

    def test_remove_location_success(self, config_manager):
        """Test successfully removing a location."""
        # Add locations first
        config_manager.add_location("Philadelphia, PA", 39.9526, -75.1652)
        config_manager.add_location("New York, NY", 40.7128, -74.0060)

        result = config_manager.remove_location("Philadelphia, PA")

        assert result is True

        locations = config_manager.get_all_locations()
        assert len(locations) == 1
        assert locations[0].name == "New York, NY"

    def test_remove_location_not_found(self, config_manager):
        """Test removing non-existent location."""
        result = config_manager.remove_location("Non-existent City")

        assert result is False

    def test_remove_current_location_updates_current(self, config_manager):
        """Test removing current location updates current location."""
        # Add locations
        config_manager.add_location("Philadelphia, PA", 39.9526, -75.1652)
        config_manager.add_location("New York, NY", 40.7128, -74.0060)

        # Set first as current
        config_manager.set_current_location("Philadelphia, PA")

        # Remove current location
        config_manager.remove_location("Philadelphia, PA")

        # Should automatically set remaining location as current
        current = config_manager.get_current_location()
        assert current.name == "New York, NY"

    def test_remove_last_location_clears_current(self, config_manager):
        """Test removing last location clears current location."""
        # Add one location
        config_manager.add_location("Test City", 40.0, -75.0)

        # Remove it
        config_manager.remove_location("Test City")

        # Current should be None
        current = config_manager.get_current_location()
        assert current is None

    def test_set_current_location_success(self, config_manager):
        """Test successfully setting current location."""
        # Add locations
        config_manager.add_location("Philadelphia, PA", 39.9526, -75.1652)
        config_manager.add_location("New York, NY", 40.7128, -74.0060)

        result = config_manager.set_current_location("New York, NY")

        assert result is True

        current = config_manager.get_current_location()
        assert current.name == "New York, NY"

    def test_set_current_location_not_found(self, config_manager):
        """Test setting current location that doesn't exist."""
        result = config_manager.set_current_location("Non-existent City")

        assert result is False

    def test_has_locations(self, config_manager):
        """Test checking if locations exist."""
        # Initially no locations
        assert config_manager.has_locations() is False

        # Add a location
        config_manager.add_location("Test City", 40.0, -75.0)

        assert config_manager.has_locations() is True

    def test_get_location_names(self, config_manager):
        """Test getting location names."""
        # Add locations
        config_manager.add_location("Philadelphia, PA", 39.9526, -75.1652)
        config_manager.add_location("New York, NY", 40.7128, -74.0060)

        names = config_manager.get_location_names()

        assert len(names) == 2
        assert "Philadelphia, PA" in names
        assert "New York, NY" in names


class TestConfigManagerFileOperations:
    """Test ConfigManager file operations - adapted from existing test logic."""

    @pytest.fixture
    def mock_app(self):
        """Create a mock Toga app for testing."""
        app = Mock()
        app.paths = Mock()
        temp_dir = Path(tempfile.mkdtemp())
        app.paths.config = temp_dir
        return app

    @pytest.fixture
    def config_manager(self, mock_app):
        """Create a ConfigManager instance for testing."""
        return ConfigManager(mock_app)

    def test_backup_config_success(self, config_manager):
        """Test successful config backup."""
        # Create config first
        config_manager.add_location("Test City", 40.0, -75.0)

        result = config_manager.backup_config()

        assert result is True

        backup_path = config_manager.config_file.with_suffix(".json.backup")
        assert backup_path.exists()

    def test_backup_config_custom_path(self, config_manager):
        """Test config backup with custom path."""
        # Create config first
        config_manager.add_location("Test City", 40.0, -75.0)

        custom_backup = config_manager.config_file.parent / "custom_backup.json"
        result = config_manager.backup_config(custom_backup)

        assert result is True
        assert custom_backup.exists()

    def test_backup_config_no_file_to_backup(self, config_manager):
        """Test backup when no config file exists."""
        # Don't create any config
        result = config_manager.backup_config()

        assert result is False

    def test_restore_config_success(self, config_manager):
        """Test successful config restoration."""
        # Create original config
        config_manager.add_location("Original City", 40.0, -75.0)
        config_manager.update_settings(temperature_unit="f")

        # Create backup
        backup_path = config_manager.config_file.with_suffix(".json.backup")
        config_manager.backup_config(backup_path)

        # Modify config
        config_manager.add_location("New City", 41.0, -76.0)
        config_manager.update_settings(temperature_unit="c")

        # Restore from backup
        result = config_manager.restore_config(backup_path)

        assert result is True

        # Verify restoration
        config = config_manager.get_config()
        assert len(config.locations) == 1
        assert config.locations[0].name == "Original City"
        assert config.settings.temperature_unit == "f"

    def test_restore_config_file_not_found(self, config_manager):
        """Test restore when backup file doesn't exist."""
        non_existent_path = config_manager.config_file.parent / "non_existent.json"

        result = config_manager.restore_config(non_existent_path)

        assert result is False

    def test_export_locations_success(self, config_manager):
        """Test successful location export."""
        # Add locations
        config_manager.add_location("Philadelphia, PA", 39.9526, -75.1652)
        config_manager.add_location("New York, NY", 40.7128, -74.0060)

        export_path = config_manager.config_file.parent / "exported_locations.json"
        result = config_manager.export_locations(export_path)

        assert result is True
        assert export_path.exists()

        # Verify export content
        with open(export_path) as f:
            exported_data = json.load(f)

        assert "locations" in exported_data
        assert "exported_at" in exported_data
        assert len(exported_data["locations"]) == 2
        assert exported_data["locations"][0]["name"] == "Philadelphia, PA"

    def test_import_locations_success(self, config_manager):
        """Test successful location import."""
        # Create import file
        import_data = {
            "locations": [
                {"name": "Boston, MA", "latitude": 42.3601, "longitude": -71.0589},
                {"name": "Chicago, IL", "latitude": 41.8781, "longitude": -87.6298},
            ],
            "exported_at": "2024-01-01T00:00:00",
        }

        import_path = config_manager.config_file.parent / "import_locations.json"
        with open(import_path, "w") as f:
            json.dump(import_data, f)

        result = config_manager.import_locations(import_path)

        assert result is True

        locations = config_manager.get_all_locations()
        assert len(locations) == 2
        assert any(loc.name == "Boston, MA" for loc in locations)
        assert any(loc.name == "Chicago, IL" for loc in locations)

    def test_import_locations_skip_duplicates(self, config_manager):
        """Test import skips duplicate locations."""
        # Add existing location
        config_manager.add_location("Boston, MA", 42.3601, -71.0589)

        # Create import file with duplicate
        import_data = {
            "locations": [
                {"name": "Boston, MA", "latitude": 42.3601, "longitude": -71.0589},  # Duplicate
                {"name": "Chicago, IL", "latitude": 41.8781, "longitude": -87.6298},  # New
            ]
        }

        import_path = config_manager.config_file.parent / "import_locations.json"
        with open(import_path, "w") as f:
            json.dump(import_data, f)

        result = config_manager.import_locations(import_path)

        assert result is True

        locations = config_manager.get_all_locations()
        assert len(locations) == 2  # Should only add the new one
        boston_locations = [loc for loc in locations if loc.name == "Boston, MA"]
        assert len(boston_locations) == 1  # Only one Boston location


class TestConfigManagerErrorHandling:
    """Test ConfigManager error handling - adapted from existing test logic."""

    @pytest.fixture
    def mock_app(self):
        """Create a mock Toga app for testing."""
        app = Mock()
        app.paths = Mock()
        temp_dir = Path(tempfile.mkdtemp())
        app.paths.config = temp_dir
        return app

    @pytest.fixture
    def config_manager(self, mock_app):
        """Create a ConfigManager instance for testing."""
        return ConfigManager(mock_app)

    def test_save_config_file_permission_error(self, config_manager):
        """Test save_config handles file permission errors."""
        # Load config first
        config_manager.load_config()

        # Mock file write to raise permission error
        with patch("builtins.open", side_effect=PermissionError("Permission denied")):
            result = config_manager.save_config()

            assert result is False

    def test_load_config_file_permission_error(self, config_manager):
        """Test load_config handles file permission errors."""
        # Create config file first
        config_manager.load_config()  # This creates the file

        # Mock file read to raise permission error
        with patch("builtins.open", side_effect=PermissionError("Permission denied")):
            # Clear cached config to force reload
            config_manager._config = None

            config = config_manager.load_config()

            # Should fall back to default config
            assert isinstance(config, AppConfig)
            assert config.settings.temperature_unit == "both"

    def test_export_locations_file_error(self, config_manager):
        """Test export_locations handles file errors."""
        config_manager.add_location("Test City", 40.0, -75.0)

        export_path = config_manager.config_file.parent / "export_test.json"

        with patch("builtins.open", side_effect=OSError("Disk full")):
            result = config_manager.export_locations(export_path)

            assert result is False

    def test_import_locations_invalid_json(self, config_manager):
        """Test import_locations handles invalid JSON."""
        import_path = config_manager.config_file.parent / "invalid_import.json"

        # Create invalid JSON file
        with open(import_path, "w") as f:
            f.write("invalid json content")

        result = config_manager.import_locations(import_path)

        assert result is False

    def test_import_locations_missing_fields(self, config_manager):
        """Test import_locations handles missing required fields."""
        import_data = {
            "locations": [
                {"name": "Incomplete Location"},  # Missing latitude/longitude
                {"latitude": 40.0, "longitude": -75.0},  # Missing name
            ]
        }

        import_path = config_manager.config_file.parent / "incomplete_import.json"
        with open(import_path, "w") as f:
            json.dump(import_data, f)

        # Should handle gracefully and not crash
        result = config_manager.import_locations(import_path)

        # May return False due to KeyError, but shouldn't crash
        assert result is False


# Smoke test functions that can be run with briefcase dev --test
def test_config_manager_can_be_imported():
    """Test that ConfigManager can be imported successfully."""
    from accessiweather.config import ConfigManager

    # Basic instantiation test with mock app
    mock_app = Mock()
    mock_app.paths = Mock()
    mock_app.paths.config = Path(tempfile.mkdtemp())

    config_manager = ConfigManager(mock_app)
    assert config_manager is not None


def test_config_manager_basic_functionality():
    """Test basic ConfigManager functionality without complex scenarios."""
    from accessiweather.config import ConfigManager

    # Create mock app
    mock_app = Mock()
    mock_app.paths = Mock()
    mock_app.paths.config = Path(tempfile.mkdtemp())

    config_manager = ConfigManager(mock_app)

    # Test basic operations
    config = config_manager.get_config()
    assert isinstance(config, AppConfig)

    # Test settings access
    settings = config_manager.get_settings()
    assert isinstance(settings, AppSettings)

    # Test location operations
    assert config_manager.has_locations() is False

    result = config_manager.add_location("Test City", 40.0, -75.0)
    assert result is True

    assert config_manager.has_locations() is True

    locations = config_manager.get_all_locations()
    assert len(locations) == 1
    assert locations[0].name == "Test City"
