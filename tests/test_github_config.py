"""Tests for GitHub configuration operations."""

from unittest.mock import Mock

import pytest

from accessiweather.config.github_config import GitHubConfigOperations
from accessiweather.models.config import AppConfig, AppSettings


@pytest.fixture
def mock_config_manager():
    """Create a mock ConfigManager."""
    manager = Mock()
    config = AppConfig(
        settings=AppSettings(
            github_backend_url="https://custom-backend.example.com",
        ),
        locations=[],
        current_location=None,
    )
    # Manually set the github app config fields since they're not in AppSettings
    config.settings.github_app_id = "123456"
    config.settings.github_app_private_key = (
        "-----BEGIN PRIVATE KEY-----\n"
        "MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC\n"
        "-----END PRIVATE KEY-----"
    )
    config.settings.github_app_installation_id = "789012"
    manager.get_config.return_value = config
    manager.save_config.return_value = True
    manager.update_settings.return_value = True
    mock_logger = Mock()
    manager._get_logger.return_value = mock_logger
    return manager


@pytest.fixture
def github_config(mock_config_manager):
    """Create GitHubConfigOperations instance."""
    return GitHubConfigOperations(mock_config_manager)


class TestGitHubConfigOperations:
    """Test GitHubConfigOperations class."""

    def test_initialization(self, mock_config_manager):
        """Test GitHubConfigOperations initialization."""
        ops = GitHubConfigOperations(mock_config_manager)
        assert ops._manager == mock_config_manager

    def test_logger_property(self, github_config, mock_config_manager):
        """Test logger property delegation."""
        logger = github_config.logger
        mock_config_manager._get_logger.assert_called_once()
        assert logger == mock_config_manager._get_logger.return_value

    def test_validate_github_app_config_valid(self, github_config):
        """Test validating a valid GitHub App configuration."""
        valid, message = github_config.validate_github_app_config()
        assert valid is True
        assert message == "GitHub App configuration is valid"

    def test_validate_github_app_config_missing_app_id(self, github_config, mock_config_manager):
        """Test validation when App ID is missing."""
        config = mock_config_manager.get_config.return_value
        config.settings.github_app_id = ""
        valid, message = github_config.validate_github_app_config()
        assert valid is False
        assert message == "No GitHub App ID configured"

    def test_validate_github_app_config_missing_private_key(
        self, github_config, mock_config_manager
    ):
        """Test validation when private key is missing."""
        config = mock_config_manager.get_config.return_value
        config.settings.github_app_private_key = ""
        valid, message = github_config.validate_github_app_config()
        assert valid is False
        assert message == "No GitHub App private key configured"

    def test_validate_github_app_config_missing_installation_id(
        self, github_config, mock_config_manager
    ):
        """Test validation when installation ID is missing."""
        config = mock_config_manager.get_config.return_value
        config.settings.github_app_installation_id = ""
        valid, message = github_config.validate_github_app_config()
        assert valid is False
        assert message == "No GitHub App installation ID configured"

    def test_validate_github_app_config_non_numeric_app_id(
        self, github_config, mock_config_manager
    ):
        """Test validation when App ID is not numeric."""
        config = mock_config_manager.get_config.return_value
        config.settings.github_app_id = "not-a-number"
        valid, message = github_config.validate_github_app_config()
        assert valid is False
        assert message == "GitHub App ID must be numeric"

    def test_validate_github_app_config_non_numeric_installation_id(
        self, github_config, mock_config_manager
    ):
        """Test validation when installation ID is not numeric."""
        config = mock_config_manager.get_config.return_value
        config.settings.github_app_installation_id = "not-a-number"
        valid, message = github_config.validate_github_app_config()
        assert valid is False
        assert message == "GitHub App installation ID must be numeric"

    def test_validate_github_app_config_missing_pem_header(
        self, github_config, mock_config_manager
    ):
        """Test validation when PEM header is missing."""
        config = mock_config_manager.get_config.return_value
        config.settings.github_app_private_key = "INVALID KEY\n-----END PRIVATE KEY-----"
        valid, message = github_config.validate_github_app_config()
        assert valid is False
        assert "missing PEM header" in message
        assert "BEGIN PRIVATE KEY" in message

    def test_validate_github_app_config_missing_pem_footer(
        self, github_config, mock_config_manager
    ):
        """Test validation when PEM footer is missing."""
        config = mock_config_manager.get_config.return_value
        config.settings.github_app_private_key = "-----BEGIN PRIVATE KEY-----\nINVALID"
        valid, message = github_config.validate_github_app_config()
        assert valid is False
        assert "missing PEM footer" in message
        assert "END PRIVATE KEY" in message

    def test_validate_github_app_config_mismatched_headers(
        self, github_config, mock_config_manager
    ):
        """Test validation when PEM headers are mismatched."""
        config = mock_config_manager.get_config.return_value
        # PKCS#8 header with PKCS#1 footer
        config.settings.github_app_private_key = (
            "-----BEGIN PRIVATE KEY-----\nKEY DATA\n-----END RSA PRIVATE KEY-----"
        )
        valid, message = github_config.validate_github_app_config()
        assert valid is False
        assert "mismatched PEM headers/footers" in message

    def test_validate_github_app_config_pkcs1_format(self, github_config, mock_config_manager):
        """Test validation with PKCS#1 format key."""
        config = mock_config_manager.get_config.return_value
        config.settings.github_app_private_key = (
            "-----BEGIN RSA PRIVATE KEY-----\n"
            "MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC\n"
            "-----END RSA PRIVATE KEY-----"
        )
        valid, message = github_config.validate_github_app_config()
        assert valid is True
        assert message == "GitHub App configuration is valid"

    def test_set_github_app_config(self, github_config, mock_config_manager):
        """Test setting GitHub App configuration."""
        result = github_config.set_github_app_config("999888", "NEW KEY", "777666")
        assert result is True
        mock_config_manager.update_settings.assert_called_once_with(
            github_app_id="999888",
            github_app_private_key="NEW KEY",
            github_app_installation_id="777666",
        )

    def test_set_github_app_config_strips_whitespace(self, github_config, mock_config_manager):
        """Test that set_github_app_config strips whitespace."""
        result = github_config.set_github_app_config("  123  ", "  KEY  ", "  456  ")
        assert result is True
        mock_config_manager.update_settings.assert_called_once_with(
            github_app_id="123",
            github_app_private_key="KEY",
            github_app_installation_id="456",
        )

    def test_set_github_app_config_save_fails(self, github_config, mock_config_manager):
        """Test setting GitHub App config when save fails."""
        mock_config_manager.update_settings.return_value = False
        result = github_config.set_github_app_config("123", "KEY", "456")
        assert result is False

    def test_set_github_app_config_exception(self, github_config, mock_config_manager):
        """Test setting GitHub App config when exception occurs."""
        mock_config_manager.update_settings.side_effect = Exception("Config error")
        result = github_config.set_github_app_config("123", "KEY", "456")
        assert result is False
        github_config.logger.error.assert_called_once()
        assert "Failed to set GitHub App configuration" in str(
            github_config.logger.error.call_args[0][0]
        )

    def test_get_github_app_config(self, github_config, mock_config_manager):
        """Test getting GitHub App configuration."""
        app_id, private_key, installation_id = github_config.get_github_app_config()
        assert app_id == "123456"
        assert "BEGIN PRIVATE KEY" in private_key
        assert installation_id == "789012"

    def test_get_github_app_config_exception(self, github_config, mock_config_manager):
        """Test getting GitHub App config when exception occurs."""
        mock_config_manager.get_config.side_effect = Exception("Config error")
        app_id, private_key, installation_id = github_config.get_github_app_config()
        assert app_id == ""
        assert private_key == ""
        assert installation_id == ""
        github_config.logger.error.assert_called_once()

    def test_clear_github_app_config(self, github_config, mock_config_manager):
        """Test clearing GitHub App configuration."""
        result = github_config.clear_github_app_config()
        assert result is True
        mock_config_manager.update_settings.assert_called_once_with(
            github_app_id="",
            github_app_private_key="",
            github_app_installation_id="",
        )

    def test_has_github_app_config_true(self, github_config):
        """Test has_github_app_config when backend URL is configured."""
        result = github_config.has_github_app_config()
        assert result is True

    def test_has_github_app_config_false(self, github_config, mock_config_manager):
        """Test has_github_app_config when backend URL is empty."""
        config = mock_config_manager.get_config.return_value
        config.settings.github_backend_url = ""
        # Even with empty config, it returns True because get_github_backend_url returns default
        result = github_config.has_github_app_config()
        assert result is True  # Returns True because default URL is used

    def test_has_github_app_config_exception(self, github_config, mock_config_manager):
        """Test has_github_app_config when exception occurs."""
        mock_config_manager.get_config.side_effect = Exception("Config error")
        result = github_config.has_github_app_config()
        assert result is False

    def test_get_github_backend_url_custom(self, github_config):
        """Test getting custom GitHub backend URL."""
        url = github_config.get_github_backend_url()
        assert url == "https://custom-backend.example.com"

    def test_get_github_backend_url_default(self, github_config, mock_config_manager):
        """Test getting default GitHub backend URL."""
        config = mock_config_manager.get_config.return_value
        config.settings.github_backend_url = ""
        url = github_config.get_github_backend_url()
        assert url == "https://soundpack-backend.fly.dev"

    def test_get_github_backend_url_strips_whitespace(self, github_config, mock_config_manager):
        """Test that backend URL is stripped."""
        config = mock_config_manager.get_config.return_value
        config.settings.github_backend_url = "  https://example.com  "
        url = github_config.get_github_backend_url()
        assert url == "https://example.com"

    def test_set_github_backend_url(self, github_config, mock_config_manager):
        """Test setting GitHub backend URL."""
        result = github_config.set_github_backend_url("https://new-backend.example.com")
        assert result is True
        config = mock_config_manager.get_config.return_value
        assert config.settings.github_backend_url == "https://new-backend.example.com"
        mock_config_manager.save_config.assert_called_once()

    def test_set_github_backend_url_strips_whitespace(self, github_config, mock_config_manager):
        """Test that set_github_backend_url strips whitespace."""
        result = github_config.set_github_backend_url("  https://example.com  ")
        assert result is True
        config = mock_config_manager.get_config.return_value
        assert config.settings.github_backend_url == "https://example.com"

    def test_set_github_backend_url_exception(self, github_config, mock_config_manager):
        """Test setting backend URL when exception occurs."""
        mock_config_manager.get_config.side_effect = Exception("Config error")
        result = github_config.set_github_backend_url("https://example.com")
        assert result is False
        github_config.logger.error.assert_called_once()
        assert "Failed to set GitHub backend URL" in str(github_config.logger.error.call_args[0][0])

    def test_validate_empty_github_app_id_with_spaces(self, github_config, mock_config_manager):
        """Test validation when App ID contains only whitespace."""
        config = mock_config_manager.get_config.return_value
        config.settings.github_app_id = "   "
        valid, message = github_config.validate_github_app_config()
        # Should fail because stripped empty string is falsy
        assert valid is False

    def test_validate_private_key_with_extra_whitespace(self, github_config, mock_config_manager):
        """Test validation of private key with extra whitespace."""
        config = mock_config_manager.get_config.return_value
        config.settings.github_app_private_key = (
            "  -----BEGIN PRIVATE KEY-----\n"
            "MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC\n"
            "-----END PRIVATE KEY-----  "
        )
        valid, message = github_config.validate_github_app_config()
        assert valid is True
