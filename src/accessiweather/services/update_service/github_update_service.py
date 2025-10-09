"""Coordinator for the modular GitHub update service."""

from __future__ import annotations

import asyncio
import logging
import platform
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from .downloads import DownloadManager
from .releases import GITHUB_API_URL, ReleaseManager
from .settings import (
    DEFAULT_OWNER,
    DEFAULT_REPO,
    SETTINGS_FILENAME,
    SettingsManager,
    UpdateSettings,
)

logger = logging.getLogger(__name__)

CACHE_FILENAME = "github_releases_cache.json"


@dataclass
class UpdateInfo:
    """Information about an available update."""

    version: str
    download_url: str
    artifact_name: str
    release_notes: str = ""
    is_prerelease: bool = False
    file_size: int | None = None


class GitHubUpdateService:
    """Facade exposing the legacy update service API while delegating to helpers."""

    def __init__(
        self,
        app_name: str,
        config_dir: str,
        owner: str = DEFAULT_OWNER,
        repo: str = DEFAULT_REPO,
    ) -> None:
        """Set up the update service coordinator and dependencies."""
        self.app_name = app_name
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.owner = owner
        self.repo = repo
        self.cache_path = self.config_dir / CACHE_FILENAME
        self.settings_path = self.config_dir / SETTINGS_FILENAME

        try:
            from ... import __version__ as pkg_version
        except Exception:  # noqa: BLE001 - fall back to sentinel version
            pkg_version = "0.0.0"

        self._http_client = None
        self.http_client = httpx.AsyncClient(
            headers={"User-Agent": f"{self.app_name}/{pkg_version}"},
            timeout=30.0,
        )

        self.settings_manager = SettingsManager(self.settings_path)
        self.settings: UpdateSettings = self._load_settings()
        self.owner = self.settings.owner
        self.repo = self.settings.repo
        self.last_channel = self.settings.channel

        self.release_manager = ReleaseManager(
            self.http_client,
            self.owner,
            self.repo,
            self.cache_path,
            self.settings,
        )
        self.download_manager = DownloadManager(self.http_client, self.config_dir, self.app_name)

    @property
    def http_client(self) -> Any:
        return self._http_client

    @http_client.setter
    def http_client(self, client: Any) -> None:
        self._http_client = client
        if hasattr(self, "release_manager"):
            self.release_manager.http_client = client
        if hasattr(self, "download_manager"):
            self.download_manager.http_client = client

    @property
    def owner(self) -> str:
        return getattr(self, "_owner", DEFAULT_OWNER)

    @owner.setter
    def owner(self, value: str) -> None:
        self._owner = value
        if hasattr(self, "release_manager"):
            self.release_manager.owner = value

    @property
    def repo(self) -> str:
        return getattr(self, "_repo", DEFAULT_REPO)

    @repo.setter
    def repo(self, value: str) -> None:
        self._repo = value
        if hasattr(self, "release_manager"):
            self.release_manager.repo = value

    @property
    def _cache(self) -> dict[str, Any] | None:  # noqa: D401 - retain legacy attribute name
        """Expose the internal release cache for backwards compatibility."""
        return self.release_manager._cache

    @_cache.setter
    def _cache(self, value: dict[str, Any] | None) -> None:
        self.release_manager._cache = value

    async def check_for_updates(
        self,
        method: str | None = None,
        current_version: str | None = None,
    ) -> UpdateInfo | None:
        if current_version is None:
            try:
                from ... import __version__ as pkg_version
            except Exception:  # noqa: BLE001 - ensure comparison always succeeds
                pkg_version = "0.0.0"
            current_version = pkg_version

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

    async def download_update(self, *args, **kwargs):
        return await self.download_manager.download_update(*args, **kwargs)

    async def _get_releases(self) -> list[dict[str, Any]]:
        """Maintain backward compatibility for tests that access the old helper."""
        return await self.release_manager.get_releases()

    def _filter_releases_by_channel(
        self, releases: list[dict[str, Any]], channel: str
    ) -> list[dict[str, Any]]:
        return self.release_manager.filter_releases_by_channel(releases, channel)

    def _find_latest_release(
        self, releases: list[dict[str, Any]], current_version: str
    ) -> dict[str, Any] | None:
        return self.release_manager.find_latest_release(releases, current_version)

    def _find_platform_asset(self, release: dict[str, Any]) -> dict[str, Any] | None:
        return self.release_manager.find_platform_asset(release)

    def _is_newer_version(self, candidate: str, current: str) -> bool:
        return self.release_manager._is_newer_version(candidate, current)

    async def _download_asset(
        self,
        asset_url: str,
        dest_path: str | Path,
        progress_callback=None,
        cancel_event=None,
        expected_sha256: str | None = None,
        checksums_url: str | None = None,
        artifact_name: str | None = None,
    ) -> str | bool:
        return await self.download_manager._download_asset(  # type: ignore[attr-defined]
            asset_url,
            dest_path,
            progress_callback=progress_callback,
            cancel_event=cancel_event,
            expected_sha256=expected_sha256,
            checksums_url=checksums_url,
            artifact_name=artifact_name,
        )

    def _load_settings(self) -> UpdateSettings:
        return self.settings_manager.load_settings()

    def save_settings(self) -> None:
        self.settings_manager.save_settings(self.settings)
        self.owner = self.settings.owner
        self.repo = self.settings.repo
        self.release_manager = ReleaseManager(
            self.http_client,
            self.owner,
            self.repo,
            self.cache_path,
            self.settings,
        )

    def get_settings_dict(self) -> dict[str, str]:
        return self.settings_manager.get_settings_dict(self.settings)

    async def get_github_diagnostics(self) -> dict[str, object]:
        cache = self._cache
        info = {
            "repo": f"{self.owner}/{self.repo}",
            "cache_exists": self.cache_path.exists(),
            "cache_age": time.time() - cache.get("last_check", 0) if cache else None,
            "channel": self.settings.channel,
            "platform": platform.system(),
        }
        try:
            url = GITHUB_API_URL.format(owner=self.owner, repo=self.repo)
            response = await self.http_client.get(url)
            info["api_status"] = response.status_code
        except Exception as exc:  # noqa: BLE001 - capture errors for diagnostics
            info["api_status"] = str(exc)
        return info

    async def cleanup(self) -> None:
        await self.http_client.aclose()

    def __del__(self) -> None:
        try:
            if hasattr(self, "http_client") and self.http_client:
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None
                if loop and loop.is_running():
                    loop.create_task(self.http_client.aclose())
        except Exception:  # noqa: BLE001 - avoid destructor errors
            pass
