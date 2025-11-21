"""Tests for version management - ensuring pyproject.toml is the single source of truth."""

from pathlib import Path

import tomllib


class TestVersionManagement:
    """Test that version is managed from a single source."""

    def test_pyproject_has_project_version(self):
        """Test that pyproject.toml has a version in the [project] section."""
        root = Path(__file__).resolve().parents[1]
        pyproject_path = root / "pyproject.toml"

        with pyproject_path.open("rb") as f:
            data = tomllib.load(f)

        project_version = data.get("project", {}).get("version")
        assert project_version is not None, "project.version must be set in pyproject.toml"
        assert isinstance(project_version, str), "version must be a string"
        assert len(project_version) > 0, "version must not be empty"

    def test_briefcase_does_not_have_version(self):
        """
        Test that tool.briefcase does NOT have a duplicate version field.

        This ensures pyproject.toml [project] section is the single source of truth.
        Briefcase will read the version from [project] automatically.
        """
        root = Path(__file__).resolve().parents[1]
        pyproject_path = root / "pyproject.toml"

        with pyproject_path.open("rb") as f:
            data = tomllib.load(f)

        briefcase_version = data.get("tool", {}).get("briefcase", {}).get("version")
        assert briefcase_version is None, (
            "tool.briefcase.version should not exist; [project] version is the single source of truth"
        )

    def test_read_pyproject_version_function(self):
        """Test the _read_pyproject_version function in accessiweather/__init__.py."""
        root = Path(__file__).resolve().parents[1]

        # Import and test the function (if possible without full dependencies)
        init_file = root / "src" / "accessiweather" / "__init__.py"
        assert init_file.exists(), "accessiweather/__init__.py must exist"

        # Verify the function exists and has proper logic by checking source
        init_content = init_file.read_text()
        assert "_read_pyproject_version" in init_content
        assert 'data.get("project", {}).get("version")' in init_content
        # Ensure it doesn't fallback to briefcase version anymore
        assert (
            'data.get("tool", {}).get("briefcase"' not in init_content
            or 'get("briefcase", {})\n        ).get("version")' not in init_content
        ), "Should not read from tool.briefcase.version"

    def test_installer_make_reads_version(self):
        """Test that installer/make.py can read version from pyproject.toml."""
        root = Path(__file__).resolve().parents[1]
        pyproject_path = root / "pyproject.toml"

        with pyproject_path.open("rb") as f:
            data = tomllib.load(f)
        expected_version = data.get("project", {}).get("version")

        # Test the installer/make.py _read_version function
        import sys

        sys.path.insert(0, str(root / "installer"))
        try:
            import make

            version = make._read_version()
            assert version == expected_version, (
                f"installer/make.py should read version {expected_version}, but got {version}"
            )
        finally:
            sys.path.pop(0)

    def test_version_format_is_valid(self):
        """Test that version follows PEP 440 format."""
        root = Path(__file__).resolve().parents[1]
        pyproject_path = root / "pyproject.toml"

        with pyproject_path.open("rb") as f:
            data = tomllib.load(f)

        version = data.get("project", {}).get("version")

        # Basic PEP 440 validation - should have at least major.minor.patch
        # Can have .devN, .aN, .bN, .rcN suffixes
        import re

        # PEP 440 regex (simplified - covers most common cases)
        pep440_pattern = r"^\d+(\.\d+)*((a|b|rc)\d+)?(\.post\d+)?(\.dev\d+)?$"
        assert re.match(pep440_pattern, version), (
            f"Version '{version}' does not follow PEP 440 format. "
            f"Should match pattern: {pep440_pattern}"
        )
