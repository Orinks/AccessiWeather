"""
Helpers for PyInstaller spec filtering.

These utilities keep platform-irrelevant sound_lib binaries out of bundles and
avoid packaging obvious cross-platform binary artifacts.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

_BINARY_EXTS = (".dll", ".dylib", ".pyd", ".exe", ".bundle")
_SOUND_LIB_ROOT = "sound_lib/lib/"
_SOUND_LIB_X86 = "sound_lib/lib/x86"


def normalize_path(path: str) -> str:
    """Normalize a filesystem path for cross-platform substring checks."""
    return path.replace("\\", "/")


def _entry_paths(entry: tuple) -> list[str]:
    paths: list[str] = []
    for value in entry:
        if isinstance(value, str):
            paths.append(normalize_path(value))
    return paths


def _binary_extension(path: str) -> str | None:
    lower = path.lower()
    for ext in _BINARY_EXTS:
        if lower.endswith(ext):
            return ext
    if re.search(r"\.so(\.\d+)*$", lower):
        return ".so"
    return None


def _first_binary_ext(paths: Iterable[str]) -> str | None:
    for path in paths:
        ext = _binary_extension(path)
        if ext:
            return ext
    return None


def filter_platform_binaries(binaries: Iterable[tuple], platform_system: str) -> list[tuple]:
    """Remove obvious cross-platform binaries based on file extension."""
    allowed = {
        "Windows": {".dll", ".pyd", ".exe"},
        "Darwin": {".dylib", ".so", ".bundle"},
        "Linux": {".so"},
    }
    allowed_exts = allowed.get(platform_system)
    if not allowed_exts:
        return list(binaries)

    filtered: list[tuple] = []
    for entry in binaries:
        paths = _entry_paths(entry)
        ext = _first_binary_ext(paths)
        if ext is None or ext in allowed_exts:
            filtered.append(entry)
            continue
        if ext in {".dll", ".dylib", ".so", ".pyd", ".exe", ".bundle"}:
            continue
        filtered.append(entry)
    return filtered


def filter_sound_lib_entries(entries: Iterable[tuple], platform_system: str) -> list[tuple]:
    """Filter sound_lib artifacts to the platform-compatible set."""
    allowed_ext = {
        "Windows": ".dll",
        "Darwin": ".dylib",
        "Linux": ".so",
    }.get(platform_system)

    filtered: list[tuple] = []
    for entry in entries:
        paths = _entry_paths(entry)
        if any(_SOUND_LIB_X86 in path for path in paths):
            continue
        if any(_SOUND_LIB_ROOT in path for path in paths):
            ext = _first_binary_ext(paths)
            if ext and allowed_ext and ext != allowed_ext:
                continue
        filtered.append(entry)
    return filtered
