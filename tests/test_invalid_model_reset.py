"""
Regression tests for the invalid-AI-model reset dialog.

The "Reset to Default" button previously called ``settings._replace(...)``,
a namedtuple method that does not exist on the ``AppSettings`` dataclass, so
the reset always failed with ``'AppSettings' object has no attribute '_replace'``.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import wx

from accessiweather.ai_explainer import DEFAULT_FREE_MODEL
from accessiweather.app_initialization import _show_invalid_model_warning
from accessiweather.models.config_settings import AppSettings


def _ensure_wx_constants():
    # The default test harness stubs wx without message-dialog constants.
    for name, value in {
        "OK": 0,
        "YES_NO": 0,
        "ICON_INFORMATION": 0,
        "ICON_WARNING": 0,
        "ICON_ERROR": 0,
        "ID_YES": 1,
        "ID_NO": 0,
    }.items():
        if not hasattr(wx, name):
            setattr(wx, name, value)


_ensure_wx_constants()


def _make_app(settings: AppSettings) -> SimpleNamespace:
    config_manager = MagicMock()
    config_manager.get_settings.return_value = settings
    return SimpleNamespace(config_manager=config_manager, main_window=MagicMock())


def test_reset_to_default_updates_model_without_replace_error():
    """Clicking 'Reset to Default' saves settings with the default model."""
    app = _make_app(AppSettings(ai_model_preference="removed/model"))

    dialog = MagicMock()
    dialog.ShowModal.return_value = wx.ID_YES

    with (
        patch("accessiweather.app_initialization.wx.MessageDialog", return_value=dialog),
        patch("accessiweather.app_initialization.wx.MessageBox") as message_box,
    ):
        _show_invalid_model_warning(app, "removed/model", DEFAULT_FREE_MODEL)

    app.config_manager.save_settings.assert_called_once()
    saved = app.config_manager.save_settings.call_args.args[0]
    assert isinstance(saved, AppSettings)
    assert saved.ai_model_preference == DEFAULT_FREE_MODEL
    # Success confirmation shown, not the error dialog.
    assert message_box.call_count == 1
    assert "reset" in message_box.call_args.args[0].lower()


def test_open_settings_when_user_declines_reset():
    """Clicking 'Open Settings' does not touch settings and opens the dialog."""
    app = _make_app(AppSettings(ai_model_preference="removed/model"))
    app.main_window.on_settings = MagicMock()

    dialog = MagicMock()
    dialog.ShowModal.return_value = wx.ID_NO

    with patch("accessiweather.app_initialization.wx.MessageDialog", return_value=dialog):
        _show_invalid_model_warning(app, "removed/model", DEFAULT_FREE_MODEL)

    app.config_manager.save_settings.assert_not_called()
    app.main_window.on_settings.assert_called_once()
