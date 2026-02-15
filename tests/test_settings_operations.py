"""Tests for settings operations functionality."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from accessiweather.config.settings import SettingsOperations
from accessiweather.models import AppConfig, AppSettings


class TestSettingsOperations:
    """Tests for SettingsOperations class."""

    @pytest.fixture
    def mock_manager(self):
        """Create mock ConfigManager."""
        manager = MagicMock()
        manager._get_logger.return_value = MagicMock()

        config = AppConfig.default()
        manager._config = config
        manager.get_config.return_value = config
        manager.save_config.return_value = True

        return manager

    @pytest.fixture
    def operations(self, mock_manager):
        """Create SettingsOperations instance."""
        return SettingsOperations(mock_manager)

    def test_logger_property(self, operations, mock_manager):
        """Test logger property returns manager's logger."""
        logger = operations.logger

        assert logger is mock_manager._get_logger.return_value


class TestValidateAndFixConfig:
    """Tests for _validate_and_fix_config method."""

    @pytest.fixture
    def mock_manager(self):
        """Create mock ConfigManager."""
        manager = MagicMock()
        manager._get_logger.return_value = MagicMock()
        manager.save_config.return_value = True

        config = AppConfig.default()
        manager._config = config

        return manager

    @pytest.fixture
    def operations(self, mock_manager):
        """Create SettingsOperations instance."""
        return SettingsOperations(mock_manager)

    def test_no_config_early_return(self, mock_manager, operations):
        """Test that method returns early when config is None."""
        mock_manager._config = None

        operations._validate_and_fix_config()

        mock_manager.save_config.assert_not_called()

    def test_invalid_data_source_corrected(self, mock_manager, operations):
        """Test that invalid data_source is corrected to 'auto'."""
        mock_manager._config.settings.data_source = "invalid_source"

        operations._validate_and_fix_config()

        assert mock_manager._config.settings.data_source == "auto"
        mock_manager.save_config.assert_called_once()

    def test_valid_data_sources_unchanged(self, mock_manager, operations):
        """Test that valid data sources are not changed."""
        valid_sources = ["auto", "nws", "openmeteo", "visualcrossing"]

        for source in valid_sources:
            mock_manager._config.settings.data_source = source
            # visualcrossing requires an API key to stay valid
            if source == "visualcrossing":
                mock_manager._config.settings.visual_crossing_api_key = "test_key"
            else:
                mock_manager._config.settings.visual_crossing_api_key = ""
            mock_manager.save_config.reset_mock()

            operations._validate_and_fix_config()

            assert mock_manager._config.settings.data_source == source
            mock_manager.save_config.assert_not_called()

    def test_visualcrossing_without_api_key_switches_to_auto(self, mock_manager, operations):
        """Test that visualcrossing without API key switches to auto."""
        mock_manager._config.settings.data_source = "visualcrossing"
        mock_manager._config.settings.visual_crossing_api_key = ""

        operations._validate_and_fix_config()

        assert mock_manager._config.settings.data_source == "auto"
        mock_manager.save_config.assert_called_once()

    def test_visualcrossing_with_api_key_unchanged(self, mock_manager, operations):
        """Test that visualcrossing with API key is unchanged."""
        mock_manager._config.settings.data_source = "visualcrossing"
        mock_manager._config.settings.visual_crossing_api_key = "test_key"

        operations._validate_and_fix_config()

        assert mock_manager._config.settings.data_source == "visualcrossing"
        mock_manager.save_config.assert_not_called()


class TestValidateNonCritical:
    """Tests for validate_non_critical method."""

    @pytest.fixture
    def mock_manager(self):
        """Create mock ConfigManager."""
        manager = MagicMock()
        manager._get_logger.return_value = MagicMock()
        manager.save_config.return_value = True

        config = AppConfig.default()
        manager._config = config

        return manager

    @pytest.fixture
    def operations(self, mock_manager):
        """Create SettingsOperations instance."""
        return SettingsOperations(mock_manager)

    def test_no_config_returns_true(self, mock_manager, operations):
        """Test that method returns True when config is None."""
        mock_manager._config = None

        result = operations.validate_non_critical()

        assert result is True

    def test_empty_github_app_id_cleared(self, mock_manager, operations):
        """Test that empty GitHub App ID is cleared."""
        mock_manager._config.settings.github_app_id = "   "  # Whitespace only

        result = operations.validate_non_critical()

        assert mock_manager._config.settings.github_app_id == ""
        assert result is True
        mock_manager.save_config.assert_called_once()

    def test_invalid_github_app_id_validation_fails(self, mock_manager, operations):
        """Test that invalid GitHub App ID causes validation to fail."""
        mock_manager._config.settings.github_app_id = "not_a_number"

        result = operations.validate_non_critical()

        assert result is False
        mock_manager.save_config.assert_not_called()

    def test_valid_github_app_id_passes(self, mock_manager, operations):
        """Test that valid GitHub App ID passes validation."""
        mock_manager._config.settings.github_app_id = "123456"

        result = operations.validate_non_critical()

        assert result is True
        mock_manager.save_config.assert_not_called()

    def test_empty_private_key_cleared(self, mock_manager, operations):
        """Test that empty private key is cleared."""
        mock_manager._config.settings.github_app_private_key = "   "  # Whitespace only

        result = operations.validate_non_critical()

        assert mock_manager._config.settings.github_app_private_key == ""
        assert result is True
        mock_manager.save_config.assert_called_once()

    def test_invalid_private_key_validation_fails(self, mock_manager, operations):
        """Test that invalid private key format causes validation to fail."""
        mock_manager._config.settings.github_app_private_key = "invalid_key_format"

        result = operations.validate_non_critical()

        assert result is False

    def test_valid_pkcs8_private_key_passes(self, mock_manager, operations):
        """Test that valid PKCS#8 private key passes validation."""
        valid_key = "-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC...\n-----END PRIVATE KEY-----"
        mock_manager._config.settings.github_app_private_key = valid_key

        result = operations.validate_non_critical()

        assert result is True
        mock_manager.save_config.assert_not_called()

    def test_valid_pkcs1_private_key_passes(self, mock_manager, operations):
        """Test that valid PKCS#1 private key passes validation."""
        valid_key = "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEAwU2qM8QI...\n-----END RSA PRIVATE KEY-----"
        mock_manager._config.settings.github_app_private_key = valid_key

        result = operations.validate_non_critical()

        assert result is True
        mock_manager.save_config.assert_not_called()

    def test_empty_installation_id_cleared(self, mock_manager, operations):
        """Test that empty installation ID is cleared."""
        mock_manager._config.settings.github_app_installation_id = "   "  # Whitespace only

        result = operations.validate_non_critical()

        assert mock_manager._config.settings.github_app_installation_id == ""
        assert result is True
        mock_manager.save_config.assert_called_once()

    def test_invalid_installation_id_validation_fails(self, mock_manager, operations):
        """Test that invalid installation ID causes validation to fail."""
        mock_manager._config.settings.github_app_installation_id = "not_a_number"

        result = operations.validate_non_critical()

        assert result is False

    def test_valid_installation_id_passes(self, mock_manager, operations):
        """Test that valid installation ID passes validation."""
        mock_manager._config.settings.github_app_installation_id = "789012"

        result = operations.validate_non_critical()

        assert result is True
        mock_manager.save_config.assert_not_called()

    def test_specific_setting_validation(self, mock_manager, operations):
        """Test validation of a specific setting."""
        mock_manager._config.settings.github_app_id = "invalid"

        result = operations.validate_non_critical("github_app_id")

        assert result is False

    def test_non_github_setting_validation_passes(self, mock_manager, operations):
        """Test that non-GitHub settings validation passes."""
        result = operations.validate_non_critical("temperature_unit")

        assert result is True

    def test_private_key_missing_header_validation_fails(self, mock_manager, operations):
        """Test private key validation with missing header."""
        invalid_key = "some_key_content\n-----END PRIVATE KEY-----"
        mock_manager._config.settings.github_app_private_key = invalid_key

        result = operations.validate_non_critical()

        assert result is False

    def test_private_key_missing_footer_validation_fails(self, mock_manager, operations):
        """Test private key validation with missing footer."""
        invalid_key = "-----BEGIN PRIVATE KEY-----\nsome_key_content"
        mock_manager._config.settings.github_app_private_key = invalid_key

        result = operations.validate_non_critical()

        assert result is False

    def test_private_key_mismatched_headers_validation_fails(self, mock_manager, operations):
        """Test private key validation with mismatched headers/footers."""
        invalid_key = "-----BEGIN PRIVATE KEY-----\nsome_key_content\n-----END RSA PRIVATE KEY-----"
        mock_manager._config.settings.github_app_private_key = invalid_key

        result = operations.validate_non_critical()

        assert result is False


class TestUpdateSettings:
    """Tests for update_settings method."""

    @pytest.fixture
    def mock_manager(self):
        """Create mock ConfigManager."""
        manager = MagicMock()
        manager.save_config.return_value = True

        config = AppConfig.default()
        manager.get_config.return_value = config

        logger = MagicMock()
        manager._get_logger.return_value = logger

        return manager

    @pytest.fixture
    def operations(self, mock_manager):
        """Create SettingsOperations instance."""
        return SettingsOperations(mock_manager)

    def test_update_regular_setting(self, operations, mock_manager):
        """Test updating a regular setting."""
        result = operations.update_settings(temperature_unit="celsius")

        config = mock_manager.get_config.return_value
        assert config.settings.temperature_unit == "celsius"
        assert result is True
        mock_manager.save_config.assert_called_once()

    @patch('accessiweather.config.settings.SecureStorage.set_password')
    def test_update_secure_setting(self, mock_set_password, operations, mock_manager):
        """Test updating a secure setting."""
        mock_set_password.return_value = True

        result = operations.update_settings(visual_crossing_api_key="test_key")

        config = mock_manager.get_config.return_value
        assert config.settings.visual_crossing_api_key == "test_key"
        mock_set_password.assert_called_once_with("visual_crossing_api_key", "test_key")
        assert result is True

    @patch('accessiweather.config.settings.SecureStorage.set_password')
    def test_update_secure_setting_storage_fails(self, mock_set_password, operations, mock_manager):
        """Test updating a secure setting when secure storage fails."""
        mock_set_password.return_value = False

        result = operations.update_settings(visual_crossing_api_key="test_key")

        # Should still update the setting and save config
        config = mock_manager.get_config.return_value
        assert config.settings.visual_crossing_api_key == "test_key"
        assert result is True

    def test_update_multiple_settings(self, operations, mock_manager):
        """Test updating multiple settings at once."""
        result = operations.update_settings(
            temperature_unit="celsius",
            update_interval_minutes=15,
            data_source="openmeteo"
        )

        config = mock_manager.get_config.return_value
        assert config.settings.temperature_unit == "celsius"
        assert config.settings.update_interval_minutes == 15
        assert config.settings.data_source == "openmeteo"
        assert result is True

    def test_update_unknown_setting(self, operations, mock_manager):
        """Test updating an unknown setting."""
        result = operations.update_settings(unknown_setting="value")

        # Should still save config even with unknown setting
        assert result is True
        mock_manager.save_config.assert_called_once()

    def test_save_config_failure(self, operations, mock_manager):
        """Test when save_config fails."""
        mock_manager.save_config.return_value = False

        result = operations.update_settings(temperature_unit="celsius")

        assert result is False

    def test_redacted_logging(self, operations, mock_manager):
        """Test that sensitive values are redacted in logs."""
        operations.update_settings(github_app_private_key="secret_key")

        logger = mock_manager._get_logger.return_value
        # Check that logger.info was called with redacted value
        logger.info.assert_called_with("Updated setting github_app_private_key = ***redacted***")


class TestGetSettings:
    """Tests for get_settings method."""

    @pytest.fixture
    def mock_manager(self):
        """Create mock ConfigManager."""
        manager = MagicMock()

        config = AppConfig.default()
        config.settings.temperature_unit = "celsius"
        manager.get_config.return_value = config

        return manager

    @pytest.fixture
    def operations(self, mock_manager):
        """Create SettingsOperations instance."""
        return SettingsOperations(mock_manager)

    def test_get_settings_returns_appsettings(self, operations, mock_manager):
        """Test that get_settings returns the AppSettings instance."""
        settings = operations.get_settings()

        assert isinstance(settings, AppSettings)
        assert settings.temperature_unit == "celsius"


class TestResetToDefaults:
    """Tests for reset_to_defaults method."""

    @pytest.fixture
    def mock_manager(self):
        """Create mock ConfigManager."""
        manager = MagicMock()
        manager._get_logger.return_value = MagicMock()
        manager.save_config.return_value = True

        return manager

    @pytest.fixture
    def operations(self, mock_manager):
        """Create SettingsOperations instance."""
        return SettingsOperations(mock_manager)

    def test_reset_to_defaults_success(self, operations, mock_manager):
        """Test successful reset to defaults."""
        result = operations.reset_to_defaults()

        assert result is True
        assert isinstance(mock_manager._config, AppConfig)
        mock_manager.save_config.assert_called_once()

    def test_reset_to_defaults_save_failure(self, operations, mock_manager):
        """Test reset to defaults when save fails."""
        mock_manager.save_config.return_value = False

        result = operations.reset_to_defaults()

        assert result is False


class TestResetAllData:
    """Tests for reset_all_data method."""

    @pytest.fixture
    def mock_manager(self, tmp_path):
        """Create mock ConfigManager with real config directory."""
        manager = MagicMock()
        manager._get_logger.return_value = MagicMock()
        manager.config_dir = tmp_path / "config"
        manager.config_dir.mkdir()
        manager.save_config.return_value = True

        return manager

    @pytest.fixture
    def operations(self, mock_manager):
        """Create SettingsOperations instance."""
        return SettingsOperations(mock_manager)

    def test_reset_all_data_success(self, operations, mock_manager):
        """Test successful reset of all data."""
        # Create some test files and directories
        (mock_manager.config_dir / "test_file.txt").write_text("test")
        (mock_manager.config_dir / "test_dir").mkdir()
        (mock_manager.config_dir / "test_dir" / "nested.txt").write_text("nested")

        result = operations.reset_all_data()

        assert result is True
        assert isinstance(mock_manager._config, AppConfig)
        mock_manager.save_config.assert_called_once()

        # Directory should still exist but be empty
        assert mock_manager.config_dir.exists()
        assert len(list(mock_manager.config_dir.iterdir())) == 0

    def test_reset_all_data_with_permission_errors(self, operations, mock_manager, tmp_path):
        """Test reset all data with permission errors on some files."""
        # Use a MagicMock config_dir that simulates permission errors
        mock_dir = MagicMock()
        mock_file = MagicMock()
        mock_file.is_dir.return_value = False
        mock_file.unlink.side_effect = PermissionError("Access denied")
        mock_dir.iterdir.return_value = [mock_file]
        mock_dir.mkdir = MagicMock()
        mock_manager.config_dir = mock_dir

        result = operations.reset_all_data()

        # Should still succeed despite permission errors (ignore_errors-like behavior)
        assert result is True

    def test_reset_all_data_save_failure(self, operations, mock_manager):
        """Test reset all data when save fails."""
        mock_manager.save_config.return_value = False

        result = operations.reset_all_data()

        assert result is False

    def test_reset_all_data_exception_handling(self, operations, mock_manager):
        """Test reset all data with general exception."""
        # Use a MagicMock config_dir that raises on iterdir
        mock_dir = MagicMock()
        mock_dir.iterdir.side_effect = OSError("Filesystem error")
        mock_manager.config_dir = mock_dir

        result = operations.reset_all_data()

        assert result is False

    def test_reset_all_data_recreates_config_dir(self, operations, mock_manager, tmp_path):
        """Test that reset_all_data works with an empty config directory."""
        # Use an empty dir (already created by fixture)
        result = operations.reset_all_data()

        assert result is True
        assert isinstance(mock_manager._config, AppConfig)
        mock_manager.save_config.assert_called_once()
