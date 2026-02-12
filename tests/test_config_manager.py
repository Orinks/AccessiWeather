"""
Tests for ConfigManager.

Tests configuration loading, saving, and location management.
"""

from __future__ import annotations

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

    def test_add_location(self, manager):
        """Test adding a location."""
        result = manager.add_location(
            name="New York", latitude=40.7128, longitude=-74.0060, country_code="US"
        )
        assert result is True

        locations = manager.get_all_locations()
        non_nationwide = [loc for loc in locations if loc.name != "Nationwide"]
        assert len(non_nationwide) == 1
        assert non_nationwide[0].name == "New York"

    def test_add_duplicate_location_fails(self, manager):
        """Test that adding duplicate location fails."""
        manager.add_location("Test", 40.0, -74.0)
        result = manager.add_location("Test", 40.0, -74.0)
        assert result is False

    def test_remove_location(self, manager):
        """Test removing a location."""
        manager.add_location("Test", 40.0, -74.0)
        result = manager.remove_location("Test")
        assert result is True
        non_nationwide = [loc for loc in manager.get_all_locations() if loc.name != "Nationwide"]
        assert len(non_nationwide) == 0

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
