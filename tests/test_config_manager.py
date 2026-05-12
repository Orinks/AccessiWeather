"""
Tests for ConfigManager.

Tests configuration loading, saving, and location management.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from accessiweather.config import ConfigManager
from accessiweather.models import AppConfig, AppSettings


class TestConfigManager:
    """Tests for ConfigManager class."""

    @pytest.fixture
    def config_dir(self, tmp_path):
        """Create temporary config directory."""
        return tmp_path / "config"

    @pytest.fixture
    def mock_app(self, config_dir):
        """Create mock app with config path."""
        app = MagicMock()
        app.paths = MagicMock()
        app.paths.config = config_dir
        app.build_tag = None
        return app

    @pytest.fixture
    def manager(self, mock_app, config_dir):
        """Create ConfigManager instance."""
        return ConfigManager(mock_app, config_dir=config_dir)

    def test_creates_config_dir(self, mock_app, tmp_path):
        """Test that config directory is created."""
        config_dir = tmp_path / "new_config"
        ConfigManager(mock_app, config_dir=config_dir)
        assert config_dir.exists()

    def test_portable_mode_uses_current_directory_in_source_runtime(
        self, mock_app, tmp_path, monkeypatch
    ):
        """Portable source-runtime config is stored under the current directory."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "accessiweather.config.config_manager.is_compiled_runtime", lambda: False
        )

        manager = ConfigManager(mock_app, portable_mode=True)

        assert manager.config_dir == Path.cwd() / "config"

    def test_load_creates_default_config(self, manager):
        """Test that loading creates default config when none exists."""
        config = manager.load_config()
        assert config is not None
        assert isinstance(config, AppConfig)
        assert isinstance(config.settings, AppSettings)

    def test_save_and_load_config(self, manager):
        """Test saving and loading configuration."""
        config = manager.load_config()
        config.settings.update_interval_minutes = 30
        manager.save_config()

        # Create new manager to load saved config
        manager2 = ConfigManager(manager.app, config_dir=manager.config_dir)
        loaded = manager2.load_config()
        assert loaded.settings.update_interval_minutes == 30

    def test_legacy_show_nationwide_location_is_ignored_on_load(self, manager):
        """Legacy show_nationwide_location config no longer becomes a setting."""
        manager.config_file.parent.mkdir(parents=True, exist_ok=True)
        manager.config_file.write_text(
            '{"settings": {"show_nationwide_location": true}, '
            '"locations": [], "current_location": null}',
            encoding="utf-8",
        )

        loaded = manager.load_config()

        assert not hasattr(loaded.settings, "show_nationwide_location")

    def test_legacy_nationwide_location_is_filtered_on_load(self, manager):
        """A persisted Nationwide location should not count as a saved location."""
        manager.config_file.parent.mkdir(parents=True, exist_ok=True)
        manager.config_file.write_text(
            '{"settings": {}, '
            '"locations": [{"name": "Nationwide", "latitude": 39.8283, "longitude": -98.5795}], '
            '"current_location": {"name": "Nationwide", "latitude": 39.8283, "longitude": -98.5795}}',
            encoding="utf-8",
        )

        config = manager.load_config()
        manager.save_config()

        manager2 = ConfigManager(manager.app, config_dir=manager.config_dir)
        loaded = manager2.load_config()

        assert config.current_location is None
        assert loaded.current_location is None
        assert manager2.get_all_locations() == []
        assert manager2.get_location_names() == []
        assert manager2.has_locations() is False

    def test_add_location(self, manager):
        """Test adding a location."""
        result = manager.add_location(
            name="New York", latitude=40.7128, longitude=-74.0060, country_code="US"
        )
        assert result is True

        locations = manager.get_all_locations()
        assert len(locations) == 1
        assert locations[0].name == "New York"

    def test_add_location_persists_marine_mode_roundtrip(self, manager):
        """Marine mode should save and reload with locations."""
        result = manager.add_location(
            name="Annapolis",
            latitude=38.9784,
            longitude=-76.4922,
            country_code="US",
            marine_mode=True,
        )
        assert result is True

        manager.set_current_location("Annapolis")
        manager.save_config()

        manager2 = ConfigManager(manager.app, config_dir=manager.config_dir)
        loaded = manager2.load_config()

        saved_location = next(loc for loc in loaded.locations if loc.name == "Annapolis")
        assert saved_location.marine_mode is True
        assert loaded.current_location is not None
        assert loaded.current_location.name == "Annapolis"
        assert loaded.current_location.marine_mode is True

    def test_add_duplicate_location_fails(self, manager):
        """Test that adding duplicate location fails."""
        manager.add_location("Test", 40.0, -74.0)
        result = manager.add_location("Test", 40.0, -74.0)
        assert result is False

    def test_locations_are_returned_alphabetically(self, manager):
        """Saved locations are listed alphabetically regardless of add order."""
        manager.add_location("zurich", 47.3769, 8.5417)
        manager.add_location("Austin", 30.2672, -97.7431)
        manager.add_location("boston", 42.3601, -71.0589)

        assert [location.name for location in manager.get_all_locations()] == [
            "Austin",
            "boston",
            "zurich",
        ]
        assert manager.get_location_names() == ["Austin", "boston", "zurich"]

    def test_locations_are_saved_alphabetically(self, manager):
        """Location order is persisted alphabetically for future app launches."""
        manager.add_location("Zurich", 47.3769, 8.5417)
        manager.add_location("Austin", 30.2672, -97.7431)

        data = json.loads(manager.config_file.read_text(encoding="utf-8"))
        assert [location["name"] for location in data["locations"]] == ["Austin", "Zurich"]

        manager2 = ConfigManager(manager.app, config_dir=manager.config_dir)
        manager2.load_config()
        assert manager2.get_location_names() == ["Austin", "Zurich"]

    def test_remove_location(self, manager):
        """Test removing a location."""
        manager.add_location("Test", 40.0, -74.0)
        result = manager.remove_location("Test")
        assert result is True
        assert manager.get_all_locations() == []

    def test_remove_nonexistent_location_fails(self, manager):
        """Test that removing non-existent location fails."""
        result = manager.remove_location("Nonexistent")
        assert result is False

    def test_set_current_location(self, manager):
        """Test setting current location."""
        manager.add_location("Test", 40.0, -74.0)
        result = manager.set_current_location("Test")
        assert result is True

        current = manager.get_current_location()
        assert current is not None
        assert current.name == "Test"

    def test_get_current_location_none(self, manager):
        """Test getting current location when none set."""
        current = manager.get_current_location()
        assert current is None

    def test_get_location_names(self, manager):
        """Test getting location names."""
        manager.add_location("City A", 40.0, -74.0)
        manager.add_location("City B", 41.0, -75.0)

        names = manager.get_location_names()
        assert "City A" in names
        assert "City B" in names

    def test_has_locations(self, manager):
        """Test has_locations method."""
        assert manager.has_locations() is False
        manager.add_location("Test", 40.0, -74.0)
        assert manager.has_locations() is True

    def test_update_location_marine_mode_toggles_flag(self, manager):
        """update_location_marine_mode flips marine_mode and persists it."""
        manager.add_location("Annapolis", 38.9784, -76.4922)

        result = manager.update_location_marine_mode("Annapolis", True)
        assert result is True

        stored = next(loc for loc in manager.get_all_locations() if loc.name == "Annapolis")
        assert stored.marine_mode is True

        # Persists across a fresh manager instance.
        manager2 = ConfigManager(manager.app, config_dir=manager.config_dir)
        manager2.load_config()
        reloaded = next(loc for loc in manager2.get_all_locations() if loc.name == "Annapolis")
        assert reloaded.marine_mode is True

    def test_update_location_marine_mode_nonexistent_returns_false(self, manager):
        """Updating marine_mode on an unknown location returns False."""
        assert manager.update_location_marine_mode("Nowhere", True) is False

    def test_update_location_details_changes_coordinates_and_clears_zone_metadata(self, manager):
        """Updating saved coordinates keeps the name and clears stale zone fields."""
        manager.add_location("Lumberton", 39.965, -74.805, country_code="US")
        location = manager.get_all_locations()[0]
        location.timezone = "America/New_York"
        location.forecast_zone_id = "NJZ020"
        location.cwa_office = "PHI"
        location.county_zone_id = "NJC005"
        location.fire_zone_id = "NJZ020"
        location.radar_station = "KDIX"
        manager.save_config()

        result = manager.update_location_details(
            "Lumberton",
            latitude=39.9571,
            longitude=-74.8069,
            country_code="US",
            marine_mode=True,
        )

        assert result is True
        updated = manager.get_all_locations()[0]
        assert updated.name == "Lumberton"
        assert updated.latitude == pytest.approx(39.9571)
        assert updated.longitude == pytest.approx(-74.8069)
        assert updated.country_code == "US"
        assert updated.marine_mode is True
        assert updated.timezone is None
        assert updated.forecast_zone_id is None
        assert updated.cwa_office is None
        assert updated.county_zone_id is None
        assert updated.fire_zone_id is None
        assert updated.radar_station is None
        assert manager.get_current_location() is not None
        assert manager.get_current_location().latitude == pytest.approx(39.9571)

    def test_update_location_details_keeps_zone_metadata_when_coordinates_match(self, manager):
        """Updating only marine mode/country preserves resolved zone metadata."""
        manager.add_location("Lumberton", 39.965, -74.805, country_code="US")
        location = manager.get_all_locations()[0]
        location.forecast_zone_id = "NJZ020"
        location.county_zone_id = "NJC005"
        manager.save_config()

        result = manager.update_location_details(
            "Lumberton",
            latitude=39.965,
            longitude=-74.805,
            country_code="US",
            marine_mode=True,
        )

        assert result is True
        updated = manager.get_all_locations()[0]
        assert updated.forecast_zone_id == "NJZ020"
        assert updated.county_zone_id == "NJC005"

    def test_update_location_details_nonexistent_returns_false(self, manager):
        """Updating an unknown location returns False."""
        assert (
            manager.update_location_details(
                "Nowhere",
                latitude=1.0,
                longitude=2.0,
                country_code="US",
                marine_mode=False,
            )
            is False
        )

    def test_update_settings(self, manager):
        """Test updating settings."""
        manager.load_config()
        result = manager.update_settings(update_interval_minutes=15, enable_alerts=False)
        assert result is True

        settings = manager.get_settings()
        assert settings.update_interval_minutes == 15
        assert settings.enable_alerts is False

    def test_reset_to_defaults(self, manager):
        """Test resetting to defaults."""
        manager.load_config()
        manager.update_settings(update_interval_minutes=999)
        manager.reset_to_defaults()

        settings = manager.get_settings()
        # Should be back to default (10)
        assert settings.update_interval_minutes != 999

    def test_get_settings(self, manager):
        """Test getting settings."""
        settings = manager.get_settings()
        assert isinstance(settings, AppSettings)

    def test_backup_and_restore(self, manager, tmp_path):
        """Test backup and restore functionality."""
        manager.load_config()
        manager.add_location("Backup Test", 40.0, -74.0)

        backup_path = tmp_path / "backup.json"
        result = manager.backup_config(backup_path)
        assert result is True
        assert backup_path.exists()

        # Clear and restore
        manager.remove_location("Backup Test")
        result = manager.restore_config(backup_path)
        assert result is True

        locations = manager.get_all_locations()
        assert any(loc.name == "Backup Test" for loc in locations)

    def test_export_and_import_locations(self, manager, tmp_path):
        """Test exporting and importing locations."""
        manager.load_config()
        manager.add_location("Export Test", 40.0, -74.0)

        export_path = tmp_path / "locations.json"
        result = manager.export_locations(export_path)
        assert result is True

        # Clear and import
        manager.remove_location("Export Test")
        result = manager.import_locations(export_path)
        assert result is True

        locations = manager.get_all_locations()
        assert any(loc.name == "Export Test" for loc in locations)

    def test_atomic_save(self, manager):
        """Test that save is atomic (uses temp file)."""
        manager.load_config()
        manager.save_config()

        # Verify the config file exists (not a temp file)
        assert manager.config_file.exists()
        assert not manager.config_file.with_suffix(".json.tmp").exists()

    def test_default_update_channel_is_nightly_for_nightly_build(self, mock_app, config_dir):
        """Nightly builds should default to nightly channel on new config."""
        mock_app.build_tag = "nightly-20260226"
        manager = ConfigManager(mock_app, config_dir=config_dir)

        config = manager.load_config()

        assert config.settings.update_channel == "nightly"

    def test_encrypted_api_key_wrapper_methods_delegate(self, manager):
        manager._import_export = MagicMock()
        manager._import_export.export_encrypted_api_keys.return_value = True
        manager._import_export.import_encrypted_api_keys.return_value = True

        export_path = manager.config_dir / "keys.keys"

        assert manager.export_encrypted_api_keys(export_path, "pass") is True
        manager._import_export.export_encrypted_api_keys.assert_called_once_with(
            export_path, "pass"
        )

        assert manager.import_encrypted_api_keys(export_path, "pass") is True
        manager._import_export.import_encrypted_api_keys.assert_called_once_with(
            export_path, "pass"
        )

    def test_missing_update_channel_in_legacy_config_uses_build_default(self, mock_app, config_dir):
        """Legacy config without update_channel should get build-aware default."""
        mock_app.build_tag = "nightly-20260226"
        manager = ConfigManager(mock_app, config_dir=config_dir)

        # Write legacy config payload missing update_channel in settings.
        manager.config_file.parent.mkdir(parents=True, exist_ok=True)
        manager.config_file.write_text(
            '{"settings": {"temperature_unit": "both"}, "locations": [], "current_location": null}',
            encoding="utf-8",
        )

        config = manager.load_config()

        assert config.settings.update_channel == "nightly"
