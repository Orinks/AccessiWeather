"""Tests for Windows AppUserModelID registration at startup."""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

from accessiweather.app import AccessiWeatherApp
from accessiweather.constants import WINDOWS_APP_USER_MODEL_ID
from accessiweather.windows_toast_identity import (
    _is_unc_path,
    _load_toast_identity_stamp,
    _needs_shortcut_repair,
    _resolve_start_menu_shortcut_path,
    _run_powershell_json,
    _should_repair_shortcut,
    ensure_windows_toast_identity,
    set_windows_app_user_model_id,
)


def test_sets_app_user_model_id_on_windows_non_frozen(monkeypatch):
    shell32 = MagicMock()
    fake_ctypes = SimpleNamespace(windll=SimpleNamespace(shell32=shell32))

    monkeypatch.setattr("accessiweather.windows_toast_identity.sys.platform", "win32")
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

    monkeypatch.setattr("accessiweather.windows_toast_identity.sys.platform", "win32")
    monkeypatch.setattr("accessiweather.app.sys.frozen", True, raising=False)
    monkeypatch.setitem(sys.modules, "ctypes", fake_ctypes)

    set_windows_app_user_model_id()

    shell32.SetCurrentProcessExplicitAppUserModelID.assert_called_once_with(
        WINDOWS_APP_USER_MODEL_ID
    )


def test_skips_app_user_model_id_on_non_windows(monkeypatch):
    monkeypatch.setattr("accessiweather.windows_toast_identity.sys.platform", "linux")
    monkeypatch.delattr(sys, "frozen", raising=False)

    set_windows_app_user_model_id()


def test_is_unc_path_detects_network_paths():
    assert _is_unc_path(r"\\server\share\AccessiWeather.exe") is True
    assert _is_unc_path(r"C:\Apps\AccessiWeather.exe") is False


def test_resolve_start_menu_shortcut_path_prefers_nested_installer_shortcut(tmp_path, monkeypatch):
    monkeypatch.setattr("accessiweather.windows_toast_identity.Path.home", lambda: tmp_path)

    programs = (
        tmp_path / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    )
    nested = programs / "AccessiWeather" / "AccessiWeather.lnk"
    nested.parent.mkdir(parents=True)
    nested.write_text("lnk")

    resolved = _resolve_start_menu_shortcut_path("AccessiWeather")

    assert resolved == nested


def test_resolve_start_menu_shortcut_path_finds_recursive_candidate(tmp_path, monkeypatch):
    monkeypatch.setattr("accessiweather.windows_toast_identity.Path.home", lambda: tmp_path)

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
    monkeypatch.setattr(
        "accessiweather.windows_toast_identity._TOAST_IDENTITY_ENSURED_THIS_STARTUP", False
    )
    monkeypatch.setattr("accessiweather.windows_toast_identity.sys.platform", "win32")
    monkeypatch.setattr(
        "accessiweather.windows_toast_identity.sys.executable", str(tmp_path / "AccessiWeather.exe")
    )
    monkeypatch.setattr("accessiweather.windows_toast_identity.Path.home", lambda: tmp_path)
    monkeypatch.setattr(
        "accessiweather.windows_toast_identity.set_windows_app_user_model_id", MagicMock()
    )

    written: list[dict] = []
    monkeypatch.setattr(
        "accessiweather.windows_toast_identity._load_toast_identity_stamp", lambda _: None
    )
    monkeypatch.setattr(
        "accessiweather.windows_toast_identity._write_toast_identity_stamp",
        lambda **kwargs: written.append(kwargs),
    )
    monkeypatch.setattr(
        "accessiweather.windows_toast_identity._run_powershell_json",
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
    monkeypatch.setattr(
        "accessiweather.windows_toast_identity._TOAST_IDENTITY_ENSURED_THIS_STARTUP", False
    )
    monkeypatch.setattr("accessiweather.windows_toast_identity.sys.platform", "win32")
    monkeypatch.setattr(
        "accessiweather.windows_toast_identity.sys.executable", str(tmp_path / "AccessiWeather.exe")
    )
    monkeypatch.setattr("accessiweather.windows_toast_identity.Path.home", lambda: tmp_path)
    monkeypatch.setattr(
        "accessiweather.windows_toast_identity.set_windows_app_user_model_id", MagicMock()
    )

    written: list[dict] = []
    monkeypatch.setattr(
        "accessiweather.windows_toast_identity._load_toast_identity_stamp", lambda _: None
    )
    monkeypatch.setattr(
        "accessiweather.windows_toast_identity._write_toast_identity_stamp",
        lambda **kwargs: written.append(kwargs),
    )
    monkeypatch.setattr(
        "accessiweather.windows_toast_identity._run_powershell_json",
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
    monkeypatch.setattr(
        "accessiweather.windows_toast_identity._TOAST_IDENTITY_ENSURED_THIS_STARTUP", False
    )
    set_id = MagicMock()

    monkeypatch.setattr("accessiweather.windows_toast_identity.sys.platform", "linux")
    monkeypatch.setattr(
        "accessiweather.windows_toast_identity.set_windows_app_user_model_id", set_id
    )

    ensure_windows_toast_identity()

    set_id.assert_not_called()


def test_run_powershell_json_uses_hidden_window_flags_on_windows(monkeypatch):
    monkeypatch.setattr("accessiweather.windows_toast_identity.sys.platform", "win32")
    monkeypatch.setattr("accessiweather.windows_toast_identity.os", SimpleNamespace(name="nt"))

    class _StartupInfo:
        def __init__(self):
            self.dwFlags = 0
            self.wShowWindow = None

    fake_run = MagicMock(
        return_value=SimpleNamespace(returncode=0, stdout='{"ok":true}', stderr="")
    )

    monkeypatch.setattr(
        "accessiweather.windows_toast_identity.subprocess.STARTUPINFO", _StartupInfo, raising=False
    )
    monkeypatch.setattr(
        "accessiweather.windows_toast_identity.subprocess.STARTF_USESHOWWINDOW", 0x1, raising=False
    )
    monkeypatch.setattr(
        "accessiweather.windows_toast_identity.subprocess.SW_HIDE", 0, raising=False
    )
    monkeypatch.setattr(
        "accessiweather.windows_toast_identity.subprocess.CREATE_NO_WINDOW",
        0x08000000,
        raising=False,
    )
    monkeypatch.setattr("accessiweather.windows_toast_identity.subprocess.run", fake_run)

    payload = _run_powershell_json("$state = @{ok=$true}; $state | ConvertTo-Json -Compress")

    assert payload == {"ok": True}
    kwargs = fake_run.call_args.kwargs
    assert kwargs["creationflags"] == 0x08000000
    assert kwargs["startupinfo"].dwFlags & 0x1
    assert kwargs["startupinfo"].wShowWindow == 0


def test_run_powershell_json_passes_named_args_and_empty_stdout_returns_empty_dict(monkeypatch):
    monkeypatch.setattr("accessiweather.windows_toast_identity.sys.platform", "win32")
    monkeypatch.setattr("accessiweather.windows_toast_identity.os", SimpleNamespace(name="posix"))

    fake_run = MagicMock(return_value=SimpleNamespace(returncode=0, stdout="", stderr=""))
    monkeypatch.setattr("accessiweather.windows_toast_identity.subprocess.run", fake_run)

    payload = _run_powershell_json("Write-Output ''", ShortcutPath="C:/x.lnk")

    assert payload == {}
    called_cmd = fake_run.call_args.args[0]
    assert "-ShortcutPath" in called_cmd
    assert "C:/x.lnk" in called_cmd


def test_run_powershell_json_raises_on_nonzero_exit(monkeypatch):
    monkeypatch.setattr("accessiweather.windows_toast_identity.sys.platform", "win32")
    monkeypatch.setattr("accessiweather.windows_toast_identity.os", SimpleNamespace(name="posix"))

    fake_run = MagicMock(return_value=SimpleNamespace(returncode=7, stdout="", stderr="boom"))
    monkeypatch.setattr("accessiweather.windows_toast_identity.subprocess.run", fake_run)

    import pytest

    with pytest.raises(RuntimeError, match="boom"):
        _run_powershell_json("Write-Error boom")


def test_ensure_windows_toast_identity_runs_repair_only_once_per_startup(monkeypatch, tmp_path):
    monkeypatch.setattr("accessiweather.windows_toast_identity.sys.platform", "win32")
    monkeypatch.setattr(
        "accessiweather.windows_toast_identity.sys.executable", str(tmp_path / "AccessiWeather.exe")
    )
    monkeypatch.setattr("accessiweather.windows_toast_identity.Path.home", lambda: tmp_path)
    monkeypatch.setattr(
        "accessiweather.windows_toast_identity.set_windows_app_user_model_id", MagicMock()
    )
    monkeypatch.setattr(
        "accessiweather.windows_toast_identity._TOAST_IDENTITY_ENSURED_THIS_STARTUP", False
    )
    monkeypatch.setattr(
        "accessiweather.windows_toast_identity._load_toast_identity_stamp", lambda _: None
    )

    run_mock = MagicMock(
        return_value={
            "shortcut_path": str(tmp_path / "AccessiWeather.lnk"),
            "verified": True,
            "readback_app_id": WINDOWS_APP_USER_MODEL_ID,
            "shortcut_exists": True,
            "repaired": True,
        }
    )
    monkeypatch.setattr("accessiweather.windows_toast_identity._run_powershell_json", run_mock)

    ensure_windows_toast_identity()
    ensure_windows_toast_identity()

    # Primary repair script should only execute once in a process startup.
    assert run_mock.call_count == 1


def test_load_toast_identity_stamp_invalid_payload_returns_none(tmp_path):
    stamp = tmp_path / "toast_identity_stamp.json"
    stamp.write_text("[]", encoding="utf-8")

    assert _load_toast_identity_stamp(stamp) is None


def test_load_toast_identity_stamp_bad_json_returns_none(tmp_path):
    stamp = tmp_path / "toast_identity_stamp.json"
    stamp.write_text("{not json", encoding="utf-8")

    assert _load_toast_identity_stamp(stamp) is None


def test_ensure_windows_toast_identity_skips_repair_when_stamp_valid(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "accessiweather.windows_toast_identity._TOAST_IDENTITY_ENSURED_THIS_STARTUP", False
    )
    monkeypatch.setattr("accessiweather.windows_toast_identity.sys.platform", "win32")
    monkeypatch.setattr(
        "accessiweather.windows_toast_identity.sys.executable", str(tmp_path / "AccessiWeather.exe")
    )
    monkeypatch.setattr("accessiweather.windows_toast_identity.Path.home", lambda: tmp_path)
    monkeypatch.setattr(
        "accessiweather.windows_toast_identity.set_windows_app_user_model_id", MagicMock()
    )

    shortcut = (
        tmp_path
        / "AppData"
        / "Roaming"
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / "AccessiWeather"
        / "AccessiWeather.lnk"
    )
    shortcut.parent.mkdir(parents=True)
    shortcut.write_text("lnk")

    monkeypatch.setattr(
        "accessiweather.windows_toast_identity._load_toast_identity_stamp",
        lambda _p: {
            "verified": True,
            "exe_path": str(tmp_path / "AccessiWeather.exe"),
            "app_version": "1.0.0",
            "shortcut_path": str(shortcut),
        },
    )
    monkeypatch.setattr("accessiweather.__version__", "1.0.0")
    run_mock = MagicMock()
    monkeypatch.setattr("accessiweather.windows_toast_identity._run_powershell_json", run_mock)

    ensure_windows_toast_identity()

    assert run_mock.call_count == 0


def test_accessiweather_app_init_falls_back_when_portable_detection_errors(monkeypatch):
    monkeypatch.setattr(
        "accessiweather.app.detect_portable_mode", MagicMock(side_effect=RuntimeError("oops"))
    )
    init_mock = MagicMock(return_value=None)
    monkeypatch.setattr("wx.App.__init__", init_mock)

    app = AccessiWeatherApp(config_dir=None, portable_mode=False)

    assert app._portable_mode is False


def test_request_exit_does_not_use_blocking_sound_in_frozen_build(monkeypatch):
    app = AccessiWeatherApp.__new__(AccessiWeatherApp)
    app._update_timer = None
    app.config_manager = SimpleNamespace(
        get_settings=lambda: SimpleNamespace(
            sound_enabled=True, sound_pack="default", muted_sound_events=[]
        )
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

    mock_play_exit_sound.assert_called_once_with("default", muted_events=[])
    mock_play_exit_sound_blocking.assert_not_called()
    app.ExitMainLoop.assert_called_once()
