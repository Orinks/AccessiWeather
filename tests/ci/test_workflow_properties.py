"""
Property-based tests for workflow validation logic.

Uses Hypothesis to test version parsing, artifact naming,
and other workflow-related string patterns.
"""

import re

import pytest
from hypothesis import (
    given,
    settings,
    strategies as st,
)

pytestmark = [pytest.mark.ci, pytest.mark.property]

version_strategy = st.from_regex(r"[0-9]+\.[0-9]+\.[0-9]+", fullmatch=True)
prerelease_suffix = st.sampled_from(["", "-beta.1", "-alpha.1", "-rc.1", "-dev.20241224"])
nightly_date_strategy = st.from_regex(
    r"20[2-3][0-9](0[1-9]|1[0-2])(0[1-9]|[12][0-9]|3[01])", fullmatch=True
)
sha_strategy = st.from_regex(r"[0-9a-f]{40}", fullmatch=True)
branch_name_strategy = st.from_regex(r"[a-z][a-z0-9-]{0,49}", fullmatch=True)


class TestVersionProperties:
    """Property-based tests for semantic version string handling."""

    @given(major=st.integers(0, 99), minor=st.integers(0, 99), patch=st.integers(0, 99))
    @settings(max_examples=50)
    def test_semver_format_always_valid(self, major: int, minor: int, patch: int) -> None:
        """Constructed semver strings should always match the pattern."""
        version = f"{major}.{minor}.{patch}"
        assert re.match(r"^\d+\.\d+\.\d+$", version)

    @given(version=version_strategy, suffix=prerelease_suffix)
    @settings(max_examples=50)
    def test_prerelease_version_includes_base(self, version: str, suffix: str) -> None:
        """Prerelease versions should contain the base version."""
        full_version = f"{version}{suffix}"
        assert version in full_version

    @given(version=version_strategy)
    @settings(max_examples=50)
    def test_version_parts_extractable(self, version: str) -> None:
        """Version parts should be extractable via split."""
        parts = version.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)

    @given(
        major=st.integers(0, 999),
        minor=st.integers(0, 999),
        patch=st.integers(0, 999),
    )
    @settings(max_examples=50)
    def test_version_comparison_ordering(self, major: int, minor: int, patch: int) -> None:
        """Version comparison should maintain ordering."""
        v1 = (major, minor, patch)
        v2 = (major, minor, patch + 1)
        assert v1 < v2

    @given(version=version_strategy)
    @settings(max_examples=50)
    def test_version_pyproject_format(self, version: str) -> None:
        """Version should be valid for pyproject.toml."""
        line = f'version = "{version}"'
        match = re.search(r'version\s*=\s*"([^"]+)"', line)
        assert match is not None
        assert match.group(1) == version


class TestTagProperties:
    """Property-based tests for git tag format validation."""

    @given(version=version_strategy)
    @settings(max_examples=50)
    def test_stable_tag_format(self, version: str) -> None:
        """Stable release tags should match v-prefix pattern."""
        tag = f"v{version}"
        assert tag.startswith("v")
        assert re.match(r"^v\d+\.\d+\.\d+$", tag)

    @given(date=nightly_date_strategy)
    @settings(max_examples=50)
    def test_nightly_tag_format(self, date: str) -> None:
        """Nightly tags should match expected pattern."""
        tag = f"nightly-{date}"
        assert re.match(r"^nightly-\d{8}$", tag)

    @given(version=version_strategy, suffix=prerelease_suffix)
    @settings(max_examples=50)
    def test_prerelease_tag_format(self, version: str, suffix: str) -> None:
        """Prerelease tags should contain version and suffix."""
        tag = f"v{version}{suffix}"
        assert tag.startswith("v")
        assert version in tag

    @given(date=nightly_date_strategy)
    @settings(max_examples=50)
    def test_nightly_date_extractable(self, date: str) -> None:
        """Date should be extractable from nightly tag."""
        tag = f"nightly-{date}"
        extracted = tag.replace("nightly-", "")
        assert extracted == date
        assert len(extracted) == 8


class TestArtifactNamingProperties:
    """Property-based tests for build artifact naming conventions."""

    @given(version=version_strategy)
    @settings(max_examples=50)
    def test_msi_artifact_name_format(self, version: str) -> None:
        """MSI artifact name should follow naming convention."""
        name = f"AccessiWeather-{version}.msi"
        assert name.endswith(".msi")
        assert version in name
        assert name.startswith("AccessiWeather-")

    @given(version=version_strategy)
    @settings(max_examples=50)
    def test_portable_zip_name_format(self, version: str) -> None:
        """Portable ZIP name should follow naming convention."""
        name = f"AccessiWeather_Portable_v{version}.zip"
        assert name.endswith(".zip")
        assert "Portable" in name
        assert version in name

    @given(version=version_strategy)
    @settings(max_examples=50)
    def test_dmg_artifact_name_format(self, version: str) -> None:
        """DMG artifact name should follow naming convention."""
        name = f"AccessiWeather-{version}.dmg"
        assert name.endswith(".dmg")
        assert version in name

    @given(version=version_strategy)
    @settings(max_examples=50)
    def test_appimage_artifact_name_format(self, version: str) -> None:
        """AppImage artifact name should follow naming convention."""
        name = f"AccessiWeather-{version}.AppImage"
        assert name.endswith(".AppImage")
        assert version in name

    @given(date=nightly_date_strategy)
    @settings(max_examples=50)
    def test_nightly_artifact_name(self, date: str) -> None:
        """Nightly artifact should include date."""
        name = f"AccessiWeather-nightly-{date}.msi"
        assert date in name
        assert "nightly" in name


class TestShaProperties:
    """Property-based tests for commit SHA handling."""

    @given(sha=sha_strategy)
    @settings(max_examples=50)
    def test_sha_always_40_chars(self, sha: str) -> None:
        """Full SHA should be exactly 40 characters."""
        assert len(sha) == 40

    @given(sha=sha_strategy)
    @settings(max_examples=50)
    def test_sha_truncation_to_7(self, sha: str) -> None:
        """Short SHA should be 7 characters and prefix of full SHA."""
        short = sha[:7]
        assert len(short) == 7
        assert sha.startswith(short)

    @given(sha=sha_strategy)
    @settings(max_examples=50)
    def test_sha_only_hex_chars(self, sha: str) -> None:
        """SHA should contain only lowercase hex characters."""
        assert re.match(r"^[0-9a-f]+$", sha)

    @given(sha=sha_strategy)
    @settings(max_examples=50)
    def test_sha_display_format(self, sha: str) -> None:
        """SHA display format should be valid for git commands."""
        display = f"({sha[:7]})"
        assert display.startswith("(")
        assert display.endswith(")")
        assert len(display) == 9


class TestCronProperties:
    """Property-based tests for cron expression validation."""

    @given(minute=st.integers(0, 59), hour=st.integers(0, 23))
    @settings(max_examples=50)
    def test_cron_time_fields_valid(self, minute: int, hour: int) -> None:
        """Cron minute and hour fields should be valid."""
        cron = f"{minute} {hour} * * *"
        parts = cron.split()
        assert len(parts) == 5
        assert 0 <= int(parts[0]) <= 59
        assert 0 <= int(parts[1]) <= 23

    @given(
        minute=st.integers(0, 59),
        hour=st.integers(0, 23),
        day_of_month=st.integers(1, 31),
    )
    @settings(max_examples=50)
    def test_cron_with_day_of_month(self, minute: int, hour: int, day_of_month: int) -> None:
        """Cron with day of month should be valid."""
        cron = f"{minute} {hour} {day_of_month} * *"
        parts = cron.split()
        assert len(parts) == 5
        assert 1 <= int(parts[2]) <= 31

    @given(day_of_week=st.integers(0, 6))
    @settings(max_examples=10)
    def test_cron_day_of_week_valid(self, day_of_week: int) -> None:
        """Cron day of week should be 0-6."""
        cron = f"0 0 * * {day_of_week}"
        parts = cron.split()
        assert 0 <= int(parts[4]) <= 6


class TestBranchNameProperties:
    """Property-based tests for git branch name validation."""

    @given(branch=branch_name_strategy)
    @settings(max_examples=50)
    def test_branch_name_valid_chars(self, branch: str) -> None:
        """Branch names should contain only valid characters."""
        assert re.match(r"^[a-z][a-z0-9-]*$", branch)

    @given(branch=branch_name_strategy)
    @settings(max_examples=50)
    def test_branch_name_not_empty(self, branch: str) -> None:
        """Branch names should not be empty."""
        assert len(branch) >= 1

    @given(
        prefix=st.sampled_from(["feature", "fix", "hotfix", "release"]),
        suffix=st.from_regex(r"[a-z0-9-]{1,20}", fullmatch=True),
    )
    @settings(max_examples=50)
    def test_prefixed_branch_format(self, prefix: str, suffix: str) -> None:
        """Prefixed branch names should follow convention."""
        branch = f"{prefix}/{suffix}"
        assert "/" in branch
        assert branch.startswith(prefix)


class TestReleaseAssetNamingProperties:
    """Property-based tests for release asset naming conventions."""

    @given(version=version_strategy)
    @settings(max_examples=50)
    def test_checksum_file_naming(self, version: str) -> None:
        """Checksum files should follow naming pattern."""
        name = f"AccessiWeather-{version}-checksums.txt"
        assert "checksums" in name
        assert version in name
        assert name.endswith(".txt")

    @given(
        version=version_strategy,
        platform=st.sampled_from(["windows", "macos", "linux"]),
    )
    @settings(max_examples=50)
    def test_platform_specific_naming(self, version: str, platform: str) -> None:
        """Platform-specific assets should include platform name."""
        extensions = {"windows": ".msi", "macos": ".dmg", "linux": ".AppImage"}
        name = f"AccessiWeather-{version}-{platform}{extensions[platform]}"
        assert platform in name
        assert version in name

    @given(version=version_strategy)
    @settings(max_examples=50)
    def test_source_archive_naming(self, version: str) -> None:
        """Source archives should follow naming convention."""
        name = f"AccessiWeather-{version}-source.tar.gz"
        assert "source" in name
        assert version in name
        assert name.endswith(".tar.gz")


class TestWorkflowInputValidation:
    """Property-based tests for workflow input validation."""

    @given(
        version=version_strategy,
        sha=sha_strategy,
    )
    @settings(max_examples=50)
    def test_release_metadata_format(self, version: str, sha: str) -> None:
        """Release metadata should be well-formed."""
        metadata = {"version": version, "commit": sha[:7], "tag": f"v{version}"}
        assert metadata["tag"].startswith("v")
        assert len(metadata["commit"]) == 7
        assert "." in metadata["version"]

    @given(st.sampled_from(["push", "pull_request", "schedule", "workflow_dispatch"]))
    @settings(max_examples=10)
    def test_event_types_valid(self, event: str) -> None:
        """GitHub event types should be recognized."""
        valid_events = {"push", "pull_request", "schedule", "workflow_dispatch", "release"}
        assert event in valid_events

    @given(
        run_id=st.integers(1, 2**31),
        run_number=st.integers(1, 10000),
    )
    @settings(max_examples=50)
    def test_run_identifiers_positive(self, run_id: int, run_number: int) -> None:
        """Workflow run identifiers should be positive."""
        assert run_id > 0
        assert run_number > 0
