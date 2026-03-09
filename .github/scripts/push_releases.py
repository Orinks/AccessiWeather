"""Update the existing WordPress release page from the latest public GitHub release."""

from __future__ import annotations

import base64
import datetime as dt
import html
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

REPO = os.environ["REPO"]
WP_URL = os.environ["WP_URL"].rstrip("/")
WP_PAGE_ID = os.environ["WP_PAGE_ID"]
WP_USERNAME = os.environ["WP_USERNAME"]
WP_APPLICATION_PASSWORD = os.environ["WP_APPLICATION_PASSWORD"]
GH_TOKEN = os.environ.get("GITHUB_TOKEN")

START_MARKER = "<!-- accessiweather-release:start -->"
END_MARKER = "<!-- accessiweather-release:end -->"
DEFAULT_SECTION_HEADING = "Download AccessiWeather"
DEFAULT_SECTION_DESCRIPTION = (
    "Get the latest stable AccessiWeather release directly from GitHub Releases."
)

GH_API_HEADERS: dict[str, str] = {
    "Accept": "application/vnd.github+json",
}
if GH_TOKEN:
    GH_API_HEADERS["Authorization"] = f"Bearer {GH_TOKEN}"


@dataclass(frozen=True)
class ReleaseAsset:
    """Normalized release asset information used for page rendering."""

    name: str
    url: str
    download_count: int
    kind: str
    label: str


def gh_json(endpoint: str, allow_missing: bool = False) -> Any:
    """Fetch JSON from the GitHub API."""
    request = urllib.request.Request(f"https://api.github.com/{endpoint}", headers=GH_API_HEADERS)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        if allow_missing and exc.code == 404:
            return None
        raise


def wp_request(
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    query: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Call the WordPress REST API using Application Password auth."""
    auth = base64.b64encode(f"{WP_USERNAME}:{WP_APPLICATION_PASSWORD}".encode()).decode("ascii")
    url = f"{WP_URL}{path}"
    if query:
        url = f"{url}?{urllib.parse.urlencode(query)}"

    headers = {
        "Authorization": f"Basic {auth}",
        "Accept": "application/json",
    }
    data: bytes | None = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def classify_asset(asset: dict[str, Any]) -> ReleaseAsset | None:
    """Return a display asset for page links, or None for sidecar files."""
    name = str(asset.get("name", ""))
    lower_name = name.lower()
    url = str(asset.get("browser_download_url", ""))
    download_count = int(asset.get("download_count", 0))

    if lower_name.endswith((".sha256", ".sha256sum", ".txt", ".sig", ".asc")):
        return None
    if lower_name.endswith(".exe") and ("setup" in lower_name or "installer" in lower_name):
        return ReleaseAsset(name, url, download_count, "windows-installer", "Windows installer")
    if lower_name.endswith(".msi"):
        return ReleaseAsset(name, url, download_count, "windows-installer", "Windows installer")
    if lower_name.endswith(".zip") and "portable" in lower_name:
        return ReleaseAsset(name, url, download_count, "windows-portable", "Windows portable")
    if lower_name.endswith(".dmg"):
        return ReleaseAsset(name, url, download_count, "macos", "macOS")
    if lower_name.endswith(".appimage"):
        return ReleaseAsset(name, url, download_count, "linux", "Linux AppImage")
    return None


def select_primary_asset(assets: list[ReleaseAsset], release_url: str) -> ReleaseAsset:
    """Choose the main download target shown in the page button."""
    priority = {
        "windows-installer": 0,
        "windows-portable": 1,
        "macos": 2,
        "linux": 3,
    }
    if assets:
        return sorted(assets, key=lambda asset: priority.get(asset.kind, 99))[0]
    return ReleaseAsset(
        name="GitHub release",
        url=release_url,
        download_count=0,
        kind="release-page",
        label="Latest release",
    )


def format_date(date_str: str | None) -> str:
    """Format GitHub timestamps for the page."""
    if not date_str:
        return "Unknown"
    parsed = dt.datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    return parsed.strftime("%B %d, %Y")


def format_count(value: int) -> str:
    """Add separators for download counts."""
    return f"{value:,}"


def build_release_context(release: dict[str, Any]) -> dict[str, Any]:
    """Build the page rendering context from the latest GitHub release."""
    assets = [
        classified for asset in release.get("assets", []) if (classified := classify_asset(asset))
    ]
    primary_asset = select_primary_asset(
        assets,
        release.get("html_url", f"https://github.com/{REPO}/releases"),
    )
    total_downloads = sum(asset.download_count for asset in assets)

    return {
        "version": str(release.get("tag_name", "Latest release")).lstrip("v"),
        "published_at": format_date(release.get("published_at")),
        "release_url": release.get("html_url", f"https://github.com/{REPO}/releases"),
        "primary_asset": primary_asset,
        "assets": assets,
        "total_downloads": total_downloads,
    }


def render_release_section(context: dict[str, Any]) -> str:
    """Render the generated HTML block that lives inside the existing WP page."""
    primary_asset: ReleaseAsset = context["primary_asset"]
    assets: list[ReleaseAsset] = context["assets"]
    version = html.escape(context["version"])
    published_at = html.escape(context["published_at"])
    primary_label = html.escape(primary_asset.label)
    primary_url = html.escape(primary_asset.url, quote=True)
    release_url = html.escape(context["release_url"], quote=True)
    total_downloads = format_count(context["total_downloads"])

    platform_links: list[str] = []
    seen_kinds: set[str] = set()
    for asset in assets:
        if asset.kind in seen_kinds:
            continue
        seen_kinds.add(asset.kind)
        platform_links.append(
            "<li>"
            f'<a href="{html.escape(asset.url, quote=True)}">{html.escape(asset.label)}</a>'
            f" ({format_count(asset.download_count)} downloads)"
            "</li>"
        )

    platform_links_html = "\n".join(platform_links)
    if platform_links_html:
        platform_links_html = (
            '<div class="accessiweather-release-links">'
            "<p><strong>Available downloads</strong></p>"
            f"<ul>{platform_links_html}</ul>"
            "</div>"
        )

    return f"""
{START_MARKER}
<!-- wp:group {{"layout":{{"type":"constrained"}}}} -->
<div class="wp-block-group accessiweather-release-downloads">
  <!-- wp:heading {{"level":2}} -->
  <h2>{html.escape(DEFAULT_SECTION_HEADING)}</h2>
  <!-- /wp:heading -->
  <!-- wp:paragraph -->
  <p>{html.escape(DEFAULT_SECTION_DESCRIPTION)}</p>
  <!-- /wp:paragraph -->
  <!-- wp:buttons -->
  <div class="wp-block-buttons">
    <!-- wp:button -->
    <div class="wp-block-button">
      <a class="wp-block-button__link wp-element-button" href="{primary_url}">Download {primary_label}</a>
    </div>
    <!-- /wp:button -->
    <!-- wp:button {{"className":"is-style-outline"}} -->
    <div class="wp-block-button is-style-outline">
      <a class="wp-block-button__link wp-element-button" href="{release_url}">View release notes</a>
    </div>
    <!-- /wp:button -->
  </div>
  <!-- /wp:buttons -->
  <!-- wp:list -->
  <ul>
    <li><strong>Version:</strong> {version}</li>
    <li><strong>Release date:</strong> {published_at}</li>
    <li><strong>Total downloads:</strong> {total_downloads}</li>
  </ul>
  <!-- /wp:list -->
  {platform_links_html}
</div>
<!-- /wp:group -->
{END_MARKER}
""".strip()


def replace_managed_section(existing_content: str, generated_section: str) -> str:
    """Replace the managed page fragment or append it if no markers exist yet."""
    pattern = re.compile(
        rf"{re.escape(START_MARKER)}.*?{re.escape(END_MARKER)}",
        flags=re.DOTALL,
    )
    if pattern.search(existing_content):
        return pattern.sub(generated_section, existing_content, count=1)
    stripped_content = existing_content.rstrip()
    if not stripped_content:
        return generated_section
    return f"{stripped_content}\n\n{generated_section}\n"


def fetch_page() -> dict[str, Any]:
    """Load the target page with raw editable content."""
    return wp_request(f"/wp-json/wp/v2/pages/{WP_PAGE_ID}", query={"context": "edit"})


def update_page_content(content: str) -> dict[str, Any]:
    """Persist new page content to WordPress."""
    return wp_request(
        f"/wp-json/wp/v2/pages/{WP_PAGE_ID}",
        method="POST",
        payload={"content": content},
    )


def fetch_latest_release() -> dict[str, Any]:
    """Get the latest public stable release for the repository."""
    latest = gh_json(f"repos/{REPO}/releases/latest", allow_missing=True)
    if not isinstance(latest, dict) or not latest.get("tag_name"):
        raise RuntimeError(f"No public stable GitHub release found for {REPO}")
    return latest


def main() -> None:
    release = fetch_latest_release()
    context = build_release_context(release)
    generated_section = render_release_section(context)

    page = fetch_page()
    existing_content = (
        page.get("content", {}).get("raw") or page.get("content", {}).get("rendered") or ""
    )
    updated_content = replace_managed_section(existing_content, generated_section)
    if updated_content == existing_content:
        print(f"No WordPress content changes needed for page {WP_PAGE_ID}")
        return

    result = update_page_content(updated_content)
    print(
        "Updated page",
        result.get("id", WP_PAGE_ID),
        "to",
        context["version"],
        "with primary asset",
        context["primary_asset"].name,
        f"and {context['total_downloads']} total downloads",
    )


if __name__ == "__main__":
    main()
