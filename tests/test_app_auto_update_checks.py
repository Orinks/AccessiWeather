"""Tests for automatic update-check scheduling and notifications."""

from __future__ import annotations

import sys
import types
from types import SimpleNamespace
from unittest.mock import MagicMock

import wx

from accessiweather.app import AccessiWeatherApp


class _ImmediateThread:
    def __init__(self, *, target, daemon=True):
        self._target = target

    def start(self):
        self._target()


def test_start_auto_update_checks_uses_configured_interval(monkeypatch):
    app = AccessiWeatherApp.__new__(AccessiWeatherApp)
    app.config_manager = MagicMock()
    app.config_manager.get_settings.return_value = SimpleNamespace(
        auto_update_enabled=True,
        update_check_interval_hours=6,
    )
    app._auto_update_check_timer = None

    timer = MagicMock()
    monkeypatch.setattr(wx, "Timer", lambda: timer)

    app._start_auto_update_checks()

    timer.Bind.assert_called_once_with(wx.EVT_TIMER, app._on_auto_update_check_timer)
    timer.Start.assert_called_once_with(6 * 60 * 60 * 1000)
    assert app._auto_update_check_timer is timer


def test_check_for_updates_on_startup_surfaces_update_dialog(monkeypatch):
    app = AccessiWeatherApp.__new__(AccessiWeatherApp)
    app.config_manager = MagicMock()
    app.config_manager.get_settings.return_value = SimpleNamespace(
        auto_update_enabled=True,
        update_channel="stable",
    )
    app.version = "1.0.0"
    app.build_tag = None
    app.GetTopWindow = MagicMock(return_value=None)
    app._download_and_apply_update = MagicMock()

    monkeypatch.setattr(sys, "frozen", True, raising=False)

    import threading

    monkeypatch.setattr(threading, "Thread", _ImmediateThread)

    # Execute wx.CallAfter callbacks immediately in test.
    monkeypatch.setattr(wx, "CallAfter", lambda fn, *a, **k: fn(*a, **k))

    # Stub update service used inside startup auto-check.
    import accessiweather.services.simple_update as simple_update

    class _FakeUpdateService:
        def __init__(self, app_name):
            self.app_name = app_name

        async def check_for_updates(self, **kwargs):
            return SimpleNamespace(
                is_nightly=False,
                version="1.2.3",
                release_notes="Bug fixes",
            )

        async def close(self):
            return None

    monkeypatch.setattr(simple_update, "UpdateService", _FakeUpdateService)

    # Stub update dialog class imported by the callback.
    dialog_module = types.ModuleType("accessiweather.ui.dialogs.update_dialog")
    created = {}

    class _FakeDialog:
        def __init__(self, **kwargs):
            created["kwargs"] = kwargs

        def ShowModal(self):
            return wx.ID_CANCEL

        def Destroy(self):
            return None

    dialog_module.UpdateAvailableDialog = _FakeDialog
    monkeypatch.setitem(sys.modules, "accessiweather.ui.dialogs.update_dialog", dialog_module)

    app._check_for_updates_on_startup()

    assert created["kwargs"]["new_version"] == "1.2.3"
    assert created["kwargs"]["channel_label"] == "Stable"
    app._download_and_apply_update.assert_not_called()
