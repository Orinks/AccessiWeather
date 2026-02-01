from __future__ import annotations

from pathlib import Path

from accessiweather.services.simple_update import (
    build_portable_update_script,
    is_nightly_release,
    is_update_available,
    parse_commit_hash,
    plan_restart,
    select_asset,
    select_latest_release,
)


def _release(**overrides):
    data = {
        "tag_name": "v1.0.0",
        "prerelease": False,
        "body": "",
        "published_at": "2025-01-01T00:00:00Z",
        "assets": [],
    }
    data.update(overrides)
    return data


def test_parse_commit_hash_prefers_commit_label():
    notes = "Changelog\n\nCommit: abcdef1234567890"
    assert parse_commit_hash(notes) == "abcdef1234567890"


def test_is_nightly_release_from_commit_hash():
    release = _release(body="Nightly build\nCommit hash=deadbeef")
    assert is_nightly_release(release) is True


def test_select_latest_release_stable_filters_prerelease_and_nightly():
    releases = [
        _release(tag_name="v1.0.0", published_at="2025-01-01T00:00:00Z"),
        _release(tag_name="v1.1.0", prerelease=True, published_at="2025-02-01T00:00:00Z"),
        _release(
            tag_name="nightly-20250202",
            body="Commit: 1111111",
            published_at="2025-02-02T00:00:00Z",
        ),
    ]
    latest = select_latest_release(releases, "stable")
    assert latest["tag_name"] == "v1.0.0"


def test_is_update_available_stable_version_compare():
    release = _release(tag_name="v1.2.0")
    assert is_update_available(release, "1.1.0", None) is True
    assert is_update_available(release, "1.2.0", None) is False


def test_is_update_available_nightly_commit_compare():
    release = _release(tag_name="nightly-20250101", body="Commit: a1b2c3d")
    assert is_update_available(release, "1.0.0", "deadbeef") is True
    assert is_update_available(release, "1.0.0", "a1b2c3d") is False


def test_select_asset_windows_portable():
    release = _release(
        assets=[
            {"name": "AccessiWeather_Setup_v1.0.0.exe"},
            {"name": "AccessiWeather_Portable_v1.0.0.zip"},
        ]
    )
    asset = select_asset(release, portable=True, platform_system="Windows")
    assert asset["name"].endswith(".zip")


def test_build_portable_update_script_contains_extract_and_restart():
    script = build_portable_update_script(
        Path("C:/temp/update.zip"),
        Path("C:/Program Files/AccessiWeather"),
        Path("C:/Program Files/AccessiWeather/AccessiWeather.exe"),
    )
    assert "Expand-Archive" in script
    assert "start" in script


def test_plan_restart_windows_installer():
    plan = plan_restart(Path("C:/temp/installer.exe"), portable=False, platform_system="Windows")
    assert plan.kind == "windows_installer"
