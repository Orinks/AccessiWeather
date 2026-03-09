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


def test_replace_managed_section_appends_when_markers_missing():
    module = load_module()

    updated = module.replace_managed_section("<p>Intro</p>", "NEW BLOCK")

    assert updated.startswith("<p>Intro</p>")
    assert updated.rstrip().endswith("NEW BLOCK")
