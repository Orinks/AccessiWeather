"""Tests for pyproject.toml prismatoid dependency."""

from pathlib import Path

import tomllib

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def _load_pyproject():
    """Load pyproject.toml."""
    with open(PYPROJECT, "rb") as f:
        return tomllib.load(f)


class TestPrismatoidDependency:
    """Verify prismatoid is listed as a main dependency."""

    def test_prismatoid_in_main_dependencies(self):
        """Prismatoid should be a default dependency."""
        data = _load_pyproject()
        main_deps = data["project"]["dependencies"]
        assert any("prismatoid" in d for d in main_deps)

    def test_prismatoid_version_constraint(self):
        """Prismatoid should require >= 0.7.0."""
        data = _load_pyproject()
        main_deps = data["project"]["dependencies"]
        assert any("prismatoid>=0.7.0" in d for d in main_deps)
