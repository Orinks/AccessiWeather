"""Tests for Windows AppUserModelID registration at startup."""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

from accessiweather.app import set_windows_app_user_model_id
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


def test_skips_app_user_model_id_on_windows_frozen(monkeypatch):
    shell32 = MagicMock()
    fake_ctypes = SimpleNamespace(windll=SimpleNamespace(shell32=shell32))

    monkeypatch.setattr("accessiweather.app.sys.platform", "win32")
    monkeypatch.setattr("accessiweather.app.sys.frozen", True, raising=False)
    monkeypatch.setitem(sys.modules, "ctypes", fake_ctypes)

    set_windows_app_user_model_id()

    shell32.SetCurrentProcessExplicitAppUserModelID.assert_not_called()


def test_skips_app_user_model_id_on_non_windows(monkeypatch):
    monkeypatch.setattr("accessiweather.app.sys.platform", "linux")
    monkeypatch.delattr(sys, "frozen", raising=False)

    set_windows_app_user_model_id()
