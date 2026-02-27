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
    """Return the base soundpacks directory for dev or packaged builds."""
    if getattr(sys, "frozen", False):
        base_path = Path(sys._MEIPASS) if hasattr(sys, "_MEIPASS") else Path(sys.executable).parent
        result = base_path / "soundpacks"
        logger.debug(
            "[packaging-diag] soundpacks_dir resolved (frozen=%s, meipass=%s, executable=%s): %s exists=%s",
            getattr(sys, "frozen", False),
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
