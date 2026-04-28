"""Tests for soundpack path resolution in source vs packaged runs."""

from __future__ import annotations

import sys
from unittest.mock import patch

from accessiweather import soundpack_paths


def test_get_soundpacks_dir_frozen_meipass(tmp_path):
    """Frozen builds should prefer sys._MEIPASS for bundled soundpacks."""
    with (
        patch.object(sys, "frozen", True, create=True),
        patch.object(sys, "_MEIPASS", str(tmp_path), create=True),
        patch.object(sys, "executable", str(tmp_path / "AccessiWeather.exe"), create=True),
    ):
        result = soundpack_paths.get_soundpacks_dir()

    assert result == tmp_path / "soundpacks"


def test_get_soundpacks_dir_frozen_without_meipass(tmp_path):
    """Frozen builds without _MEIPASS should fall back to executable parent."""
    exe_path = tmp_path / "AccessiWeather.exe"
    with (
        patch.object(sys, "frozen", True, create=True),
        patch.object(sys, "executable", str(exe_path), create=True),
        patch.dict(sys.__dict__, {"_MEIPASS": None}, clear=False),
    ):
        del sys.__dict__["_MEIPASS"]
        result = soundpack_paths.get_soundpacks_dir()

    assert result == tmp_path / "soundpacks"


def test_get_soundpacks_dir_nuitka_installed_uses_executable_parent(tmp_path):
    """Nuitka installed builds should find bundled soundpacks beside the executable."""
    exe_path = tmp_path / "AccessiWeather.exe"
    main_module = sys.modules["__main__"]
    original_compiled = getattr(main_module, "__compiled__", None)

    try:
        main_module.__compiled__ = True
        with (
            patch.object(sys, "frozen", False, create=True),
            patch.object(sys, "executable", str(exe_path), create=True),
            patch.dict(sys.__dict__, {"_MEIPASS": None}, clear=False),
        ):
            del sys.__dict__["_MEIPASS"]
            result = soundpack_paths.get_soundpacks_dir()
    finally:
        if original_compiled is None:
            delattr(main_module, "__compiled__")
        else:
            main_module.__compiled__ = original_compiled

    assert result == tmp_path / "soundpacks"


def test_get_soundpacks_dir_nuitka_portable_uses_data_soundpacks(tmp_path):
    """Nuitka portable builds should use the writable data/soundpacks layout."""
    exe_path = tmp_path / "AccessiWeather.exe"
    (tmp_path / ".portable").write_text("1", encoding="utf-8")
    main_module = sys.modules["__main__"]
    original_compiled = getattr(main_module, "__compiled__", None)

    try:
        main_module.__compiled__ = True
        with (
            patch.object(sys, "frozen", False, create=True),
            patch.object(sys, "executable", str(exe_path), create=True),
            patch.dict(sys.__dict__, {"_MEIPASS": None}, clear=False),
        ):
            del sys.__dict__["_MEIPASS"]
            result = soundpack_paths.get_soundpacks_dir()
    finally:
        if original_compiled is None:
            delattr(main_module, "__compiled__")
        else:
            main_module.__compiled__ = original_compiled

    assert result == tmp_path / "data" / "soundpacks"
