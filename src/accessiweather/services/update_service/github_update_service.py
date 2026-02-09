"""Coordinator for the modular GitHub update service."""

from __future__ import annotations

import asyncio
import logging
import os
import platform
import subprocess
import sys
import textwrap
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from ...config.config_manager import ConfigManager

from .downloads import DownloadManager
from .releases import GITHUB_API_URL, ReleaseManager
from .settings import (
    DEFAULT_OWNER,
    DEFAULT_REPO,
    SETTINGS_FILENAME,
    SettingsManager,
    UpdateSettings,
)

try:
    from ...config_utils import is_portable_mode
except ImportError:

    def is_portable_mode() -> bool:
        return False


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
    signature_url: str | None = None


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
            follow_redirects=True,
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
        """Check for updates against the configured channel (stable, beta, nightly)."""
        if current_version is None:
            # For nightly builds, use the build tag (nightly-YYYYMMDD) as the
            # current version so the updater correctly compares nightly dates
            # instead of comparing against the pyproject.toml semver.
            try:
                from ..._build_info import BUILD_TAG
            except Exception:  # noqa: BLE001
                BUILD_TAG = None

            if BUILD_TAG:
                current_version = BUILD_TAG
            else:
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

        is_portable = self._is_portable_environment()
        asset = self._find_platform_asset(latest, portable=is_portable)
        if not asset:
            logger.warning("No suitable asset found for platform")
            return None

        # Find signature asset for the platform asset
        signature_asset = ReleaseManager.find_signature_asset(latest, asset["name"])
        signature_url = signature_asset["browser_download_url"] if signature_asset else None

        return UpdateInfo(
            version=latest["tag_name"].lstrip("v"),
            download_url=asset["browser_download_url"],
            artifact_name=asset["name"],
            release_notes=latest.get("body", ""),
            is_prerelease=latest.get("prerelease", False),
            file_size=asset.get("size"),
            signature_url=signature_url,
        )

    async def download_update(self, *args, **kwargs):
        return await self.download_manager.download_update(*args, **kwargs)

    async def _get_releases(self) -> list[dict[str, Any]]:
        """Maintain backward compatibility for tests that access the old helper."""
        try:
            return await self.release_manager.get_releases()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - fall back to cache when possible
            cache = self.release_manager._cache or {}
            cached_releases = cache.get("releases", [])
            if cached_releases:
                logger.warning("Using cached releases after fetch failure: %s", exc)
                return cached_releases
            raise

    def _filter_releases_by_channel(
        self, releases: list[dict[str, Any]], channel: str
    ) -> list[dict[str, Any]]:
        return self.release_manager.filter_releases_by_channel(releases, channel)

    def _find_latest_release(
        self, releases: list[dict[str, Any]], current_version: str
    ) -> dict[str, Any] | None:
        return self.release_manager.find_latest_release(releases, current_version)

    def _find_platform_asset(
        self, release: dict[str, Any], portable: bool = False
    ) -> dict[str, Any] | None:
        return self.release_manager.find_platform_asset(release, portable=portable)

    def _is_newer_version(self, candidate: str, current: str) -> bool:
        return self.release_manager._is_newer_version(candidate, current)

    def _is_portable_environment(self) -> bool:
        """Check if running in a portable environment."""
        try:
            return is_portable_mode()
        except Exception as e:
            logger.debug(f"Error checking portable mode: {e}")
            return False

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
        try:
            return await self.download_manager._download_asset(  # type: ignore[attr-defined]
                asset_url,
                dest_path,
                progress_callback=progress_callback,
                cancel_event=cancel_event,
                expected_sha256=expected_sha256,
                checksums_url=checksums_url,
                artifact_name=artifact_name,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            return False

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

    def schedule_portable_update_and_restart(self, zip_path: str | Path) -> None:
        """
        Schedule a portable update by creating a batch script to swap files and restart.

        This method:
        1. Verifies platform is Windows.
        2. Creates a temporary batch script that:
           - Waits for this process to exit
           - Unzips the new version
           - Overwrites the current installation
           - Cleans up
           - Restarts the application
        3. Launches the script and exits immediately
        """
        if platform.system() != "Windows":
            logger.error("Portable update is only supported on Windows")
            return

        zip_path = Path(zip_path).resolve()
        exe_path = Path(sys.executable).resolve()
        target_dir = exe_path.parent

        # Temporary extraction directory inside the target directory
        extract_dir = target_dir / "update_tmp"
        batch_path = target_dir / "accessiweather_portable_update.bat"

        # Create the batch script content
        # Note: We use powershell for extraction as it's available on all modern Windows
        batch_content = textwrap.dedent(f"""
            @echo off
            set "PID={os.getpid()}"
            set "ZIP_PATH={zip_path}"
            set "TARGET_DIR={target_dir}"
            set "EXE_PATH={exe_path}"
            set "EXTRACT_DIR={extract_dir}"

            echo Waiting for AccessiWeather to exit (PID %PID%)...
            :WAIT_LOOP
            tasklist /FI "PID eq %PID%" 2>NUL | find /I /N "%PID%" >NUL
            if "%ERRORLEVEL%"=="0" (
                timeout /t 1 /nobreak >NUL
                goto WAIT_LOOP
            )

            REM Extra wait for file handles and antivirus to release
            timeout /t 2 /nobreak >NUL

            echo Extracting update...
            if exist "%EXTRACT_DIR%" rd /s /q "%EXTRACT_DIR%"
            powershell -Command "Expand-Archive -Path '%ZIP_PATH%' -DestinationPath '%EXTRACT_DIR%' -Force"
            if %ERRORLEVEL% neq 0 (
                echo ERROR: Failed to extract update.
                pause
                exit /b 1
            )

            echo Installing update...
            xcopy "%EXTRACT_DIR%\\*" "%TARGET_DIR%\\" /E /H /Y /Q
            if %ERRORLEVEL% neq 0 (
                echo ERROR: Failed to copy update files.
                pause
                exit /b 1
            )

            echo Cleaning up...
            rd /s /q "%EXTRACT_DIR%"
            del "%ZIP_PATH%"

            REM Wait for filesystem to settle before restarting
            timeout /t 2 /nobreak >NUL

            echo Restarting application...
            start "" "%EXE_PATH%"

            (goto) 2>nul & del "%~f0"
        """)

        with open(batch_path, "w") as f:
            f.write(batch_content)

        # Launch the batch script detached
        # CREATE_NEW_CONSOLE = 0x00000010
        creation_flags = 0x00000010
        subprocess.Popen(
            [str(batch_path)],
            shell=True,
            cwd=str(target_dir),
            creationflags=creation_flags,
        )

        # Force exit to allow the update script to proceed
        os._exit(0)

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


def sync_update_channel_to_service(
    config_manager: ConfigManager | None,
    update_service: GitHubUpdateService | None,
) -> None:
    """
    Synchronize AppSettings.update_channel to UpdateSettings.channel.

    This ensures that when the user changes the update channel setting in the
    main settings, the UpdateSettings used by the update service reflects that
    change immediately. Also invalidates the release cache to ensure fresh data
    is fetched with the new channel.

    Args:
        config_manager: The application's ConfigManager (may be None)
        update_service: The GitHubUpdateService (may be None)

    """
    if not config_manager or not update_service:
        return

    try:
        config = config_manager.get_config()
        if config and config.settings:
            app_channel = getattr(config.settings, "update_channel", "stable")
            old_channel = update_service.settings.channel

            # Update the channel
            update_service.settings.channel = app_channel

            # If the channel changed, invalidate the cache
            if old_channel != app_channel:
                logger.info(
                    f"Update channel changed from '{old_channel}' to '{app_channel}', invalidating release cache"
                )
                # Clear the in-memory cache
                update_service.release_manager._cache = None
                # The disk cache will be automatically invalidated on next load because
                # the channel in the cached data won't match the new channel
            else:
                logger.debug(f"Update channel is already set to: {app_channel}")
    except Exception as exc:
        logger.warning(f"Failed to sync update channel: {exc}")
