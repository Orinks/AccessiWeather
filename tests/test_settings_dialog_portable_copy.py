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
        "OK": 0,
        "YES_NO": 0,
        "ICON_QUESTION": 0,
        "ICON_INFORMATION": 0,
        "ICON_WARNING": 0,
        "ICON_ERROR": 0,
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


def test_copy_installed_config_to_portable_success_reloads_and_mentions_keyring(
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
    calls: list[tuple] = []

    def _fake_message_box(message, title, style):
        calls.append((message, title, style))
        if title == "Copy installed config to portable":
            return module.wx.YES
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

    final_message = calls[-1][0]
    assert calls[-1][1] == "Copy complete"
    assert "• accessiweather.json" in final_message
    assert "cache.db" not in final_message
    assert "API keys are stored in your system keyring" in final_message
    assert "Please re-enter your API keys in Settings." in final_message


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
    dialog.config_manager.save_config.assert_not_called()
