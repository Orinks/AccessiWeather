from __future__ import annotations

import asyncio
import base64
import logging
import os
import re
from collections.abc import Callable
from pathlib import Path

import httpx

from accessiweather.config import ConfigManager
from accessiweather.notifications.sound_player import validate_sound_pack
from accessiweather.version import __version__ as APP_VERSION

logger = logging.getLogger(__name__)


class PackSubmissionService:
    """Service to validate a sound pack and submit it to the community repo via GitHub REST API.

    This uses direct HTTP calls to the GitHub API (no git/gh CLI), preserving
    progress reporting and cancellation semantics.
    """

    def __init__(
        self,
        repo_owner: str = "accessiweather-community",
        repo_name: str = "soundpacks",
        dest_subdir: str = "packs",
        user_agent: str | None = None,
        default_base_branch: str = "main",
        config_manager: ConfigManager | None = None,
    ) -> None:
        """Initialize the submission service.

        Args:
            repo_owner: GitHub org/user that hosts community packs
            repo_name: Repository name for packs
            dest_subdir: Subdirectory within repo to place packs
            user_agent: Optional user-agent string
            default_base_branch: The base branch to target PRs against
            config_manager: Configuration manager for accessing GitHub App configuration

        """
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.dest_subdir = dest_subdir
        self.default_base_branch = default_base_branch
        self.user_agent = user_agent or f"AccessiWeather/{APP_VERSION}"
        self.config_manager = config_manager

    async def submit_pack(
        self,
        pack_path: Path,
        pack_meta: dict,
        progress_callback: Callable[[float, str], bool | None] | None = None,
        cancel_event: asyncio.Event | None = None,
    ) -> str:
        """Validate, prepare, and submit a sound pack as a GitHub PR (API-based).

        This implementation uses the GitHub REST API via httpx, preserving the
        existing interface, progress reporting, and cancellation behavior.
        """
        if cancel_event is None:
            cancel_event = asyncio.Event()

        async def report(pct: float, status: str) -> None:
            try:
                if progress_callback is not None:
                    res = progress_callback(pct, status)
                    if asyncio.iscoroutine(res):
                        res = await res
                    if res is False:
                        cancel_event.set()
                        raise asyncio.CancelledError("Operation cancelled by user")
            except asyncio.CancelledError:
                raise
            except Exception:
                pass

        await report(5.0, "Checking prerequisites...")

        # Verify GitHub App configuration
        await report(7.0, "Verifying GitHub App authentication...")

        # TODO: Replace with GitHub App authentication
        # This is a placeholder for the GitHub App integration
        raise NotImplementedError(
            "GitHub App authentication not yet implemented. User tokens are no longer supported."
        )

        # TODO: Implement GitHub App authentication flow to restore pack submission functionality

    def _get_auth_client_with_headers(self, headers: dict) -> httpx.AsyncClient:
        """Create an authenticated HTTP client with the provided headers.
        
        Args:
            headers: Dictionary of HTTP headers to include in requests
            
        Returns:
            Configured httpx.AsyncClient for GitHub API requests
        """
        default_headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": self.user_agent,
            "X-GitHub-Api-Version": "2022-11-28",
        }
        # Merge provided headers with defaults, allowing overrides
        final_headers = {**default_headers, **headers}
        
        timeout = httpx.Timeout(30.0)
        return httpx.AsyncClient(
            base_url="https://api.github.com/", headers=final_headers, timeout=timeout
        )

    def _get_auth_client_for_installation(self, installation_token: str) -> httpx.AsyncClient:
        """Create an authenticated HTTP client for GitHub App installation.
        
        Args:
            installation_token: GitHub App installation access token
            
        Returns:
            Configured httpx.AsyncClient for GitHub API requests with App authentication
        """
        headers = {
            "Authorization": f"token {installation_token}",
        }
        return self._get_auth_client_with_headers(headers)

    def _raise_if_cancelled(self, cancel_event: asyncio.Event | None) -> None:
        """Check cancellation and raise if cancelled."""
        if cancel_event and cancel_event.is_set():
            raise asyncio.CancelledError("Operation cancelled by user")

    async def _github_request(
        self,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        *,
        json: dict | None = None,
        params: dict | None = None,
        expected: int | tuple[int, ...] = (200, 201),
        cancel_event: asyncio.Event | None = None,
    ) -> dict:
        self._raise_if_cancelled(cancel_event)
        resp = await client.request(method, url, json=json, params=params)
        if resp.status_code == 404 and 404 in (
            expected if isinstance(expected, tuple) else (expected,)
        ):
            return {}
        if resp.status_code not in (expected if isinstance(expected, tuple) else (expected,)):
            try:
                detail = resp.json()
            except Exception:
                detail = {"message": resp.text}
            raise RuntimeError(f"GitHub API error {resp.status_code} for {url}: {detail}")
        try:
            return resp.json()
        except Exception:
            return {}

    async def _get_repo_info(
        self, client: httpx.AsyncClient, cancel_event: asyncio.Event | None = None
    ) -> dict:
        return await self._github_request(
            client, "GET", f"/repos/{self.repo_owner}/{self.repo_name}", cancel_event=cancel_event
        )

    async def _get_user_login(
        self, client: httpx.AsyncClient, cancel_event: asyncio.Event | None = None
    ) -> str:
        me = await self._github_request(client, "GET", "/user", cancel_event=cancel_event)
        login = me.get("login")
        if not login:
            raise RuntimeError("Unable to determine authenticated user login")
        return login

    async def _ensure_fork(
        self, client: httpx.AsyncClient, login: str, cancel_event: asyncio.Event | None = None
    ) -> str:
        # Try to get fork; if missing, create
        fork_name = f"{login}/{self.repo_name}"
        repo = await self._github_request(
            client, "GET", f"/repos/{fork_name}", cancel_event=cancel_event
        )
        if (
            repo.get("fork")
            and repo.get("parent", {}).get("full_name") == f"{self.repo_owner}/{self.repo_name}"
        ):
            return repo["full_name"]
        # Create fork
        await self._github_request(
            client,
            "POST",
            f"/repos/{self.repo_owner}/{self.repo_name}/forks",
            expected=(202, 201),
            cancel_event=cancel_event,
        )
        # Fork creation can be asynchronous; poll a few times
        for _ in range(10):
            self._raise_if_cancelled(cancel_event)
            await asyncio.sleep(1)
            repo = await self._github_request(
                client, "GET", f"/repos/{fork_name}", cancel_event=cancel_event
            )
            if repo.get("full_name"):
                return repo["full_name"]
        raise RuntimeError("Timed out waiting for fork to become available")

    async def _get_branch_sha(self, client: httpx.AsyncClient, full_name: str, branch: str) -> str:
        ref = await self._github_request(
            client, "GET", f"/repos/{full_name}/git/ref/heads/{branch}", expected=(200,)
        )
        obj = ref.get("object") or {}
        sha = obj.get("sha")
        if not sha:
            raise RuntimeError(f"Unable to resolve branch SHA for {full_name}@{branch}")
        return sha

    async def _create_branch(
        self, client: httpx.AsyncClient, full_name: str, branch: str, base_sha: str
    ) -> None:
        await self._github_request(
            client,
            "POST",
            f"/repos/{full_name}/git/refs",
            json={"ref": f"refs/heads/{branch}", "sha": base_sha},
            expected=(201,),
        )

    async def _upload_file(
        self,
        client: httpx.AsyncClient,
        full_name: str,
        path: str,
        content: bytes,
        message: str,
        branch: str,
    ) -> None:
        import urllib.parse

        b64 = base64.b64encode(content).decode("ascii")
        encoded_path = urllib.parse.quote(path, safe="/")
        await self._github_request(
            client,
            "PUT",
            f"/repos/{full_name}/contents/{encoded_path}",
            json={"message": message, "content": b64, "branch": branch},
            expected=(201, 200),
        )

    async def _create_pull_request(
        self,
        client: httpx.AsyncClient,
        upstream_full_name: str,
        title: str,
        body: str,
        head: str,
        base: str,
        label: str | None = None,
    ) -> str:
        pr = await self._github_request(
            client,
            "POST",
            f"/repos/{upstream_full_name}/pulls",
            json={"title": title, "body": body, "head": head, "base": base},
            expected=(201,),
        )
        # Optionally add label
        if label:
            from contextlib import suppress

            with suppress(Exception):
                await self._github_request(
                    client,
                    "POST",
                    f"/repos/{upstream_full_name}/issues/{pr['number']}/labels",
                    json={"labels": [label]},
                    expected=(200,),
                )
        return pr.get("html_url") or ""

    async def _path_exists(
        self,
        client: httpx.AsyncClient,
        full_name: str,
        path: str,
        ref: str,
        cancel_event: asyncio.Event | None = None,
    ) -> bool:
        import urllib.parse

        encoded_path = urllib.parse.quote(path, safe="/")
        result = await self._github_request(
            client,
            "GET",
            f"/repos/{full_name}/contents/{encoded_path}",
            params={"ref": ref},
            expected=(200, 404),
            cancel_event=cancel_event,
        )
        return bool(result)  # Empty dict for 404, non-empty for 200

    # Internal helpers

    @staticmethod
    def _derive_pack_id(pack_path: Path, meta: dict) -> str:
        # Prefer metadata name, then directory name, with optional author for uniqueness
        name = (meta.get("name") or pack_path.name or "pack").strip()
        author = (meta.get("author") or "").strip()

        # Include author if available to reduce collision risk
        pack_id = f"{name}-{author}" if author and author.lower() != "unknown" else name

        return PackSubmissionService._sanitize_id(pack_id)

    @staticmethod
    def _sanitize_id(text: str) -> str:
        s = text.strip().lower()
        s = s.replace(" ", "-")
        s = re.sub(r"[^a-z0-9\-]+", "", s)
        return s or "pack"

    @staticmethod
    def _build_branch_name(pack_id: str) -> str:
        import time as _time

        ts = _time.strftime("%Y%m%d-%H%M%S")
        return f"soundpack/{pack_id}-{ts}"
