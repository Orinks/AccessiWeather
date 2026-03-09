from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path


def load_module():
    script_path = Path(__file__).resolve().parents[1] / ".github" / "scripts" / "push_releases.py"
    spec = importlib.util.spec_from_file_location("push_releases", script_path)
    module = importlib.util.module_from_spec(spec)

    original_env = os.environ.copy()
    os.environ.setdefault("REPO", "Orinks/AccessiWeather")
    os.environ.setdefault("WP_URL", "https://example.com")
    os.environ.setdefault("WP_PAGE_ID", "123")
    os.environ.setdefault("WP_USERNAME", "tester")
    os.environ.setdefault("WP_APPLICATION_PASSWORD", "secret")
    try:
        assert spec and spec.loader
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)
        os.environ.clear()
        os.environ.update(original_env)
    return module


def test_classify_asset_filters_sidecars():
    module = load_module()

    assert module.classify_asset({"name": "checksums.txt", "download_count": 10}) is None
    assert module.classify_asset({"name": "AccessiWeather-1.0.0.sig", "download_count": 10}) is None


def test_primary_asset_prefers_windows_installer():
    module = load_module()

    portable = module.ReleaseAsset(
        "portable.zip",
        "https://example.com/portable.zip",
        5,
        "windows-portable",
        "Windows portable",
    )
    installer = module.ReleaseAsset(
        "setup.exe", "https://example.com/setup.exe", 8, "windows-installer", "Windows installer"
    )

    chosen = module.select_primary_asset([portable, installer], "https://example.com/release")

    assert chosen == installer


def test_replace_managed_section_replaces_existing_markers():
    module = load_module()
    existing = "\n".join(
        [
            "<p>Intro</p>",
            module.START_MARKER,
            "<p>Old block</p>",
            module.END_MARKER,
            "<p>Footer</p>",
        ]
    )

    updated = module.replace_managed_section(existing, "NEW BLOCK")

    assert "NEW BLOCK" in updated
    assert "<p>Old block</p>" not in updated
    assert "<p>Intro</p>" in updated
    assert "<p>Footer</p>" in updated


def test_replace_managed_section_replaces_legacy_download_sections():
    module = load_module()
    existing = "\n".join(
        [
            "<p>Intro</p>",
            "<!-- download-links:accessiweather-stable -->",
            "<p>Old stable block</p>",
            "<!-- /download-links:accessiweather-stable -->",
            "<!-- download-links:accessiweather-nightly -->",
            "<p>Old nightly block</p>",
            "<!-- /download-links:accessiweather-nightly -->",
            "<p>Footer</p>",
        ]
    )

    updated = module.replace_managed_section(existing, "NEW BLOCK")

    assert "NEW BLOCK" in updated
    assert "Old stable block" not in updated
    assert "Old nightly block" not in updated
    assert "<p>Footer</p>" in updated


def test_replace_managed_section_appends_when_markers_missing():
    module = load_module()

    updated = module.replace_managed_section("<p>Intro</p>", "NEW BLOCK")

    assert updated.startswith("<p>Intro</p>")
    assert updated.rstrip().endswith("NEW BLOCK")


def test_build_release_context_includes_five_nightlies():
    module = load_module()
    stable_release = {
        "tag_name": "v0.4.3",
        "published_at": "2026-02-11T00:00:00Z",
        "html_url": "https://example.com/stable",
        "body": "## Stable changes\n\n- Added a thing",
        "assets": [
            {
                "name": "AccessiWeather-0.4.3-windows-setup.exe",
                "browser_download_url": "https://example.com/stable.exe",
                "download_count": 12,
            }
        ],
    }
    nightlies = []
    for i in range(1, 7):
        nightlies.append(
            {
                "tag_name": f"nightly-2026030{i}",
                "name": f"Nightly 2026-03-0{i}",
                "published_at": f"2026-03-0{i}T04:00:00Z",
                "html_url": f"https://example.com/nightly-{i}",
                "body": f"## Nightly {i}\n\n- Change {i}\n- Fix {i}",
                "prerelease": True,
                "assets": [
                    {
                        "name": f"AccessiWeather-nightly-2026030{i}-windows-setup.exe",
                        "browser_download_url": f"https://example.com/nightly-{i}.exe",
                        "download_count": i,
                    }
                ],
            }
        )

    context = module.build_release_context(stable_release, nightlies)

    assert context["stable"].tag_name == "v0.4.3"
    assert context["stable"].body == "## Stable changes\n\n- Added a thing"
    assert len(context["nightlies"]) == 5
    assert context["nightlies"][0].tag_name == "nightly-20260301"


def test_render_release_notes_handles_headings_lists_and_links():
    module = load_module()

    html_block = module.render_release_notes(
        "## Highlights\n\n- Added **bold** support\n- Visit [Docs](https://example.com/docs)\n\nA short `code` note."
    )

    assert "<h4>Highlights</h4>" in html_block
    assert "<ul>" in html_block
    assert "<strong>bold</strong>" in html_block
    assert '<a href="https://example.com/docs">Docs</a>' in html_block
    assert "<code>code</code>" in html_block


def test_render_nightly_notes_summary_limits_list_items():
    module = load_module()
    release = module.ReleaseInfo(
        tag_name="nightly-20260309",
        name="Nightly 2026-03-09",
        published_at="March 09, 2026",
        html_url="https://example.com/nightly",
        body="## Changes\n\n- One\n- Two\n- Three\n- Four",
        assets=[],
        total_downloads=0,
        primary_asset=module.ReleaseAsset(
            "setup.exe",
            "https://example.com/nightly.exe",
            0,
            "windows-installer",
            "Windows installer",
        ),
        prerelease=True,
    )

    html_block = module.render_nightly_notes_summary(release)

    assert "<li>One</li>" in html_block
    assert "<li>Three</li>" in html_block
    assert "<li>Four</li>" not in html_block


def test_render_release_section_contains_stable_and_nightlies():
    module = load_module()
    stable_release = {
        "tag_name": "v0.4.3",
        "published_at": "2026-02-11T00:00:00Z",
        "html_url": "https://example.com/stable",
        "body": "## Highlights\n\n- Stable change one\n- Stable change two",
        "assets": [
            {
                "name": "AccessiWeather-0.4.3-windows-setup.exe",
                "browser_download_url": "https://example.com/stable.exe",
                "download_count": 12,
            },
            {
                "name": "AccessiWeather-0.4.3-windows-portable.zip",
                "browser_download_url": "https://example.com/stable-portable.zip",
                "download_count": 7,
            },
        ],
    }
    nightlies = [
        {
            "tag_name": "nightly-20260309",
            "name": "Nightly 2026-03-09",
            "published_at": "2026-03-09T04:00:00Z",
            "html_url": "https://example.com/nightly",
            "body": "## Nightly notes\n\n- Fixed updater\n- Polished layout\n- Improved tests\n- Extra detail",
            "prerelease": True,
            "assets": [
                {
                    "name": "AccessiWeather-nightly-20260309-windows-setup.exe",
                    "browser_download_url": "https://example.com/nightly.exe",
                    "download_count": 3,
                },
                {
                    "name": "AccessiWeather-nightly-20260309-windows-portable.zip",
                    "browser_download_url": "https://example.com/nightly-portable.zip",
                    "download_count": 2,
                },
            ],
        }
    ]

    html_block = module.render_release_section(
        module.build_release_context(stable_release, nightlies)
    )

    assert "Stable (0.4.3)" in html_block
    assert "Latest Nightly Builds" in html_block
    assert "nightly-20260309" in html_block
    assert "What&apos;s new" in html_block
    assert "Stable change one" in html_block
    assert "Fixed updater" in html_block
    assert "Extra detail" not in html_block
    assert "Download Windows portable" in html_block
