"""Update the existing WordPress release page from GitHub stable + nightly releases."""

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
NIGHTLY_COUNT = 5

START_MARKER = "<!-- accessiweather-release:start -->"
END_MARKER = "<!-- accessiweather-release:end -->"
DEFAULT_SECTION_HEADING = "Download AccessiWeather"
DEFAULT_SECTION_DESCRIPTION = "Download the latest stable release directly, or grab one of the newest nightly builds if you want the freshest fixes and features."

GH_API_HEADERS: dict[str, str] = {
    "Accept": "application/vnd.github+json",
}
if GH_TOKEN:
    GH_API_HEADERS["Authorization"] = f"Bearer {GH_TOKEN}"


@dataclass(frozen=True)
class ReleaseAsset:
    name: str
    url: str
    download_count: int
    kind: str
    label: str


@dataclass(frozen=True)
class ReleaseInfo:
    tag_name: str
    name: str
    published_at: str
    html_url: str
    body: str
    assets: list[ReleaseAsset]
    total_downloads: int
    primary_asset: ReleaseAsset
    prerelease: bool


def gh_json(endpoint: str, allow_missing: bool = False) -> Any:
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
    if not date_str:
        return "Unknown"
    parsed = dt.datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    return parsed.strftime("%B %d, %Y")


def format_count(value: int) -> str:
    return f"{value:,}"


def normalize_release(release: dict[str, Any]) -> ReleaseInfo:
    assets = [
        classified for asset in release.get("assets", []) if (classified := classify_asset(asset))
    ]
    html_url = release.get("html_url", f"https://github.com/{REPO}/releases")
    return ReleaseInfo(
        tag_name=str(release.get("tag_name", "")),
        name=str(release.get("name") or release.get("tag_name") or "Release"),
        published_at=format_date(release.get("published_at")),
        html_url=html_url,
        body=str(release.get("body") or "").strip(),
        assets=assets,
        total_downloads=sum(asset.download_count for asset in assets),
        primary_asset=select_primary_asset(assets, html_url),
        prerelease=bool(release.get("prerelease", False)),
    )


def build_release_context(
    stable_release: dict[str, Any], nightly_releases: list[dict[str, Any]]
) -> dict[str, Any]:
    stable = normalize_release(stable_release)
    nightlies = [normalize_release(release) for release in nightly_releases[:NIGHTLY_COUNT]]
    return {
        "stable": stable,
        "nightlies": nightlies,
    }


def find_asset(assets: list[ReleaseAsset], kind: str) -> ReleaseAsset | None:
    for asset in assets:
        if asset.kind == kind:
            return asset
    return None


def render_asset_links(
    assets: list[ReleaseAsset], *, exclude_urls: set[str] | None = None
) -> str:
    if not assets:
        return ""

    exclude_urls = exclude_urls or set()
    links: list[str] = []
    seen_kinds: set[str] = set()
    for asset in assets:
        if asset.url in exclude_urls:
            continue
        if asset.kind in seen_kinds:
            continue
        seen_kinds.add(asset.kind)
        links.append(
            "<li>"
            f'<a href="{html.escape(asset.url, quote=True)}">{html.escape(asset.label)}</a>'
            f" ({format_count(asset.download_count)} downloads)"
            "</li>"
        )
    return ("<ul>" + "".join(links) + "</ul>") if links else ""


def _inline_markdown_to_html(text: str) -> str:
    rendered = html.escape(text)
    rendered = re.sub(r"`([^`]+)`", r"<code>\1</code>", rendered)
    rendered = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', rendered)
    rendered = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", rendered)
    rendered = re.sub(r"__([^_]+)__", r"<strong>\1</strong>", rendered)
    rendered = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", rendered)
    return re.sub(r"(?<!_)_([^_]+)_(?!_)", r"<em>\1</em>", rendered)


def render_release_notes(body: str, *, max_items: int | None = None) -> str:
    if not body.strip():
        return "<p>No release notes published for this release yet.</p>"

    blocks: list[str] = []
    in_list = False
    list_items = 0
    paragraph_lines: list[str] = []

    def flush_paragraph() -> None:
        nonlocal paragraph_lines
        if paragraph_lines:
            text = " ".join(line.strip() for line in paragraph_lines if line.strip())
            if text:
                blocks.append(f"<p>{_inline_markdown_to_html(text)}</p>")
            paragraph_lines = []

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            blocks.append("</ul>")
            in_list = False

    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            flush_paragraph()
            close_list()
            continue

        heading_match = re.match(r"^(#{1,3})\s+(.+)$", line)
        if heading_match:
            flush_paragraph()
            close_list()
            level = min(len(heading_match.group(1)) + 2, 6)
            heading_text = _inline_markdown_to_html(heading_match.group(2).strip())
            blocks.append(f"<h{level}>{heading_text}</h{level}>")
            continue

        list_match = re.match(r"^[-*]\s+(.+)$", line)
        if list_match:
            flush_paragraph()
            if max_items is not None and list_items >= max_items:
                continue
            if not in_list:
                blocks.append("<ul>")
                in_list = True
            blocks.append(f"<li>{_inline_markdown_to_html(list_match.group(1).strip())}</li>")
            list_items += 1
            continue

        close_list()
        paragraph_lines.append(line)

    flush_paragraph()
    close_list()
    return "".join(blocks) or "<p>No release notes published for this release yet.</p>"


def render_nightly_notes_summary(release: ReleaseInfo) -> str:
    return render_release_notes(release.body, max_items=10)


def ordered_unique_assets(
    assets: list[ReleaseAsset], *, primary: ReleaseAsset | None = None
) -> list[ReleaseAsset]:
    seen_urls: set[str] = set()
    ordered_assets = list(assets)
    if primary is not None:
        ordered_assets.sort(key=lambda asset: 0 if asset.url == primary.url else 1)

    unique_assets: list[ReleaseAsset] = []
    for asset in ordered_assets:
        if asset.url in seen_urls:
            continue
        seen_urls.add(asset.url)
        unique_assets.append(asset)
    return unique_assets


def render_download_actions(assets: list[ReleaseAsset], *, primary: ReleaseAsset | None = None) -> list[str]:
    return [
        f'<a href="{html.escape(asset.url, quote=True)}">Download {html.escape(asset.label)}</a>'
        for asset in ordered_unique_assets(assets, primary=primary)
    ]


def render_nightly_card(release: ReleaseInfo) -> str:
    primary = release.primary_asset
    actions = render_download_actions(release.assets, primary=primary)
    actions.append(f'<a href="{html.escape(release.html_url, quote=True)}">Full release</a>')
    return (
        '<li class="accessiweather-nightly-card">'
        f"<h4>{html.escape(release.published_at)} ({html.escape(release.tag_name)})</h4>"
        f"<div>{' · '.join(actions)}"
        f" · {format_count(release.total_downloads)} downloads</div>"
        f'<div class="accessiweather-nightly-notes">{render_nightly_notes_summary(release)}</div>'
        "</li>"
    )


def render_release_section(context: dict[str, Any]) -> str:
    stable: ReleaseInfo = context["stable"]
    nightlies: list[ReleaseInfo] = context["nightlies"]

    promoted_assets = ordered_unique_assets(stable.assets, primary=stable.primary_asset)
    promoted_urls = {asset.url for asset in promoted_assets}
    stable_links = render_asset_links(stable.assets, exclude_urls=promoted_urls)
    nightly_items = "".join(render_nightly_card(release) for release in nightlies)
    nightly_html = (
        '<div class="accessiweather-nightlies">'
        "<h3>Latest Nightly Builds</h3>"
        "<p>The newest pre-release builds from the dev branch.</p>"
        f"<ul>{nightly_items}</ul>"
        "</div>"
        if nightly_items
        else ""
    )

    primary = stable.primary_asset
    stable_buttons = []
    for i, asset in enumerate(ordered_unique_assets(stable.assets, primary=primary)):
        button_class = '' if i == 0 else ' is-style-outline'
        stable_buttons.append(
            f'<div class="wp-block-button{button_class}">'
            f'<a class="wp-block-button__link wp-element-button" href="{html.escape(asset.url, quote=True)}">Download {html.escape(asset.label)}</a>'
            '</div>'
        )
    stable_buttons.append(
        '<div class="wp-block-button is-style-outline">'
        f'<a class="wp-block-button__link wp-element-button" href="{html.escape(stable.html_url, quote=True)}">View release notes</a>'
        '</div>'
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
  <!-- wp:group -->
  <div class="wp-block-group accessiweather-release-stable">
    <h3>Stable ({html.escape(stable.tag_name.lstrip("v"))})</h3>
    <div class="wp-block-buttons">
      {''.join(stable_buttons)}
    </div>
    <ul>
      <li><strong>Version:</strong> {html.escape(stable.tag_name.lstrip("v"))}</li>
      <li><strong>Release date:</strong> {html.escape(stable.published_at)}</li>
      <li><strong>Total downloads:</strong> {format_count(stable.total_downloads)}</li>
    </ul>
    {stable_links}
    <div class="accessiweather-release-notes">
      <h4>What&apos;s new</h4>
      {render_release_notes(stable.body)}
    </div>
  </div>
  <!-- /wp:group -->
  {nightly_html}
</div>
<!-- /wp:group -->
{END_MARKER}
""".strip()


def replace_managed_section(existing_content: str, generated_section: str) -> str:
    pattern = re.compile(
        rf"{re.escape(START_MARKER)}.*?{re.escape(END_MARKER)}",
        flags=re.DOTALL,
    )
    if pattern.search(existing_content):
        return pattern.sub(generated_section, existing_content, count=1)

    legacy_pattern = re.compile(
        r"<!-- download-links:accessiweather-stable -->.*?<!-- /download-links:accessiweather-nightly -->",
        flags=re.DOTALL,
    )
    if legacy_pattern.search(existing_content):
        return legacy_pattern.sub(generated_section, existing_content, count=1)

    stripped_content = existing_content.rstrip()
    if not stripped_content:
        return generated_section
    return f"{stripped_content}\n\n{generated_section}\n"


def fetch_page() -> dict[str, Any]:
    return wp_request(f"/wp-json/wp/v2/pages/{WP_PAGE_ID}", query={"context": "edit"})


def update_page_content(content: str) -> dict[str, Any]:
    return wp_request(
        f"/wp-json/wp/v2/pages/{WP_PAGE_ID}",
        method="POST",
        payload={"content": content},
    )


def fetch_latest_stable_release() -> dict[str, Any]:
    latest = gh_json(f"repos/{REPO}/releases/latest", allow_missing=True)
    if not isinstance(latest, dict) or not latest.get("tag_name"):
        raise RuntimeError(f"No public stable GitHub release found for {REPO}")
    return latest


def fetch_recent_nightlies() -> list[dict[str, Any]]:
    releases = gh_json(f"repos/{REPO}/releases?per_page=20")
    if not isinstance(releases, list):
        return []
    nightlies = [
        release
        for release in releases
        if isinstance(release, dict)
        and release.get("prerelease")
        and str(release.get("tag_name", "")).startswith("nightly-")
        and not release.get("draft")
    ]
    return nightlies[:NIGHTLY_COUNT]


def main() -> None:
    stable_release = fetch_latest_stable_release()
    nightly_releases = fetch_recent_nightlies()
    context = build_release_context(stable_release, nightly_releases)
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
        "stable",
        context["stable"].tag_name,
        "nightlies",
        len(context["nightlies"]),
    )


if __name__ == "__main__":
    main()
