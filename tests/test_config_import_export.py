"""Tests for configuration import/export functionality."""

from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from accessiweather.config import ConfigManager
from accessiweather.models import AppConfig, AppSettings


class TestExportSettings:
    """Test settings export functionality."""

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

    def test_export_settings_success(self, config_manager):
        """Test successful export to valid path."""
        # Configure some settings
        config_manager.update_settings(
            temperature_unit="f",
            update_interval_minutes=15,
            data_source="nws",
            enable_alerts=True,
        )

        export_path = config_manager.config_file.parent / "exported_settings.json"
        result = config_manager.export_settings(export_path)

        assert result is True
        assert export_path.exists()

    def test_export_settings_creates_valid_json_structure(self, config_manager):
        """Test export creates valid JSON with correct structure."""
        # Configure settings
        config_manager.update_settings(
            temperature_unit="c",
            update_interval_minutes=20,
            data_source="openmeteo",
        )

        export_path = config_manager.config_file.parent / "exported_settings.json"
        config_manager.export_settings(export_path)

        # Verify export content
        with open(export_path) as f:
            exported_data = json.load(f)

        # Check structure
        assert isinstance(exported_data, dict)
        assert "settings" in exported_data
        assert "exported_at" in exported_data
        assert isinstance(exported_data["settings"], dict)

        # Verify settings values
        settings = exported_data["settings"]
        assert settings["temperature_unit"] == "c"
        assert settings["update_interval_minutes"] == 20
        assert settings["data_source"] == "openmeteo"

    def test_export_settings_includes_timestamp(self, config_manager):
        """Test exported JSON includes timestamp."""
        export_path = config_manager.config_file.parent / "exported_settings.json"

        # Record time before export
        before_export = datetime.now()
        config_manager.export_settings(export_path)
        after_export = datetime.now()

        # Verify timestamp is present
        with open(export_path) as f:
            exported_data = json.load(f)

        assert "exported_at" in exported_data
        assert isinstance(exported_data["exported_at"], str)
        assert len(exported_data["exported_at"]) > 0

        # Verify timestamp is reasonable (can be parsed)
        timestamp_str = exported_data["exported_at"]
        assert len(timestamp_str) > 10  # Basic sanity check

    def test_export_settings_excludes_secure_keys(self, config_manager):
        """Test exported JSON excludes secure keys (API keys)."""
        # Set settings including secure keys
        config = config_manager.get_config()
        config.settings.visual_crossing_api_key = "secret-api-key-123"
        config.settings.openrouter_api_key = "secret-openrouter-key"
        config.settings.github_app_id = "secret-github-app-id"
        config.settings.github_app_private_key = "secret-private-key"
        config.settings.github_app_installation_id = "secret-installation-id"
        config.settings.temperature_unit = "f"
        config_manager.save_config()

        export_path = config_manager.config_file.parent / "exported_settings.json"
        config_manager.export_settings(export_path)

        # Verify secure keys are NOT in exported file
        with open(export_path) as f:
            exported_data = json.load(f)

        settings = exported_data["settings"]

        # These secure keys should NOT be present in export
        assert "visual_crossing_api_key" not in settings
        assert "openrouter_api_key" not in settings
        assert "github_app_id" not in settings
        assert "github_app_private_key" not in settings
        assert "github_app_installation_id" not in settings

        # But regular settings should be present
        assert "temperature_unit" in settings
        assert settings["temperature_unit"] == "f"

    def test_export_settings_returns_true_on_success(self, config_manager):
        """Test export returns True on success."""
        export_path = config_manager.config_file.parent / "exported_settings.json"
        result = config_manager.export_settings(export_path)

        assert result is True

    def test_export_settings_returns_false_on_write_error(self, config_manager):
        """Test export returns False on write error."""
        export_path = config_manager.config_file.parent / "exported_settings.json"

        # Mock open to raise OSError
        with patch("builtins.open", side_effect=OSError("Disk full")):
            result = config_manager.export_settings(export_path)

            assert result is False

    def test_export_settings_handles_permission_errors(self, config_manager):
        """Test export handles permission errors gracefully."""
        export_path = config_manager.config_file.parent / "exported_settings.json"

        # Mock open to raise PermissionError
        with patch("builtins.open", side_effect=PermissionError("Permission denied")):
            result = config_manager.export_settings(export_path)

            assert result is False

    def test_export_settings_logs_success(self, config_manager):
        """Test export logs success message."""
        export_path = config_manager.config_file.parent / "exported_settings.json"

        with patch("accessiweather.config.import_export.logger") as mock_logger:
            config_manager.export_settings(export_path)

            # Verify success was logged
            mock_logger.info.assert_called()
            call_args = mock_logger.info.call_args[0][0]
            assert "exported" in call_args.lower()
            assert str(export_path) in call_args

    def test_export_settings_logs_failure(self, config_manager):
        """Test export logs failure message on error."""
        export_path = config_manager.config_file.parent / "exported_settings.json"

        with patch("accessiweather.config.import_export.logger") as mock_logger:
            with patch("builtins.open", side_effect=OSError("Disk full")):
                config_manager.export_settings(export_path)

                # Verify error was logged
                mock_logger.error.assert_called()
                call_args = mock_logger.error.call_args[0][0]
                assert "failed" in call_args.lower()
                assert "export" in call_args.lower()

    def test_export_settings_preserves_complex_settings(self, config_manager):
        """Test export preserves complex settings like lists."""
        # Configure settings with list values
        config = config_manager.get_config()
        config.settings.alert_ignored_categories = ["Flood", "Wind"]
        config.settings.source_priority_us = ["nws", "openmeteo"]
        config.settings.category_order = ["temperature", "precipitation", "wind"]
        config_manager.save_config()

        export_path = config_manager.config_file.parent / "exported_settings.json"
        config_manager.export_settings(export_path)

        # Verify complex settings are preserved
        with open(export_path) as f:
            exported_data = json.load(f)

        settings = exported_data["settings"]
        assert settings["alert_ignored_categories"] == ["Flood", "Wind"]
        assert settings["source_priority_us"] == ["nws", "openmeteo"]
        assert settings["category_order"] == ["temperature", "precipitation", "wind"]

    def test_export_settings_with_all_default_values(self, config_manager):
        """Test export with all default settings values."""
        # Use default settings (no modifications)
        export_path = config_manager.config_file.parent / "exported_settings.json"
        result = config_manager.export_settings(export_path)

        assert result is True

        # Verify all expected settings are present
        with open(export_path) as f:
            exported_data = json.load(f)

        settings = exported_data["settings"]

        # Check some default values
        assert "temperature_unit" in settings
        assert "update_interval_minutes" in settings
        assert "data_source" in settings
        assert "enable_alerts" in settings

    def test_export_settings_to_nested_directory(self, config_manager):
        """Test export to nested directory path."""
        # Create nested directory
        nested_dir = config_manager.config_file.parent / "backups" / "settings"
        nested_dir.mkdir(parents=True, exist_ok=True)

        export_path = nested_dir / "exported_settings.json"
        result = config_manager.export_settings(export_path)

        assert result is True
        assert export_path.exists()

    def test_export_settings_overwrites_existing_file(self, config_manager):
        """Test export overwrites existing file."""
        export_path = config_manager.config_file.parent / "exported_settings.json"

        # First export
        config_manager.update_settings(temperature_unit="f")
        config_manager.export_settings(export_path)

        # Modify settings and export again
        config_manager.update_settings(temperature_unit="c")
        result = config_manager.export_settings(export_path)

        assert result is True

        # Verify file was overwritten with new values
        with open(export_path) as f:
            exported_data = json.load(f)

        assert exported_data["settings"]["temperature_unit"] == "c"

    def test_export_settings_with_custom_values(self, config_manager):
        """Test export with custom non-default values."""
        # Set custom values for various settings
        config_manager.update_settings(
            temperature_unit="c",
            update_interval_minutes=30,
            data_source="visualcrossing",
            enable_alerts=False,
            sound_enabled=False,
            debug_mode=True,
            alert_global_cooldown_minutes=10,
            trend_hours=48,
        )

        export_path = config_manager.config_file.parent / "exported_settings.json"
        config_manager.export_settings(export_path)

        # Verify custom values are exported
        with open(export_path) as f:
            exported_data = json.load(f)

        settings = exported_data["settings"]
        assert settings["temperature_unit"] == "c"
        assert settings["update_interval_minutes"] == 30
        assert settings["data_source"] == "visualcrossing"
        assert settings["enable_alerts"] is False
        assert settings["sound_enabled"] is False
        assert settings["debug_mode"] is True
        assert settings["alert_global_cooldown_minutes"] == 10
        assert settings["trend_hours"] == 48

    def test_export_settings_json_is_valid_utf8(self, config_manager):
        """Test exported JSON file is valid UTF-8."""
        export_path = config_manager.config_file.parent / "exported_settings.json"
        config_manager.export_settings(export_path)

        # Read as UTF-8 (should not raise exception)
        with open(export_path, encoding="utf-8") as f:
            content = f.read()
            assert len(content) > 0

        # Verify it's valid JSON
        json.loads(content)

    def test_export_settings_json_is_pretty_printed(self, config_manager):
        """Test exported JSON is formatted with indentation."""
        export_path = config_manager.config_file.parent / "exported_settings.json"
        config_manager.export_settings(export_path)

        with open(export_path) as f:
            content = f.read()

        # Check for indentation (pretty printing)
        assert "\n" in content  # Has newlines
        assert "  " in content or "\t" in content  # Has indentation
