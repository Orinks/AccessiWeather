"""Tests for Windows AppUserModelID registration at startup."""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

from accessiweather.app import (
    AccessiWeatherApp,
    _is_unc_path,
    _needs_shortcut_repair,
    _resolve_start_menu_shortcut_path,
    _run_powershell_json,
    _should_repair_shortcut,
    ensure_windows_toast_identity,
    register_app_id_in_registry,
    set_windows_app_user_model_id,
)
from accessiweather.constants import WINDOWS_APP_USER_MODEL_ID


def test_sets_app_user_model_id_on_windows_non_frozen(monkeypatch):
    shell32 = MagicMock()
    fake_ctypes = SimpleNamespace(windll=SimpleNamespace(shell32=shell32))

    monkeypatch.setattr("accessiweather.app.sys.platform", "win32")
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.setitem(sys.modules, "ctypes", fake_ctypes)

    set_windows_app_user_model_id()

    shell32.SetCurrentProcessExplicitAppUserModelID.assert_called_once_with(
        WINDOWS_APP_USER_MODEL_ID
    )


def test_sets_app_user_model_id_on_windows_frozen(monkeypatch):
    """
    Frozen builds (including portable) must also register the AppID.

    Previously this was skipped for frozen builds on the assumption the
    installer shortcut handled it — but portable builds have no installer
    shortcut, so the programmatic call is required in all cases.
    """
    shell32 = MagicMock()
    fake_ctypes = SimpleNamespace(windll=SimpleNamespace(shell32=shell32))

    monkeypatch.setattr("accessiweather.app.sys.platform", "win32")
    monkeypatch.setattr("accessiweather.app.sys.frozen", True, raising=False)
    monkeypatch.setitem(sys.modules, "ctypes", fake_ctypes)

    set_windows_app_user_model_id()

    shell32.SetCurrentProcessExplicitAppUserModelID.assert_called_once_with(
        WINDOWS_APP_USER_MODEL_ID
    )


def test_skips_app_user_model_id_on_non_windows(monkeypatch):
    monkeypatch.setattr("accessiweather.app.sys.platform", "linux")
    monkeypatch.delattr(sys, "frozen", raising=False)

    set_windows_app_user_model_id()


def test_registers_app_id_in_registry_on_windows(monkeypatch):
    create_key_context = MagicMock()
    fake_key = MagicMock()
    create_key_context.__enter__.return_value = fake_key

    fake_winreg = SimpleNamespace(
        HKEY_CURRENT_USER=object(),
        KEY_SET_VALUE=0x0002,
        REG_SZ=1,
        CreateKeyEx=MagicMock(return_value=create_key_context),
        SetValueEx=MagicMock(),
    )

    monkeypatch.setattr("accessiweather.app.sys.platform", "win32")
    monkeypatch.setitem(sys.modules, "winreg", fake_winreg)

    register_app_id_in_registry(icon_path=r"C:\apps\AccessiWeather.exe")

    fake_winreg.CreateKeyEx.assert_called_once_with(
        fake_winreg.HKEY_CURRENT_USER,
        rf"Software\Classes\AppUserModelId\{WINDOWS_APP_USER_MODEL_ID}",
        0,
        fake_winreg.KEY_SET_VALUE,
    )
    fake_winreg.SetValueEx.assert_any_call(
        fake_key, "DisplayName", 0, fake_winreg.REG_SZ, "AccessiWeather"
    )
    fake_winreg.SetValueEx.assert_any_call(
        fake_key,
        "IconUri",
        0,
        fake_winreg.REG_SZ,
        r"C:\apps\AccessiWeather.exe",
    )


def test_register_app_id_skips_registry_on_non_windows(monkeypatch):
    monkeypatch.setattr("accessiweather.app.sys.platform", "linux")
    fake_winreg = SimpleNamespace(CreateKeyEx=MagicMock(), SetValueEx=MagicMock())
    monkeypatch.setitem(sys.modules, "winreg", fake_winreg)

    register_app_id_in_registry()

    fake_winreg.CreateKeyEx.assert_not_called()
    fake_winreg.SetValueEx.assert_not_called()


def test_is_unc_path_detects_network_paths():
    assert _is_unc_path(r"\\server\share\AccessiWeather.exe") is True
    assert _is_unc_path(r"C:\Apps\AccessiWeather.exe") is False


def test_resolve_start_menu_shortcut_path_prefers_nested_installer_shortcut(tmp_path, monkeypatch):
    monkeypatch.setattr("accessiweather.app.Path.home", lambda: tmp_path)

    programs = (
        tmp_path / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    )
    nested = programs / "AccessiWeather" / "AccessiWeather.lnk"
    nested.parent.mkdir(parents=True)
    nested.write_text("lnk")

    resolved = _resolve_start_menu_shortcut_path("AccessiWeather")

    assert resolved == nested


def test_resolve_start_menu_shortcut_path_finds_recursive_candidate(tmp_path, monkeypatch):
    monkeypatch.setattr("accessiweather.app.Path.home", lambda: tmp_path)

    programs = (
        tmp_path / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    )
    deep = programs / "Utilities" / "Weather" / "AccessiWeather.lnk"
    deep.parent.mkdir(parents=True)
    deep.write_text("lnk")

    resolved = _resolve_start_menu_shortcut_path("AccessiWeather")

    assert resolved == deep


def test_needs_shortcut_repair_target_or_appid_mismatch(tmp_path):
    exe = tmp_path / "AccessiWeather.exe"
    exe.write_text("x")

    assert _needs_shortcut_repair(
        expected_target=str(exe),
        current_target=None,
        current_app_id=WINDOWS_APP_USER_MODEL_ID,
        app_id=WINDOWS_APP_USER_MODEL_ID,
    )

    assert _needs_shortcut_repair(
        expected_target=str(exe),
        current_target=str(tmp_path / "other.exe"),
        current_app_id=WINDOWS_APP_USER_MODEL_ID,
        app_id=WINDOWS_APP_USER_MODEL_ID,
    )

    assert _needs_shortcut_repair(
        expected_target=str(exe),
        current_target=str(exe),
        current_app_id="Wrong.AppId",
        app_id=WINDOWS_APP_USER_MODEL_ID,
    )

    assert not _needs_shortcut_repair(
        expected_target=str(exe),
        current_target=str(exe),
        current_app_id=WINDOWS_APP_USER_MODEL_ID,
        app_id=WINDOWS_APP_USER_MODEL_ID,
    )


def test_should_repair_shortcut_cache_logic(tmp_path):
    shortcut = tmp_path / "AccessiWeather" / "AccessiWeather.lnk"
    shortcut.parent.mkdir(parents=True)
    shortcut.write_text("x")
    exe = r"C:\Apps\AccessiWeather.exe"
    version = "1.2.3"

    good_stamp = {
        "verified": True,
        "exe_path": exe,
        "app_version": version,
        "shortcut_path": str(shortcut),
    }
    assert not _should_repair_shortcut(
        stamp=good_stamp,
        shortcut_path=shortcut,
        exe_path=exe,
        app_version=version,
    )

    assert _should_repair_shortcut(
        stamp={**good_stamp, "verified": False},
        shortcut_path=shortcut,
        exe_path=exe,
        app_version=version,
    )
    assert _should_repair_shortcut(
        stamp={**good_stamp, "exe_path": r"C:\Other.exe"},
        shortcut_path=shortcut,
        exe_path=exe,
        app_version=version,
    )
    assert _should_repair_shortcut(
        stamp={**good_stamp, "app_version": "2.0.0"},
        shortcut_path=shortcut,
        exe_path=exe,
        app_version=version,
    )


def test_ensure_windows_toast_identity_verification_success_writes_stamp(monkeypatch, tmp_path):
    monkeypatch.setattr("accessiweather.app._TOAST_IDENTITY_ENSURED_THIS_STARTUP", False)
    monkeypatch.setattr("accessiweather.app.sys.platform", "win32")
    monkeypatch.setattr("accessiweather.app.sys.executable", str(tmp_path / "AccessiWeather.exe"))
    monkeypatch.setattr("accessiweather.app.Path.home", lambda: tmp_path)
    monkeypatch.setattr("accessiweather.app.register_app_id_in_registry", MagicMock())
    monkeypatch.setattr("accessiweather.app.set_windows_app_user_model_id", MagicMock())

    written: list[dict] = []
    monkeypatch.setattr("accessiweather.app._load_toast_identity_stamp", lambda _: None)
    monkeypatch.setattr(
        "accessiweather.app._write_toast_identity_stamp", lambda **kwargs: written.append(kwargs)
    )
    monkeypatch.setattr(
        "accessiweather.app._run_powershell_json",
        lambda *_args, **_kwargs: {
            "shortcut_path": str(
                tmp_path
                / "AppData"
                / "Roaming"
                / "Microsoft"
                / "Windows"
                / "Start Menu"
                / "Programs"
                / "AccessiWeather"
                / "AccessiWeather.lnk"
            ),
            "verified": True,
            "readback_app_id": WINDOWS_APP_USER_MODEL_ID,
            "shortcut_exists": True,
            "repaired": True,
        },
    )

    ensure_windows_toast_identity()

    assert written and written[0]["verified"] is True
    assert written[0]["readback_app_id"] == WINDOWS_APP_USER_MODEL_ID


def test_ensure_windows_toast_identity_verification_failure_writes_failed_stamp(
    monkeypatch, tmp_path
):
    monkeypatch.setattr("accessiweather.app._TOAST_IDENTITY_ENSURED_THIS_STARTUP", False)
    monkeypatch.setattr("accessiweather.app.sys.platform", "win32")
    monkeypatch.setattr("accessiweather.app.sys.executable", str(tmp_path / "AccessiWeather.exe"))
    monkeypatch.setattr("accessiweather.app.Path.home", lambda: tmp_path)
    monkeypatch.setattr("accessiweather.app.register_app_id_in_registry", MagicMock())
    monkeypatch.setattr("accessiweather.app.set_windows_app_user_model_id", MagicMock())

    written: list[dict] = []
    monkeypatch.setattr("accessiweather.app._load_toast_identity_stamp", lambda _: None)
    monkeypatch.setattr(
        "accessiweather.app._write_toast_identity_stamp", lambda **kwargs: written.append(kwargs)
    )
    monkeypatch.setattr(
        "accessiweather.app._run_powershell_json",
        lambda *_args, **_kwargs: {
            "shortcut_path": str(tmp_path / "bad.lnk"),
            "verified": False,
            "readback_app_id": "Wrong.AppId",
            "shortcut_exists": True,
            "repaired": True,
        },
    )

    ensure_windows_toast_identity()

    assert written and written[0]["verified"] is False
    assert written[0]["readback_app_id"] == "Wrong.AppId"


def test_ensure_windows_toast_identity_skips_non_windows(monkeypatch):
    monkeypatch.setattr("accessiweather.app._TOAST_IDENTITY_ENSURED_THIS_STARTUP", False)
    reg = MagicMock()
    set_id = MagicMock()

    monkeypatch.setattr("accessiweather.app.sys.platform", "linux")
    monkeypatch.setattr("accessiweather.app.register_app_id_in_registry", reg)
    monkeypatch.setattr("accessiweather.app.set_windows_app_user_model_id", set_id)

    ensure_windows_toast_identity()

    reg.assert_not_called()
    set_id.assert_not_called()


def test_run_powershell_json_uses_hidden_window_flags_on_windows(monkeypatch):
    monkeypatch.setattr("accessiweather.app.sys.platform", "win32")
    monkeypatch.setattr("accessiweather.app.os", SimpleNamespace(name="nt"))

    class _StartupInfo:
        def __init__(self):
            self.dwFlags = 0
            self.wShowWindow = None

    fake_run = MagicMock(
        return_value=SimpleNamespace(returncode=0, stdout='{"ok":true}', stderr="")
    )

    monkeypatch.setattr("accessiweather.app.subprocess.STARTUPINFO", _StartupInfo, raising=False)
    monkeypatch.setattr("accessiweather.app.subprocess.STARTF_USESHOWWINDOW", 0x1, raising=False)
    monkeypatch.setattr("accessiweather.app.subprocess.SW_HIDE", 0, raising=False)
    monkeypatch.setattr("accessiweather.app.subprocess.CREATE_NO_WINDOW", 0x08000000, raising=False)
    monkeypatch.setattr("accessiweather.app.subprocess.run", fake_run)

    payload = _run_powershell_json("$state = @{ok=$true}; $state | ConvertTo-Json -Compress")

    assert payload == {"ok": True}
    kwargs = fake_run.call_args.kwargs
    assert kwargs["creationflags"] == 0x08000000
    assert kwargs["startupinfo"].dwFlags & 0x1
    assert kwargs["startupinfo"].wShowWindow == 0


def test_ensure_windows_toast_identity_runs_repair_only_once_per_startup(monkeypatch, tmp_path):
    monkeypatch.setattr("accessiweather.app.sys.platform", "win32")
    monkeypatch.setattr("accessiweather.app.sys.executable", str(tmp_path / "AccessiWeather.exe"))
    monkeypatch.setattr("accessiweather.app.Path.home", lambda: tmp_path)
    monkeypatch.setattr("accessiweather.app.register_app_id_in_registry", MagicMock())
    monkeypatch.setattr("accessiweather.app.set_windows_app_user_model_id", MagicMock())
    monkeypatch.setattr("accessiweather.app._TOAST_IDENTITY_ENSURED_THIS_STARTUP", False)
    monkeypatch.setattr("accessiweather.app._load_toast_identity_stamp", lambda _: None)

    run_mock = MagicMock(
        return_value={
            "shortcut_path": str(tmp_path / "AccessiWeather.lnk"),
            "verified": True,
            "readback_app_id": WINDOWS_APP_USER_MODEL_ID,
            "shortcut_exists": True,
            "repaired": True,
        }
    )
    monkeypatch.setattr("accessiweather.app._run_powershell_json", run_mock)

    ensure_windows_toast_identity()
    ensure_windows_toast_identity()

    # Primary repair script should only execute once in a process startup.
    assert run_mock.call_count == 1


def test_request_exit_does_not_use_blocking_sound_in_frozen_build(monkeypatch):
    app = AccessiWeatherApp.__new__(AccessiWeatherApp)
    app._update_timer = None
    app.config_manager = SimpleNamespace(
        get_settings=lambda: SimpleNamespace(sound_enabled=True, sound_pack="default")
    )
    app.tray_icon = None
    app.single_instance_manager = None
    app._async_loop = None
    app.main_window = None
    app.ExitMainLoop = MagicMock()

    mock_play_exit_sound = MagicMock()
    mock_play_exit_sound_blocking = MagicMock()

    monkeypatch.setattr("accessiweather.app.sys.frozen", True, raising=False)
    monkeypatch.setattr(
        "accessiweather.notifications.sound_player.play_exit_sound",
        mock_play_exit_sound,
    )
    monkeypatch.setattr(
        "accessiweather.notifications.sound_player.play_exit_sound_blocking",
        mock_play_exit_sound_blocking,
    )

    app.request_exit()

    mock_play_exit_sound.assert_called_once_with("default")
    mock_play_exit_sound_blocking.assert_not_called()
    app.ExitMainLoop.assert_called_once()
