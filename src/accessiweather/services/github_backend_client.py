"""GitHub App backend service client for AccessiWeather.

This module provides a client for communicating with the AccessiWeather GitHub App
backend service, which handles GitHub App authentication and pull request creation.
"""

import asyncio
import logging
from typing import Any

import httpx

from ..version import __version__ as APP_VERSION

logger = logging.getLogger(__name__)


class GitHubBackendClient:
    """Client for the AccessiWeather GitHub App backend service.

    This client communicates with a backend service that handles GitHub App
    authentication and pull request creation, eliminating the need to manage
    GitHub App credentials directly in the client application.
    """

    def __init__(
        self,
        backend_url: str,
        *,
        user_agent: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        """Initialize the GitHub backend client.

        Args:
            backend_url: Base URL of the GitHub App backend service
            user_agent: Optional user-agent string
            timeout: Request timeout in seconds

        """
        self.backend_url = backend_url.rstrip("/")
        self.user_agent = user_agent or f"AccessiWeather/{APP_VERSION}"
        self.timeout = timeout

    async def create_pull_request(
        self,
        branch: str,
        title: str,
        body: str = "",
        *,
        cancel_event: asyncio.Event | None = None,
    ) -> dict[str, Any]:
        """Create a pull request via the backend service.

        Args:
            branch: The branch name to create PR from
            title: Pull request title
            body: Pull request description/body
            cancel_event: Optional cancellation event

        Returns:
            Dictionary containing PR information from GitHub API

        Raises:
            RuntimeError: If the backend request fails
            asyncio.CancelledError: If operation is cancelled

        """
        if cancel_event and cancel_event.is_set():
            raise asyncio.CancelledError("Operation cancelled by user")

        url = f"{self.backend_url}/create-pr"
        data = {
            "branch": branch,
            "title": title,
            "body": body,
        }

        headers = {
            "User-Agent": self.user_agent,
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                if cancel_event and cancel_event.is_set():
                    raise asyncio.CancelledError("Operation cancelled by user")

                logger.debug(f"Creating PR via backend: {url}")
                response = await client.post(url, json=data, headers=headers)

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
        """Check if the backend service is available.

        Args:
            cancel_event: Optional cancellation event

        Returns:
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
