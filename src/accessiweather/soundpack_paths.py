"""Sound pack path helpers."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def _find_project_root(start: Path) -> Path | None:
    for parent in (start, *start.parents):
        if (parent / "pyproject.toml").exists():
            return parent
    return None


def get_soundpacks_dir() -> Path:
    """
    Return the base soundpacks directory for dev or packaged builds.

    In frozen builds, portable mode uses the exe directory so users can add
    their own packs alongside the executable. Installed/onefile builds fall
    back to the PyInstaller extraction dir (sys._MEIPASS).
    """
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        meipass_dir = Path(sys._MEIPASS) if hasattr(sys, "_MEIPASS") else exe_dir

        # Portable: soundpacks live next to the exe so users can manage them.
        # Detect via .portable marker (same logic as config_utils.is_portable_mode).
        portable_marker = exe_dir / ".portable"
        legacy_config_marker = exe_dir / "config"
        is_portable = portable_marker.exists() or legacy_config_marker.is_dir()

        base_path = exe_dir if is_portable else meipass_dir
        result = base_path / "soundpacks"
        logger.debug(
            "[packaging-diag] soundpacks_dir resolved (frozen=%s, portable=%s, meipass=%s, executable=%s): %s exists=%s",
            getattr(sys, "frozen", False),
            is_portable,
            getattr(sys, "_MEIPASS", None),
            getattr(sys, "executable", None),
            result,
            result.exists(),
        )
        return result

    start = Path(__file__).resolve()
    project_root = _find_project_root(start)
    if project_root is None:
        # Fallback: repo layout is root/src/accessiweather/
        project_root = start.parents[2]
    return project_root / "soundpacks"
