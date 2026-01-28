"""
Tests for PyInstaller spec filtering utilities.
"""

from __future__ import annotations

import pytest

from installer.spec_utils import filter_platform_binaries, filter_sound_lib_entries


@pytest.mark.parametrize(
    ("platform_system", "expected_exts"),
    [
        ("Windows", {".dll", ".pyd", ".exe"}),
        ("Darwin", {".dylib", ".so", ".bundle"}),
        ("Linux", {".so"}),
    ],
)
def test_filter_platform_binaries_removes_cross_platform(platform_system, expected_exts):
    binaries = [
        ("C:/path/libsound.dll", "libsound.dll", "BINARY"),
        ("/usr/lib/libsound.dylib", "libsound.dylib", "BINARY"),
        ("/usr/lib/libsound.so", "libsound.so", "BINARY"),
        ("/usr/lib/libsound.so.1", "libsound.so.1", "BINARY"),
        ("/usr/lib/libsound.pyd", "libsound.pyd", "BINARY"),
        ("/usr/lib/libsound.bundle", "libsound.bundle", "BINARY"),
        ("/usr/lib/data.txt", "data.txt", "BINARY"),
    ]

    filtered = filter_platform_binaries(binaries, platform_system)
    filtered_paths = {entry[0] for entry in filtered}

    assert "/usr/lib/data.txt" in filtered_paths

    for entry in binaries:
        ext = entry[0].lower()
        if ext.endswith(".dll"):
            assert (".dll" in expected_exts) == (entry in filtered)
        elif ext.endswith(".dylib"):
            assert (".dylib" in expected_exts) == (entry in filtered)
        elif ext.endswith(".bundle"):
            assert (".bundle" in expected_exts) == (entry in filtered)
        elif ext.endswith(".pyd"):
            assert (".pyd" in expected_exts) == (entry in filtered)
        elif ext.endswith(".so") or ext.endswith(".so.1"):
            assert (".so" in expected_exts) == (entry in filtered)


@pytest.mark.parametrize(
    ("platform_system", "expected_entries"),
    [
        (
            "Darwin",
            [
                (
                    "/opt/sound_lib/lib/x64/libbass_fx.dylib",
                    "sound_lib/lib/x64/libbass_fx.dylib",
                    "BINARY",
                ),
                ("/opt/other/lib/other.dll", "other.dll", "BINARY"),
            ],
        ),
        (
            "Windows",
            [
                (
                    "/opt/sound_lib/lib/x64/libbass_fx.dll",
                    "sound_lib/lib/x64/libbass_fx.dll",
                    "BINARY",
                ),
                ("/opt/other/lib/other.dll", "other.dll", "BINARY"),
            ],
        ),
        (
            "Linux",
            [
                (
                    "/opt/sound_lib/lib/x64/libbass_fx.so",
                    "sound_lib/lib/x64/libbass_fx.so",
                    "BINARY",
                ),
                (
                    "/opt/sound_lib/lib/x64/libbass_fx.so.1",
                    "sound_lib/lib/x64/libbass_fx.so.1",
                    "BINARY",
                ),
                ("/opt/other/lib/other.dll", "other.dll", "BINARY"),
            ],
        ),
    ],
)
def test_filter_sound_lib_entries_keeps_platform_entries(platform_system, expected_entries):
    entries = [
        (
            "C:\\Python\\site-packages\\sound_lib\\lib\\x86\\libbass_fx.dylib",
            "sound_lib\\lib\\x86\\libbass_fx.dylib",
            "BINARY",
        ),
        ("/opt/sound_lib/lib/x64/libbass_fx.dylib", "sound_lib/lib/x64/libbass_fx.dylib", "BINARY"),
        ("/opt/sound_lib/lib/x64/libbass_fx.dll", "sound_lib/lib/x64/libbass_fx.dll", "BINARY"),
        ("/opt/sound_lib/lib/x64/libbass_fx.so", "sound_lib/lib/x64/libbass_fx.so", "BINARY"),
        ("/opt/sound_lib/lib/x64/libbass_fx.so.1", "sound_lib/lib/x64/libbass_fx.so.1", "BINARY"),
        ("/opt/other/lib/other.dll", "other.dll", "BINARY"),
    ]

    assert filter_sound_lib_entries(entries, platform_system) == expected_entries
