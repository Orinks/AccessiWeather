"""
Build GitHub Pages content from release data.

Fetches release information from the GitHub API, renders release notes
as HTML, and generates the pages index from a template.

Environment variables:
    GITHUB_TOKEN: GitHub API token for authenticated requests
    GITHUB_REPOSITORY: Repository in owner/repo format
"""

from __future__ import annotations

import datetime as dt
import html
import json
import os
import urllib.request


def request_json(url: str, token: str) -> list[dict]:
    """Fetch JSON from a GitHub API endpoint."""
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def render_markdown(text: str, token: str, repo: str) -> str:
    """Convert markdown to HTML using GitHub's Markdown API."""
    if not text.strip():
        return ""
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
    }
    data = json.dumps(
        {
            "text": text,
            "mode": "gfm",
            "context": repo,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://api.github.com/markdown",
        data=data,
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.read().decode("utf-8")
    except Exception:
        return f"<pre>{html.escape(text)}</pre>"


def latest_release(releases: list[dict], is_prerelease: bool) -> dict | None:
    """Find the latest release matching prerelease status."""
    for rel in releases:
        if rel.get("draft"):
            continue
        if rel.get("prerelease", False) == is_prerelease:
            return rel
    return None


def format_date(date_str: str | None) -> str:
    """Format an ISO date string to a readable format."""
    if not date_str:
        return "N/A"
    try:
        dt_obj = dt.datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt_obj.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return date_str


def get_asset_info(release: dict | None, releases_url: str) -> dict[str, dict]:
    """Extract asset download URLs and download counts from a release."""
    result = {
        "installer": {"url": releases_url, "downloads": 0},
        "portable": {"url": releases_url, "downloads": 0},
        "macos": {"url": releases_url, "downloads": 0},
        "total_downloads": 0,
    }
    if not release:
        return result
    assets = release.get("assets", [])
    release_url = release.get("html_url", releases_url)
    total = 0
    for asset in assets:
        name = asset.get("name", "").lower()
        url = asset.get("browser_download_url", release_url)
        downloads = asset.get("download_count", 0)
        total += downloads
        if name.endswith(".msi") or "setup" in name and name.endswith(".exe"):
            result["installer"] = {"url": url, "downloads": downloads}
        elif "portable" in name and name.endswith(".zip"):
            result["portable"] = {"url": url, "downloads": downloads}
        elif name.endswith(".dmg"):
            result["macos"] = {"url": url, "downloads": downloads}
    result["total_downloads"] = total
    return result


def format_downloads(count: int) -> str:
    """Format download count with thousands separator."""
    if count >= 1000:
        return f"{count:,}"
    return str(count)


def build_pages() -> None:
    """Build GitHub Pages content from release data."""
    repo = os.environ["GITHUB_REPOSITORY"]
    token = os.environ.get("GITHUB_TOKEN", "")
    releases_url = f"https://github.com/{repo}/releases"

    releases = request_json(
        f"https://api.github.com/repos/{repo}/releases?per_page=100",
        token,
    )
    stable = latest_release(releases, False)
    prerelease = latest_release(releases, True)

    main_version = (stable or {}).get("tag_name", "Latest Release").lstrip("v")
    main_date = format_date((stable or {}).get("published_at"))
    main_commit = (stable or {}).get("target_commitish", "")
    main_has_release = "true" if stable else "false"
    main_assets = get_asset_info(stable, releases_url)
    main_notes_raw = (stable or {}).get("body", "")
    if main_notes_raw:
        main_notes = render_markdown(main_notes_raw, token, repo)
    else:
        main_notes = (
            f'<p>No stable release available. <a href="{releases_url}">View releases</a></p>'
        )

    dev_version = (prerelease or {}).get("tag_name", "Development").lstrip("v")
    dev_date = format_date((prerelease or {}).get("published_at"))
    dev_commit = (prerelease or {}).get("target_commitish", "")
    dev_release_url = (prerelease or {}).get("html_url", releases_url)
    dev_has_release = "true" if prerelease else "false"
    dev_assets = get_asset_info(prerelease, releases_url)
    dev_notes_raw = (prerelease or {}).get("body", "")
    if dev_notes_raw:
        dev_notes = render_markdown(dev_notes_raw, token, repo)
    else:
        dev_notes = f'<p>No pre-release available. <a href="{releases_url}">View releases</a></p>'

    last_updated = dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    substitutions = {
        "MAIN_VERSION": main_version,
        "MAIN_DATE": main_date,
        "MAIN_COMMIT": main_commit,
        "MAIN_INSTALLER_URL": main_assets["installer"]["url"],
        "MAIN_PORTABLE_URL": main_assets["portable"]["url"],
        "MAIN_MACOS_INSTALLER_URL": main_assets["macos"]["url"],
        "MAIN_INSTALLER_DOWNLOADS": format_downloads(main_assets["installer"]["downloads"]),
        "MAIN_PORTABLE_DOWNLOADS": format_downloads(main_assets["portable"]["downloads"]),
        "MAIN_MACOS_DOWNLOADS": format_downloads(main_assets["macos"]["downloads"]),
        "MAIN_TOTAL_DOWNLOADS": format_downloads(main_assets["total_downloads"]),
        "MAIN_HAS_RELEASE": main_has_release,
        "MAIN_RELEASE_NOTES": main_notes,
        "DEV_VERSION": dev_version,
        "DEV_DATE": dev_date,
        "DEV_COMMIT": dev_commit,
        "DEV_RELEASE_URL": dev_release_url,
        "DEV_INSTALLER_URL": dev_assets["installer"]["url"],
        "DEV_PORTABLE_URL": dev_assets["portable"]["url"],
        "DEV_MACOS_INSTALLER_URL": dev_assets["macos"]["url"],
        "DEV_INSTALLER_DOWNLOADS": format_downloads(dev_assets["installer"]["downloads"]),
        "DEV_PORTABLE_DOWNLOADS": format_downloads(dev_assets["portable"]["downloads"]),
        "DEV_MACOS_DOWNLOADS": format_downloads(dev_assets["macos"]["downloads"]),
        "DEV_TOTAL_DOWNLOADS": format_downloads(dev_assets["total_downloads"]),
        "DEV_HAS_RELEASE": dev_has_release,
        "DEV_RELEASE_NOTES": dev_notes,
        "LAST_UPDATED": last_updated,
    }

    with open("docs/index.template.html", encoding="utf-8") as f:
        html_content = f.read()
    for key, value in substitutions.items():
        html_content = html_content.replace(f"{{{{{key}}}}}", value)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)

    with open("docs/download-links.md", "w", encoding="utf-8") as f:
        f.write(
            "# AccessiWeather Download Links\n\n"
            f"All downloads are on GitHub: {releases_url}\n\n"
            "## Build Info\n\n"
            f"- Main version: {main_version}\n"
            f"- Main date: {main_date}\n"
            f"- Dev version: {dev_version}\n"
            f"- Dev date: {dev_date}\n"
            f"- Last updated: {last_updated}\n"
        )

    with open(".nojekyll", "w", encoding="utf-8") as f:
        f.write("")


if __name__ == "__main__":
    build_pages()
