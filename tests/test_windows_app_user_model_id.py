"""Tests for Windows AppUserModelID registration at startup."""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

from accessiweather.app import register_app_id_in_registry, set_windows_app_user_model_id
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
