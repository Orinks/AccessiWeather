"""
Tests for ConfigManager.apply_startup_setting().

Reconciles the OS-level startup entry to match the startup_enabled setting.
Called from both the Settings dialog save path and at app startup, so the
shortcut/LaunchAgent/.desktop always matches the user's configured intent.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from accessiweather.config import ConfigManager


@pytest.fixture
def config_dir(tmp_path):
    return tmp_path / "config"


@pytest.fixture
def mock_app(config_dir):
    app = MagicMock()
    app.paths = MagicMock()
    app.paths.config = config_dir
    app.build_tag = None
    return app


@pytest.fixture
def manager(mock_app, config_dir):
    mgr = ConfigManager(mock_app, config_dir=config_dir)
    mgr.load_config()
    mgr._startup_manager = MagicMock()
    return mgr


def test_apply_enables_when_setting_true_and_os_disabled(manager):
    manager.update_settings(startup_enabled=True)
    manager._startup_manager.is_startup_enabled.return_value = False
    manager._startup_manager.enable_startup.return_value = True

    assert manager.apply_startup_setting() is True

    manager._startup_manager.enable_startup.assert_called_once()
    manager._startup_manager.disable_startup.assert_not_called()


def test_apply_disables_when_setting_false_and_os_enabled(manager):
    manager.update_settings(startup_enabled=False)
    manager._startup_manager.is_startup_enabled.return_value = True
    manager._startup_manager.disable_startup.return_value = True

    assert manager.apply_startup_setting() is True

    manager._startup_manager.disable_startup.assert_called_once()
    manager._startup_manager.enable_startup.assert_not_called()


def test_apply_noop_when_states_already_match_enabled(manager):
    manager.update_settings(startup_enabled=True)
    manager._startup_manager.is_startup_enabled.return_value = True

    assert manager.apply_startup_setting() is True

    manager._startup_manager.enable_startup.assert_not_called()
    manager._startup_manager.disable_startup.assert_not_called()


def test_apply_noop_when_states_already_match_disabled(manager):
    manager.update_settings(startup_enabled=False)
    manager._startup_manager.is_startup_enabled.return_value = False

    assert manager.apply_startup_setting() is True

    manager._startup_manager.enable_startup.assert_not_called()
    manager._startup_manager.disable_startup.assert_not_called()


def test_apply_returns_false_when_enable_fails(manager):
    manager.update_settings(startup_enabled=True)
    manager._startup_manager.is_startup_enabled.return_value = False
    manager._startup_manager.enable_startup.return_value = False

    assert manager.apply_startup_setting() is False


def test_apply_honors_explicit_desired_overriding_stored_setting(manager):
    """
    Dialog path passes the just-collected checkbox value explicitly.

    update_settings has already persisted it by the time we call, but the
    explicit arg lets the caller avoid relying on that ordering.
    """
    manager.update_settings(startup_enabled=False)  # stored = False
    manager._startup_manager.is_startup_enabled.return_value = False
    manager._startup_manager.enable_startup.return_value = True

    # Caller overrides with explicit desired=True
    assert manager.apply_startup_setting(desired=True) is True

    manager._startup_manager.enable_startup.assert_called_once()
