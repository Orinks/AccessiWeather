"""
GitHub App backend service client for AccessiWeather.

This module provides a client for communicating with the AccessiWeather GitHub App
backend service, which handles GitHub App authentication and soundpack submissions.
"""

import asyncio
import logging
from typing import Any

import httpx

from .. import __version__ as APP_VERSION

logger = logging.getLogger(__name__)


class GitHubBackendClient:
    """
    Client for the AccessiWeather GitHub App backend service.

    This client communicates with a backend service that handles GitHub App
    authentication and soundpack submission, eliminating the need to manage
    GitHub App credentials directly in the client application.
    """

    def __init__(
        self,
        backend_url: str,
        *,
        user_agent: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        """
        Initialize the GitHub backend client.

        Args:
        ----
            backend_url: Base URL of the GitHub App backend service
            user_agent: Optional user-agent string
            timeout: Request timeout in seconds

        """
        self.backend_url = backend_url.rstrip("/")
        self.user_agent = user_agent or f"AccessiWeather/{APP_VERSION}"
        self.timeout = timeout

    async def upload_zip(
        self,
        zip_bytes: bytes,
        filename: str = "soundpack.zip",
        *,
        cancel_event: asyncio.Event | None = None,
    ) -> dict[str, Any]:
        """
        Upload a ZIP soundpack to the backend which will create a PR.

        Args:
        ----
            zip_bytes: Bytes of the ZIP file containing pack.json and audio files
            filename: Name to send for the multipart file
            cancel_event: Optional cancellation event

        Returns:
        -------
            Dictionary containing PR information from the backend

        """
        if cancel_event and cancel_event.is_set():
            raise asyncio.CancelledError("Operation cancelled by user")

        url = f"{self.backend_url}/upload-zip"
        headers = {"User-Agent": self.user_agent}
        files = {"zip_file": (filename, zip_bytes, "application/zip")}

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                if cancel_event and cancel_event.is_set():
                    raise asyncio.CancelledError("Operation cancelled by user")

                logger.debug(f"Uploading soundpack ZIP to backend: {url}")
                response = await client.post(url, files=files, headers=headers)

                if cancel_event and cancel_event.is_set():
                    raise asyncio.CancelledError("Operation cancelled by user")

                if response.status_code >= 400:
                    error_detail = "Unknown error"
                    try:
                        error_data = response.json()
                        error_detail = error_data.get("detail", response.text)
                    except Exception:
                        error_detail = response.text

                    raise RuntimeError(
                        f"Backend service error (HTTP {response.status_code}): {error_detail}"
                    )

                return response.json()

        except asyncio.CancelledError:
            raise
        except httpx.TimeoutException as e:
            raise RuntimeError(f"Backend service timeout after {self.timeout}s") from e
        except httpx.RequestError as e:
            raise RuntimeError(f"Failed to connect to backend service: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Unexpected error communicating with backend: {e}") from e

    async def upload_pack_json_only(
        self,
        pack_data: dict[str, Any],
        *,
        cancel_event: asyncio.Event | None = None,
    ) -> dict[str, Any]:
        """Submit only pack.json metadata (legacy endpoint)."""
        if cancel_event and cancel_event.is_set():
            raise asyncio.CancelledError("Operation cancelled by user")

        url = f"{self.backend_url}/share-pack"
        headers = {"User-Agent": self.user_agent, "Content-Type": "application/json"}

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=pack_data, headers=headers)
                if cancel_event and cancel_event.is_set():
                    raise asyncio.CancelledError("Operation cancelled by user")
                if response.status_code >= 400:
                    error_detail = "Unknown error"
                    try:
                        error_data = response.json()
                        error_detail = error_data.get("detail", response.text)
                    except Exception:
                        error_detail = response.text
                    raise RuntimeError(
                        f"Backend service error (HTTP {response.status_code}): {error_detail}"
                    )
                return response.json()
        except asyncio.CancelledError:
            raise
        except httpx.TimeoutException as e:
            raise RuntimeError(f"Backend service timeout after {self.timeout}s") from e
        except httpx.RequestError as e:
            raise RuntimeError(f"Failed to connect to backend service: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Unexpected error communicating with backend: {e}") from e

    async def health_check(self, *, cancel_event: asyncio.Event | None = None) -> bool:
        """
        Check if the backend service is available.

        Args:
        ----
            cancel_event: Optional cancellation event

        Returns:
        -------
            True if backend is healthy, False otherwise

        """
        if cancel_event and cancel_event.is_set():
            return False

        try:
            url = f"{self.backend_url}/health"
            headers = {"User-Agent": self.user_agent}

            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url, headers=headers)
                return response.status_code == 200

        except Exception:
            return False
