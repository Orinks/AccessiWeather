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
        "ICON_WARNING": 0,
        "OK": 0,
        "ID_OK": 1,
        "TE_PASSWORD": 0,
        "ID_YES": 1,
        "ID_NO": 0,
        "ID_CANCEL": 2,
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


class _FakeTextEntryDialog:
    def __init__(self, responses: list[str]):
        self._responses = responses

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def ShowModal(self):
        return getattr(wx, "ID_OK", 1)

    def GetValue(self):
        return self._responses.pop(0)


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
    app._portable_mode = False
    app.main_window = SimpleNamespace(on_add_location=MagicMock(), open_settings=MagicMock())
    settings = SimpleNamespace(onboarding_wizard_shown=False)
    app.config_manager = SimpleNamespace(
        get_config=lambda: SimpleNamespace(locations=[], settings=settings),
        update_settings=MagicMock(),
    )

    _ensure_wx_dialog_constants()
    skip_id = getattr(wx, "ID_NO", 0)
    cancel_id = getattr(wx, "ID_CANCEL", 2)
    responses = [skip_id, cancel_id, cancel_id, getattr(wx, "ID_OK", 1)]
    monkeypatch.setattr(
        "accessiweather.app.wx.MessageDialog",
        lambda *args, **kwargs: _FakeDialog(responses),
        raising=False,
    )
    text_responses = ["", ""]
    monkeypatch.setattr(
        "accessiweather.app.wx.TextEntryDialog",
        lambda *args, **kwargs: _FakeTextEntryDialog(text_responses),
        raising=False,
    )

    app._maybe_show_first_start_onboarding()

    app.main_window.on_add_location.assert_not_called()
    app.main_window.open_settings.assert_not_called()
    assert app.config_manager.update_settings.call_args_list[-1].kwargs == {
        "onboarding_wizard_shown": True
    }

    settings.onboarding_wizard_shown = True
    app.config_manager.update_settings.reset_mock()
    app._maybe_show_first_start_onboarding()
    app.config_manager.update_settings.assert_not_called()


def test_onboarding_wizard_portable_happy_path_sets_keys_and_bundle(monkeypatch):
    app = AccessiWeatherApp.__new__(AccessiWeatherApp)
    app._portable_mode = True
    app.main_window = SimpleNamespace(on_add_location=MagicMock(), open_settings=MagicMock())
    settings = SimpleNamespace(onboarding_wizard_shown=False)
    app.config_manager = SimpleNamespace(
        get_config=lambda: SimpleNamespace(locations=[], settings=settings),
        update_settings=MagicMock(),
        set_portable_bundle_passphrase=MagicMock(),
        refresh_portable_api_key_bundle=MagicMock(),
    )

    _ensure_wx_dialog_constants()
    responses = [
        getattr(wx, "ID_NO", 0),
        getattr(wx, "ID_YES", 1),
        getattr(wx, "ID_NO", 0),
        getattr(wx, "ID_YES", 1),
        getattr(wx, "ID_NO", 0),
        getattr(wx, "ID_YES", 1),
        getattr(wx, "ID_OK", 1),
    ]
    monkeypatch.setattr(
        "accessiweather.app.wx.MessageDialog",
        lambda *args, **kwargs: _FakeDialog(responses),
        raising=False,
    )
    text_responses = ["sk-or", "vc-key", "bundle-pass"]
    monkeypatch.setattr(
        "accessiweather.app.wx.TextEntryDialog",
        lambda *args, **kwargs: _FakeTextEntryDialog(text_responses),
        raising=False,
    )

    app._maybe_show_first_start_onboarding()

    calls = app.config_manager.update_settings.call_args_list
    assert calls[0].kwargs == {"openrouter_api_key": "sk-or"}
    assert calls[1].kwargs == {"visual_crossing_api_key": "vc-key"}
    assert calls[2].kwargs == {"portable_auto_bundle_enabled": True}
    assert calls[3].kwargs == {"onboarding_wizard_shown": True}
    app.config_manager.set_portable_bundle_passphrase.assert_called_once_with("bundle-pass")
    app.config_manager.refresh_portable_api_key_bundle.assert_called_once()


def test_onboarding_wizard_api_key_link_actions_open_browser(monkeypatch):
    app = AccessiWeatherApp.__new__(AccessiWeatherApp)
    app._portable_mode = False
    app.main_window = SimpleNamespace(on_add_location=MagicMock(), open_settings=MagicMock())
    settings = SimpleNamespace(onboarding_wizard_shown=False)
    app.config_manager = SimpleNamespace(
        get_config=lambda: SimpleNamespace(locations=[], settings=settings),
        update_settings=MagicMock(),
    )

    _ensure_wx_dialog_constants()
    responses = [
        getattr(wx, "ID_NO", 0),
        getattr(wx, "ID_NO", 0),
        getattr(wx, "ID_YES", 1),
        getattr(wx, "ID_NO", 0),
        getattr(wx, "ID_NO", 0),
        getattr(wx, "ID_CANCEL", 2),
        getattr(wx, "ID_OK", 1),
    ]
    monkeypatch.setattr(
        "accessiweather.app.wx.MessageDialog",
        lambda *args, **kwargs: _FakeDialog(responses),
        raising=False,
    )
    text_responses = ["sk-or"]
    monkeypatch.setattr(
        "accessiweather.app.wx.TextEntryDialog",
        lambda *args, **kwargs: _FakeTextEntryDialog(text_responses),
        raising=False,
    )

    opened_urls: list[str] = []
    monkeypatch.setattr(
        "accessiweather.app.webbrowser.open",
        lambda url: opened_urls.append(url),
        raising=False,
    )

    app._maybe_show_first_start_onboarding()

    assert opened_urls == [
        "https://openrouter.ai/keys",
        "https://www.visualcrossing.com/sign-up",
    ]
    calls = app.config_manager.update_settings.call_args_list
    assert calls[0].kwargs == {"openrouter_api_key": "sk-or"}
    assert calls[1].kwargs == {"onboarding_wizard_shown": True}


def test_onboarding_summary_includes_readiness_status(monkeypatch):
    app = AccessiWeatherApp.__new__(AccessiWeatherApp)
    app._portable_mode = False
    app.main_window = SimpleNamespace(on_add_location=MagicMock(), open_settings=MagicMock())
    settings = SimpleNamespace(onboarding_wizard_shown=False, portable_auto_bundle_enabled=False)
    configs = iter(
        [
            SimpleNamespace(locations=[], settings=settings),
            SimpleNamespace(locations=[SimpleNamespace(name="Home")], settings=settings),
        ]
    )
    app.config_manager = SimpleNamespace(
        get_config=lambda: next(configs),
        update_settings=MagicMock(),
    )

    _ensure_wx_dialog_constants()
    responses = [
        getattr(wx, "ID_NO", 0),
        getattr(wx, "ID_CANCEL", 2),
        getattr(wx, "ID_CANCEL", 2),
        getattr(wx, "ID_OK", 1),
    ]
    captured_messages: list[str] = []

    class _CapturingDialog(_FakeDialog):
        def __init__(self, message: str, responses: list[int]):
            super().__init__(responses)
            captured_messages.append(message)

    monkeypatch.setattr(
        "accessiweather.app.wx.MessageDialog",
        lambda _parent, message, *_args, **_kwargs: _CapturingDialog(message, responses),
        raising=False,
    )
    monkeypatch.setattr(
        "accessiweather.app.wx.TextEntryDialog",
        lambda *args, **kwargs: _FakeTextEntryDialog([]),
        raising=False,
    )
    monkeypatch.setattr(
        app, "_has_saved_api_key", lambda key_name: key_name == "openrouter_api_key"
    )

    app._maybe_show_first_start_onboarding()

    summary = captured_messages[-1]
    assert "Location configured: Yes" in summary
    assert "OpenRouter key set: Yes" in summary
    assert "Visual Crossing weather provider key set: No" in summary
    assert "Portable encrypted bundle enabled: No" in summary
