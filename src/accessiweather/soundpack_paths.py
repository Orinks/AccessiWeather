"""Sound pack path helpers."""

from __future__ import annotations

import sys
from pathlib import Path


def _find_project_root(start: Path) -> Path | None:
    for parent in (start, *start.parents):
        if (parent / "pyproject.toml").exists():
            return parent
    return None


def get_soundpacks_dir() -> Path:
    """Return the base soundpacks directory for dev or packaged builds."""
    if getattr(sys, "frozen", False):
        base_path = Path(sys._MEIPASS) if hasattr(sys, "_MEIPASS") else Path(sys.executable).parent
        return base_path / "soundpacks"

    start = Path(__file__).resolve()
    project_root = _find_project_root(start)
    if project_root is None:
        # Fallback: repo layout is root/src/accessiweather/
        project_root = start.parents[2]
    return project_root / "soundpacks"
