"""
App initialization reconciles OS startup entry with the persisted setting.

If a previous build wrote startup_enabled=True but never created the Startup
shortcut (the bug fixed in this branch), users shouldn't have to re-open
Settings to self-heal. On app launch we call apply_startup_setting() so the
shortcut/LaunchAgent/.desktop matches the stored setting.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from accessiweather.app_initialization import _apply_startup_setting_deferred


def test_deferred_helper_calls_apply_startup_setting():
    app = MagicMock()
    app.config_manager = MagicMock()

    _apply_startup_setting_deferred(app)

    app.config_manager.apply_startup_setting.assert_called_once_with()


def test_deferred_helper_tolerates_missing_config_manager():
    app = MagicMock()
    app.config_manager = None

    # Must not raise — app init shouldn't crash if config_manager unset yet.
    _apply_startup_setting_deferred(app)


def test_deferred_helper_swallows_exceptions():
    app = MagicMock()
    app.config_manager = MagicMock()
    app.config_manager.apply_startup_setting.side_effect = RuntimeError("boom")

    # Background sync must never crash the app on launch.
    _apply_startup_setting_deferred(app)
