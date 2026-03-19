from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from unittest.mock import MagicMock


def _load_settings_dialog_module():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "accessiweather"
        / "ui"
        / "dialogs"
        / "settings_dialog.py"
    )
    spec = importlib.util.spec_from_file_location("test_settings_dialog_copy_module", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


module = _load_settings_dialog_module()
SettingsDialogSimple = module.SettingsDialogSimple


def _ensure_wx_constants() -> None:
    for name, value in {
        "YES": 1,
        "NO": 0,
        "OK": 0,
        "YES_NO": 0,
        "CANCEL": 0,
        "ID_OK": 1,
        "ICON_QUESTION": 0,
        "ICON_INFORMATION": 0,
        "ICON_WARNING": 0,
        "ICON_ERROR": 0,
        "TE_PASSWORD": 0,
    }.items():
        if not hasattr(module.wx, name):
            setattr(module.wx, name, value)


def _write_config(config_dir: Path, *, ai_model: str, locations: list[dict]) -> None:
    config_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "settings": {
            "ai_model_preference": ai_model,
            "data_source": "auto",
            "temperature_unit": "f",
        },
        "locations": locations,
    }
    (config_dir / "accessiweather.json").write_text(json.dumps(payload), encoding="utf-8")


def _make_dialog(portable_config_dir: Path) -> SettingsDialogSimple:
    dialog = SettingsDialogSimple.__new__(SettingsDialogSimple)
    dialog.config_manager = MagicMock()
    dialog.config_manager.config_dir = portable_config_dir
    dialog._load_settings = MagicMock()
    dialog.app = MagicMock()
    return dialog


def test_validate_portable_copy_detects_missing_locations(tmp_path):
    installed = tmp_path / "installed"
    portable = tmp_path / "portable"
    _write_config(installed, ai_model="openrouter/auto", locations=[{"name": "Seattle"}])
    _write_config(portable, ai_model="openrouter/auto", locations=[])

    dialog = _make_dialog(portable)
    valid, errors = dialog._validate_portable_copy(installed, portable)

    assert valid is False
    assert any("Location count mismatch" in e for e in errors)


def test_copy_installed_config_to_portable_success_reloads_and_offers_key_export(
    tmp_path, monkeypatch
):
    installed = tmp_path / "installed"
    portable = tmp_path / "portable"
    _write_config(installed, ai_model="openrouter/auto", locations=[{"name": "Seattle"}])
    (installed / "cache.db").write_text("cache", encoding="utf-8")
    (installed / "weather_cache").mkdir(parents=True, exist_ok=True)
    (installed / "weather_cache" / "foo.txt").write_text("x", encoding="utf-8")

    dialog = _make_dialog(portable)
    dialog._get_installed_config_dir = lambda: installed

    _ensure_wx_constants()
    if not hasattr(module.wx, "YES_NO"):
        module.wx.YES_NO = 0
    calls: list[tuple] = []

    def _fake_message_box(message, title, style):
        calls.append((message, title, style))
        if title == "Copy installed config to portable":
            return module.wx.YES
        # Decline the API key export offer
        if title == "Export API keys?":
            return getattr(module.wx, "NO", 0)
        return module.wx.OK

    monkeypatch.setattr(module.wx, "MessageBox", _fake_message_box, raising=False)

    dialog._on_copy_installed_config_to_portable(None)

    dialog.config_manager.save_config.assert_called_once()
    dialog.config_manager.load_config.assert_called_once()
    dialog._load_settings.assert_called_once()
    assert dialog.config_manager._config is None
    assert (portable / "accessiweather.json").exists()
    assert not (portable / "cache.db").exists()
    assert not (portable / "weather_cache").exists()

    # Check "Copy complete" message
    copy_complete = next((msg, t, s) for msg, t, s in calls if t == "Copy complete")
    assert "• accessiweather.json" in copy_complete[0]
    assert "Copied settings summary:" in copy_complete[0]
    assert "• locations: 1" in copy_complete[0]
    assert "• data source: auto" in copy_complete[0]
    assert "• AI model preference: openrouter/auto" in copy_complete[0]
    assert "• temperature unit: f" in copy_complete[0]
    assert "• custom prompt: no" in copy_complete[0]
    assert "cache.db" not in copy_complete[0]

    # Check API key export was offered
    assert any(t == "Export API keys?" for _, t, _ in calls)
    # Declined → reminder message shown
    assert any(t == "API keys not exported" for _, t, _ in calls)


def test_copy_installed_config_to_portable_excludes_runtime_state_files(tmp_path, monkeypatch):
    installed = tmp_path / "installed"
    portable = tmp_path / "portable"
    _write_config(installed, ai_model="openrouter/auto", locations=[{"name": "Seattle"}])
    (installed / "alert_state.json").write_text("{}", encoding="utf-8")
    (installed / "notification_event_state.json").write_text("{}", encoding="utf-8")
    (installed / "state").mkdir(parents=True, exist_ok=True)
    (installed / "state" / "runtime_state.json").write_text("{}", encoding="utf-8")

    dialog = _make_dialog(portable)
    dialog._get_installed_config_dir = lambda: installed

    _ensure_wx_constants()
    calls: list[tuple] = []

    def _fake_message_box(message, title, style):
        calls.append((message, title, style))
        if title == "Copy installed config to portable":
            return module.wx.YES
        if title == "Export API keys?":
            return getattr(module.wx, "NO", 0)
        return module.wx.OK

    monkeypatch.setattr(module.wx, "MessageBox", _fake_message_box, raising=False)

    dialog._on_copy_installed_config_to_portable(None)

    assert (portable / "accessiweather.json").exists()
    assert not (portable / "alert_state.json").exists()
    assert not (portable / "notification_event_state.json").exists()
    assert not (portable / "state" / "runtime_state.json").exists()
    copy_complete = next((msg, t, s) for msg, t, s in calls if t == "Copy complete")
    assert "runtime_state.json" not in copy_complete[0]
    assert "alert_state.json" not in copy_complete[0]
    assert "notification_event_state.json" not in copy_complete[0]


def test_copy_installed_config_to_portable_validation_failure_reports_incomplete(
    tmp_path, monkeypatch
):
    installed = tmp_path / "installed"
    portable = tmp_path / "portable"
    _write_config(installed, ai_model="openrouter/auto", locations=[{"name": "Seattle"}])

    dialog = _make_dialog(portable)
    dialog._get_installed_config_dir = lambda: installed

    _ensure_wx_constants()
    calls: list[tuple] = []

    def _fake_message_box(message, title, style):
        calls.append((message, title, style))
        if title == "Copy installed config to portable":
            return module.wx.YES
        return module.wx.OK

    monkeypatch.setattr(module.wx, "MessageBox", _fake_message_box, raising=False)
    monkeypatch.setattr(
        dialog,
        "_validate_portable_copy",
        lambda _installed, _portable: (False, ["Location count mismatch after copy"]),
    )

    dialog._on_copy_installed_config_to_portable(None)

    assert any(title == "Copy incomplete" for _, title, _ in calls)
    dialog.config_manager.load_config.assert_not_called()
    dialog._load_settings.assert_not_called()


def test_copy_installed_config_to_portable_empty_source_dir_warns_and_stops(tmp_path, monkeypatch):
    installed = tmp_path / "installed"
    installed.mkdir(parents=True, exist_ok=True)
    portable = tmp_path / "portable"

    dialog = _make_dialog(portable)
    dialog._get_installed_config_dir = lambda: installed

    _ensure_wx_constants()
    calls: list[tuple] = []

    monkeypatch.setattr(
        module.wx,
        "MessageBox",
        lambda message, title, style: calls.append((message, title, style)) or module.wx.OK,
        raising=False,
    )

    dialog._on_copy_installed_config_to_portable(None)

    assert any(title == "Nothing to copy" for _, title, _ in calls)
    assert not any(title == "Copy installed config to portable" for _, title, _ in calls)
    dialog.config_manager.save_config.assert_not_called()
    dialog.config_manager.load_config.assert_not_called()


def test_copy_installed_config_to_portable_missing_or_empty_config_warns_and_stops(
    tmp_path, monkeypatch
):
    installed = tmp_path / "installed"
    portable = tmp_path / "portable"

    dialog = _make_dialog(portable)
    dialog._get_installed_config_dir = lambda: installed

    _ensure_wx_constants()

    # Missing config file
    installed.mkdir(parents=True, exist_ok=True)
    (installed / "cache.db").write_text("cache", encoding="utf-8")
    calls_missing: list[tuple] = []
    monkeypatch.setattr(
        module.wx,
        "MessageBox",
        lambda message, title, style: calls_missing.append((message, title, style)) or module.wx.OK,
        raising=False,
    )
    dialog._on_copy_installed_config_to_portable(None)
    assert any(title == "Nothing to copy" for _, title, _ in calls_missing)
    assert not any(title == "Copy installed config to portable" for _, title, _ in calls_missing)

    # Empty config file
    for item in installed.iterdir():
        if item.is_file():
            item.unlink()
    (installed / "accessiweather.json").write_text("", encoding="utf-8")
    calls_empty: list[tuple] = []
    monkeypatch.setattr(
        module.wx,
        "MessageBox",
        lambda message, title, style: calls_empty.append((message, title, style)) or module.wx.OK,
        raising=False,
    )
    dialog._on_copy_installed_config_to_portable(None)
    assert any(title == "Nothing to copy" for _, title, _ in calls_empty)
    assert not any(title == "Copy installed config to portable" for _, title, _ in calls_empty)

    dialog.config_manager.save_config.assert_not_called()
    dialog.config_manager.load_config.assert_not_called()


def test_runtime_portable_mode_prefers_app_runtime_flag_over_heuristic(monkeypatch):
    dialog = _make_dialog(Path("/tmp/portable"))
    dialog.app._portable_mode = True

    monkeypatch.setattr(
        module,
        "is_portable_mode",
        lambda: (_ for _ in ()).throw(AssertionError("heuristic should not be used")),
        raising=False,
    )

    assert dialog._is_runtime_portable_mode() is True


def test_export_settings_message_mentions_encrypted_api_key_transfer(monkeypatch, tmp_path):
    dialog = _make_dialog(tmp_path / "portable")
    dialog.config_manager.export_settings = MagicMock(return_value=True)

    _ensure_wx_constants()
    if not hasattr(module.wx, "ID_OK"):
        module.wx.ID_OK = 1
    if not hasattr(module.wx, "FD_SAVE"):
        module.wx.FD_SAVE = 0
    if not hasattr(module.wx, "FD_OVERWRITE_PROMPT"):
        module.wx.FD_OVERWRITE_PROMPT = 0

    messages: list[tuple] = []

    class _FakeFileDialog:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def ShowModal(self):
            return module.wx.ID_OK

        def GetPath(self):
            return str(tmp_path / "settings.json")

    monkeypatch.setattr(
        module.wx, "FileDialog", lambda *args, **kwargs: _FakeFileDialog(), raising=False
    )
    monkeypatch.setattr(
        module.wx,
        "MessageBox",
        lambda message, title, style: messages.append((message, title, style)) or module.wx.OK,
        raising=False,
    )

    dialog._on_export_settings(None)

    assert messages
    export_message = messages[-1][0]
    assert "API keys are not included here" in export_message
    assert "Export API keys (encrypted)" in export_message
    assert "Import API keys (encrypted)" in export_message


def test_import_settings_confirm_and_success_messages_mention_encrypted_key_transfer(
    monkeypatch, tmp_path
):
    dialog = _make_dialog(tmp_path / "portable")
    dialog.config_manager.import_settings = MagicMock(return_value=True)

    _ensure_wx_constants()
    if not hasattr(module.wx, "ID_OK"):
        module.wx.ID_OK = 1
    if not hasattr(module.wx, "FD_OPEN"):
        module.wx.FD_OPEN = 0
    if not hasattr(module.wx, "FD_FILE_MUST_EXIST"):
        module.wx.FD_FILE_MUST_EXIST = 0

    calls: list[tuple] = []

    class _FakeFileDialog:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def ShowModal(self):
            return module.wx.ID_OK

        def GetPath(self):
            return str(tmp_path / "settings.json")

    def _fake_message_box(message, title, style):
        calls.append((message, title, style))
        if title == "Confirm Import":
            return module.wx.YES
        return module.wx.OK

    monkeypatch.setattr(
        module.wx, "FileDialog", lambda *args, **kwargs: _FakeFileDialog(), raising=False
    )
    monkeypatch.setattr(module.wx, "MessageBox", _fake_message_box, raising=False)

    dialog._on_import_settings(None)

    confirm_message = next(msg for msg, title, _ in calls if title == "Confirm Import")
    complete_message = next(msg for msg, title, _ in calls if title == "Import Complete")
    assert "API keys are not included here" in confirm_message
    assert "Export API keys (encrypted)" in confirm_message
    assert "Import API keys (encrypted)" in complete_message


def test_export_encrypted_api_keys_dialog_uses_keys_primary_and_awkeys_legacy(
    monkeypatch, tmp_path
):
    dialog = _make_dialog(tmp_path / "portable")
    dialog.config_manager.export_encrypted_api_keys = MagicMock(return_value=True)
    dialog._prompt_passphrase = MagicMock(side_effect=["FAKE_PASS", "FAKE_PASS"])

    _ensure_wx_constants()
    if not hasattr(module.wx, "ID_OK"):
        module.wx.ID_OK = 1
    if not hasattr(module.wx, "FD_SAVE"):
        module.wx.FD_SAVE = 0
    if not hasattr(module.wx, "FD_OVERWRITE_PROMPT"):
        module.wx.FD_OVERWRITE_PROMPT = 0

    file_dialog_kwargs: dict = {}

    class _FakeFileDialog:
        def __init__(self, *args, **kwargs):
            file_dialog_kwargs.update(kwargs)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def ShowModal(self):
            return module.wx.ID_OK

        def GetPath(self):
            return str(tmp_path / "exported.keys")

    monkeypatch.setattr(module.wx, "FileDialog", _FakeFileDialog, raising=False)
    monkeypatch.setattr(module.wx, "MessageBox", lambda *a, **k: module.wx.OK, raising=False)

    dialog._on_export_encrypted_api_keys(None)

    assert file_dialog_kwargs["wildcard"].startswith("Encrypted bundle (*.keys)|*.keys|")
    assert "Legacy bundle (*.awkeys)|*.awkeys" in file_dialog_kwargs["wildcard"]
    assert "JSON files (*.json)|*.json" not in file_dialog_kwargs["wildcard"]
    assert file_dialog_kwargs["defaultFile"] == "accessiweather_api_keys.keys"


def test_import_encrypted_api_keys_dialog_accepts_keys_and_awkeys(monkeypatch, tmp_path):
    dialog = _make_dialog(tmp_path / "portable")
    dialog.config_manager.import_encrypted_api_keys = MagicMock(return_value=True)
    dialog._prompt_passphrase = MagicMock(return_value="FAKE_PASS")
    dialog._load_settings = MagicMock()

    _ensure_wx_constants()
    if not hasattr(module.wx, "ID_OK"):
        module.wx.ID_OK = 1
    if not hasattr(module.wx, "FD_OPEN"):
        module.wx.FD_OPEN = 0
    if not hasattr(module.wx, "FD_FILE_MUST_EXIST"):
        module.wx.FD_FILE_MUST_EXIST = 0

    file_dialog_kwargs: dict = {}

    class _FakeFileDialog:
        def __init__(self, *args, **kwargs):
            file_dialog_kwargs.update(kwargs)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def ShowModal(self):
            return module.wx.ID_OK

        def GetPath(self):
            return str(tmp_path / "legacy.awkeys")

    monkeypatch.setattr(module.wx, "FileDialog", _FakeFileDialog, raising=False)
    monkeypatch.setattr(module.wx, "MessageBox", lambda *a, **k: module.wx.OK, raising=False)

    dialog._on_import_encrypted_api_keys(None)

    assert file_dialog_kwargs["wildcard"].startswith("Encrypted bundle (*.keys)|*.keys|")
    assert "Legacy bundle (*.awkeys)|*.awkeys" in file_dialog_kwargs["wildcard"]
    assert "JSON files (*.json)|*.json" not in file_dialog_kwargs["wildcard"]
    dialog.config_manager.import_encrypted_api_keys.assert_called_once()
    called_path = dialog.config_manager.import_encrypted_api_keys.call_args[0][0]
    assert called_path.name == "legacy.awkeys"


def test_copy_installed_config_to_portable_no_locations_warns_and_stops(tmp_path, monkeypatch):
    installed = tmp_path / "installed"
    portable = tmp_path / "portable"
    _write_config(installed, ai_model="openrouter/auto", locations=[])

    dialog = _make_dialog(portable)
    dialog._get_installed_config_dir = lambda: installed

    _ensure_wx_constants()
    calls: list[tuple] = []

    monkeypatch.setattr(
        module.wx,
        "MessageBox",
        lambda message, title, style: calls.append((message, title, style)) or module.wx.OK,
        raising=False,
    )

    dialog._on_copy_installed_config_to_portable(None)

    assert any(title == "Nothing to copy" for _, title, _ in calls)
    assert any("no saved locations" in message.lower() for message, _, _ in calls)
    assert not any(title == "Copy installed config to portable" for _, title, _ in calls)


def test_offer_api_key_export_after_copy_yes_exports_bundle(tmp_path, monkeypatch):
    """When user accepts the key export offer, export_encrypted_api_keys is called."""
    portable = tmp_path / "portable"
    portable.mkdir(parents=True, exist_ok=True)

    dialog = _make_dialog(portable)
    dialog.config_manager.export_encrypted_api_keys = MagicMock(return_value=True)

    _ensure_wx_constants()
    if not hasattr(module.wx, "YES_NO"):
        module.wx.YES_NO = 0
    if not hasattr(module.wx, "NO"):
        module.wx.NO = 0
    if not hasattr(module.wx, "ID_OK"):
        module.wx.ID_OK = 1

    calls: list[tuple] = []

    def _fake_message_box(message, title, style):
        calls.append((message, title, style))
        if title == "Export API keys?":
            return module.wx.YES
        return module.wx.OK

    passphrase_responses = iter(["FAKE_MY_PASS", "FAKE_MY_PASS"])

    class _FakeTextEntryDialog:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def ShowModal(self):
            return module.wx.ID_OK

        def GetValue(self):
            return next(passphrase_responses)

    monkeypatch.setattr(module.wx, "MessageBox", _fake_message_box, raising=False)
    monkeypatch.setattr(module.wx, "TextEntryDialog", _FakeTextEntryDialog, raising=False)

    dialog._offer_api_key_export_after_copy(portable)

    dialog.config_manager.export_encrypted_api_keys.assert_called_once_with(
        portable / "api-keys.keys", "FAKE_MY_PASS"
    )
    assert any(t == "Export complete" for _, t, _ in calls)


def test_offer_api_key_export_after_copy_no_shows_reminder(tmp_path, monkeypatch):
    """When user declines the key export offer, a reminder is shown."""
    portable = tmp_path / "portable"
    portable.mkdir(parents=True, exist_ok=True)

    dialog = _make_dialog(portable)

    _ensure_wx_constants()
    if not hasattr(module.wx, "YES_NO"):
        module.wx.YES_NO = 0
    if not hasattr(module.wx, "NO"):
        module.wx.NO = 0

    calls: list[tuple] = []

    def _fake_message_box(message, title, style):
        calls.append((message, title, style))
        if title == "Export API keys?":
            return getattr(module.wx, "NO", 0)
        return module.wx.OK

    monkeypatch.setattr(module.wx, "MessageBox", _fake_message_box, raising=False)

    dialog._offer_api_key_export_after_copy(portable)

    assert any(t == "API keys not exported" for _, t, _ in calls)
    reminder = next(msg for msg, t, _ in calls if t == "API keys not exported")
    assert "Export API keys (encrypted)" in reminder


def test_offer_api_key_export_after_copy_mismatch_cancels(tmp_path, monkeypatch):
    """When passphrases don't match, export is cancelled."""
    portable = tmp_path / "portable"
    portable.mkdir(parents=True, exist_ok=True)

    dialog = _make_dialog(portable)
    dialog.config_manager.export_encrypted_api_keys = MagicMock()

    _ensure_wx_constants()
    if not hasattr(module.wx, "YES_NO"):
        module.wx.YES_NO = 0
    if not hasattr(module.wx, "ID_OK"):
        module.wx.ID_OK = 1

    calls: list[tuple] = []

    def _fake_message_box(message, title, style):
        calls.append((message, title, style))
        if title == "Export API keys?":
            return module.wx.YES
        return module.wx.OK

    passphrase_responses = iter(["FAKE_PASS_ONE", "FAKE_PASS_TWO"])

    class _FakeTextEntryDialog:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def ShowModal(self):
            return module.wx.ID_OK

        def GetValue(self):
            return next(passphrase_responses)

    monkeypatch.setattr(module.wx, "MessageBox", _fake_message_box, raising=False)
    monkeypatch.setattr(module.wx, "TextEntryDialog", _FakeTextEntryDialog, raising=False)

    dialog._offer_api_key_export_after_copy(portable)

    dialog.config_manager.export_encrypted_api_keys.assert_not_called()
    assert any(t == "Export cancelled" for _, t, _ in calls)


def _make_mock_secure_storage(get_password_fn=None, set_password_fn=None):
    """Create a mock SecureStorage class for injection into the settings_dialog module."""
    mock_cls = MagicMock()
    mock_cls.get_password = staticmethod(get_password_fn or (lambda key: None))
    mock_cls.set_password = staticmethod(set_password_fn or (lambda key, val: True))
    return mock_cls


def _get_real_settings_dialog_class():
    """Import SettingsDialogSimple through proper package paths (handles wx stubs)."""
    import sys

    # Ensure wx.lib.scrolledpanel exists (may be missing in test env)
    if "wx.lib.scrolledpanel" not in sys.modules:
        from types import ModuleType

        fake_scrolled = ModuleType("wx.lib.scrolledpanel")
        fake_scrolled.ScrolledPanel = type("ScrolledPanel", (), {})
        sys.modules["wx.lib.scrolledpanel"] = fake_scrolled

    from accessiweather.ui.dialogs.settings_dialog import SettingsDialogSimple

    return SettingsDialogSimple


def test_maybe_update_portable_bundle_uses_export_encrypted_api_keys(tmp_path, monkeypatch):
    """_maybe_update_portable_bundle_after_save delegates to export_encrypted_api_keys."""
    from accessiweather.config.secure_storage import SecureStorage

    RealClass = _get_real_settings_dialog_class()

    portable = tmp_path / "portable"
    portable.mkdir(parents=True, exist_ok=True)

    dialog = RealClass.__new__(RealClass)
    dialog.config_manager = MagicMock()
    dialog.config_manager.config_dir = portable
    dialog.config_manager.export_encrypted_api_keys = MagicMock(return_value=True)
    dialog.app = MagicMock()
    dialog.app._PORTABLE_PASSPHRASE_KEYRING_KEY = "portable_bundle_passphrase"

    # Simulate cached passphrase via SecureStorage.get_password
    monkeypatch.setattr(
        SecureStorage,
        "get_password",
        staticmethod(
            lambda key: "FAKE_CACHED_PASS" if key == "portable_bundle_passphrase" else None
        ),
    )

    dialog._maybe_update_portable_bundle_after_save(
        {
            "visual_crossing_api_key": "FAKE_VC_KEY_123",
            "pirate_weather_api_key": "FAKE_PW_KEY_123",
            "other_setting": "ignored",
        }
    )

    dialog.config_manager.export_encrypted_api_keys.assert_called_once_with(
        portable / "api-keys.keys", "FAKE_CACHED_PASS"
    )


def test_maybe_update_portable_bundle_prompts_when_no_cached_passphrase(tmp_path, monkeypatch):
    """When no cached passphrase, user is prompted; export runs on success."""
    import wx

    from accessiweather.config.secure_storage import SecureStorage

    RealClass = _get_real_settings_dialog_class()

    portable = tmp_path / "portable"
    portable.mkdir(parents=True, exist_ok=True)

    dialog = RealClass.__new__(RealClass)
    dialog.config_manager = MagicMock()
    dialog.config_manager.config_dir = portable
    dialog.config_manager.export_encrypted_api_keys = MagicMock(return_value=True)
    dialog.app = MagicMock()
    dialog.app._PORTABLE_PASSPHRASE_KEYRING_KEY = "portable_bundle_passphrase"

    # No cached passphrase
    monkeypatch.setattr(SecureStorage, "get_password", staticmethod(lambda key: None))
    set_pw_calls: list[tuple] = []
    monkeypatch.setattr(
        SecureStorage,
        "set_password",
        staticmethod(lambda key, val: set_pw_calls.append((key, val)) or True),
    )

    class _FakeTextEntryDialog:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def ShowModal(self):
            return wx.ID_OK

        def GetValue(self):
            return "FAKE_NEW_PASSPHRASE"

    monkeypatch.setattr(wx, "TextEntryDialog", _FakeTextEntryDialog, raising=False)

    dialog._maybe_update_portable_bundle_after_save({"pirate_weather_api_key": "FAKE_PW_KEY_456"})

    dialog.config_manager.export_encrypted_api_keys.assert_called_once_with(
        portable / "api-keys.keys", "FAKE_NEW_PASSPHRASE"
    )
    # Passphrase was cached for future use
    assert ("portable_bundle_passphrase", "FAKE_NEW_PASSPHRASE") in set_pw_calls


def test_maybe_update_portable_bundle_skips_when_no_key_changes(tmp_path, monkeypatch):
    """When no API keys are in settings_dict, bundle update is skipped entirely."""
    portable = tmp_path / "portable"
    portable.mkdir(parents=True, exist_ok=True)

    dialog = _make_dialog(portable)
    dialog.config_manager.export_encrypted_api_keys = MagicMock()

    dialog._maybe_update_portable_bundle_after_save({"temperature_unit": "c", "data_source": "nws"})

    dialog.config_manager.export_encrypted_api_keys.assert_not_called()
