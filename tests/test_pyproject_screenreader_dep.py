"""Tests for pyproject.toml screenreader optional dependency."""

from pathlib import Path

import tomllib

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def _load_pyproject():
    with open(PYPROJECT, "rb") as f:
        return tomllib.load(f)


class TestScreenreaderOptionalDependency:
    """Verify prismatoid is listed as an optional (not required) dependency."""

    def test_screenreader_group_exists(self):
        data = _load_pyproject()
        assert "screenreader" in data["project"]["optional-dependencies"]

    def test_prismatoid_in_screenreader_group(self):
        data = _load_pyproject()
        deps = data["project"]["optional-dependencies"]["screenreader"]
        assert any("prismatoid" in d for d in deps)

    def test_prismatoid_version_constraint(self):
        data = _load_pyproject()
        deps = data["project"]["optional-dependencies"]["screenreader"]
        assert any("prismatoid>=0.7.0" in d for d in deps)

    def test_prismatoid_not_in_main_dependencies(self):
        data = _load_pyproject()
        main_deps = data["project"]["dependencies"]
        assert not any("prismatoid" in d for d in main_deps)
