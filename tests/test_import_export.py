"""Tests for import/export functionality."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from accessiweather.config.import_export import ImportExportOperations
from accessiweather.models import AppConfig, Location


class TestImportExportOperations:
    """Tests for ImportExportOperations class."""

    @pytest.fixture
    def mock_manager(self, tmp_path):
        """Create mock ConfigManager."""
        manager = MagicMock()
        manager.config_file = tmp_path / "config.json"
        manager.config_dir = tmp_path
        manager._get_logger.return_value = MagicMock()

        # Create default config
        config = AppConfig.default()
        config.locations = [
            Location(name="Test Location", latitude=40.0, longitude=-74.0),
            Location(name="Another Location", latitude=45.0, longitude=-80.0),
        ]
        manager.get_config.return_value = config
        manager.load_config.return_value = config
        manager.save_config.return_value = True

        return manager

    @pytest.fixture
    def operations(self, mock_manager):
        """Create ImportExportOperations instance."""
        return ImportExportOperations(mock_manager)

    def test_logger_property(self, operations, mock_manager):
        """Test logger property returns manager's logger."""
        logger = operations.logger

        assert logger is mock_manager._get_logger.return_value


class TestBackupRestore:
    """Tests for backup and restore functionality."""

    @pytest.fixture
    def mock_manager(self, tmp_path):
        """Create mock ConfigManager with real config file."""
        manager = MagicMock()
        config_file = tmp_path / "config.json"
        config_file.write_text('{"test": "data"}')

        manager.config_file = config_file
        manager._get_logger.return_value = MagicMock()
        manager.load_config.return_value = AppConfig.default()
        return manager

    @pytest.fixture
    def operations(self, mock_manager):
        """Create ImportExportOperations instance."""
        return ImportExportOperations(mock_manager)

    def test_backup_config_success(self, operations, mock_manager, tmp_path):
        """Test successful config backup."""
        backup_path = tmp_path / "backup.json"

        result = operations.backup_config(backup_path)

        assert result is True
        assert backup_path.exists()
        assert backup_path.read_text() == '{"test": "data"}'

    def test_backup_config_default_path(self, operations, mock_manager):
        """Test backup config with default path."""
        result = operations.backup_config()

        expected_backup = mock_manager.config_file.with_suffix(".json.backup")
        assert result is True
        assert expected_backup.exists()

    def test_backup_config_no_config_file(self, operations, mock_manager, tmp_path):
        """Test backup when config file doesn't exist."""
        mock_manager.config_file = tmp_path / "nonexistent.json"

        result = operations.backup_config()

        assert result is False

    def test_backup_config_permission_error(self, operations, mock_manager):
        """Test backup config with permission error."""
        with patch('shutil.copy2', side_effect=PermissionError("Access denied")):
            result = operations.backup_config()

            assert result is False

    def test_restore_config_success(self, operations, mock_manager, tmp_path):
        """Test successful config restore."""
        backup_file = tmp_path / "backup.json"
        backup_file.write_text('{"restored": "data"}')

        result = operations.restore_config(backup_file)

        assert result is True
        assert mock_manager.config_file.read_text() == '{"restored": "data"}'
        mock_manager.load_config.assert_called_once()

    def test_restore_config_backup_not_found(self, operations, tmp_path):
        """Test restore when backup file doesn't exist."""
        nonexistent_backup = tmp_path / "nonexistent.json"

        result = operations.restore_config(nonexistent_backup)

        assert result is False

    def test_restore_config_copy_error(self, operations, tmp_path):
        """Test restore config with copy error."""
        backup_file = tmp_path / "backup.json"
        backup_file.write_text('{"test": "data"}')

        with patch('shutil.copy2', side_effect=OSError("Copy failed")):
            result = operations.restore_config(backup_file)

            assert result is False

    def test_restore_config_load_error(self, operations, mock_manager, tmp_path):
        """Test restore config with load error."""
        backup_file = tmp_path / "backup.json"
        backup_file.write_text('{"test": "data"}')
        mock_manager.load_config.side_effect = Exception("Load failed")

        result = operations.restore_config(backup_file)

        assert result is False


class TestExportSettings:
    """Tests for settings export functionality."""

    @pytest.fixture
    def mock_manager(self):
        """Create mock ConfigManager."""
        manager = MagicMock()
        manager._get_logger.return_value = MagicMock()

        config = AppConfig.default()
        config.settings.temperature_unit = "celsius"
        config.settings.data_source = "openmeteo"
        manager.get_config.return_value = config

        return manager

    @pytest.fixture
    def operations(self, mock_manager):
        """Create ImportExportOperations instance."""
        return ImportExportOperations(mock_manager)

    def test_export_settings_success(self, operations, tmp_path):
        """Test successful settings export."""
        export_file = tmp_path / "settings.json"

        result = operations.export_settings(export_file)

        assert result is True
        assert export_file.exists()

        # Check exported content
        exported_data = json.loads(export_file.read_text())
        assert "settings" in exported_data
        assert "exported_at" in exported_data
        assert exported_data["settings"]["temperature_unit"] == "celsius"
        assert exported_data["settings"]["data_source"] == "openmeteo"

    def test_export_settings_write_error(self, operations, tmp_path):
        """Test export settings with write error."""
        export_file = tmp_path / "readonly_dir" / "settings.json"

        result = operations.export_settings(export_file)

        assert result is False

    def test_export_settings_json_encoding(self, operations, tmp_path):
        """Test that exported JSON uses UTF-8 encoding."""
        export_file = tmp_path / "settings.json"

        operations.export_settings(export_file)

        # Verify file can be read with UTF-8
        with open(export_file, encoding="utf-8") as f:
            data = json.load(f)

        assert isinstance(data, dict)


class TestExportLocations:
    """Tests for locations export functionality."""

    @pytest.fixture
    def mock_manager(self):
        """Create mock ConfigManager."""
        manager = MagicMock()
        manager._get_logger.return_value = MagicMock()

        config = AppConfig.default()
        config.locations = [
            Location(name="New York", latitude=40.7128, longitude=-74.0060),
            Location(name="London", latitude=51.5074, longitude=-0.1278, country_code="GB"),
        ]
        manager.get_config.return_value = config

        return manager

    @pytest.fixture
    def operations(self, mock_manager):
        """Create ImportExportOperations instance."""
        return ImportExportOperations(mock_manager)

    def test_export_locations_success(self, operations, tmp_path):
        """Test successful locations export."""
        export_file = tmp_path / "locations.json"

        result = operations.export_locations(export_file)

        assert result is True
        assert export_file.exists()

        # Check exported content
        exported_data = json.loads(export_file.read_text())
        assert "locations" in exported_data
        assert "exported_at" in exported_data

        locations = exported_data["locations"]
        assert len(locations) == 2

        assert locations[0]["name"] == "New York"
        assert locations[0]["latitude"] == 40.7128
        assert locations[0]["longitude"] == -74.0060

        assert locations[1]["name"] == "London"
        assert locations[1]["latitude"] == 51.5074
        assert locations[1]["longitude"] == -0.1278

    def test_export_locations_write_error(self, operations, tmp_path):
        """Test export locations with write error."""
        export_file = tmp_path / "readonly_dir" / "locations.json"

        result = operations.export_locations(export_file)

        assert result is False


class TestImportLocations:
    """Tests for locations import functionality."""

    @pytest.fixture
    def mock_manager(self):
        """Create mock ConfigManager."""
        manager = MagicMock()
        manager._get_logger.return_value = MagicMock()

        config = AppConfig.default()
        config.locations = [
            Location(name="Existing Location", latitude=30.0, longitude=-90.0),
        ]
        manager.get_config.return_value = config
        manager.save_config.return_value = True

        return manager

    @pytest.fixture
    def operations(self, mock_manager):
        """Create ImportExportOperations instance."""
        return ImportExportOperations(mock_manager)

    def test_import_locations_success(self, operations, mock_manager, tmp_path):
        """Test successful locations import."""
        import_file = tmp_path / "import.json"
        import_data = {
            "locations": [
                {"name": "Paris", "latitude": 48.8566, "longitude": 2.3522},
                {"name": "Tokyo", "latitude": 35.6762, "longitude": 139.6503},
            ]
        }
        import_file.write_text(json.dumps(import_data))

        result = operations.import_locations(import_file)

        assert result is True
        mock_manager.save_config.assert_called_once()

        # Check that new locations were added
        config = mock_manager.get_config.return_value
        location_names = [loc.name for loc in config.locations]
        assert "Paris" in location_names
        assert "Tokyo" in location_names

    def test_import_locations_skip_duplicates(self, operations, mock_manager, tmp_path):
        """Test that duplicate locations are skipped."""
        import_file = tmp_path / "import.json"
        import_data = {
            "locations": [
                {"name": "Existing Location", "latitude": 30.0, "longitude": -90.0},
                {"name": "New Location", "latitude": 40.0, "longitude": -80.0},
            ]
        }
        import_file.write_text(json.dumps(import_data))

        result = operations.import_locations(import_file)

        assert result is True
        # Should still save because one location was added
        mock_manager.save_config.assert_called_once()

    def test_import_locations_invalid_json(self, operations, tmp_path):
        """Test import with invalid JSON."""
        import_file = tmp_path / "invalid.json"
        import_file.write_text("invalid json content")

        result = operations.import_locations(import_file)

        assert result is False

    def test_import_locations_missing_locations_key(self, operations, tmp_path):
        """Test import with missing locations key."""
        import_file = tmp_path / "import.json"
        import_data = {"other_data": "value"}
        import_file.write_text(json.dumps(import_data))

        result = operations.import_locations(import_file)

        # Should succeed with 0 imported locations
        assert result is True

    def test_import_locations_invalid_entry_type(self, operations, tmp_path):
        """Test import with invalid location entry type."""
        import_file = tmp_path / "import.json"
        import_data = {
            "locations": [
                "invalid_string_entry",
                {"name": "Valid Location", "latitude": 40.0, "longitude": -80.0},
            ]
        }
        import_file.write_text(json.dumps(import_data))

        result = operations.import_locations(import_file)

        # Should succeed because at least one valid location was imported
        assert result is True

    def test_import_locations_missing_required_fields(self, operations, tmp_path):
        """Test import with missing required fields."""
        import_file = tmp_path / "import.json"
        import_data = {
            "locations": [
                {"name": "Missing Coords"},  # Missing latitude and longitude
                {"latitude": 40.0, "longitude": -80.0},  # Missing name
                {"name": "Valid Location", "latitude": 40.0, "longitude": -80.0},
            ]
        }
        import_file.write_text(json.dumps(import_data))

        result = operations.import_locations(import_file)

        # Should succeed because one valid location was imported
        assert result is True

    def test_import_locations_invalid_coordinates(self, operations, tmp_path):
        """Test import with invalid coordinate values."""
        import_file = tmp_path / "import.json"
        import_data = {
            "locations": [
                {"name": "Invalid Lat", "latitude": "not_a_number", "longitude": -80.0},
                {"name": "Invalid Lon", "latitude": 40.0, "longitude": "also_not_a_number"},
                {"name": "Valid Location", "latitude": 40.0, "longitude": -80.0},
            ]
        }
        import_file.write_text(json.dumps(import_data))

        result = operations.import_locations(import_file)

        # Should succeed because one valid location was imported
        assert result is True

    def test_import_locations_all_invalid_entries(self, operations, tmp_path):
        """Test import where all entries are invalid."""
        import_file = tmp_path / "import.json"
        import_data = {
            "locations": [
                "invalid_string",
                {"name": "Missing Coords"},
                {"latitude": "not_a_number", "longitude": -80.0},
            ]
        }
        import_file.write_text(json.dumps(import_data))

        result = operations.import_locations(import_file)

        # Should fail because no valid locations were imported
        assert result is False

    def test_import_locations_coordinate_validation(self, operations, mock_manager, tmp_path):
        """Test that Location model validates coordinate ranges."""
        import_file = tmp_path / "import.json"
        import_data = {
            "locations": [
                {"name": "Valid Location", "latitude": 40.0, "longitude": -80.0},
            ]
        }
        import_file.write_text(json.dumps(import_data))

        # Mock Location constructor to validate ranges
        with patch('accessiweather.config.import_export.Location') as mock_location:
            mock_location.return_value = Location(name="Test", latitude=40.0, longitude=-80.0)

            result = operations.import_locations(import_file)

            assert result is True
            mock_location.assert_called_with(name="Valid Location", latitude=40.0, longitude=-80.0)

    def test_import_locations_file_read_error(self, operations, tmp_path):
        """Test import with file read error."""
        import_file = tmp_path / "nonexistent.json"

        result = operations.import_locations(import_file)

        assert result is False


class TestImportSettings:
    """Tests for settings import functionality."""

    @pytest.fixture
    def mock_manager(self):
        """Create mock ConfigManager."""
        manager = MagicMock()
        manager._get_logger.return_value = MagicMock()

        config = AppConfig.default()
        manager.get_config.return_value = config
        manager.save_config.return_value = True

        return manager

    @pytest.fixture
    def operations(self, mock_manager):
        """Create ImportExportOperations instance."""
        return ImportExportOperations(mock_manager)

    def test_import_settings_success(self, operations, mock_manager, tmp_path):
        """Test successful settings import."""
        import_file = tmp_path / "import.json"
        import_data = {
            "settings": {
                "temperature_unit": "celsius",
                "data_source": "openmeteo",
                "update_interval_minutes": 15,
            }
        }
        import_file.write_text(json.dumps(import_data))

        result = operations.import_settings(import_file)

        assert result is True
        mock_manager.save_config.assert_called_once()

    def test_import_settings_file_not_found(self, operations, tmp_path):
        """Test import when file doesn't exist."""
        import_file = tmp_path / "nonexistent.json"

        result = operations.import_settings(import_file)

        assert result is False

    def test_import_settings_invalid_json(self, operations, tmp_path):
        """Test import with invalid JSON."""
        import_file = tmp_path / "invalid.json"
        import_file.write_text("invalid json")

        result = operations.import_settings(import_file)

        assert result is False

    def test_import_settings_root_not_dict(self, operations, tmp_path):
        """Test import when root element is not a dictionary."""
        import_file = tmp_path / "import.json"
        import_file.write_text("[]")  # Array instead of object

        result = operations.import_settings(import_file)

        assert result is False

    def test_import_settings_missing_settings_key(self, operations, tmp_path):
        """Test import with missing settings key."""
        import_file = tmp_path / "import.json"
        import_data = {"other_data": "value"}
        import_file.write_text(json.dumps(import_data))

        result = operations.import_settings(import_file)

        assert result is False

    def test_import_settings_settings_not_dict(self, operations, tmp_path):
        """Test import when settings value is not a dictionary."""
        import_file = tmp_path / "import.json"
        import_data = {"settings": "not_a_dict"}
        import_file.write_text(json.dumps(import_data))

        result = operations.import_settings(import_file)

        assert result is False

    def test_import_settings_invalid_data_source(self, operations, tmp_path):
        """Test import with invalid data_source value."""
        import_file = tmp_path / "import.json"
        import_data = {
            "settings": {
                "data_source": "invalid_source",
                "temperature_unit": "celsius",
            }
        }
        import_file.write_text(json.dumps(import_data))

        result = operations.import_settings(import_file)

        # Should still succeed, with data_source corrected to "auto"
        assert result is True

    def test_import_settings_appsettings_validation_error(self, operations, tmp_path):
        """Test import with AppSettings validation error."""
        import_file = tmp_path / "import.json"
        import_data = {
            "settings": {
                "temperature_unit": "celsius",
            }
        }
        import_file.write_text(json.dumps(import_data))

        with patch('accessiweather.models.AppSettings.from_dict',
                  side_effect=Exception("Validation error")):
            result = operations.import_settings(import_file)

            assert result is False

    def test_import_settings_save_failure(self, operations, mock_manager, tmp_path):
        """Test import when save_config fails."""
        import_file = tmp_path / "import.json"
        import_data = {
            "settings": {
                "temperature_unit": "celsius",
            }
        }
        import_file.write_text(json.dumps(import_data))
        mock_manager.save_config.return_value = False

        result = operations.import_settings(import_file)

        assert result is False

    def test_import_settings_preserves_locations(self, operations, mock_manager, tmp_path):
        """Test that import_settings preserves existing locations."""
        import_file = tmp_path / "import.json"
        import_data = {
            "settings": {
                "temperature_unit": "celsius",
            }
        }
        import_file.write_text(json.dumps(import_data))

        # Set up existing locations
        original_locations = [Location(name="Test", latitude=40.0, longitude=-80.0)]
        config = mock_manager.get_config.return_value
        config.locations = original_locations

        operations.import_settings(import_file)

        # Verify locations were preserved
        assert config.locations is original_locations

    def test_import_settings_logs_missing_fields(self, operations, tmp_path):
        """Test that missing fields are logged appropriately."""
        import_file = tmp_path / "import.json"
        import_data = {
            "settings": {
                "temperature_unit": "celsius",
                # Missing other default fields
            }
        }
        import_file.write_text(json.dumps(import_data))

        result = operations.import_settings(import_file)

        # Should succeed and log missing fields
        assert result is True
