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
        "ICON_QUESTION": 0,
        "ICON_ERROR": 0,
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


def test_portable_missing_api_keys_hint_shown_once_and_persists(monkeypatch, tmp_path):
    app = AccessiWeatherApp.__new__(AccessiWeatherApp)
    app._portable_mode = True
    app._force_wizard = False
    app._portable_keys_imported_this_session = False
    app.main_window = SimpleNamespace(open_settings=MagicMock())
    settings = SimpleNamespace(
        portable_missing_api_keys_hint_shown=False,
        onboarding_wizard_shown=True,  # wizard already done — hint should show
    )
    config = SimpleNamespace(settings=settings, locations={"Home": object()})
    app.config_manager = SimpleNamespace(
        get_settings=lambda: settings,
        get_config=lambda: config,
        update_settings=MagicMock(),
        config_dir=tmp_path,  # no bundle files → hint should show
    )

    _ensure_wx_dialog_constants()
    responses = [getattr(wx, "ID_YES", 1)]
    monkeypatch.setattr(
        "accessiweather.app.wx.MessageDialog",
        lambda *args, **kwargs: _FakeDialog(responses),
        raising=False,
    )

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

    assert calls[0][0] == 400
    assert calls[0][1] == app._maybe_auto_import_keys_file
    assert calls[1][0] == 800
    assert calls[1][1] == app._maybe_show_first_start_onboarding
    assert calls[2][0] == 1400
    assert calls[2][1] == app._maybe_show_portable_missing_keys_hint


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
    app._force_wizard = False
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
    app._force_wizard = False
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
    app._force_wizard = False
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
    app._force_wizard = False
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
    app._force_wizard = False
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


def test_onboarding_completion_triggers_deferred_startup_update_check(monkeypatch):
    app = AccessiWeatherApp.__new__(AccessiWeatherApp)
    app._portable_mode = False
    app._force_wizard = False
    app.main_window = SimpleNamespace(on_add_location=MagicMock(), open_settings=MagicMock())
    settings = SimpleNamespace(onboarding_wizard_shown=False)
    app.config_manager = SimpleNamespace(
        get_config=lambda: SimpleNamespace(locations=[], settings=settings),
        update_settings=MagicMock(),
    )
    app._run_deferred_startup_update_check = MagicMock()
    app._force_wizard = False

    _ensure_wx_dialog_constants()
    responses = [
        getattr(wx, "ID_NO", 0),
        getattr(wx, "ID_CANCEL", 2),
        getattr(wx, "ID_CANCEL", 2),
        getattr(wx, "ID_OK", 1),
    ]
    monkeypatch.setattr(
        "accessiweather.app.wx.MessageDialog",
        lambda *args, **kwargs: _FakeDialog(responses),
        raising=False,
    )
    monkeypatch.setattr(
        "accessiweather.app.wx.TextEntryDialog",
        lambda *args, **kwargs: _FakeTextEntryDialog([]),
        raising=False,
    )

    app._maybe_show_first_start_onboarding()

    app._run_deferred_startup_update_check.assert_called_once()


# ---------------------------------------------------------------------------
# Tests for _maybe_offer_portable_key_export
# ---------------------------------------------------------------------------


def _make_app_for_key_export(monkeypatch, has_keys: bool, config_dir=None):
    """Build a minimal AccessiWeatherApp stub for key-export tests."""
    from pathlib import Path

    app = AccessiWeatherApp.__new__(AccessiWeatherApp)
    app._portable_mode = True
    app._force_wizard = False
    app.main_window = SimpleNamespace()

    cfg_dir = Path(config_dir) if config_dir else Path("/tmp/portable-config")
    app.config_manager = SimpleNamespace(
        config_dir=cfg_dir,
        export_encrypted_api_keys=MagicMock(return_value=True),
    )

    # Patch _has_any_saved_api_keys directly on the instance
    app._has_any_saved_api_keys = MagicMock(return_value=has_keys)
    app._force_wizard = False

    _ensure_wx_dialog_constants()
    return app


def test_portable_key_export_skips_when_no_keyring_keys(monkeypatch):
    """If no keyring keys exist, _maybe_offer_portable_key_export is a no-op."""
    app = _make_app_for_key_export(monkeypatch, has_keys=False)

    dialog_calls = []
    monkeypatch.setattr(
        "accessiweather.app.wx.MessageDialog",
        lambda *a, **kw: dialog_calls.append(a) or _FakeDialog([]),
        raising=False,
    )

    app._maybe_offer_portable_key_export()

    assert dialog_calls == [], "No dialog should appear when no keyring keys exist"
    app.config_manager.export_encrypted_api_keys.assert_not_called()


def test_portable_key_export_skips_when_user_declines(monkeypatch):
    """User says 'Skip' → no export attempted."""
    app = _make_app_for_key_export(monkeypatch, has_keys=True)

    responses = [getattr(wx, "ID_NO", 0)]
    monkeypatch.setattr(
        "accessiweather.app.wx.MessageDialog",
        lambda *a, **kw: _FakeDialog(responses),
        raising=False,
    )

    app._maybe_offer_portable_key_export()

    app.config_manager.export_encrypted_api_keys.assert_not_called()


def test_portable_key_export_skips_when_no_passphrase(monkeypatch):
    """User says yes but enters no passphrase → show warning, no export."""
    app = _make_app_for_key_export(monkeypatch, has_keys=True)

    dialog_responses = [getattr(wx, "ID_YES", 1)]
    monkeypatch.setattr(
        "accessiweather.app.wx.MessageDialog",
        lambda *a, **kw: _FakeDialog(dialog_responses),
        raising=False,
    )
    # Empty passphrase from TextEntryDialog
    monkeypatch.setattr(
        "accessiweather.app.wx.TextEntryDialog",
        lambda *a, **kw: _FakeTextEntryDialog([""]),
        raising=False,
    )
    messagebox_calls = []
    monkeypatch.setattr(
        "accessiweather.app.wx.MessageBox",
        lambda *a, **kw: messagebox_calls.append(a),
        raising=False,
    )

    app._maybe_offer_portable_key_export()

    app.config_manager.export_encrypted_api_keys.assert_not_called()
    assert messagebox_calls, "A warning MessageBox should have been shown"


def test_portable_key_export_happy_path(monkeypatch, tmp_path):
    """User accepts export, provides passphrase → export called, success dialog shown."""
    app = _make_app_for_key_export(monkeypatch, has_keys=True, config_dir=str(tmp_path))

    dialog_responses = [getattr(wx, "ID_YES", 1)]
    monkeypatch.setattr(
        "accessiweather.app.wx.MessageDialog",
        lambda *a, **kw: _FakeDialog(dialog_responses),
        raising=False,
    )
    monkeypatch.setattr(
        "accessiweather.app.wx.TextEntryDialog",
        lambda *a, **kw: _FakeTextEntryDialog(["my-secret-pass"]),
        raising=False,
    )
    messagebox_calls = []
    monkeypatch.setattr(
        "accessiweather.app.wx.MessageBox",
        lambda *a, **kw: messagebox_calls.append(a),
        raising=False,
    )

    app._maybe_offer_portable_key_export()

    expected_path = tmp_path / "api-keys.keys"
    app.config_manager.export_encrypted_api_keys.assert_called_once_with(
        expected_path, "my-secret-pass"
    )
    assert messagebox_calls, "A success MessageBox should have been shown"
    assert (
        "successful" in messagebox_calls[0][1].lower()
        or "successful" in messagebox_calls[0][0].lower()
    )


def test_portable_key_export_shows_error_on_failure(monkeypatch, tmp_path):
    """When export_encrypted_api_keys returns False, an error dialog is shown."""
    app = _make_app_for_key_export(monkeypatch, has_keys=True, config_dir=str(tmp_path))
    app.config_manager.export_encrypted_api_keys = MagicMock(return_value=False)

    dialog_responses = [getattr(wx, "ID_YES", 1)]
    monkeypatch.setattr(
        "accessiweather.app.wx.MessageDialog",
        lambda *a, **kw: _FakeDialog(dialog_responses),
        raising=False,
    )
    monkeypatch.setattr(
        "accessiweather.app.wx.TextEntryDialog",
        lambda *a, **kw: _FakeTextEntryDialog(["pass"]),
        raising=False,
    )
    messagebox_calls = []
    monkeypatch.setattr(
        "accessiweather.app.wx.MessageBox",
        lambda *a, **kw: messagebox_calls.append(a),
        raising=False,
    )

    app._maybe_offer_portable_key_export()

    assert messagebox_calls, "An error MessageBox should have been shown"
    assert "fail" in messagebox_calls[0][0].lower() or "fail" in messagebox_calls[0][1].lower()


# ---------------------------------------------------------------------------
# Tests for _maybe_auto_import_keys_file
# ---------------------------------------------------------------------------


def _make_app_for_auto_import(tmp_path, all_keys_missing: bool = True):
    """Build a minimal AccessiWeatherApp stub for auto-import tests."""
    app = AccessiWeatherApp.__new__(AccessiWeatherApp)
    app._portable_mode = True
    app._force_wizard = False
    app._portable_keys_imported_this_session = False
    app.main_window = SimpleNamespace()
    app.config_manager = SimpleNamespace(
        config_dir=tmp_path,
        import_encrypted_api_keys=MagicMock(return_value=True),
    )

    app._force_wizard = False
    # all_keys_missing controls whether SecureStorage returns keys or not;
    # callers that need "all present" should patch SecureStorage.get_password.

    _ensure_wx_dialog_constants()
    return app


def test_auto_import_noops_in_non_portable_mode(tmp_path):
    """_maybe_auto_import_keys_file is a no-op when not in portable mode."""
    app = _make_app_for_auto_import(tmp_path)
    app._portable_mode = False
    app._force_wizard = False

    # Create a .keys file — should still be ignored.
    (tmp_path / "api-keys.keys").write_bytes(b"dummy")

    app._maybe_auto_import_keys_file()

    app.config_manager.import_encrypted_api_keys.assert_not_called()


def test_auto_import_silent_when_passphrase_cached(monkeypatch, tmp_path):
    """If passphrase is cached in keyring, bundle is imported silently."""
    app = _make_app_for_auto_import(tmp_path)
    (tmp_path / "api-keys.keys").write_bytes(b"dummy")
    app.config_manager.import_encrypted_api_keys = MagicMock(return_value=True)

    monkeypatch.setattr(
        "accessiweather.config.secure_storage.SecureStorage.get_password",
        lambda name: "cached-pass" if name == app._PORTABLE_PASSPHRASE_KEYRING_KEY else None,
        raising=False,
    )
    monkeypatch.setattr(
        "accessiweather.config.secure_storage.SecureStorage.set_password",
        lambda *a: True,
        raising=False,
    )

    app._maybe_auto_import_keys_file()

    app.config_manager.import_encrypted_api_keys.assert_called_once()
    assert app._portable_keys_imported_this_session is True


def test_auto_import_prompts_when_no_cached_passphrase(monkeypatch, tmp_path):
    """Without cached passphrase, user is prompted."""
    app = _make_app_for_auto_import(tmp_path)
    (tmp_path / "api-keys.keys").write_bytes(b"dummy")
    app.config_manager.import_encrypted_api_keys = MagicMock(return_value=True)

    monkeypatch.setattr(
        "accessiweather.config.secure_storage.SecureStorage.get_password",
        lambda name: None,
        raising=False,
    )
    monkeypatch.setattr(
        "accessiweather.config.secure_storage.SecureStorage.set_password",
        lambda *a: True,
        raising=False,
    )
    monkeypatch.setattr(
        "accessiweather.app.wx.TextEntryDialog",
        lambda *a, **kw: _FakeTextEntryDialog(["my-passphrase"]),
        raising=False,
    )
    monkeypatch.setattr(
        "accessiweather.app.wx.MessageBox",
        lambda *a, **kw: None,
        raising=False,
    )

    app._maybe_auto_import_keys_file()

    app.config_manager.import_encrypted_api_keys.assert_called_once()
    assert app._portable_keys_imported_this_session is True


def test_auto_import_noops_when_no_keys_file(tmp_path):
    """If neither .keys nor .awkeys file exists, nothing happens."""
    app = _make_app_for_auto_import(tmp_path)

    app._maybe_auto_import_keys_file()

    app.config_manager.import_encrypted_api_keys.assert_not_called()


def test_auto_import_happy_path_keys_file(monkeypatch, tmp_path):
    """User enters correct passphrase → import succeeds, confirmation shown."""
    app = _make_app_for_auto_import(tmp_path)
    keys_file = tmp_path / "api-keys.keys"
    keys_file.write_bytes(b"encrypted-blob")

    monkeypatch.setattr(
        "accessiweather.app.wx.TextEntryDialog",
        lambda *a, **kw: _FakeTextEntryDialog(["correct-pass"]),
        raising=False,
    )
    messagebox_calls = []
    monkeypatch.setattr(
        "accessiweather.app.wx.MessageBox",
        lambda *a, **kw: messagebox_calls.append(a),
        raising=False,
    )

    app._maybe_auto_import_keys_file()

    app.config_manager.import_encrypted_api_keys.assert_called_once_with(keys_file, "correct-pass")
    assert messagebox_calls, "A success message should appear"
    assert "imported" in messagebox_calls[0][0].lower()


def test_auto_import_happy_path_legacy_awkeys(monkeypatch, tmp_path):
    """Legacy api-keys.awkeys file is also detected."""
    app = _make_app_for_auto_import(tmp_path)
    legacy_file = tmp_path / "api-keys.awkeys"
    legacy_file.write_bytes(b"encrypted-blob")

    monkeypatch.setattr(
        "accessiweather.app.wx.TextEntryDialog",
        lambda *a, **kw: _FakeTextEntryDialog(["pass"]),
        raising=False,
    )
    monkeypatch.setattr(
        "accessiweather.app.wx.MessageBox",
        lambda *a, **kw: None,
        raising=False,
    )

    app._maybe_auto_import_keys_file()

    app.config_manager.import_encrypted_api_keys.assert_called_once_with(legacy_file, "pass")


def test_auto_import_prefers_keys_over_awkeys(monkeypatch, tmp_path):
    """When both exist, api-keys.keys takes precedence over the legacy name."""
    app = _make_app_for_auto_import(tmp_path)
    (tmp_path / "api-keys.keys").write_bytes(b"preferred")
    (tmp_path / "api-keys.awkeys").write_bytes(b"legacy")

    monkeypatch.setattr(
        "accessiweather.app.wx.TextEntryDialog",
        lambda *a, **kw: _FakeTextEntryDialog(["pass"]),
        raising=False,
    )
    monkeypatch.setattr(
        "accessiweather.app.wx.MessageBox",
        lambda *a, **kw: None,
        raising=False,
    )

    app._maybe_auto_import_keys_file()

    called_path = app.config_manager.import_encrypted_api_keys.call_args[0][0]
    assert called_path.name == "api-keys.keys"


def test_auto_import_wrong_passphrase_then_skip(monkeypatch, tmp_path):
    """Wrong passphrase → error dialog → user picks Skip → no import."""
    app = _make_app_for_auto_import(tmp_path)
    (tmp_path / "api-keys.keys").write_bytes(b"blob")
    app.config_manager.import_encrypted_api_keys = MagicMock(return_value=False)

    monkeypatch.setattr(
        "accessiweather.app.wx.TextEntryDialog",
        lambda *a, **kw: _FakeTextEntryDialog(["bad-pass"]),
        raising=False,
    )
    # Retry dialog → user picks "Skip" (ID_NO)
    monkeypatch.setattr(
        "accessiweather.app.wx.MessageDialog",
        lambda *a, **kw: _FakeDialog([getattr(wx, "ID_NO", 0)]),
        raising=False,
    )

    app._maybe_auto_import_keys_file()

    app.config_manager.import_encrypted_api_keys.assert_called_once()


def test_auto_import_wrong_passphrase_then_retry_success(monkeypatch, tmp_path):
    """Wrong passphrase first → user retries → second attempt succeeds."""
    app = _make_app_for_auto_import(tmp_path)
    (tmp_path / "api-keys.keys").write_bytes(b"blob")

    call_count = {"n": 0}

    def _import_side_effect(path, passphrase):
        call_count["n"] += 1
        return call_count["n"] > 1  # fails first, succeeds after

    app.config_manager.import_encrypted_api_keys = MagicMock(side_effect=_import_side_effect)

    text_iter = iter(["bad-pass", "good-pass"])
    monkeypatch.setattr(
        "accessiweather.app.wx.TextEntryDialog",
        lambda *a, **kw: _FakeTextEntryDialog([next(text_iter)]),
        raising=False,
    )
    # First retry dialog → "Try again" (ID_YES)
    monkeypatch.setattr(
        "accessiweather.app.wx.MessageDialog",
        lambda *a, **kw: _FakeDialog([getattr(wx, "ID_YES", 1)]),
        raising=False,
    )
    messagebox_calls = []
    monkeypatch.setattr(
        "accessiweather.app.wx.MessageBox",
        lambda *a, **kw: messagebox_calls.append(a),
        raising=False,
    )

    app._maybe_auto_import_keys_file()

    assert app.config_manager.import_encrypted_api_keys.call_count == 2
    assert messagebox_calls, "Success confirmation should appear"


def test_auto_import_cancel_passphrase_dialog_exits_silently(monkeypatch, tmp_path):
    """User cancels passphrase dialog → no import, no error."""
    app = _make_app_for_auto_import(tmp_path)
    (tmp_path / "api-keys.keys").write_bytes(b"blob")

    class _CancelDialog:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def ShowModal(self):
            return getattr(wx, "ID_CANCEL", 2)

        def GetValue(self):
            return ""

    monkeypatch.setattr(
        "accessiweather.app.wx.TextEntryDialog",
        _CancelDialog,
        raising=False,
    )

    app._maybe_auto_import_keys_file()

    app.config_manager.import_encrypted_api_keys.assert_not_called()


def test_schedule_startup_guidance_prompts_includes_auto_import(monkeypatch):
    """_schedule_startup_guidance_prompts schedules the auto-import step first."""
    app = AccessiWeatherApp.__new__(AccessiWeatherApp)

    calls: list[tuple[int, object]] = []
    monkeypatch.setattr(
        "accessiweather.app.wx.CallLater",
        lambda delay, fn: calls.append((delay, fn)),
        raising=False,
    )

    app._schedule_startup_guidance_prompts()

    fns = [fn for _, fn in calls]
    assert app._maybe_auto_import_keys_file in fns
    # auto-import must fire before onboarding
    auto_idx = fns.index(app._maybe_auto_import_keys_file)
    onboard_idx = fns.index(app._maybe_show_first_start_onboarding)
    assert auto_idx < onboard_idx
