"""Version information for AccessiWeather.

Prefer project metadata (pyproject.toml / installed package) over hardcoded strings.
"""

from __future__ import annotations

# Try to read version from installed package metadata first.
try:  # Python 3.8+
    from importlib.metadata import (  # type: ignore
        PackageNotFoundError,
        version as _pkg_version,
    )
except Exception:  # pragma: no cover - extremely rare fallback
    _pkg_version = None  # type: ignore

    class PackageNotFoundError(Exception):  # type: ignore
        pass


def _read_pyproject_version() -> str | None:
    """Read project version from pyproject.toml if available.

    Falls back to tool.briefcase.version if project.version is missing.
    """
    try:
        import tomllib  # Python 3.11+
        from pathlib import Path

        root = Path(__file__).resolve().parents[2]
        py = root / "pyproject.toml"
        if not py.exists():
            return None
        with py.open("rb") as f:
            data = tomllib.load(f)
        return data.get("project", {}).get("version") or data.get("tool", {}).get(
            "briefcase", {}
        ).get("version")
    except Exception:
        return None


try:
    __version__ = _pkg_version("accessiweather") if _pkg_version else None  # type: ignore
except PackageNotFoundError:
    __version__ = None  # type: ignore

if not __version__:
    __version__ = _read_pyproject_version() or "0.0.0"
