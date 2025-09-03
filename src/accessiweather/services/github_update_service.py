"""GitHubUpdateService: GitHub-only update service for AccessiWeather.

Replaces TUF functionality. Integrates with GitHub releases API, supports channels, platform asset selection, caching, and diagnostics.
"""

import json
import logging
import platform
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from packaging.version import Version


@dataclass
class UpdateSettings:
    channel: str = "stable"
    owner: str = "orinks"
    repo: str = "accessiweather"


@dataclass
class UpdateInfo:
    version: str
    download_url: str
    artifact_name: str
    release_notes: str = ""
    is_prerelease: bool = False
    file_size: int | None = None


logger = logging.getLogger(__name__)

GITHUB_API_URL = "https://api.github.com/repos/{owner}/{repo}/releases"
CACHE_FILENAME = "github_releases_cache.json"
SETTINGS_FILENAME = "update_settings.json"
DEFAULT_OWNER = "orinks"
DEFAULT_REPO = "accessiweather"
CACHE_EXPIRY_SECONDS = 3600  # 1 hour
USER_AGENT = "AccessiWeather-Updater"


class GitHubUpdateService:
    def __init__(
        self, app_name: str, config_dir: str, owner: str = DEFAULT_OWNER, repo: str = DEFAULT_REPO
    ):
        """Initialize the GitHubUpdateService.

        Sets up configuration, HTTP client, and loads update settings.
        """
        self.app_name = app_name
        self.config_dir = Path(config_dir)
        self.owner = owner
        self.repo = repo
        self.cache_path = self.config_dir / CACHE_FILENAME
        self.settings_path = self.config_dir / SETTINGS_FILENAME
        from ..version import __version__

        self.http_client = httpx.AsyncClient(
            headers={"User-Agent": f"{self.app_name}/{__version__}"}, timeout=30.0
        )
        self.settings = self._load_settings()
        self.owner = self.settings.owner
        self.repo = self.settings.repo
        self.last_channel = self.settings.channel
        self._cache = None

    async def check_for_updates(
        self, method: str | None = None, current_version: str | None = None
    ) -> UpdateInfo | None:
        """Compatibility wrapper for update check. Ignores method, uses current_version or '0.0.0'."""
        releases = await self._get_releases()
        filtered = self._filter_releases_by_channel(releases, self.settings.channel)
        latest = self._find_latest_release(filtered, current_version or "0.0.0")
        if not latest:
            logger.info("No newer release found for channel %s", self.settings.channel)
            return None
        asset = self._find_platform_asset(latest)
        if not asset:
            logger.warning("No suitable asset found for platform")
            return None
        return UpdateInfo(
            version=latest["tag_name"].lstrip("v"),
            download_url=asset["browser_download_url"],
            artifact_name=asset["name"],
            release_notes=latest.get("body", ""),
            is_prerelease=latest.get("prerelease", False),
            file_size=asset.get("size"),
        )

    async def _get_releases(self) -> list[dict[str, Any]]:
        # Use cache if valid and matches current settings
        cache_valid = (
            self._cache
            and self._cache.get("last_check", 0) + CACHE_EXPIRY_SECONDS > time.time()
            and self._cache.get("channel") == self.settings.channel
            and self._cache.get("owner") == self.owner
            and self._cache.get("repo") == self.repo
        )
        if cache_valid:
            return self._cache.get("releases", [])
        # Load cache from disk
        if self.cache_path.exists():
            try:
                with open(self.cache_path, encoding="utf-8") as f:
                    self._cache = json.load(f)
                cache_valid = (
                    self._cache.get("last_check", 0) + CACHE_EXPIRY_SECONDS > time.time()
                    and self._cache.get("channel") == self.settings.channel
                    and self._cache.get("owner") == self.owner
                    and self._cache.get("repo") == self.repo
                )
                if cache_valid:
                    return self._cache.get("releases", [])
            except Exception as e:
                logger.warning(f"Failed to load cache: {e}")

        # Fetch from GitHub with pagination and ETag
        url = GITHUB_API_URL.format(owner=self.owner, repo=self.repo) + "?per_page=50"
        headers = {}
        etag = self._cache.get("etag") if self._cache else None
        if etag:
            headers["If-None-Match"] = etag
        all_releases = []
        page_count = 0
        next_url = url
        try:
            while next_url and page_count < 3:
                resp = await self.http_client.get(
                    next_url, headers=headers if page_count == 0 else {}
                )
                # Rate limit handling
                if resp.status_code == 403 and resp.headers.get("X-RateLimit-Reset"):
                    reset_time = resp.headers["X-RateLimit-Reset"]
                    logger.warning(
                        f"GitHub API rate limit exceeded; resets at {reset_time}. Using cached releases if available."
                    )
                    return self._cache.get("releases", []) if self._cache else []
                # Only send ETag on first request
                if resp.status_code == 304 and self._cache and page_count == 0:
                    # Not modified
                    self._cache["last_check"] = time.time()
                    self._save_cache()
                    return self._cache.get("releases", [])
                resp.raise_for_status()
                releases = resp.json()
                if isinstance(releases, list):
                    all_releases.extend(releases)
                else:
                    logger.warning("Unexpected releases response type: %s", type(releases))
                    break
                # Parse Link header for pagination
                link = resp.headers.get("Link")
                next_url = None
                if link:
                    # Example: <https://api.github.com/.../releases?page=2>; rel="next", <...>; rel="last"
                    parts = link.split(",")
                    for part in parts:
                        if 'rel="next"' in part:
                            start = part.find("<") + 1
                            end = part.find(">", start)
                            next_url = part[start:end]
                            break
                page_count += 1
        except httpx.TimeoutException:
            logger.warning("GitHub API timeout; using cached releases if available")
            return self._cache.get("releases", []) if self._cache else []
        except httpx.RequestError as e:
            logger.error(f"Network error: {e}")
            return self._cache.get("releases", []) if self._cache else []
        except httpx.HTTPStatusError as e:
            logger.error(f"GitHub API error: {e}")
            return self._cache.get("releases", []) if self._cache else []
        except Exception as e:
            logger.error(f"Failed to fetch releases: {e}")
            return self._cache.get("releases", []) if self._cache else []

        # Cache aggregated releases and ETag from first response
        etag = resp.headers.get("etag") if "resp" in locals() else None
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

    def _save_cache(self):
        try:
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(self._cache, f)
        except Exception as e:
            logger.warning(f"Failed to save cache: {e}")

    def _filter_releases_by_channel(self, releases, channel):
        channel = channel.lower()
        out = []
        for rel in releases:
            tag = rel.get("tag_name", "").lower()
            pre = rel.get("prerelease", False)
            if (
                channel == "stable"
                and not pre
                or channel == "beta"
                and pre
                and ("beta" in tag or "rc" in tag)
                or channel == "dev"
            ):
                out.append(rel)
        return out

    def _find_latest_release(self, releases, current_version):
        # Sort releases by published date descending
        releases = sorted(releases, key=lambda r: r.get("published_at", ""), reverse=True)
        for rel in releases:
            tag = rel.get("tag_name", "")
            if self._is_newer_version(tag, current_version):
                return rel
        return None

    def _is_newer_version(self, candidate: str, current: str) -> bool:
        cand = Version(candidate.lstrip("v"))
        curr = Version(current.lstrip("v"))
        return cand > curr

    def _find_platform_asset(self, release):
        assets = release.get("assets", [])
        sys = platform.system().lower()
        patterns = []
        if "windows" in sys:
            patterns = [".exe", ".msi", "windows", "win"]
        elif "linux" in sys:
            patterns = [".tar.gz", ".deb", ".rpm", "linux"]
        elif "darwin" in sys or "mac" in sys:
            patterns = [".dmg", ".pkg", "macos", "darwin"]
        for asset in assets:
            name = asset.get("name", "").lower()
            if any(p in name for p in patterns):
                return asset
        return assets[0] if assets else None

    async def download_update(
        self,
        asset_url,
        dest_path,
        progress_callback=None,
        cancel_event=None,
        expected_sha256=None,
        checksums_url=None,
        artifact_name=None,
    ):
        from pathlib import Path

        # Check cancel_event at start
        if cancel_event and cancel_event.is_set():
            logger.info("Download cancelled before start")
            return False
        # Ensure parent directory exists
        Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
        import hashlib

        try:
            with open(dest_path, "wb") as f:
                try:
                    async with self.http_client.stream("GET", asset_url) as resp:
                        resp.raise_for_status()
                        total = int(resp.headers.get("content-length", 0))
                        downloaded = 0
                        async for chunk in resp.aiter_bytes():
                            if cancel_event and cancel_event.is_set():
                                logger.info("Download cancelled")
                                f.close()
                                Path(dest_path).unlink(missing_ok=True)
                                return False
                            f.write(chunk)
                            downloaded += len(chunk)
                            if progress_callback:
                                progress_callback(downloaded, total)
                except Exception as e:
                    logger.error(f"Download failed: {e}")
                    f.close()
                    Path(dest_path).unlink(missing_ok=True)
                    return False
            # After download, verify SHA256 if provided
            if expected_sha256:
                sha256 = hashlib.sha256()
                with open(dest_path, "rb") as f:
                    for chunk in iter(lambda: f.read(8192), b""):
                        sha256.update(chunk)
                digest = sha256.hexdigest()
                if digest.lower() != expected_sha256.lower():
                    logger.error(f"SHA256 mismatch: expected {expected_sha256}, got {digest}")
                    Path(dest_path).unlink(missing_ok=True)
                    return False
            # Alternatively, verify using checksums.txt asset if provided
            if checksums_url and artifact_name:
                try:
                    resp = await self.http_client.get(checksums_url)
                    resp.raise_for_status()
                    lines = resp.text.splitlines()
                    expected = None
                    for line in lines:
                        parts = line.strip().split()
                        if len(parts) == 2 and parts[1] == artifact_name:
                            expected = parts[0]
                            break
                    if expected:
                        sha256 = hashlib.sha256()
                        with open(dest_path, "rb") as f:
                            for chunk in iter(lambda: f.read(8192), b""):
                                sha256.update(chunk)
                        digest = sha256.hexdigest()
                        if digest.lower() != expected.lower():
                            logger.error(
                                f"SHA256 mismatch from checksums.txt: expected {expected}, got {digest}"
                            )
                            Path(dest_path).unlink(missing_ok=True)
                            return False
                except Exception as e:
                    logger.error(f"Failed to verify checksum from checksums.txt: {e}")
                    Path(dest_path).unlink(missing_ok=True)
                    return False
            return True
        except Exception as e:
            logger.error(f"Download failed: {e}")
            Path(dest_path).unlink(missing_ok=True)
            return False

    def _load_settings(self):
        if self.settings_path.exists():
            try:
                with open(self.settings_path, encoding="utf-8") as f:
                    data = json.load(f)
                return UpdateSettings(**data)
            except Exception as e:
                logger.warning(f"Failed to load update settings: {e}")
        # Defaults
        return UpdateSettings(channel="stable", owner=DEFAULT_OWNER, repo=DEFAULT_REPO)

    def save_settings(self):
        try:
            with open(self.settings_path, "w", encoding="utf-8") as f:
                json.dump(self.settings.__dict__, f)
            self.owner = self.settings.owner
            self.repo = self.settings.repo
            self._cache = None
        except Exception as e:
            logger.warning(f"Failed to save update settings: {e}")

    def get_settings_dict(self):
        return self.settings.__dict__

    async def get_github_diagnostics(self):
        info = {
            "repo": f"{self.owner}/{self.repo}",
            "cache_exists": self.cache_path.exists(),
            "cache_age": time.time() - self._cache.get("last_check", 0) if self._cache else None,
            "channel": self.settings.channel,
            "platform": platform.system(),
        }
        # Test API connectivity
        try:
            url = GITHUB_API_URL.format(owner=self.owner, repo=self.repo)
            resp = await self.http_client.get(url)
            info["api_status"] = resp.status_code
        except Exception as e:
            info["api_status"] = str(e)
        return info

    async def cleanup(self):
        await self.http_client.aclose()

    def __del__(self):
        try:
            if hasattr(self, "http_client") and self.http_client:
                try:
                    import asyncio

                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None
                if loop and loop.is_running():
                    loop.create_task(self.http_client.aclose())
        except Exception:
            pass
