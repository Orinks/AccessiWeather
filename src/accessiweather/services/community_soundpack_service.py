"""
Community Sound Pack service for browsing and downloading packs from GitHub.

This module provides an async service that queries a GitHub repository for
available community sound packs and downloads them as ZIP files for
installation using SoundPackInstaller.

Design notes:
- Mirrors httpx async client usage and logging patterns from GitHubUpdateService
- Provides simple in-memory caching for the list of packs
- Supports authentication via GitHub App for higher rate limits when available
- Gracefully handles rate limits and transient errors with lightweight retries
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import logging
import shutil
import tempfile
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from accessiweather.constants import COMMUNITY_REPO_NAME, COMMUNITY_REPO_OWNER

logger = logging.getLogger(__name__)


@dataclass(order=True)
class CommunityPack:
    """Metadata describing a community sound pack."""

    name: str
    author: str
    description: str
    version: str
    download_url: str
    file_size: int | None
    repository_url: str
    release_tag: str
    # Optional/extra
    download_count: int | None = None
    created_date: str | None = None  # ISO 8601 string
    preview_image_url: str | None = None
    repo_path: str | None = None
    tree_sha: str | None = None
    ref: str | None = "main"

    def __str__(self) -> str:
        return f"{self.name} {self.version} by {self.author}"


class CommunitySoundPackService:
    """Service for discovering and downloading community sound packs from GitHub."""

    def __init__(
        self,
        repo_owner: str = COMMUNITY_REPO_OWNER,
        repo_name: str = COMMUNITY_REPO_NAME,
        timeout: float = 30.0,
        cache_duration_seconds: int = 300,
        user_agent: str = "AccessiWeather-CommunityPacks/1.0",
    ) -> None:
        """
        Initialize the community packs service.

        Args:
        ----
            repo_owner: GitHub org/user that hosts community packs
            repo_name: Repository name for packs
            timeout: HTTP timeout in seconds
            cache_duration_seconds: Cache duration for pack list
            user_agent: Custom user agent for GitHub API compliance

        """
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.cache_duration_seconds = cache_duration_seconds
        headers = {"User-Agent": user_agent, "Accept": "application/vnd.github+json"}

        # Note: GitHub authentication removed for security reasons
        # Future implementation should use GitHub App authentication

        self._http = httpx.AsyncClient(timeout=timeout, headers=headers)
        self._cached_packs: list[CommunityPack] | None = None
        self._cached_at: float | None = None

    async def aclose(self) -> None:
        with contextlib.suppress(Exception):
            await self._http.aclose()

    async def fetch_available_packs(self, force_refresh: bool = False) -> list[CommunityPack]:
        """
        Fetch a list of available community packs.

        Strategy:
        1) Try curated index.json in the repo root via GitHub API contents
        2) Fallback to releases API and gather assets ending with .zip
        Results are cached in-memory for cache_duration_seconds.
        """
        # Cache check
        now = asyncio.get_event_loop().time()
        if (
            not force_refresh
            and self._cached_packs is not None
            and self._cached_at is not None
            and (now - self._cached_at) < self.cache_duration_seconds
        ):
            return list(self._cached_packs)

        packs: list[CommunityPack] = []

        # Try curated index.json via contents API (raw content base64 encoded)
        try:
            url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/contents/index.json"
            resp = await self._http.get(url)
            if resp.status_code == 200:
                data = resp.json()
                content_b64 = data.get("content")
                if content_b64:
                    try:
                        content = base64.b64decode(content_b64).decode("utf-8")
                        index = json.loads(content)
                        for entry in index.get("packs", []):
                            packs.append(
                                CommunityPack(
                                    name=entry.get("name") or entry.get("id") or "unknown",
                                    author=entry.get("author", "Unknown"),
                                    description=entry.get("description", ""),
                                    version=str(entry.get("version", "1.0")),
                                    download_url=entry.get("download_url", ""),
                                    file_size=entry.get("file_size"),
                                    repository_url=entry.get("homepage")
                                    or f"https://github.com/{self.repo_owner}/{self.repo_name}",
                                    release_tag=str(entry.get("release_tag", "")),
                                    download_count=entry.get("download_count"),
                                    created_date=entry.get("created_date"),
                                    preview_image_url=entry.get("preview_image_url"),
                                )
                            )
                    except Exception as e:  # fall back to releases
                        logger.warning(f"Failed to parse curated index.json: {e}")
                # If content not present, fall through to releases
        except Exception as e:
            logger.info(f"Curated index.json not available or failed: {e}")

        # Fallback to releases if packs still empty
        if not packs:
            try:
                rel_url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/releases?per_page=50"
                resp = await self._http.get(rel_url)
                if resp.status_code == 200:
                    releases = resp.json()
                    for release in releases:
                        tag = release.get("tag_name") or ""
                        body = release.get("body") or ""
                        author = (release.get("author") or {}).get("login", "Unknown")
                        created = release.get("published_at")
                        html_url = (
                            release.get("html_url")
                            or f"https://github.com/{self.repo_owner}/{self.repo_name}/releases"
                        )
                        assets = release.get("assets") or []
                        for asset in assets:
                            name = asset.get("name") or ""
                            if not name.lower().endswith(".zip"):
                                continue
                            dl = asset.get("browser_download_url")
                            size = asset.get("size")
                            dl_count = asset.get("download_count")
                            # Attempt to extract pack name/version from asset or tag
                            version = tag.lstrip("v") or "1.0"
                            pack_name = name.rsplit(".zip", 1)[0]
                            packs.append(
                                CommunityPack(
                                    name=pack_name,
                                    author=author,
                                    description=body.strip(),
                                    version=str(version),
                                    download_url=dl,
                                    file_size=size,
                                    repository_url=html_url,
                                    release_tag=tag,
                                    download_count=dl_count,
                                    created_date=created,
                                )
                            )
                elif resp.status_code == 403:
                    # Likely rate limited
                    logger.warning("GitHub API rate limit reached while fetching releases.")
                else:
                    logger.warning(f"Unexpected GitHub API status: {resp.status_code}")
            except Exception as e:
                logger.error(f"Failed to fetch releases: {e}")

        # Final fallback: scan repository directories for packs (no releases yet)
        if not packs:
            try:
                repo_packs = await self._fetch_repo_directory_packs()
                packs.extend(repo_packs)
            except Exception as e:
                logger.error(f"Failed to discover packs from repository contents: {e}")

        # Cache results
        self._cached_packs = packs
        self._cached_at = now
        return packs

    async def _fetch_repo_directory_packs(self) -> list[CommunityPack]:
        """Discover packs from /packs when no curated index or releases exist."""
        ref = "main"
        contents_url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/contents/packs?ref={ref}"
        resp = await self._http.get(contents_url)
        if resp.status_code != 200:
            logger.debug("Repository contents fallback unavailable (status %s)", resp.status_code)
            return []

        entries: list[dict[str, Any]] = resp.json()  # type: ignore[assignment]
        packs: list[CommunityPack] = []
        for entry in entries:
            if entry.get("type") != "dir":
                continue
            dir_name = entry.get("name") or "unknown"
            repo_path = entry.get("path") or f"packs/{dir_name}"
            tree_sha = entry.get("sha")

            pack_json_url = (
                f"https://raw.githubusercontent.com/"
                f"{self.repo_owner}/{self.repo_name}/{ref}/{repo_path}/pack.json"
            )
            try:
                pack_resp = await self._http.get(pack_json_url)
                if pack_resp.status_code != 200:
                    logger.debug("Skipping pack %s: pack.json not found", dir_name)
                    continue
                pack_meta = pack_resp.json()
            except Exception as exc:
                logger.debug("Skipping pack %s: failed to parse pack.json (%s)", dir_name, exc)
                continue

            total_size = await self._calculate_tree_size(tree_sha)
            packs.append(
                CommunityPack(
                    name=pack_meta.get("name") or dir_name,
                    author=pack_meta.get("author", "Unknown"),
                    description=pack_meta.get("description", ""),
                    version=str(pack_meta.get("version", "1.0")),
                    download_url="",  # zip generated on demand
                    file_size=total_size,
                    repository_url=(
                        f"https://github.com/{self.repo_owner}/{self.repo_name}/tree/{ref}/{repo_path}"
                    ),
                    release_tag=ref,
                    download_count=None,
                    created_date=None,
                    preview_image_url=pack_meta.get("preview_image_url"),
                    repo_path=repo_path,
                    tree_sha=tree_sha,
                    ref=ref,
                )
            )
        return packs

    async def _calculate_tree_size(self, tree_sha: str | None) -> int | None:
        if not tree_sha:
            return None
        tree_url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/git/trees/{tree_sha}?recursive=1"
        try:
            resp = await self._http.get(tree_url)
            if resp.status_code != 200:
                return None
            data = resp.json()
            tree_entries = data.get("tree", [])
            total = 0
            for item in tree_entries:
                if item.get("type") == "blob":
                    total += int(item.get("size") or 0)
            return total
        except Exception as exc:
            logger.debug("Failed to calculate tree size for %s: %s", tree_sha, exc)
            return None

    async def download_pack(
        self,
        pack: CommunityPack,
        dest_dir: Path,
        progress_callback: Callable[[float, int, int], asyncio.Future | bool | None] | None = None,
        max_retries: int = 2,
    ) -> Path:
        """
        Download a community pack ZIP to the destination directory.

        Args:
        ----
            pack: CommunityPack to download
            dest_dir: Directory to store the downloaded ZIP
            progress_callback: Optional callback(progress, downloaded_bytes, total_bytes) -> bool | None.
                If returns False, the download will be cancelled.
            max_retries: Number of simple retries for transient errors

        Returns:
        -------
            Path to the downloaded ZIP file.

        """
        dest_dir.mkdir(parents=True, exist_ok=True)

        # Choose a stable filename
        base_name = f"{pack.name}-{pack.version}".replace(" ", "_")
        final_path = dest_dir / f"{base_name}.zip"
        # Avoid overwriting
        if final_path.exists():
            i = 2
            while (dest_dir / f"{base_name}_{i}.zip").exists():
                i += 1
            final_path = dest_dir / f"{base_name}_{i}.zip"

        if pack.download_url:
            return await self._download_from_url(
                pack,
                final_path,
                progress_callback=progress_callback,
                max_retries=max_retries,
            )

        if pack.repo_path:
            return await self._download_repo_pack(
                pack,
                final_path,
                progress_callback=progress_callback,
            )

        raise RuntimeError(f"Pack {pack.name} has no download source")

    async def _download_from_url(
        self,
        pack: CommunityPack,
        final_path: Path,
        progress_callback: Callable[[float, int, int], asyncio.Future | bool | None] | None,
        max_retries: int,
    ) -> Path:
        attempt = 0
        last_exc: Exception | None = None
        while attempt <= max_retries:
            attempt += 1
            try:
                tmp_path: Path | None = None
                async with self._http.stream("GET", pack.download_url) as resp:
                    if resp.status_code != 200:
                        raise RuntimeError(f"Download failed with status {resp.status_code}")
                    total = int(resp.headers.get("Content-Length", "0") or 0)
                    downloaded = 0

                    parent_dir = str(final_path.parent)
                    with tempfile.NamedTemporaryFile(
                        delete=False, suffix=".zip", dir=parent_dir
                    ) as tmp:
                        tmp_path = Path(tmp.name)
                        async for chunk in resp.aiter_bytes(chunk_size=65536):
                            if not chunk:
                                continue
                            tmp.write(chunk)
                            downloaded += len(chunk)
                            if progress_callback is not None:
                                try:
                                    pct = (downloaded / total * 100.0) if total else 0.0
                                    res = progress_callback(pct, downloaded, total)
                                    if asyncio.iscoroutine(res):
                                        res = await res  # type: ignore[assignment]
                                    if res is False:
                                        raise asyncio.CancelledError(
                                            "Download cancelled by callback"
                                        )
                                except Exception as cb_err:
                                    logger.debug(f"Progress callback error ignored: {cb_err}")
                        tmp.flush()
                    tmp_path.replace(final_path)
                    return final_path
            except asyncio.CancelledError:
                # Cleanup partial file(s)
                with contextlib.suppress(Exception):
                    if final_path.exists():
                        final_path.unlink()
                    if tmp_path and tmp_path.exists():
                        tmp_path.unlink()
                raise
            except Exception as e:
                # Remove any temp file created this attempt
                with contextlib.suppress(Exception):
                    if tmp_path and tmp_path.exists():
                        tmp_path.unlink()
                last_exc = e
                logger.warning(f"Download attempt {attempt} failed: {e}")
                await asyncio.sleep(min(2 * attempt, 5))

        # Exhausted retries
        raise RuntimeError(f"Failed to download {pack.name}: {last_exc}")

    async def _download_repo_pack(
        self,
        pack: CommunityPack,
        final_path: Path,
        progress_callback: Callable[[float, int, int], asyncio.Future | bool | None] | None,
    ) -> Path:
        ref = pack.ref or "main"
        tree_entries = await self._fetch_tree_entries(pack)
        if not tree_entries:
            raise RuntimeError(f"No files found for {pack.name}")

        total_bytes = sum(
            int(item.get("size") or 0) for item in tree_entries if item.get("type") == "blob"
        )
        downloaded = 0

        staging_dir = Path(tempfile.mkdtemp(prefix="aw_pack_", dir=str(final_path.parent)))
        try:
            for item in tree_entries:
                if item.get("type") != "blob":
                    continue
                rel_path = item.get("path") or ""
                target_path = staging_dir / rel_path
                target_path.parent.mkdir(parents=True, exist_ok=True)
                raw_url = (
                    f"https://raw.githubusercontent.com/{self.repo_owner}/{self.repo_name}/"
                    f"{ref}/{pack.repo_path}/{rel_path}"
                )
                async with self._http.stream("GET", raw_url) as resp:
                    if resp.status_code != 200:
                        raise RuntimeError(
                            f"Failed to download {rel_path} (status {resp.status_code})"
                        )
                    with target_path.open("wb") as f:
                        async for chunk in resp.aiter_bytes(chunk_size=65536):
                            if not chunk:
                                continue
                            f.write(chunk)
                            downloaded += len(chunk)
                            if progress_callback is not None:
                                pct = (downloaded / total_bytes * 100.0) if total_bytes else 0.0
                                try:
                                    res = progress_callback(pct, downloaded, total_bytes)
                                    if asyncio.iscoroutine(res):
                                        res = await res  # type: ignore[assignment]
                                    if res is False:
                                        raise asyncio.CancelledError(
                                            "Download cancelled by callback"
                                        )
                                except Exception as cb_err:
                                    logger.debug("Progress callback error ignored: %s", cb_err)
            # Bundle into zip
            with zipfile.ZipFile(final_path, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
                for file_path in staging_dir.rglob("*"):
                    if file_path.is_file():
                        zipf.write(file_path, arcname=file_path.relative_to(staging_dir))
            return final_path
        except Exception:
            with contextlib.suppress(Exception):
                if final_path.exists():
                    final_path.unlink()
            raise
        finally:
            shutil.rmtree(staging_dir, ignore_errors=True)

    async def _fetch_tree_entries(self, pack: CommunityPack) -> list[dict[str, Any]]:
        tree_sha = pack.tree_sha
        if not tree_sha:
            return []
        tree_url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/git/trees/{tree_sha}?recursive=1"
        resp = await self._http.get(tree_url)
        if resp.status_code != 200:
            logger.error(
                "Failed to fetch tree %s for pack %s (status %s)",
                tree_sha,
                pack.name,
                resp.status_code,
            )
            return []
        data = resp.json()
        return data.get("tree", []) or []
