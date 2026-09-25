"""
Golden outputs for `cargo xtask pages` from `scripts/build_pages.py`.

The GitHub API calls are replaced: releases come from fixtures, Markdown
renders through a stand-in the Rust test repeats, and the clock is fixed.

Run from the Python checkout:
    uv run python <worktree>/rust/tools/golden/pages.py
Writes rust/testdata/golden/pages/cases.json.
"""

from __future__ import annotations

import copy
import datetime as dt
import html
import importlib.util
import json
import os
import re
import tempfile
from pathlib import Path
from types import SimpleNamespace

RUST = Path(__file__).resolve().parents[2]
ROOT = RUST.parent
OUT = RUST / "testdata" / "golden" / "pages" / "cases.json"
RELEASES = json.loads((RUST / "testdata" / "services" / "github_releases.json").read_text("utf-8"))

spec = importlib.util.spec_from_file_location("build_pages", ROOT / "scripts" / "build_pages.py")
bp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bp)


class FixedDateTime(dt.datetime):
    @classmethod
    def utcnow(cls):
        return cls(2026, 9, 25, 12, 34, 56)


bp.dt = SimpleNamespace(datetime=FixedDateTime)


def fake_markdown(text: str, token: str, repo: str) -> str:
    if not text.strip():
        return ""
    return f'<div data-repo="{repo}">{html.escape(text)}</div>'


bp.render_markdown = fake_markdown


def with_counts(releases):
    out = copy.deepcopy(releases)
    for i, release in enumerate(out):
        for j, asset in enumerate(release["assets"]):
            asset["download_count"] = (i + 1) * 997 * (j + 1)
    return out


rust_release = {
    "tag_name": "v0.11.0",
    "prerelease": False,
    "draft": False,
    "published_at": "2026-10-01T09:05:00Z",
    "target_commitish": "main",
    "html_url": "https://github.com/Orinks/AccessiWeather/releases/tag/v0.11.0",
    "body": "## Added\n- Native <edition> & \"quotes\" 'too'\n",
    "assets": [
        {"name": n, "browser_download_url": f"https://example.test/{n}", "download_count": c}
        for n, c in [
            ("AccessiWeather-0.11.0-linux-x86_64.AppImage", 5),
            ("AccessiWeather-0.11.0-macOS.dmg", 1500),
            ("AccessiWeather-0.11.0-macOS.zip", 7),
            ("AccessiWeather-0.11.0-windows-portable.zip", 12345),
            ("AccessiWeather-0.11.0-windows-setup.exe", 1234567),
            ("checksums.txt", 3),
        ]
    ],
}

CASES = {
    "recorded": RELEASES,
    "recorded with counts": with_counts(RELEASES),
    "rust release first": [rust_release, *RELEASES],
    "draft skipped": [{**rust_release, "draft": True}, *RELEASES[:2]],
    "only prereleases": [r for r in RELEASES if r.get("prerelease")][:2],
    "only stable, blank body": [{**rust_release, "body": "   \n", "published_at": "not a date"}],
    "empty body and no date": [{**rust_release, "body": "", "published_at": None}],
    "msi and missing urls": [
        {
            "tag_name": "vv1.0",
            "prerelease": True,
            "assets": [{"name": "App.MSI"}, {"name": "Portable.ZIP", "download_count": 1000}],
        }
    ],
    "none": [],
}


def main() -> None:
    real = (ROOT / "docs" / "index.template.html").read_text(encoding="utf-8")
    # Only one case renders the real page; the rest use every placeholder
    # once, which keeps the golden file small.
    compact = "\n".join(sorted(set(re.findall(r"\{\{[A-Z_]*\}\}", real)))) + "\n"
    cases = []
    cwd = os.getcwd()
    for name, releases in CASES.items():
        full = name == "rust release first"
        template = real if full else compact
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "docs").mkdir()
            (Path(tmp) / "docs" / "index.template.html").write_bytes(template.encode("utf-8"))
            bp.request_json = lambda url, token, releases=releases: copy.deepcopy(releases)
            os.environ["GITHUB_REPOSITORY"] = "Orinks/AccessiWeather"
            os.environ["GITHUB_TOKEN"] = "unused"
            os.chdir(tmp)
            try:
                bp.build_pages()
            finally:
                os.chdir(cwd)

            def read(rel, tmp=tmp):
                return (Path(tmp) / rel).read_bytes().decode("utf-8").replace("\r\n", "\n")

            cases.append(
                {
                    "name": name,
                    "full_template": full,
                    "repo": "Orinks/AccessiWeather",
                    "releases": releases,
                    "index": read("index.html"),
                    "download_links": read("docs/download-links.md"),
                }
            )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(
            {"template": real, "compact_template": compact, "cases": cases},
            indent=1,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print("wrote", OUT, len(cases), "cases")


if __name__ == "__main__":
    main()
