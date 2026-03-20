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
        if self._responses:
            return self._responses.pop(0)
        return ""


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
    app.main_window.open_settings.assert_called_once_with()

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
    responses = [skip_id, cancel_id, cancel_id, cancel_id, getattr(wx, "ID_OK", 1)]
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


def test_onboarding_wizard_portable_happy_path_sets_keys_and_bundle(monkeypatch, tmp_path):
    app = AccessiWeatherApp.__new__(AccessiWeatherApp)
    app._portable_mode = True
    app._force_wizard = False
    app._portable_keys_imported_this_session = False
    app.main_window = SimpleNamespace(on_add_location=MagicMock(), open_settings=MagicMock())
    settings = SimpleNamespace(onboarding_wizard_shown=False)
    config = SimpleNamespace(locations=[], settings=settings)
    bundle_path = tmp_path / "api-keys.keys"
    export_mock = MagicMock(return_value=True)
    app.config_manager = SimpleNamespace(
        get_config=lambda: config,
        update_settings=MagicMock(),
        get_portable_api_key_bundle_path=lambda: bundle_path,
        export_encrypted_api_keys=export_mock,
    )

    _ensure_wx_dialog_constants()
    # Step 1: skip location; step 2: OR key; step 3: VC key; step 4: Pirate key; summary OK
    responses = [
        getattr(wx, "ID_NO", 0),  # step 1: skip location
        getattr(wx, "ID_YES", 1),  # step 2: OR key — choose "Enter key"
        getattr(wx, "ID_YES", 1),  # step 3: VC key — choose "Enter key"
        getattr(wx, "ID_YES", 1),  # step 4: Pirate key — choose "Enter key"
        getattr(wx, "ID_OK", 1),  # onboarding summary
    ]
    monkeypatch.setattr(
        "accessiweather.app.wx.MessageDialog",
        lambda *args, **kwargs: _FakeDialog(responses),
        raising=False,
    )
    # TextEntryDialog: OR key, VC key, Pirate key, bundle passphrase
    text_responses = [
        "FAKE_OR_KEY_TEST",
        "FAKE_VC_KEY_TEST",
        "FAKE_PW_KEY_TEST",
        "FAKE_BUNDLE_PASSPHRASE",
    ]
    monkeypatch.setattr(
        "accessiweather.app.wx.TextEntryDialog",
        lambda *args, **kwargs: _FakeTextEntryDialog(text_responses),
        raising=False,
    )
    monkeypatch.setattr(
        "accessiweather.app.wx.MessageBox",
        lambda *a, **kw: None,
        raising=False,
    )
    monkeypatch.setattr(
        "accessiweather.config.secure_storage.SecureStorage.set_password",
        lambda *a: True,
        raising=False,
    )
    monkeypatch.setattr(
        "accessiweather.config.secure_storage.SecureStorage.get_password",
        lambda *a: None,
        raising=False,
    )

    app._maybe_show_first_start_onboarding()

    # Wizard should delegate to export_encrypted_api_keys (not raw encrypt_secret_bundle)
    export_mock.assert_called_once_with(bundle_path, "FAKE_BUNDLE_PASSPHRASE")
    # Keys should be live in session memory (set before export call)
    assert settings.openrouter_api_key == "FAKE_OR_KEY_TEST"
    assert settings.visual_crossing_api_key == "FAKE_VC_KEY_TEST"
    assert settings.pirate_weather_api_key == "FAKE_PW_KEY_TEST"
    assert app._portable_keys_imported_this_session is True
    # wizard_shown should be marked
    last_call = app.config_manager.update_settings.call_args_list[-1]
    assert last_call.kwargs == {"onboarding_wizard_shown": True}


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
        getattr(wx, "ID_NO", 0),
        getattr(wx, "ID_CANCEL", 2),
        getattr(wx, "ID_OK", 1),
    ]
    monkeypatch.setattr(
        "accessiweather.app.wx.MessageDialog",
        lambda *args, **kwargs: _FakeDialog(responses),
        raising=False,
    )
    text_responses = ["FAKE_OR_KEY_TEST"]
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
        "https://pirateweather.net/",
    ]
    calls = app.config_manager.update_settings.call_args_list
    assert calls[0].kwargs == {"openrouter_api_key": "FAKE_OR_KEY_TEST"}
    assert calls[1].kwargs == {"onboarding_wizard_shown": True}


def test_onboarding_summary_includes_readiness_status(monkeypatch):
    app = AccessiWeatherApp.__new__(AccessiWeatherApp)
    app._portable_mode = False
    app._force_wizard = False
    app.main_window = SimpleNamespace(on_add_location=MagicMock(), open_settings=MagicMock())
    settings = SimpleNamespace(onboarding_wizard_shown=False)
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
    assert "Pirate Weather provider key set: No" in summary
    # portable_auto_bundle_enabled line removed — not relevant in new design


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
# Tests for wizard step numbering (non-portable = 4 steps, portable = 5)
# ---------------------------------------------------------------------------


def _capture_wizard_step_messages(monkeypatch, *, portable: bool):
    """Run the wizard and capture all dialog messages to verify step numbering."""
    app = AccessiWeatherApp.__new__(AccessiWeatherApp)
    app._portable_mode = portable
    app._force_wizard = False
    app._portable_keys_imported_this_session = False
    app.main_window = SimpleNamespace(on_add_location=MagicMock(), open_settings=MagicMock())
    settings = SimpleNamespace(onboarding_wizard_shown=False)
    app.config_manager = SimpleNamespace(
        get_config=lambda: SimpleNamespace(locations=[], settings=settings),
        update_settings=MagicMock(),
    )

    _ensure_wx_dialog_constants()
    captured_messages: list[str] = []

    class _CapturingDialog(_FakeDialog):
        def __init__(self, message: str, responses: list[int]):
            super().__init__(responses)
            captured_messages.append(message)

    # Skip location, skip OR key, skip VC key, skip Pirate key, OK summary
    responses = [
        getattr(wx, "ID_NO", 0),
        getattr(wx, "ID_CANCEL", 2),
        getattr(wx, "ID_CANCEL", 2),
        getattr(wx, "ID_CANCEL", 2),
        getattr(wx, "ID_OK", 1),
    ]
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
    monkeypatch.setattr(app, "_has_saved_api_key", lambda key_name: False)

    app._maybe_show_first_start_onboarding()
    return captured_messages


def test_wizard_step_numbering_non_portable(monkeypatch):
    """Non-portable wizard uses 'of 4' in step labels."""
    messages = _capture_wizard_step_messages(monkeypatch, portable=False)
    step1 = messages[0]
    assert "Step 1 of 4" in step1, f"Expected 'Step 1 of 4' in: {step1}"


def test_wizard_step_numbering_portable(monkeypatch):
    """Portable wizard uses 'of 5' in step labels."""
    messages = _capture_wizard_step_messages(monkeypatch, portable=True)
    step1 = messages[0]
    assert "Step 1 of 5" in step1, f"Expected 'Step 1 of 5' in: {step1}"


def test_wizard_step2_step3_step4_numbering_non_portable(monkeypatch):
    """Non-portable wizard passes 'of 4' to provider key prompts."""
    app = AccessiWeatherApp.__new__(AccessiWeatherApp)
    app._portable_mode = False
    app._force_wizard = False
    app._portable_keys_imported_this_session = False
    app.main_window = SimpleNamespace(on_add_location=MagicMock(), open_settings=MagicMock())
    settings = SimpleNamespace(onboarding_wizard_shown=False)
    app.config_manager = SimpleNamespace(
        get_config=lambda: SimpleNamespace(locations=[], settings=settings),
        update_settings=MagicMock(),
    )

    _ensure_wx_dialog_constants()
    prompt_messages: list[str] = []

    def fake_prompt(title, message, url, label):
        prompt_messages.append(message)
        return ""

    responses = [
        getattr(wx, "ID_NO", 0),  # step 1 skip
        getattr(wx, "ID_OK", 1),  # summary
    ]
    monkeypatch.setattr(
        "accessiweather.app.wx.MessageDialog",
        lambda *args, **kwargs: _FakeDialog(responses),
        raising=False,
    )
    monkeypatch.setattr(app, "_prompt_optional_secret_with_link", fake_prompt)
    monkeypatch.setattr(app, "_has_saved_api_key", lambda key_name: False)

    app._maybe_show_first_start_onboarding()

    assert len(prompt_messages) == 3
    assert "Step 2 of 4" in prompt_messages[0], f"Expected 'Step 2 of 4' in: {prompt_messages[0]}"
    assert "Step 3 of 4" in prompt_messages[1], f"Expected 'Step 3 of 4' in: {prompt_messages[1]}"
    assert "Step 4 of 4" in prompt_messages[2], f"Expected 'Step 4 of 4' in: {prompt_messages[2]}"


def test_wizard_step2_step3_step4_numbering_portable(monkeypatch):
    """Portable wizard passes 'of 5' to provider key prompts."""
    app = AccessiWeatherApp.__new__(AccessiWeatherApp)
    app._portable_mode = True
    app._force_wizard = False
    app._portable_keys_imported_this_session = False
    app.main_window = SimpleNamespace(on_add_location=MagicMock(), open_settings=MagicMock())
    settings = SimpleNamespace(onboarding_wizard_shown=False)
    app.config_manager = SimpleNamespace(
        get_config=lambda: SimpleNamespace(locations=[], settings=settings),
        update_settings=MagicMock(),
    )

    _ensure_wx_dialog_constants()
    prompt_messages: list[str] = []

    def fake_prompt(title, message, url, label):
        prompt_messages.append(message)
        return ""

    responses = [
        getattr(wx, "ID_NO", 0),  # step 1 skip
        getattr(wx, "ID_OK", 1),  # summary
    ]
    monkeypatch.setattr(
        "accessiweather.app.wx.MessageDialog",
        lambda *args, **kwargs: _FakeDialog(responses),
        raising=False,
    )
    monkeypatch.setattr(app, "_prompt_optional_secret_with_link", fake_prompt)
    monkeypatch.setattr(app, "_has_saved_api_key", lambda key_name: False)

    app._maybe_show_first_start_onboarding()

    assert len(prompt_messages) == 3
    assert "Step 2 of 5" in prompt_messages[0], f"Expected 'Step 2 of 5' in: {prompt_messages[0]}"
    assert "Step 3 of 5" in prompt_messages[1], f"Expected 'Step 3 of 5' in: {prompt_messages[1]}"
    assert "Step 4 of 5" in prompt_messages[2], f"Expected 'Step 4 of 5' in: {prompt_messages[2]}"


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
        export_encrypted_api_keys=MagicMock(return_value=True),
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
        lambda name: "FAKE_CACHED_PASS" if name == app._PORTABLE_PASSPHRASE_KEYRING_KEY else None,
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
        lambda *a, **kw: _FakeTextEntryDialog(["FAKE_MY_PASSPHRASE"]),
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
        lambda *a, **kw: _FakeTextEntryDialog(["FAKE_CORRECT_PASSPHRASE"]),
        raising=False,
    )
    messagebox_calls = []
    monkeypatch.setattr(
        "accessiweather.app.wx.MessageBox",
        lambda *a, **kw: messagebox_calls.append(a),
        raising=False,
    )

    app._maybe_auto_import_keys_file()

    app.config_manager.import_encrypted_api_keys.assert_called_once_with(
        keys_file, "FAKE_CORRECT_PASSPHRASE"
    )
    assert messagebox_calls, "A success message should appear"
    assert "imported" in messagebox_calls[0][0].lower()


def test_auto_import_happy_path_legacy_awkeys(monkeypatch, tmp_path):
    """Legacy api-keys.awkeys file is also detected."""
    app = _make_app_for_auto_import(tmp_path)
    legacy_file = tmp_path / "api-keys.awkeys"
    legacy_file.write_bytes(b"encrypted-blob")

    monkeypatch.setattr(
        "accessiweather.app.wx.TextEntryDialog",
        lambda *a, **kw: _FakeTextEntryDialog(["FAKE_TEST_PASSPHRASE"]),
        raising=False,
    )
    monkeypatch.setattr(
        "accessiweather.app.wx.MessageBox",
        lambda *a, **kw: None,
        raising=False,
    )

    app._maybe_auto_import_keys_file()

    app.config_manager.import_encrypted_api_keys.assert_called_once_with(
        legacy_file, "FAKE_TEST_PASSPHRASE"
    )


def test_auto_import_prefers_keys_over_awkeys(monkeypatch, tmp_path):
    """When both exist, api-keys.keys takes precedence over the legacy name."""
    app = _make_app_for_auto_import(tmp_path)
    (tmp_path / "api-keys.keys").write_bytes(b"preferred")
    (tmp_path / "api-keys.awkeys").write_bytes(b"legacy")

    monkeypatch.setattr(
        "accessiweather.app.wx.TextEntryDialog",
        lambda *a, **kw: _FakeTextEntryDialog(["FAKE_TEST_PASSPHRASE"]),
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
        lambda *a, **kw: _FakeTextEntryDialog(["FAKE_BAD_PASSPHRASE"]),
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

    text_iter = iter(["FAKE_BAD_PASSPHRASE", "FAKE_GOOD_PASSPHRASE"])
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


def test_auto_import_writes_keys_file_after_silent_import(monkeypatch, tmp_path):
    """After silent auto-import, api-keys.keys is written via export_encrypted_api_keys."""
    app = _make_app_for_auto_import(tmp_path)
    (tmp_path / "api-keys.keys").write_bytes(b"dummy")

    monkeypatch.setattr(
        "accessiweather.config.secure_storage.SecureStorage.get_password",
        lambda name: "CACHED_PASS" if name == app._PORTABLE_PASSPHRASE_KEYRING_KEY else None,
        raising=False,
    )
    monkeypatch.setattr(
        "accessiweather.config.secure_storage.SecureStorage.set_password",
        lambda *a: True,
        raising=False,
    )

    app._maybe_auto_import_keys_file()

    app.config_manager.export_encrypted_api_keys.assert_called_once_with(
        tmp_path / "api-keys.keys", "CACHED_PASS"
    )


def test_auto_import_writes_keys_file_after_prompted_import(monkeypatch, tmp_path):
    """After user-prompted import, api-keys.keys is written via export_encrypted_api_keys."""
    app = _make_app_for_auto_import(tmp_path)
    (tmp_path / "api-keys.awkeys").write_bytes(b"legacy-blob")

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
        lambda *a, **kw: _FakeTextEntryDialog(["USER_PASSPHRASE"]),
        raising=False,
    )
    monkeypatch.setattr(
        "accessiweather.app.wx.MessageBox",
        lambda *a, **kw: None,
        raising=False,
    )

    app._maybe_auto_import_keys_file()

    app.config_manager.export_encrypted_api_keys.assert_called_once_with(
        tmp_path / "api-keys.keys", "USER_PASSPHRASE"
    )


def test_auto_import_export_failure_does_not_block_import(monkeypatch, tmp_path):
    """If export_encrypted_api_keys raises, import still succeeds."""
    app = _make_app_for_auto_import(tmp_path)
    (tmp_path / "api-keys.keys").write_bytes(b"dummy")
    app.config_manager.export_encrypted_api_keys = MagicMock(side_effect=OSError("disk full"))

    monkeypatch.setattr(
        "accessiweather.config.secure_storage.SecureStorage.get_password",
        lambda name: "CACHED_PASS" if name == app._PORTABLE_PASSPHRASE_KEYRING_KEY else None,
        raising=False,
    )
    monkeypatch.setattr(
        "accessiweather.config.secure_storage.SecureStorage.set_password",
        lambda *a: True,
        raising=False,
    )

    app._maybe_auto_import_keys_file()

    # Import still marked as successful despite export failure
    assert app._portable_keys_imported_this_session is True


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


# ---------------------------------------------------------------------------
# Tests for wizard using export_encrypted_api_keys (not raw encrypt_secret_bundle)
# ---------------------------------------------------------------------------


def test_wizard_portable_export_failure_shows_warning(monkeypatch, tmp_path):
    """When export_encrypted_api_keys returns False, wizard shows bundle write failure."""
    app = AccessiWeatherApp.__new__(AccessiWeatherApp)
    app._portable_mode = True
    app._force_wizard = False
    app._portable_keys_imported_this_session = False
    app.main_window = SimpleNamespace(on_add_location=MagicMock(), open_settings=MagicMock())
    settings = SimpleNamespace(onboarding_wizard_shown=False)
    config = SimpleNamespace(locations=[], settings=settings)
    bundle_path = tmp_path / "api-keys.keys"
    export_mock = MagicMock(return_value=False)
    app.config_manager = SimpleNamespace(
        get_config=lambda: config,
        update_settings=MagicMock(),
        get_portable_api_key_bundle_path=lambda: bundle_path,
        export_encrypted_api_keys=export_mock,
    )

    _ensure_wx_dialog_constants()
    responses = [
        getattr(wx, "ID_NO", 0),  # step 1: skip location
        getattr(wx, "ID_YES", 1),  # step 2: OR key — choose "Enter key"
        getattr(wx, "ID_CANCEL", 2),  # step 3: VC key — skip
        getattr(wx, "ID_CANCEL", 2),  # step 4: Pirate key — skip
        getattr(wx, "ID_OK", 1),  # onboarding summary
    ]
    monkeypatch.setattr(
        "accessiweather.app.wx.MessageDialog",
        lambda *args, **kwargs: _FakeDialog(responses),
        raising=False,
    )
    text_responses = ["FAKE_OR_KEY_TEST", "FAKE_BUNDLE_PASSPHRASE"]
    monkeypatch.setattr(
        "accessiweather.app.wx.TextEntryDialog",
        lambda *args, **kwargs: _FakeTextEntryDialog(text_responses),
        raising=False,
    )
    messagebox_calls = []
    monkeypatch.setattr(
        "accessiweather.app.wx.MessageBox",
        lambda *a, **kw: messagebox_calls.append(a),
        raising=False,
    )
    monkeypatch.setattr(
        "accessiweather.config.secure_storage.SecureStorage.set_password",
        lambda *a: True,
        raising=False,
    )
    monkeypatch.setattr(
        "accessiweather.config.secure_storage.SecureStorage.get_password",
        lambda *a: None,
        raising=False,
    )

    app._maybe_show_first_start_onboarding()

    export_mock.assert_called_once()
    # Should NOT mark as imported when export fails
    assert app._portable_keys_imported_this_session is False
    # A failure warning should have been shown
    assert any(
        "failed" in str(call).lower() or "not persist" in str(call).lower()
        for call in messagebox_calls
    )
