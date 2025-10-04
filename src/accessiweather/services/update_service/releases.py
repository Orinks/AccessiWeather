"""Release management helpers for the GitHub update service."""

from __future__ import annotations

import json
import logging
import platform
import time
from pathlib import Path
from typing import Any

import httpx
from packaging.version import Version

from .settings import UpdateSettings

logger = logging.getLogger(__name__)

GITHUB_API_URL = "https://api.github.com/repos/{owner}/{repo}/releases"
CACHE_EXPIRY_SECONDS = 3600  # 1 hour


class ReleaseManager:
    """Handle release fetching, caching, and selection."""

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        owner: str,
        repo: str,
        cache_path: Path,
        settings: UpdateSettings,
    ) -> None:
        """Initialise release management helpers."""
        self.http_client = http_client
        self.owner = owner
        self.repo = repo
        self.cache_path = cache_path
        self.settings = settings
        self._cache: dict[str, Any] | None = None

    async def get_releases(self) -> list[dict[str, Any]]:
        """Return releases from cache or GitHub."""
        cache_valid = (
            self._cache
            and self._cache.get("last_check", 0) + CACHE_EXPIRY_SECONDS > time.time()
            and self._cache.get("channel") == self.settings.channel
            and self._cache.get("owner") == self.owner
            and self._cache.get("repo") == self.repo
        )
        if cache_valid:
            return self._cache.get("releases", [])

        if self.cache_path.exists():
            try:
                with open(self.cache_path, encoding="utf-8") as file:
                    self._cache = json.load(file)
                cache_valid = (
                    self._cache.get("last_check", 0) + CACHE_EXPIRY_SECONDS > time.time()
                    and self._cache.get("channel") == self.settings.channel
                    and self._cache.get("owner") == self.owner
                    and self._cache.get("repo") == self.repo
                )
                if cache_valid:
                    return self._cache.get("releases", [])
            except Exception as exc:  # noqa: BLE001 - log and fall back
                logger.warning(f"Failed to load cache: {exc}")

        url = GITHUB_API_URL.format(owner=self.owner, repo=self.repo) + "?per_page=50"
        headers: dict[str, str] = {}
        etag = self._cache.get("etag") if self._cache else None
        if etag:
            headers["If-None-Match"] = etag

        all_releases: list[dict[str, Any]] = []
        page_count = 0
        next_url: str | None = url
        last_response: httpx.Response | None = None

        try:
            while next_url and page_count < 3:
                response = await self.http_client.get(
                    next_url, headers=headers if page_count == 0 else {}
                )
                last_response = response

                if response.status_code == 403 and response.headers.get("X-RateLimit-Reset"):
                    reset_time = response.headers["X-RateLimit-Reset"]
                    logger.warning(
                        "GitHub API rate limit exceeded; resets at %s. Using cached releases if available.",
                        reset_time,
                    )
                    return self._cache.get("releases", []) if self._cache else []

                if response.status_code == 304 and self._cache and page_count == 0:
                    self._cache["last_check"] = time.time()
                    self._save_cache()
                    return self._cache.get("releases", [])

                response.raise_for_status()
                releases = response.json()
                if isinstance(releases, list):
                    all_releases.extend(releases)
                else:
                    logger.warning("Unexpected releases response type: %s", type(releases))
                    break

                link_header = response.headers.get("Link")
                next_url = None
                if link_header:
                    for part in link_header.split(","):
                        if 'rel="next"' in part:
                            start = part.find("<") + 1
                            end = part.find(">", start)
                            next_url = part[start:end]
                            break
                page_count += 1
        except httpx.TimeoutException:
            logger.warning("GitHub API timeout; using cached releases if available")
            return self._cache.get("releases", []) if self._cache else []
        except httpx.RequestError as exc:
            logger.error(f"Network error: {exc}")
            return self._cache.get("releases", []) if self._cache else []
        except httpx.HTTPStatusError as exc:
            logger.error(f"GitHub API error: {exc}")
            return self._cache.get("releases", []) if self._cache else []
        except Exception as exc:  # noqa: BLE001 - best-effort logging
            logger.error(f"Failed to fetch releases: {exc}")
            return self._cache.get("releases", []) if self._cache else []

        etag = last_response.headers.get("etag") if last_response else None
        self._cache = {
            "last_check": time.time(),
            "releases": all_releases,
            "etag": etag,
            "channel": self.settings.channel,
            "owner": self.owner,
            "repo": self.repo,
        }
        self._save_cache()
        return all_releases

    def _save_cache(self) -> None:
        if not self._cache:
            return
        try:
            with open(self.cache_path, "w", encoding="utf-8") as file:
                json.dump(self._cache, file)
        except Exception as exc:  # noqa: BLE001 - log and continue
            logger.warning(f"Failed to save cache: {exc}")

    @staticmethod
    def filter_releases_by_channel(
        releases: list[dict[str, Any]], channel: str
    ) -> list[dict[str, Any]]:
        """Filter releases according to channel hierarchy."""
        channel = channel.lower()
        filtered: list[dict[str, Any]] = []

        for release in releases:
            tag = release.get("tag_name", "").lower()
            prerelease = release.get("prerelease", False)

            if channel == "stable" and not prerelease:
                filtered.append(release)
            elif channel == "beta":
                if not prerelease or (prerelease and ("beta" in tag or "rc" in tag)):
                    filtered.append(release)
            elif channel == "dev":
                filtered.append(release)

        return filtered

    @staticmethod
    def find_latest_release(
        releases: list[dict[str, Any]], current_version: str
    ) -> dict[str, Any] | None:
        """Find the most recent release newer than the current version."""
        sorted_releases = sorted(releases, key=lambda r: r.get("published_at", ""), reverse=True)
        for release in sorted_releases:
            tag = release.get("tag_name", "")
            if ReleaseManager._is_newer_version(tag, current_version):
                return release
        return None

    @staticmethod
    def _is_newer_version(candidate: str, current: str) -> bool:
        return Version(candidate.lstrip("v")) > Version(current.lstrip("v"))

    @staticmethod
    def find_platform_asset(release: dict[str, Any]) -> dict[str, Any] | None:
        """Choose the best asset for the current platform."""
        assets = release.get("assets", [])
        system = platform.system().lower()

        priority_extensions: list[str] = []
        platform_patterns: list[str] = []

        if "windows" in system:
            priority_extensions = [".exe", ".msi"]
            platform_patterns = ["windows", "win"]
        elif "linux" in system:
            priority_extensions = [".appimage", ".tar.gz", ".deb", ".rpm"]
            platform_patterns = ["linux"]
        elif "darwin" in system or "mac" in system:
            priority_extensions = [".dmg", ".pkg"]
            platform_patterns = ["macos", "darwin", "mac"]

        deny_extensions = [
            ".sha256",
            ".sha512",
            ".md5",
            ".sig",
            ".asc",
            ".txt",
            ".json",
            ".xml",
            ".plist",
        ]
        deny_patterns = ["checksum", "signature", "hash", "verify", "sum"]

        filtered_assets: list[dict[str, Any]] = []
        for asset in assets:
            name = asset.get("name", "").lower()
            if any(ext in name for ext in deny_extensions):
                continue
            if any(pattern in name for pattern in deny_patterns):
                continue
            filtered_assets.append(asset)

        for extension in priority_extensions:
            for asset in filtered_assets:
                name = asset.get("name", "").lower()
                if name.endswith(extension):
                    return asset

        for asset in filtered_assets:
            name = asset.get("name", "").lower()
            if any(pattern in name for pattern in platform_patterns):
                return asset

        if filtered_assets:
            return filtered_assets[0]
        return assets[0] if assets else None
