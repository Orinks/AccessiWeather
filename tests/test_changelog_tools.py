from __future__ import annotations

from scripts.changelog_tools import (
    ChangelogSection,
    extract_release_block,
    format_sections,
    is_user_facing_path,
    normalize_entry,
    parse_sections,
    pyproject_changed_lines_require_changelog,
)


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
