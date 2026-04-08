"""Tests for Windows AppUserModelID registration at startup."""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

from accessiweather.app import AccessiWeatherApp
from accessiweather.constants import WINDOWS_APP_USER_MODEL_ID
from accessiweather.windows_toast_identity import (
    WINDOWS_TOAST_ACTIVATOR_CLSID,
    WINDOWS_TOAST_PROTOCOL_SCHEME,
    _build_protocol_handler_command,
    _is_unc_path,
    _load_toast_identity_stamp,
    _needs_shortcut_repair,
    _normalize_clsid,
    _register_protocol_activation_handler,
    _resolve_notification_launch_command,
    _resolve_start_menu_shortcut_path,
    _run_powershell_json,
    _should_repair_shortcut,
    _write_toast_identity_stamp,
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


def test_normalize_clsid_accepts_valid_guid_and_rejects_invalid():
    assert _normalize_clsid("0d3c3f8e-7303-4c9b-81c7-ff8d8c1afc07") == WINDOWS_TOAST_ACTIVATOR_CLSID
    assert _normalize_clsid("not-a-guid") is None
    assert _normalize_clsid(None) is None


def test_resolve_notification_launch_command_prefers_frozen_executable(monkeypatch, tmp_path):
    exe_path = tmp_path / "AccessiWeather.exe"
    monkeypatch.setattr("accessiweather.windows_toast_identity.sys.frozen", True, raising=False)
    monkeypatch.setattr("accessiweather.windows_toast_identity.sys.executable", str(exe_path))

    assert _resolve_notification_launch_command() == [str(exe_path.resolve())]


def test_resolve_notification_launch_command_prefers_module_launch(monkeypatch, tmp_path):
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.setattr(
        "accessiweather.windows_toast_identity.sys.executable", str(tmp_path / "python")
    )
    monkeypatch.setattr(
        "accessiweather.windows_toast_identity.importlib.util.find_spec",
        lambda name: object() if name == "accessiweather" else None,
    )

    assert _resolve_notification_launch_command() == [
        str((tmp_path / "python").resolve()),
        "-m",
        "accessiweather",
    ]


def test_resolve_notification_launch_command_falls_back_to_script_path(monkeypatch, tmp_path):
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.setattr(
        "accessiweather.windows_toast_identity.sys.executable", str(tmp_path / "python")
    )
    monkeypatch.setattr(
        "accessiweather.windows_toast_identity.sys.argv", [str(tmp_path / "launcher.py")]
    )
    monkeypatch.setattr(
        "accessiweather.windows_toast_identity.importlib.util.find_spec", lambda _name: None
    )

    assert _resolve_notification_launch_command() == [
        str((tmp_path / "python").resolve()),
        str((tmp_path / "launcher.py").resolve()),
    ]


def test_resolve_notification_launch_command_falls_back_to_executable_when_argv_empty(
    monkeypatch, tmp_path
):
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.setattr(
        "accessiweather.windows_toast_identity.sys.executable", str(tmp_path / "python")
    )
    monkeypatch.setattr("accessiweather.windows_toast_identity.sys.argv", [])
    monkeypatch.setattr(
        "accessiweather.windows_toast_identity.importlib.util.find_spec", lambda _name: None
    )

    assert _resolve_notification_launch_command() == [str((tmp_path / "python").resolve())]


def test_build_protocol_handler_command_quotes_protocol_argument(monkeypatch):
    monkeypatch.setattr(
        "accessiweather.windows_toast_identity._resolve_notification_launch_command",
        lambda: [r"C:\Program Files\AccessiWeather\AccessiWeather.exe"],
    )

    command = _build_protocol_handler_command()

    assert '"C:\\Program Files\\AccessiWeather\\AccessiWeather.exe"' in command
    assert "%1" in command


def test_register_protocol_activation_handler_returns_false_off_windows(monkeypatch):
    monkeypatch.setattr("accessiweather.windows_toast_identity.sys.platform", "linux")

    assert _register_protocol_activation_handler() is False


def test_register_protocol_activation_handler_returns_false_without_winreg(monkeypatch):
    monkeypatch.setattr("accessiweather.windows_toast_identity.sys.platform", "win32")
    original_import = __import__

    def _fake_import(name, *args, **kwargs):
        if name == "winreg":
            raise ImportError("no winreg")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", _fake_import)

    assert _register_protocol_activation_handler() is False


def test_register_protocol_activation_handler_writes_expected_registry_keys(monkeypatch):
    monkeypatch.setattr("accessiweather.windows_toast_identity.sys.platform", "win32")
    monkeypatch.setattr(
        "accessiweather.windows_toast_identity._resolve_notification_launch_command",
        lambda: [r"C:\AccessiWeather\AccessiWeather.exe"],
    )
    monkeypatch.setattr(
        "accessiweather.windows_toast_identity._build_protocol_handler_command",
        lambda protocol_argument="%1": (
            f'"C:\\AccessiWeather\\AccessiWeather.exe" "{protocol_argument}"'
        ),
    )

    writes: list[tuple[str, str | None, str]] = []

    class _Key:
        def __init__(self, path: str):
            self.path = path

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    fake_winreg = SimpleNamespace(
        HKEY_CURRENT_USER="HKCU",
        REG_SZ="REG_SZ",
        CreateKey=lambda hive, path: _Key(path),
        SetValueEx=lambda key, name, _reserved, _reg_type, value: writes.append(
            (key.path, name, value)
        ),
    )
    monkeypatch.setitem(sys.modules, "winreg", fake_winreg)

    assert _register_protocol_activation_handler() is True
    assert (
        rf"Software\Classes\{WINDOWS_TOAST_PROTOCOL_SCHEME}",
        None,
        "URL:AccessiWeather Toast",
    ) in writes
    assert (rf"Software\Classes\{WINDOWS_TOAST_PROTOCOL_SCHEME}", "URL Protocol", "") in writes
    assert (
        rf"Software\Classes\{WINDOWS_TOAST_PROTOCOL_SCHEME}\shell\open\command",
        None,
        '"C:\\AccessiWeather\\AccessiWeather.exe" "%1"',
    ) in writes


def test_register_protocol_activation_handler_returns_false_when_registry_write_fails(monkeypatch):
    monkeypatch.setattr("accessiweather.windows_toast_identity.sys.platform", "win32")
    monkeypatch.setattr(
        "accessiweather.windows_toast_identity._resolve_notification_launch_command",
        lambda: [r"C:\AccessiWeather\AccessiWeather.exe"],
    )

    class _Key:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    fake_winreg = SimpleNamespace(
        HKEY_CURRENT_USER="HKCU",
        REG_SZ="REG_SZ",
        CreateKey=lambda hive, path: _Key(),
        SetValueEx=lambda *args, **kwargs: (_ for _ in ()).throw(OSError("registry write failed")),
    )
    monkeypatch.setitem(sys.modules, "winreg", fake_winreg)

    assert _register_protocol_activation_handler() is False


def test_write_toast_identity_stamp_persists_protocol_and_normalized_clsid(tmp_path):
    stamp_path = tmp_path / "toast_identity_stamp.json"
    shortcut_path = tmp_path / "AccessiWeather.lnk"

    _write_toast_identity_stamp(
        stamp_path=stamp_path,
        shortcut_path=shortcut_path,
        exe_path=r"C:\AccessiWeather\AccessiWeather.exe",
        app_version="1.2.3",
        verified=True,
        readback_app_id=WINDOWS_TOAST_PROTOCOL_SCHEME,
        toast_activator_clsid="0d3c3f8e-7303-4c9b-81c7-ff8d8c1afc07",
        protocol_handler_registered=True,
    )

    payload = _load_toast_identity_stamp(stamp_path)
    assert payload is not None
    assert payload["toast_activator_clsid"] == WINDOWS_TOAST_ACTIVATOR_CLSID
    assert payload["protocol_handler_registered"] is True


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
        "schema_version": 2,
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
            "schema_version": 2,
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


def test_ensure_windows_toast_identity_sets_toast_activator_and_protocol_handler(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(
        "accessiweather.windows_toast_identity._TOAST_IDENTITY_ENSURED_THIS_STARTUP", False
    )
    monkeypatch.setattr("accessiweather.windows_toast_identity.sys.platform", "win32")
    exe_path = tmp_path / "AccessiWeather.exe"
    monkeypatch.setattr("accessiweather.windows_toast_identity.sys.executable", str(exe_path))
    monkeypatch.setattr("accessiweather.windows_toast_identity.Path.home", lambda: tmp_path)
    monkeypatch.setattr(
        "accessiweather.windows_toast_identity.set_windows_app_user_model_id", MagicMock()
    )
    monkeypatch.setattr(
        "accessiweather.windows_toast_identity._load_toast_identity_stamp", lambda _: None
    )
    monkeypatch.setattr("accessiweather.windows_toast_identity._ole32", MagicMock())
    monkeypatch.setattr("accessiweather.windows_toast_identity._shell32", MagicMock())

    shortcut_path = (
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
    shortcut_path.parent.mkdir(parents=True)
    shortcut_path.write_text("lnk")

    monkeypatch.setattr(
        "accessiweather.windows_toast_identity._resolve_start_menu_shortcut_path",
        lambda _display_name: shortcut_path,
    )
    monkeypatch.setattr(
        "accessiweather.windows_toast_identity._read_shortcut_target_wscript",
        lambda _shortcut_path: str(exe_path),
    )
    monkeypatch.setattr(
        "accessiweather.windows_toast_identity._read_shortcut_app_id",
        lambda _shortcut_path: WINDOWS_APP_USER_MODEL_ID,
    )
    activator_reads = iter([None, WINDOWS_TOAST_ACTIVATOR_CLSID])
    monkeypatch.setattr(
        "accessiweather.windows_toast_identity._read_shortcut_toast_activator_clsid",
        lambda _shortcut_path: next(activator_reads),
    )

    set_clsid = MagicMock(return_value=True)
    register_protocol = MagicMock(return_value=True)
    written: list[dict] = []
    monkeypatch.setattr(
        "accessiweather.windows_toast_identity._set_shortcut_toast_activator_clsid",
        set_clsid,
    )
    monkeypatch.setattr(
        "accessiweather.windows_toast_identity._register_protocol_activation_handler",
        register_protocol,
    )
    monkeypatch.setattr(
        "accessiweather.windows_toast_identity._write_toast_identity_stamp",
        lambda **kwargs: written.append(kwargs),
    )

    ensure_windows_toast_identity()

    set_clsid.assert_called_once_with(shortcut_path, WINDOWS_TOAST_ACTIVATOR_CLSID)
    register_protocol.assert_called_once()
    assert written and written[0]["verified"] is True


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
