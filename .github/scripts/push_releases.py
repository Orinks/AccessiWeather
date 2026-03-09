"""Push GitHub release metadata to the WordPress site."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

REPO = os.environ["REPO"]
WP_URL = os.environ["WP_URL"].rstrip("/")
WP_TOKEN = os.environ["WP_TOKEN"]
BUST_CACHE_FIRST = os.environ.get("BUST_CACHE_FIRST", "false").lower() == "true"
GH_TOKEN = os.environ.get("GITHUB_TOKEN")
HEADERS = {
    "Content-Type": "application/json",
    "X-OGR-Token": WP_TOKEN,
}
GH_API_HEADERS: dict[str, str] = {
    "Accept": "application/vnd.github+json",
}
if GH_TOKEN:
    GH_API_HEADERS["Authorization"] = f"Bearer {GH_TOKEN}"


def gh_json(endpoint: str, allow_missing: bool = False) -> Any:
    url = f"https://api.github.com/{endpoint}"
    request = urllib.request.Request(url, headers=GH_API_HEADERS)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        if allow_missing and exc.code == 404:
            return None
        raise


def fetch_payload() -> dict[str, Any]:
    latest = gh_json(f"repos/{REPO}/releases/latest", allow_missing=True)
    all_releases = gh_json(f"repos/{REPO}/releases?per_page=20", allow_missing=True)
    if not isinstance(all_releases, list):
        all_releases = []
    return {
        "repo": REPO,
        "releases": all_releases[:20],
        "latest": latest if isinstance(latest, dict) and latest.get("tag_name") else None,
    }


def push_releases(payload: dict[str, Any]) -> dict[str, Any]:
    """Transmit release payload to the WordPress endpoint."""
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{WP_URL}/wp-json/ogr/v1/push-releases",
        data=data,
        headers=HEADERS,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def bust_cache() -> dict[str, Any]:
    """Hit the optional bust-cache endpoint so the next push lands on fresh data."""
    req = urllib.request.Request(
        f"{WP_URL}/wp-json/ogr/v1/bust-cache",
        data=b"{}",
        headers=HEADERS,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.load(response)


def main() -> None:
    payload = fetch_payload()

    def attempt() -> dict[str, Any]:
        return push_releases(payload)

    for attempt_num in range(2):
        try:
            result = attempt()
            print(f"Pushed {result['count']} releases for {result['repo']}")
            return
        except Exception as exc:
            print("First push attempt failed." if attempt_num == 0 else "Second push attempt failed.")
            if attempt_num == 0:
                if BUST_CACHE_FIRST:
                    print("Cache nudge enabled. Hitting bust-cache before retry...")
                    bust_result = bust_cache()
                    print("Cache nudge response:", bust_result)
                print("Retrying once in 10s...")
                time.sleep(10)
                continue
            raise


if __name__ == "__main__":
    main()
