from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import wx

from accessiweather.app import AccessiWeatherApp


def _ensure_wx_dialog_constants() -> None:
    for name, value in {
        "YES_NO": 0,
        "CANCEL": 0,
        "ICON_INFORMATION": 0,
        "ID_YES": 1,
        "ID_NO": 0,
    }.items():
        if not hasattr(wx, name):
            setattr(wx, name, value)


class _FakeDialog:
    def __init__(self, responses: list[int]):
        self._responses = responses

    def SetYesNoCancelLabels(self, *_args):
        return None

    def SetYesNoLabels(self, *_args):
        return None

    def ShowModal(self):
        return self._responses.pop(0)

    def Destroy(self):
        return None


def test_portable_missing_api_keys_hint_shown_once_and_persists(monkeypatch):
    app = AccessiWeatherApp.__new__(AccessiWeatherApp)
    app._portable_mode = True
    app.main_window = SimpleNamespace(open_settings=MagicMock())
    settings = SimpleNamespace(portable_missing_api_keys_hint_shown=False)
    app.config_manager = SimpleNamespace(
        get_settings=lambda: settings,
        update_settings=MagicMock(),
    )

    _ensure_wx_dialog_constants()
    responses = [getattr(wx, "ID_YES", 1)]
    monkeypatch.setattr(
        "accessiweather.app.wx.MessageDialog",
        lambda *args, **kwargs: _FakeDialog(responses),
        raising=False,
    )
    monkeypatch.setattr(app, "_has_any_saved_api_keys", lambda: False)

    app._maybe_show_portable_missing_keys_hint()

    app.config_manager.update_settings.assert_called_once_with(
        portable_missing_api_keys_hint_shown=True
    )
    app.main_window.open_settings.assert_called_once_with(tab="AI")

    # Once persisted, prompt should no longer show.
    settings.portable_missing_api_keys_hint_shown = True
    app.config_manager.update_settings.reset_mock()
    app.main_window.open_settings.reset_mock()
    app._maybe_show_portable_missing_keys_hint()

    app.config_manager.update_settings.assert_not_called()
    app.main_window.open_settings.assert_not_called()


def test_schedule_startup_guidance_prompts_uses_call_later(monkeypatch):
    app = AccessiWeatherApp.__new__(AccessiWeatherApp)

    calls: list[tuple[int, object]] = []
    monkeypatch.setattr(
        "accessiweather.app.wx.CallLater",
        lambda delay, fn: calls.append((delay, fn)),
        raising=False,
    )

    app._schedule_startup_guidance_prompts()

    assert calls[0][0] == 800
    assert calls[0][1] == app._maybe_show_first_start_onboarding
    assert calls[1][0] == 1400
    assert calls[1][1] == app._maybe_show_portable_missing_keys_hint


def test_has_any_saved_api_keys_checks_both_keys(monkeypatch):
    app = AccessiWeatherApp.__new__(AccessiWeatherApp)

    monkeypatch.setattr(
        "accessiweather.config.secure_storage.SecureStorage.get_password",
        lambda name: "  " if name == "openrouter_api_key" else "vc-key",
        raising=False,
    )

    assert app._has_any_saved_api_keys() is True


def test_portable_missing_api_keys_hint_noops_when_not_portable():
    app = AccessiWeatherApp.__new__(AccessiWeatherApp)
    app._portable_mode = False
    app.main_window = SimpleNamespace(open_settings=MagicMock())
    app.config_manager = SimpleNamespace(
        get_settings=lambda: SimpleNamespace(portable_missing_api_keys_hint_shown=False),
        update_settings=MagicMock(),
    )

    app._maybe_show_portable_missing_keys_hint()

    app.config_manager.update_settings.assert_not_called()


def test_onboarding_wizard_shown_once_with_skip_path(monkeypatch):
    app = AccessiWeatherApp.__new__(AccessiWeatherApp)
    app.main_window = SimpleNamespace(on_add_location=MagicMock(), open_settings=MagicMock())
    settings = SimpleNamespace(onboarding_wizard_shown=False)
    app.config_manager = SimpleNamespace(
        get_config=lambda: SimpleNamespace(locations=[], settings=settings),
        update_settings=MagicMock(),
    )

    _ensure_wx_dialog_constants()
    skip_id = getattr(wx, "ID_NO", 0)
    responses = [skip_id, skip_id]  # skip location, skip AI
    monkeypatch.setattr(
        "accessiweather.app.wx.MessageDialog",
        lambda *args, **kwargs: _FakeDialog(responses),
        raising=False,
    )

    app._maybe_show_first_start_onboarding()

    app.main_window.on_add_location.assert_not_called()
    app.main_window.open_settings.assert_not_called()
    app.config_manager.update_settings.assert_called_once_with(onboarding_wizard_shown=True)

    # Once marked shown, it should not display again.
    settings.onboarding_wizard_shown = True
    app.config_manager.update_settings.reset_mock()
    app._maybe_show_first_start_onboarding()
    app.config_manager.update_settings.assert_not_called()
