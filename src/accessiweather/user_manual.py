"""User manual lookup and launching helpers."""

from __future__ import annotations

import logging
import sys
import webbrowser
from pathlib import Path

logger = logging.getLogger(__name__)

ONLINE_USER_MANUAL_URL = "https://github.com/Orinks/AccessiWeather/blob/main/docs/user_manual.md"


def _find_project_root(start: Path) -> Path | None:
    for parent in (start, *start.parents):
        if (parent / "pyproject.toml").exists():
            return parent
    return None


def get_bundled_user_manual_path() -> Path | None:
    """Return the bundled/local user manual path when available."""
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        meipass_dir = Path(getattr(sys, "_MEIPASS", exe_dir))
        candidates = [
            meipass_dir / "accessiweather" / "docs" / "user_manual.md",
            exe_dir / "accessiweather" / "docs" / "user_manual.md",
        ]
    else:
        start = Path(__file__).resolve()
        project_root = _find_project_root(start)
        if project_root is None:
            project_root = start.parents[2]
        candidates = [project_root / "docs" / "user_manual.md"]

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def open_user_manual() -> bool:
    """Open the local bundled user manual, falling back to the online manual."""
    manual_path = get_bundled_user_manual_path()

    if manual_path is not None:
        try:
            return bool(webbrowser.open(manual_path.resolve().as_uri()))
        except Exception:
            logger.exception("Failed to open local user manual at %s", manual_path)

    try:
        return bool(webbrowser.open(ONLINE_USER_MANUAL_URL))
    except Exception:
        logger.exception("Failed to open fallback online user manual")
        return False
