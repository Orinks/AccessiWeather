"""Download helpers for the GitHub update service."""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

import httpx

from ...utils.retry_utils import async_retry_with_backoff
from .signature_verification import SignatureVerifier

logger = logging.getLogger(__name__)


def _looks_like_update_info(obj: object) -> bool:
    return hasattr(obj, "download_url") and hasattr(obj, "artifact_name")


class CancelEvent(Protocol):
    """Protocol describing the subset of cancel event behaviour we rely on."""

    def is_set(self) -> bool:  # pragma: no cover - structural typing only
        ...


ProgressCallback = Callable[[int, int], None]


class DownloadManager:
    """Stream update assets to disk with verification and progress callbacks."""

    def __init__(self, http_client: httpx.AsyncClient, config_dir: Path, app_name: str) -> None:
        """Initialise the download manager."""
        self.http_client = http_client
        self.config_dir = config_dir
        self.app_name = app_name

    async def download_update(
        self,
        asset_or_info,
        dest_path: str | Path | None = None,
        progress_callback: ProgressCallback | None = None,
        cancel_event: CancelEvent | None = None,
        expected_sha256: str | None = None,
        checksums_url: str | None = None,
        artifact_name: str | None = None,
    ) -> str | bool:
        """Compatibility wrapper for both legacy and dataclass-based downloads."""
        if _looks_like_update_info(asset_or_info):
            info = asset_or_info

            if callable(dest_path) and progress_callback is None:
                progress_callback = dest_path  # type: ignore[assignment]
                dest_path = None

            url = getattr(info, "download_url", None)
            if not url:
                logger.error("UpdateInfo-like object missing download_url")
                return False

            name = artifact_name or getattr(info, "artifact_name", None)
            if not name:
                try:
                    from urllib.parse import urlparse

                    parsed = urlparse(url)
                    name = Path(parsed.path).name or f"{self.app_name}-update"
                except Exception:  # noqa: BLE001 - fall back to default name
                    name = f"{self.app_name}-update"

            file_size = getattr(info, "file_size", None)

            dest_dir = self.config_dir / "updates"
            dest_dir.mkdir(parents=True, exist_ok=True)
            file_path = dest_dir / name

            try:
                return await self._download_asset(
                    url,
                    file_path,
                    progress_callback=progress_callback,
                    cancel_event=cancel_event,
                    expected_sha256=expected_sha256,
                    checksums_url=checksums_url,
                    artifact_name=name,
                    expected_size=file_size,
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                return False

        if dest_path is None:
            logger.error("dest_path is required when calling download_update with a URL")
            return False

        with contextlib.suppress(Exception):
            Path(dest_path).parent.mkdir(parents=True, exist_ok=True)

        try:
            return await self._download_asset(
                asset_or_info,
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

    @async_retry_with_backoff(max_attempts=3, base_delay=2.0, timeout=300.0)
    async def _download_asset(
        self,
        asset_url: str,
        dest_path: str | Path,
        progress_callback: ProgressCallback | None = None,
        cancel_event: CancelEvent | None = None,
        expected_sha256: str | None = None,
        checksums_url: str | None = None,
        signature_url: str | None = None,
        artifact_name: str | None = None,
        expected_size: int | None = None,
    ) -> str | bool:
        if not asset_url or not dest_path:
            logger.error("asset_url and dest_path are required for legacy download call")
            return False

        dest_path = Path(dest_path)

        if cancel_event and cancel_event.is_set():
            logger.info("Download cancelled before start")
            return False

        dest_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(dest_path, "wb") as file_obj:
                try:
                    async with self.http_client.stream(
                        "GET", asset_url, follow_redirects=True
                    ) as response:
                        response.raise_for_status()
                        total = int(response.headers.get("content-length", 0))
                        downloaded = 0

                        async for chunk in response.aiter_bytes():
                            if cancel_event and cancel_event.is_set():
                                logger.info("Download cancelled")
                                file_obj.close()
                                dest_path.unlink(missing_ok=True)
                                return False
                            file_obj.write(chunk)
                            downloaded += len(chunk)
                            if progress_callback:
                                with contextlib.suppress(Exception):
                                    progress_callback(downloaded, total)
                except Exception as exc:  # noqa: BLE001 - ensure cleanup and propagate failure
                    logger.error(f"Download failed: {exc}")
                    try:
                        file_obj.close()
                        dest_path.unlink(missing_ok=True)
                    except Exception:  # noqa: BLE001 - best effort cleanup
                        pass
                    raise

            # Verify file size
            if dest_path.stat().st_size == 0:
                logger.error("Downloaded file is empty")
                dest_path.unlink(missing_ok=True)
                return False

            if expected_size is not None:
                actual_size = dest_path.stat().st_size
                if actual_size != expected_size:
                    logger.error(
                        "Downloaded file size mismatch: expected %s, got %s",
                        expected_size,
                        actual_size,
                    )
                    dest_path.unlink(missing_ok=True)
                    return False

            if expected_sha256 and not self._verify_sha256(dest_path, expected_sha256):
                return False

            if (
                checksums_url
                and artifact_name
                and not await self._verify_checksums_txt(dest_path, checksums_url, artifact_name)
            ):
                return False

            if signature_url and not await SignatureVerifier.download_and_verify_signature(
                dest_path, signature_url
            ):
                return False

            try:
                return str(dest_path)
            except Exception:  # noqa: BLE001 - return Path fallback
                return dest_path
        except Exception as exc:  # noqa: BLE001 - ensure failures are logged
            logger.error(f"Download failed: {exc}")
            with contextlib.suppress(Exception):
                dest_path.unlink(missing_ok=True)
            raise

    @staticmethod
    def _verify_sha256(dest_path: Path, expected_sha256: str) -> bool:
        digest = hashlib.sha256()
        with open(dest_path, "rb") as file_obj:
            for chunk in iter(lambda: file_obj.read(8192), b""):
                digest.update(chunk)
        computed = digest.hexdigest()
        if computed.lower() != expected_sha256.lower():
            logger.error(
                "SHA256 mismatch: expected %s, got %s",
                expected_sha256,
                computed,
            )
            dest_path.unlink(missing_ok=True)
            return False
        return True

    @async_retry_with_backoff(max_attempts=2, base_delay=1.0, timeout=15.0)
    async def _verify_checksums_txt(
        self,
        dest_path: Path,
        checksums_url: str,
        artifact_name: str,
    ) -> bool:
        try:
            response = await self.http_client.get(checksums_url, follow_redirects=True)
            response.raise_for_status()
            lines = response.text.splitlines()
            expected: str | None = None
            for line in lines:
                parts = line.strip().split()
                if len(parts) == 2 and parts[1] == artifact_name:
                    expected = parts[0]
                    break
            if expected:
                digest = hashlib.sha256()
                with open(dest_path, "rb") as file_obj:
                    for chunk in iter(lambda: file_obj.read(8192), b""):
                        digest.update(chunk)
                computed = digest.hexdigest()
                if computed.lower() != expected.lower():
                    logger.error(
                        "SHA256 mismatch from checksums.txt: expected %s, got %s",
                        expected,
                        computed,
                    )
                    dest_path.unlink(missing_ok=True)
                    return False
            return True
        except Exception as exc:  # noqa: BLE001 - log and fail to ensure caller cleans up
            logger.error(f"Failed to verify checksum from checksums.txt: {exc}")
            dest_path.unlink(missing_ok=True)
            raise
