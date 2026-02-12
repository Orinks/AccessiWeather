"""Tests for GitHubConfigOperations."""

from __future__ import annotations

from unittest.mock import MagicMock

from accessiweather.config.github_config import GitHubConfigOperations
from accessiweather.constants import (
    GITHUB_APP_PKCS8_PRIVATE_KEY_FOOTER,
    GITHUB_APP_PKCS8_PRIVATE_KEY_HEADER,
    GITHUB_APP_PRIVATE_KEY_FOOTER,
    GITHUB_APP_PRIVATE_KEY_HEADER,
)
from accessiweather.models import AppConfig, AppSettings


def _make_manager(settings=None):
    """Create a mock ConfigManager with given settings."""
    manager = MagicMock()
    cfg = AppConfig(settings=settings or AppSettings(), locations=[])
    manager.get_config.return_value = cfg
    manager._get_logger.return_value = MagicMock()
    manager.save_config.return_value = True
    return manager, cfg


def _pkcs1_key():
    return f"{GITHUB_APP_PRIVATE_KEY_HEADER}\nfakekey\n{GITHUB_APP_PRIVATE_KEY_FOOTER}"


def _pkcs8_key():
    return f"{GITHUB_APP_PKCS8_PRIVATE_KEY_HEADER}\nfakekey\n{GITHUB_APP_PKCS8_PRIVATE_KEY_FOOTER}"


class TestValidateGitHubAppConfig:
    def test_missing_app_id(self):
        manager, _ = _make_manager(
            AppSettings(
                github_app_private_key=_pkcs1_key(),
                github_app_installation_id="123",
            )
        )
        ops = GitHubConfigOperations(manager)
        valid, msg = ops.validate_github_app_config()
        assert not valid
        assert "App ID" in msg

    def test_missing_private_key(self):
        manager, _ = _make_manager(
            AppSettings(
                github_app_id="123",
                github_app_installation_id="456",
            )
        )
        ops = GitHubConfigOperations(manager)
        valid, msg = ops.validate_github_app_config()
        assert not valid
        assert "private key" in msg

    def test_missing_installation_id(self):
        manager, _ = _make_manager(
            AppSettings(
                github_app_id="123",
                github_app_private_key=_pkcs1_key(),
            )
        )
        ops = GitHubConfigOperations(manager)
        valid, msg = ops.validate_github_app_config()
        assert not valid
        assert "installation ID" in msg

    def test_non_numeric_app_id(self):
        manager, _ = _make_manager(
            AppSettings(
                github_app_id="abc",
                github_app_private_key=_pkcs1_key(),
                github_app_installation_id="456",
            )
        )
        ops = GitHubConfigOperations(manager)
        valid, msg = ops.validate_github_app_config()
        assert not valid
        assert "numeric" in msg

    def test_non_numeric_installation_id(self):
        manager, _ = _make_manager(
            AppSettings(
                github_app_id="123",
                github_app_private_key=_pkcs1_key(),
                github_app_installation_id="abc",
            )
        )
        ops = GitHubConfigOperations(manager)
        valid, msg = ops.validate_github_app_config()
        assert not valid
        assert "installation ID must be numeric" in msg

    def test_valid_pkcs1_key(self):
        manager, _ = _make_manager(
            AppSettings(
                github_app_id="123",
                github_app_private_key=_pkcs1_key(),
                github_app_installation_id="456",
            )
        )
        ops = GitHubConfigOperations(manager)
        valid, msg = ops.validate_github_app_config()
        assert valid
        assert "valid" in msg.lower()

    def test_valid_pkcs8_key(self):
        manager, _ = _make_manager(
            AppSettings(
                github_app_id="123",
                github_app_private_key=_pkcs8_key(),
                github_app_installation_id="456",
            )
        )
        ops = GitHubConfigOperations(manager)
        valid, msg = ops.validate_github_app_config()
        assert valid

    def test_missing_pem_header(self):
        manager, _ = _make_manager(
            AppSettings(
                github_app_id="123",
                github_app_private_key=f"badheader\n{GITHUB_APP_PRIVATE_KEY_FOOTER}",
                github_app_installation_id="456",
            )
        )
        ops = GitHubConfigOperations(manager)
        valid, msg = ops.validate_github_app_config()
        assert not valid
        assert "header" in msg.lower()

    def test_missing_pem_footer(self):
        manager, _ = _make_manager(
            AppSettings(
                github_app_id="123",
                github_app_private_key=f"{GITHUB_APP_PRIVATE_KEY_HEADER}\nkey\nbadfooter",
                github_app_installation_id="456",
            )
        )
        ops = GitHubConfigOperations(manager)
        valid, msg = ops.validate_github_app_config()
        assert not valid
        assert "footer" in msg.lower()

    def test_mismatched_headers_footers(self):
        # PKCS1 header with PKCS8 footer
        manager, _ = _make_manager(
            AppSettings(
                github_app_id="123",
                github_app_private_key=f"{GITHUB_APP_PRIVATE_KEY_HEADER}\nkey\n{GITHUB_APP_PKCS8_PRIVATE_KEY_FOOTER}",
                github_app_installation_id="456",
            )
        )
        ops = GitHubConfigOperations(manager)
        valid, msg = ops.validate_github_app_config()
        assert not valid
        assert "mismatched" in msg.lower()


class TestSetGitHubAppConfig:
    def test_set_config_delegates_to_manager(self):
        manager, _ = _make_manager()
        manager.update_settings.return_value = True
        ops = GitHubConfigOperations(manager)
        result = ops.set_github_app_config("  123 ", " key ", " 456 ")
        assert result is True
        manager.update_settings.assert_called_once_with(
            github_app_id="123",
            github_app_private_key="key",
            github_app_installation_id="456",
        )

    def test_set_config_returns_false_on_error(self):
        manager, _ = _make_manager()
        manager.update_settings.side_effect = RuntimeError("fail")
        ops = GitHubConfigOperations(manager)
        result = ops.set_github_app_config("123", "key", "456")
        assert result is False


class TestGetGitHubAppConfig:
    def test_returns_settings_values(self):
        manager, _ = _make_manager(
            AppSettings(
                github_app_id="111",
                github_app_private_key="pk",
                github_app_installation_id="222",
            )
        )
        ops = GitHubConfigOperations(manager)
        app_id, pk, inst_id = ops.get_github_app_config()
        assert app_id == "111"
        assert pk == "pk"
        assert inst_id == "222"

    def test_returns_empty_on_error(self):
        manager, _ = _make_manager()
        manager.get_config.side_effect = RuntimeError("fail")
        ops = GitHubConfigOperations(manager)
        result = ops.get_github_app_config()
        assert result == ("", "", "")


class TestClearGitHubAppConfig:
    def test_clear_sets_empty_strings(self):
        manager, _ = _make_manager()
        manager.update_settings.return_value = True
        ops = GitHubConfigOperations(manager)
        result = ops.clear_github_app_config()
        assert result is True
        manager.update_settings.assert_called_once_with(
            github_app_id="",
            github_app_private_key="",
            github_app_installation_id="",
        )


class TestHasGitHubAppConfig:
    def test_has_config_with_backend_url(self):
        manager, cfg = _make_manager(AppSettings(github_backend_url="https://example.com"))
        ops = GitHubConfigOperations(manager)
        assert ops.has_github_app_config() is True

    def test_has_config_with_default_url(self):
        manager, _ = _make_manager()
        ops = GitHubConfigOperations(manager)
        # Default URL from get_github_backend_url returns the fallback
        assert ops.has_github_app_config() is True

    def test_has_config_false_when_get_raises(self):
        manager, _ = _make_manager()
        manager.get_config.side_effect = RuntimeError("fail")
        ops = GitHubConfigOperations(manager)
        assert ops.has_github_app_config() is False


class TestGetGitHubBackendUrl:
    def test_returns_configured_url(self):
        manager, _ = _make_manager(AppSettings(github_backend_url="https://custom.dev"))
        ops = GitHubConfigOperations(manager)
        assert ops.get_github_backend_url() == "https://custom.dev"

    def test_returns_default_when_empty(self):
        manager, _ = _make_manager()
        ops = GitHubConfigOperations(manager)
        assert ops.get_github_backend_url() == "https://soundpack-backend.fly.dev"


class TestSetGitHubBackendUrl:
    def test_set_url_saves_config(self):
        manager, cfg = _make_manager()
        ops = GitHubConfigOperations(manager)
        result = ops.set_github_backend_url("  https://new.dev  ")
        assert result is True
        assert cfg.settings.github_backend_url == "https://new.dev"
        manager.save_config.assert_called_once()

    def test_set_url_returns_false_on_error(self):
        manager, _ = _make_manager()
        manager.get_config.side_effect = RuntimeError("fail")
        ops = GitHubConfigOperations(manager)
        result = ops.set_github_backend_url("https://new.dev")
        assert result is False
