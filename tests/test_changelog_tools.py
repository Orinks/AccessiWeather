from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import pytest

from scripts.changelog_tools import (
    ChangelogSection,
    check_command,
    extract_release_block,
    format_sections,
    is_user_facing_path,
    messages_opt_out_of_changelog,
    normalize_entry,
    parse_sections,
    pyproject_changed_lines_require_changelog,
    resolve_base,
    unreleased_added_entries,
)


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def make_changelog_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.email", "test@example.com")
    git(tmp_path, "config", "user.name", "Test User")

    source_file = tmp_path / "src" / "accessiweather" / "app.py"
    source_file.parent.mkdir(parents=True)
    source_file.write_text("print('hello')\n", encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text(
        """# AccessiWeather Changelog

## [Unreleased]

### Fixed
- Existing fix.

## [0.1.0] - 2026-01-01

### Fixed
- Old fix.
""",
        encoding="utf-8",
    )
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-q", "-m", "initial")
    monkeypatch.chdir(tmp_path)
    return git(tmp_path, "rev-parse", "HEAD")


def check_args(base: str) -> argparse.Namespace:
    return argparse.Namespace(base=base, head="HEAD")


def test_extract_unreleased_block_stops_at_next_release() -> None:
    changelog = """# Changelog

## [Unreleased]

### Added
- New useful thing.

## [0.1.0] - 2026-01-01

### Fixed
- Old fix.
"""

    block = extract_release_block(changelog, r"^## \[?Unreleased\]?.*$")

    assert "New useful thing" in block
    assert "Old fix" not in block


def test_parse_sections_keeps_multiline_entries() -> None:
    block = """### Added
- First entry wraps
  onto the next line.
- Second entry.

### Fixed
- Fixed entry.
"""

    sections = parse_sections(block)

    assert sections == [
        ChangelogSection(
            "Added",
            ("- First entry wraps\n  onto the next line.", "- Second entry."),
        ),
        ChangelogSection("Fixed", ("- Fixed entry.",)),
    ]


def test_format_sections_uses_release_note_headings() -> None:
    notes = format_sections(
        [
            ChangelogSection("Fixed", ("- Corrected weather alerts.",)),
            ChangelogSection("Added", ("- Added National Products.",)),
        ]
    )

    assert notes == "## Added\n- Added National Products.\n\n## Fixed\n- Corrected weather alerts."


def test_user_facing_paths_match_release_build_surface() -> None:
    assert is_user_facing_path("src/accessiweather/app.py")
    assert is_user_facing_path("installer/build_nuitka.py")
    assert is_user_facing_path("scripts/generate_build_meta.py")
    assert is_user_facing_path("accessiweather.spec")
    assert not is_user_facing_path(".github/workflows/ci.yml")
    assert not is_user_facing_path("tests/test_app.py")


def test_generated_api_client_is_not_user_facing() -> None:
    assert not is_user_facing_path("src/accessiweather/weather_gov_api_client/models/alert.py")
    # A real app module under src/ stays user-facing.
    assert is_user_facing_path("src/accessiweather/weather_client.py")


def test_skip_marker_opts_out_only_when_all_commits_carry_it() -> None:
    assert messages_opt_out_of_changelog(["chore: tidy logging\n\nChangelog: none"])
    assert messages_opt_out_of_changelog(
        ["ci: bump action [skip changelog]", "test: add case\n\nchangelog: none"]
    )
    # Mixed: one commit opts out, another does not -> gate still applies.
    assert not messages_opt_out_of_changelog(
        ["fix: real user-facing fix", "chore: cleanup\n\nChangelog: none"]
    )
    # No commits (e.g. empty range) is not an opt-out.
    assert not messages_opt_out_of_changelog([])


def test_resolve_base_uses_main_for_main_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("scripts.changelog_tools.current_branch", lambda: "main")

    assert resolve_base("auto") == "origin/main"


def test_resolve_base_uses_dev_for_other_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("scripts.changelog_tools.current_branch", lambda: "feature/fix")

    assert resolve_base("auto") == "origin/dev"


def test_resolve_base_preserves_explicit_base(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "scripts.changelog_tools.current_branch",
        lambda: pytest.fail("explicit base should not inspect the branch"),
    )

    assert resolve_base("origin/release") == "origin/release"


def test_check_command_flags_dirty_user_facing_worktree_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = make_changelog_repo(tmp_path, monkeypatch)
    source_file = tmp_path / "src" / "accessiweather" / "app.py"
    source_file.write_text("print('changed')\n", encoding="utf-8")

    assert check_command(check_args(base)) == 1


def test_check_command_accepts_dirty_worktree_changelog_entry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    base = make_changelog_repo(tmp_path, monkeypatch)
    (tmp_path / "src" / "accessiweather" / "app.py").write_text(
        "print('changed')\n",
        encoding="utf-8",
    )
    (tmp_path / "CHANGELOG.md").write_text(
        """# AccessiWeather Changelog

## [Unreleased]

### Fixed
- New user-facing fix.
- Existing fix.

## [0.1.0] - 2026-01-01

### Fixed
- Old fix.
""",
        encoding="utf-8",
    )

    assert check_command(check_args(base)) == 0
    assert "Found CHANGELOG.md Unreleased entries" in capsys.readouterr().out


def test_pyproject_metadata_only_changes_do_not_need_changelog() -> None:
    assert not pyproject_changed_lines_require_changelog(
        [
            'version = "0.7.0"',
            'version = "0.7.1.dev0"',
            'description = "Old description"',
            'description = "New description"',
        ]
    )


def test_pyproject_dependency_changes_need_changelog() -> None:
    assert pyproject_changed_lines_require_changelog(
        [
            '"requests>=2.34.2",',
        ]
    )


def test_pyproject_tooling_dependency_changes_do_not_need_changelog() -> None:
    assert not pyproject_changed_lines_require_changelog(
        [
            '"ruff>=0.9.0",',
            '"ruff>=0.15.14",',
            '"pyright",',
            '"pyright>=1.1.409",',
        ]
    )


def test_normalize_entry_matches_curated_release_body_wording() -> None:
    changelog_entry = (
        "- **National Products in Forecaster Notes** — Forecaster Notes now opens a dedicated "
        "National Products dialog."
    )
    release_body_entry = (
        "- **National Products in Forecaster Notes** - Forecaster Notes now opens a dedicated "
        "National Products dialog."
    )

    assert normalize_entry(changelog_entry) == normalize_entry(release_body_entry)


def test_unreleased_added_entries_ignores_existing_entry_reformat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base_text = """# Changelog

## [Unreleased]

### Fixed
- **National Products in Forecaster Notes** — Forecaster Notes now opens a dedicated dialog.
"""
    head_text = """# Changelog

## [Unreleased]

### Fixed
- **National Products in Forecaster Notes** - Forecaster Notes now opens a dedicated dialog.
"""

    monkeypatch.setattr("scripts.changelog_tools.changelog_at", lambda _ref: base_text)
    monkeypatch.setattr(
        "scripts.changelog_tools.run_git",
        lambda _args: head_text,
    )

    assert unreleased_added_entries("base", "head") == []
