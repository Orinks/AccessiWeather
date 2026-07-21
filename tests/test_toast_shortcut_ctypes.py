"""
Live round-trip test for the raw ctypes IShellLinkW shortcut fallback.

The ctypes path in windows_toast_identity_shortcuts previously used wrong
IShellLinkW vtable slots (SetDescription=8, SetWorkingDirectory=10,
SetIconLocation=18 — those are actually GetWorkingDirectory, GetArguments,
and SetRelativePath). Calling GetArguments with SetWorkingDirectory's
signature raised E_INVALIDARG, so the fallback always failed when pywin32
was unavailable.

These tests create a real .lnk through the ctypes path and read every field
back through the independent WScript.Shell COM object, so a future slot
mix-up fails loudly. Windows-only by nature.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows COM only")


@pytest.fixture
def com_initialized():
    import ctypes

    # Match production: ensure_windows_toast_identity calls CoInitialize
    # before any shortcut helper runs.
    ctypes.windll.ole32.CoInitialize(None)
    return True


def _read_back(lnk_path: Path):
    win32com_client = pytest.importorskip("win32com.client")
    shell = win32com_client.Dispatch("WScript.Shell")
    return shell.CreateShortcut(str(lnk_path))


def test_ishelllinkw_vtable_slots_match_shobjidl_order():
    from accessiweather import windows_toast_identity_shortcuts as mod

    # shobjidl_core.h method order after the 3 IUnknown slots.
    assert mod._ISHELLLINKW_VTBL_GET_PATH == 3
    assert mod._ISHELLLINKW_VTBL_SET_DESCRIPTION == 7
    assert mod._ISHELLLINKW_VTBL_SET_WORKING_DIRECTORY == 9
    assert mod._ISHELLLINKW_VTBL_SET_ICON_LOCATION == 17
    assert mod._ISHELLLINKW_VTBL_SET_PATH == 20


def test_ctypes_shortcut_round_trip(tmp_path, com_initialized):
    from accessiweather.windows_toast_identity_shortcuts import _create_shortcut_ctypes

    lnk = tmp_path / "AccessiWeather.lnk"
    target = r"C:\Windows\System32\notepad.exe"

    assert _create_shortcut_ctypes(lnk, target, "AccessiWeather") is True
    assert lnk.exists()

    shortcut = _read_back(lnk)
    assert shortcut.TargetPath.lower() == target.lower()
    assert shortcut.WorkingDirectory.lower() == str(Path(target).parent).lower()
    assert shortcut.Description == "AccessiWeather"
    assert shortcut.IconLocation.lower() == f"{target},0".lower()


def test_ctypes_shortcut_target_readable_by_ctypes_reader(tmp_path, com_initialized):
    from accessiweather.windows_toast_identity_shortcuts import (
        _create_shortcut_ctypes,
        _read_shortcut_target_ctypes,
    )

    lnk = tmp_path / "ReadBack.lnk"
    target = r"C:\Windows\System32\notepad.exe"

    assert _create_shortcut_ctypes(lnk, target, "ReadBack") is True
    read_target = _read_shortcut_target_ctypes(lnk)
    assert read_target is not None
    assert read_target.lower() == target.lower()
