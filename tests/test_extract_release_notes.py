from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def load_module():
    script_path = (
        Path(__file__).resolve().parents[1]
        / ".github"
        / "scripts"
        / "extract_release_notes.py"
    )
    spec = importlib.util.spec_from_file_location("extract_release_notes", script_path)
    module = importlib.util.module_from_spec(spec)
    try:
        assert spec and spec.loader
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)
    return module


SAMPLE_CHANGELOG = """# AccessiWeather Changelog

All notable changes to this project will be documented in this file.

## Unreleased

### Added
- Added clearer update summaries
- Added a new update download flow

### Fixed
- Fixed installer wording shown to users
- Improved CI coverage gate behavior
- Added missing tests for release note extraction

## [0.4.4] - 2026-03-13

### Fixed
- Fixed alert wording in the update dialog
- Updated workflow docs

## [0.4.3] - 2026-02-11

### Added
- Older stable notes
"""


def test_extract_nightly_uses_unreleased_section():
    module = load_module()

    notes = module.extract_release_notes(SAMPLE_CHANGELOG, mode="nightly")

    assert notes == (
        "### Added\n"
        "- Added clearer update summaries\n"
        "- Added a new update download flow\n\n"
        "### Fixed\n"
        "- Fixed installer wording shown to users"
    )


def test_extract_stable_uses_matching_version_section():
    module = load_module()

    notes = module.extract_release_notes(SAMPLE_CHANGELOG, mode="stable", version="0.4.4")

    assert notes == "### Fixed\n- Fixed alert wording in the update dialog"


def test_extract_stable_accepts_v_prefix():
    module = load_module()

    notes = module.extract_release_notes(SAMPLE_CHANGELOG, mode="stable", version="v0.4.3")

    assert notes == "### Added\n- Older stable notes"


def test_extract_stable_requires_version():
    module = load_module()

    try:
        module.extract_release_notes(SAMPLE_CHANGELOG, mode="stable")
    except ValueError as exc:
        assert str(exc) == "Stable mode requires a version."
    else:
        raise AssertionError("Expected ValueError when stable mode has no version")


def test_extract_returns_none_when_section_missing():
    module = load_module()

    notes = module.extract_release_notes(SAMPLE_CHANGELOG, mode="stable", version="9.9.9")

    assert notes == ""
