"""Lightweight GitHub update checks and restart handling."""

from __future__ import annotations

import logging
import os
import platform
import re
import subprocess
import sys
import tempfile
import textwrap
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from packaging.version import InvalidVersion, Version

from .update_service.settings import DEFAULT_OWNER, DEFAULT_REPO

# Type alias for progress callbacks: (bytes_downloaded, total_bytes) -> None
ProgressCallback = Callable[[int, int], None]

try:
    from ..config_utils import is_portable_mode
except ImportError:

    def is_portable_mode() -> bool:
        return False


logger = logging.getLogger(__name__)

GITHUB_RELEASES_URL = "https://api.github.com/repos/{owner}/{repo}/releases?per_page=20"
COMMIT_PATTERN = re.compile(r"(?i)\bcommit(?:\s+hash)?\s*[:=]\s*([0-9a-f]{7,40})\b")
FALLBACK_HASH_PATTERN = re.compile(r"\b[0-9a-f]{7,40}\b", re.IGNORECASE)


def is_installed_version() -> bool:
    """
    Check if running from an installed location (Program Files) vs portable.

    Returns:
        True if exe is in Program Files, False otherwise (portable or dev).

    """
    if not getattr(sys, "frozen", False):
        return False
    exe_path = sys.executable
    program_files = os.environ.get("PROGRAMFILES", r"C:\Program Files")
    program_files_x86 = os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")
    return exe_path.startswith((program_files, program_files_x86))


@dataclass(frozen=True)
class UpdateInfo:
    version: str
    download_url: str
    artifact_name: str
    release_notes: str
    commit_hash: str | None
    is_nightly: bool
    is_prerelease: bool


@dataclass(frozen=True)
class RestartPlan:
    kind: str
    command: list[str]
    script_path: Path | None = None


def parse_commit_hash(release_notes: str) -> str | None:
    match = COMMIT_PATTERN.search(release_notes)
    if match:
        return match.group(1).lower()
    match = FALLBACK_HASH_PATTERN.search(release_notes)
    return match.group(0).lower() if match else None


def is_nightly_release(release: dict[str, Any]) -> bool:
    return parse_commit_hash(release.get("body", "")) is not None


def is_update_available(
    release: dict[str, Any],
    current_version: str,
    current_commit: str | None,
) -> bool:
    commit_hash = parse_commit_hash(release.get("body", ""))
    if commit_hash:
        return commit_hash != (current_commit or "").lower()

    candidate = release.get("tag_name", "").lstrip("v")
    current = current_version.lstrip("v")
    try:
        return Version(candidate) > Version(current)
    except InvalidVersion:
        return False


def select_latest_release(
    releases: list[dict[str, Any]],
    channel: str,
) -> dict[str, Any] | None:
    channel = channel.lower()
    filtered: list[dict[str, Any]] = []
    for release in releases:
        prerelease = bool(release.get("prerelease"))
        nightly = is_nightly_release(release)
        if channel == "stable" and (prerelease or nightly):
            continue
        if channel == "nightly" and not nightly:
            continue
        filtered.append(release)

    def sort_key(item: dict[str, Any]) -> str:
        return item.get("published_at") or item.get("created_at") or ""

    return max(filtered, key=sort_key, default=None)


def select_asset(
    release: dict[str, Any],
    *,
    portable: bool,
    platform_system: str | None = None,
) -> dict[str, Any] | None:
    system = (platform_system or platform.system()).lower()
    assets = release.get("assets", [])

    deny_extensions = (
        ".sha256",
        ".sha512",
        ".md5",
        ".sig",
        ".asc",
        ".txt",
        ".json",
    )
    deny_patterns = ("checksum", "signature", "hash", "verify", "sum")

    def is_allowed(name: str) -> bool:
        lower = name.lower()
        if any(lower.endswith(ext) for ext in deny_extensions):
            return False
        return not any(pattern in lower for pattern in deny_patterns)

    filtered = [asset for asset in assets if is_allowed(asset.get("name", ""))]

    if "windows" in system:
        if portable:
            for asset in filtered:
                name = asset.get("name", "").lower()
                if "portable" in name and name.endswith(".zip"):
                    return asset
            for asset in filtered:
                name = asset.get("name", "").lower()
                if name.endswith(".zip"):
                    return asset
        for ext in (".exe", ".msi"):
            for asset in filtered:
                if asset.get("name", "").lower().endswith(ext):
                    return asset
    elif "darwin" in system or "mac" in system:
        for ext in (".dmg", ".pkg"):
            for asset in filtered:
                if asset.get("name", "").lower().endswith(ext):
                    return asset
    else:
        for ext in (".appimage", ".deb", ".rpm", ".tar.gz"):
            for asset in filtered:
                if asset.get("name", "").lower().endswith(ext):
                    return asset

    return filtered[0] if filtered else (assets[0] if assets else None)


def build_macos_update_script(
    update_path: Path,
    app_path: Path,
) -> str:
    """
    Build a shell script to apply macOS update.

    Args:
        update_path: Path to downloaded zip/dmg file.
        app_path: Path to the .app bundle to update.

    Returns:
        Shell script content as string.

    """
    app_dir = app_path.parent
    return textwrap.dedent(
        f"""
        #!/bin/bash
        sleep 2
        if [[ "{update_path}" == *.zip ]]; then
            unzip -o "{update_path}" -d "{app_dir}"
        elif [[ "{update_path}" == *.dmg ]]; then
            hdiutil attach "{update_path}" -nobrowse -quiet
            cp -R /Volumes/*/*.app "{app_dir}/"
            hdiutil detach /Volumes/* -quiet
        fi
        open "{app_path}"
        rm -f "$0" "{update_path}"
        """
    ).strip()


def build_portable_update_script(
    zip_path: Path,
    target_dir: Path,
    exe_path: Path,
) -> str:
    return textwrap.dedent(
        f"""
        @echo off
        set "PID={os.getpid()}"
        set "ZIP_PATH={zip_path}"
        set "TARGET_DIR={target_dir}"
        set "EXE_PATH={exe_path}"
        set "EXTRACT_DIR={target_dir / "update_tmp"}"

        :WAIT_LOOP
        tasklist /FI "PID eq %PID%" 2>NUL | find /I /N "%PID%" >NUL
        if "%ERRORLEVEL%"=="0" (
            timeout /t 1 /nobreak >NUL
            goto WAIT_LOOP
        )

        if exist "%EXTRACT_DIR%" rd /s /q "%EXTRACT_DIR%"
        powershell -Command "Expand-Archive -Path '%ZIP_PATH%' ^
        -DestinationPath '%EXTRACT_DIR%' -Force"
        xcopy "%EXTRACT_DIR%\\*" "%TARGET_DIR%\\" /E /H /Y /Q
        rd /s /q "%EXTRACT_DIR%"
        del "%ZIP_PATH%"
        start "" "%EXE_PATH%"
        (goto) 2>nul & del "%~f0"
        """
    ).strip()


def plan_restart(
    update_path: Path,
    *,
    portable: bool,
    platform_system: str | None = None,
) -> RestartPlan:
    """
    Plan how to apply an update and restart.

    Args:
        update_path: Path to downloaded update file.
        portable: Whether running in portable mode.
        platform_system: Override for platform.system() (for testing).

    Returns:
        RestartPlan with kind, command, and optional script_path.

    """
    system = (platform_system or platform.system()).lower()
    if "windows" in system and portable:
        exe_path = Path(sys.executable).resolve()
        script_path = exe_path.parent / "accessiweather_portable_update.bat"
        return RestartPlan("portable", [str(script_path)], script_path=script_path)
    if "windows" in system:
        return RestartPlan("windows_installer", [str(update_path)])
    if "darwin" in system or "mac" in system:
        # Use shell script for proper update handling
        script_path = Path(tempfile.gettempdir()) / "accessiweather_update.sh"
        return RestartPlan("macos_script", ["bash", str(script_path)], script_path=script_path)
    return RestartPlan("unsupported", [str(update_path)])


def apply_update(
    update_path: Path,
    *,
    portable: bool,
    platform_system: str | None = None,
) -> None:
    """
    Apply update and restart the application.

    This function does not return on success - it exits after launching
    the update process.

    Args:
        update_path: Path to downloaded update file.
        portable: Whether running in portable mode.
        platform_system: Override for platform.system() (for testing).

    """
    plan = plan_restart(update_path, portable=portable, platform_system=platform_system)

    if plan.kind == "portable" and plan.script_path:
        exe_path = Path(sys.executable).resolve()
        script_content = build_portable_update_script(
            update_path,
            exe_path.parent,
            exe_path,
        )
        plan.script_path.write_text(script_content, encoding="utf-8")
        subprocess.Popen([str(plan.script_path)], shell=True, cwd=str(exe_path.parent))
        os._exit(0)

    if plan.kind == "macos_script" and plan.script_path:
        # Find the .app bundle path
        exe_path = Path(sys.executable).resolve()
        # Typically: /path/to/App.app/Contents/MacOS/executable
        app_path = exe_path.parent.parent.parent
        script_content = build_macos_update_script(update_path, app_path)
        plan.script_path.write_text(script_content, encoding="utf-8")
        plan.script_path.chmod(0o755)
        subprocess.Popen(["bash", str(plan.script_path)])
        os._exit(0)

    if plan.kind == "windows_installer":
        subprocess.Popen(plan.command, shell=True)
        os._exit(0)

    logger.warning("Update requires manual installation: %s", update_path)


class UpdateService:
    """Simple update service for checking and downloading updates from GitHub releases."""

    def __init__(
        self,
        app_name: str,
        owner: str = DEFAULT_OWNER,
        repo: str = DEFAULT_REPO,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        """
        Initialize the update service.

        Args:
            app_name: Application name for User-Agent header.
            owner: GitHub repository owner.
            repo: GitHub repository name.
            http_client: Optional httpx.AsyncClient for custom HTTP configuration.

        """
        self.app_name = app_name
        self.owner = owner
        self.repo = repo
        self.http_client = http_client or httpx.AsyncClient(
            headers={"User-Agent": f"{app_name}"},
            timeout=30.0,
            follow_redirects=True,
        )

    async def fetch_releases(self) -> list[dict[str, Any]]:
        url = GITHUB_RELEASES_URL.format(owner=self.owner, repo=self.repo)
        response = await self.http_client.get(url)
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, list) else []

    async def check_for_updates(
        self,
        *,
        current_version: str,
        current_commit: str | None = None,
        channel: str = "stable",
        portable: bool | None = None,
        platform_system: str | None = None,
    ) -> UpdateInfo | None:
        releases = await self.fetch_releases()
        latest = select_latest_release(releases, channel)
        if not latest:
            return None

        if not is_update_available(latest, current_version, current_commit):
            return None

        portable_flag = portable if portable is not None else is_portable_mode()
        asset = select_asset(latest, portable=portable_flag, platform_system=platform_system)
        if not asset:
            return None

        commit_hash = parse_commit_hash(latest.get("body", ""))
        return UpdateInfo(
            version=commit_hash or latest.get("tag_name", "").lstrip("v"),
            download_url=asset.get("browser_download_url", ""),
            artifact_name=asset.get("name", ""),
            release_notes=latest.get("body", ""),
            commit_hash=commit_hash,
            is_nightly=commit_hash is not None,
            is_prerelease=bool(latest.get("prerelease")),
        )

    async def download_update(
        self,
        update_info: UpdateInfo,
        dest_dir: Path | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> Path:
        """
        Download an update file.

        Args:
            update_info: UpdateInfo from check_for_updates().
            dest_dir: Directory to save file (defaults to temp dir).
            progress_callback: Optional callback(bytes_downloaded, total_bytes).

        Returns:
            Path to the downloaded file.

        Raises:
            httpx.HTTPError: If download fails.

        """
        if dest_dir is None:
            dest_dir = Path(tempfile.gettempdir())
        dest_dir.mkdir(parents=True, exist_ok=True)

        dest_path = dest_dir / update_info.artifact_name

        async with self.http_client.stream("GET", update_info.download_url) as response:
            response.raise_for_status()
            total = int(response.headers.get("content-length", 0))
            downloaded = 0

            with dest_path.open("wb") as f:
                async for chunk in response.aiter_bytes(chunk_size=65536):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total)

        logger.info("Downloaded update to %s", dest_path)
        return dest_path

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.http_client.aclose()
