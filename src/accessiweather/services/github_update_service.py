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
        # Ensure the config directory exists before creating/using cache and settings files
        self.config_dir.mkdir(parents=True, exist_ok=True)
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
        """Compatibility wrapper for update check.

        If `current_version` is None, default to the running package version.
        The `method` parameter is ignored.
        """
        # Default current_version to the running package version if not provided
        if current_version is None:
            try:
                # Local import to avoid import-time side effects
                from ..version import __version__

                current_version = __version__
            except Exception:
                # Fall back to a very old version to ensure any release is considered newer
                current_version = "0.0.0"

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
        """Filter releases based on channel with hierarchical inclusion.

        Channel hierarchy (more permissive channels include releases from less permissive ones):
        - stable: Only stable releases (prerelease=False)
        - beta: Stable releases + beta/rc prereleases
        - dev: All releases (stable + beta + alpha + dev)

        Args:
            releases: List of GitHub release objects
            channel: Channel name ("stable", "beta", or "dev")

        Returns:
            List of releases appropriate for the specified channel

        """
        channel = channel.lower()
        out = []

        for rel in releases:
            tag = rel.get("tag_name", "").lower()
            pre = rel.get("prerelease", False)

            # Stable channel: only non-prerelease versions
            if channel == "stable":
                if not pre:
                    out.append(rel)

            # Beta channel: stable releases + beta/rc prereleases
            elif channel == "beta":
                if not pre or (pre and ("beta" in tag or "rc" in tag)):  # Include stable + beta/rc
                    out.append(rel)

            # Dev channel: all releases (stable + all prereleases)
            elif channel == "dev":
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

        # Define priority extensions for each platform
        priority_extensions = {}
        platform_patterns = {}

        if "windows" in sys:
            priority_extensions = [".exe", ".msi"]
            platform_patterns = ["windows", "win"]
        elif "linux" in sys:
            priority_extensions = [".appimage", ".tar.gz", ".deb", ".rpm"]
            platform_patterns = ["linux"]
        elif "darwin" in sys or "mac" in sys:
            priority_extensions = [".dmg", ".pkg"]
            platform_patterns = ["macos", "darwin", "mac"]

        # Deny list - exclude these file types
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

        # Filter out denied assets
        filtered_assets = []
        for asset in assets:
            name = asset.get("name", "").lower()

            # Skip if matches deny patterns
            if any(ext in name for ext in deny_extensions):
                continue
            if any(pattern in name for pattern in deny_patterns):
                continue

            filtered_assets.append(asset)

        # First pass: Look for priority extensions
        for ext in priority_extensions:
            for asset in filtered_assets:
                name = asset.get("name", "").lower()
                if name.endswith(ext):
                    return asset

        # Second pass: Look for platform patterns
        for asset in filtered_assets:
            name = asset.get("name", "").lower()
            if any(pattern in name for pattern in platform_patterns):
                return asset

        # Fallback: Return first filtered asset or first asset if none filtered
        return filtered_assets[0] if filtered_assets else (assets[0] if assets else None)

    async def download_update(
        self,
        asset_or_info,
        dest_path=None,
        progress_callback=None,
        cancel_event=None,
        expected_sha256=None,
        checksums_url=None,
        artifact_name=None,
    ) -> str | bool:
        """Compatibility wrapper to download an update."""
        # Detect UpdateInfo safely
        try:
            is_update_info = isinstance(asset_or_info, UpdateInfo)
        except Exception:
            is_update_info = False

        # New-style call: UpdateInfo instance provided
        if is_update_info:
            info: UpdateInfo = asset_or_info

            # Support positional progress_callback passed in dest_path slot
            if callable(dest_path) and progress_callback is None:
                progress_callback = dest_path
                dest_path = None

            url = info.download_url

            # Determine artifact name
            name = artifact_name or getattr(info, "artifact_name", None)
            if not name:
                try:
                    from urllib.parse import urlparse

                    parsed = urlparse(url)
                    name = Path(parsed.path).name or f"{self.app_name}-update"
                except Exception:
                    name = f"{self.app_name}-update"

            # Destination under config_dir/updates
            dest_dir = self.config_dir / "updates"
            dest_dir.mkdir(parents=True, exist_ok=True)
            file_path = dest_dir / name

            # _download_asset returns str(dest_path) on success, or False on failure
            return await self._download_asset(
                url,
                file_path,
                progress_callback=progress_callback,
                cancel_event=cancel_event,
                expected_sha256=expected_sha256,
                checksums_url=checksums_url,
                artifact_name=name,
            )

        # Legacy call: asset_or_info is a URL and dest_path must be provided
        if dest_path is None:
            logger.error("dest_path is required when calling download_update with a URL")
            return False

        # Ensure parent directory exists for legacy dest_path
        import contextlib

        with contextlib.suppress(Exception):
            Path(dest_path).parent.mkdir(parents=True, exist_ok=True)

        return await self._download_asset(
            asset_or_info,
            dest_path,
            progress_callback=progress_callback,
            cancel_event=cancel_event,
            expected_sha256=expected_sha256,
            checksums_url=checksums_url,
            artifact_name=artifact_name,
        )

    async def _download_asset(
        self,
        asset_url,
        dest_path,
        progress_callback=None,
        cancel_event=None,
        expected_sha256=None,
        checksums_url=None,
        artifact_name=None,
    ) -> str | bool:
        import contextlib
        import hashlib
        from pathlib import Path

        # Validate inputs for legacy path
        if not asset_url or not dest_path:
            logger.error("asset_url and dest_path are required for legacy download call")
            return False

        # Check cancel_event at start
        if cancel_event and cancel_event.is_set():
            logger.info("Download cancelled before start")
            return False

        # Ensure parent directory exists
        Path(dest_path).parent.mkdir(parents=True, exist_ok=True)

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
                                # Don't fail download due to progress callback errors
                                with contextlib.suppress(Exception):
                                    progress_callback(downloaded, total)
                except Exception as e:
                    logger.error(f"Download failed: {e}")
                    try:
                        f.close()
                        Path(dest_path).unlink(missing_ok=True)
                    except Exception:
                        pass
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

            # Return the destination path on success for callers that expect the path.
            try:
                return str(dest_path)
            except Exception:
                return dest_path
        except Exception as e:
            logger.error(f"Download failed: {e}")
            with contextlib.suppress(Exception):
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
