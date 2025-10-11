from __future__ import annotations

import asyncio
import io
import logging
import re
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from accessiweather.config import ConfigManager

from accessiweather import __version__ as APP_VERSION
from accessiweather.constants import COMMUNITY_REPO_NAME, COMMUNITY_REPO_OWNER
from accessiweather.notifications.sound_player import validate_sound_pack
from accessiweather.services.github_backend_client import GitHubBackendClient

logger = logging.getLogger(__name__)


class PackSubmissionService:
    """
    Service to validate a sound pack and submit it to the community repo via backend.

    All submissions are handled by the AccessiWeather backend service. No local GitHub
    credentials (tokens or App keys) are required by the client.
    """

    def __init__(
        self,
        repo_owner: str = COMMUNITY_REPO_OWNER,
        repo_name: str = COMMUNITY_REPO_NAME,
        dest_subdir: str = "packs",
        user_agent: str | None = None,
        default_base_branch: str = "main",
        config_manager: ConfigManager | None = None,
    ) -> None:
        """
        Initialize the submission service.

        Args:
        ----
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

    def _get_backend_client(self) -> GitHubBackendClient:
        """
        Get a configured backend client.

        Returns
        -------
            GitHubBackendClient instance

        """
        # Get backend URL from config if available, otherwise use default
        if self.config_manager:
            backend_url = self.config_manager.get_github_backend_url()
        else:
            # Use default backend URL when no config manager is available
            backend_url = "https://soundpack-backend.fly.dev"

        return GitHubBackendClient(
            backend_url=backend_url,
            user_agent=self.user_agent,
        )

    async def submit_pack(
        self,
        pack_path: Path,
        pack_meta: dict,
        progress_callback: Callable[[float, str], bool | None] | None = None,
        cancel_event: asyncio.Event | None = None,
    ) -> str:
        """
        Submit a sound pack as a GitHub PR using the backend service.

        All submissions now go through the backend service for consistency and security.
        No local GitHub App credentials are required.

        Args:
        ----
            pack_path: Path to the sound pack directory
            pack_meta: Pack metadata dictionary
            progress_callback: Optional progress callback function
            cancel_event: Optional cancellation event

        Returns:
        -------
            URL of the created pull request

        Raises:
        ------
            RuntimeError: If backend service fails or pack validation fails
            asyncio.CancelledError: If operation is cancelled

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

        # All submissions now use the backend service
        return await self._submit_pack_via_backend(
            pack_path, pack_meta, "System", "", report, cancel_event
        )

    async def submit_pack_anonymous(
        self,
        pack_path: Path,
        pack_meta: dict,
        submitter_name: str,
        submitter_email: str,
        progress_callback: Callable[[float, str], bool | None] | None = None,
        cancel_event: asyncio.Event | None = None,
    ) -> str:
        """
        Submit a sound pack with submitter attribution using the backend service.

        This method includes submitter attribution in the pull request description,
        allowing users to get credit for their contributions while using the backend
        service for all GitHub operations.

        Args:
        ----
            pack_path: Path to the sound pack directory
            pack_meta: Pack metadata dictionary
            submitter_name: Name of the person submitting the pack
            submitter_email: Email of the person submitting the pack
            progress_callback: Optional progress callback function
            cancel_event: Optional cancellation event

        Returns:
        -------
            URL of the created pull request

        Raises:
        ------
            RuntimeError: If backend service fails or pack validation fails
            asyncio.CancelledError: If operation is cancelled

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

        # Use backend service for all submissions
        return await self._submit_pack_via_backend(
            pack_path, pack_meta, submitter_name, submitter_email, report, cancel_event
        )

    async def _submit_pack_via_backend(
        self,
        pack_path: Path,
        pack_meta: dict,
        submitter_name: str,
        submitter_email: str,
        report: Callable[[float, str], None],
        cancel_event: asyncio.Event,
    ) -> str:
        """Submit pack using the backend service via the new endpoints."""
        await report(7.0, "Connecting to backend service...")

        # Get backend client
        backend_client = self._get_backend_client()

        await report(10.0, "Validating sound pack...")

        # Validate pack
        ok, msg = validate_sound_pack(pack_path)
        if not ok:
            raise RuntimeError(f"Sound pack validation failed for {pack_path}: {msg}")

        await report(15.0, "Preparing pack submission...")

        # Derive pack ID
        pack_id = self._derive_pack_id(pack_path, pack_meta)

        await report(20.0, "Packaging sound pack...")

        # Create an in-memory ZIP of the sound pack directory (rooted at pack_path)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in pack_path.rglob("*"):
                if path.is_file():
                    arcname = path.relative_to(pack_path).as_posix()
                    zf.write(path, arcname)
        buf.seek(0)

        await report(70.0, "Uploading pack to backend...")

        # Upload ZIP to backend; backend will validate and create the PR
        pr_data = await backend_client.upload_zip(
            zip_bytes=buf.getvalue(),
            filename=f"{pack_id}.zip",
            cancel_event=cancel_event,
        )

        pr_url = pr_data.get("html_url", "")
        await report(100.0, f"Pull request created: {pr_url}")
        return pr_url

    def _raise_if_cancelled(self, cancel_event: asyncio.Event | None) -> None:
        """Check cancellation and raise if cancelled."""
        if cancel_event and cancel_event.is_set():
            raise asyncio.CancelledError("Operation cancelled by user")

    def _build_pr_content(
        self, pack_meta: dict, pack_id: str, is_anonymous: bool = False
    ) -> tuple[str, str]:
        """Build pull request title and body content."""
        pack_name = pack_meta.get("name", pack_id)
        pack_author = pack_meta.get("author", "Unknown")
        pack_description = pack_meta.get("description", "No description provided")

        # Build title
        if is_anonymous:
            title = f"Add community sound pack: {pack_name}"
        else:
            title = f"Add sound pack: {pack_name} by {pack_author}"

        # Build body
        body_lines = [
            f"## Sound Pack Submission: {pack_name}",
            "",
            f"**Pack ID:** `{pack_id}`",
            f"**Author:** {pack_author}",
            f"**Description:** {pack_description}",
            "",
        ]

        # Add submitter attribution for anonymous submissions
        if is_anonymous and "_submitter" in pack_meta:
            submitter = pack_meta["_submitter"]
            body_lines.extend(
                [
                    "## Submitter Information",
                    f"**Submitted by:** {submitter.get('name', 'Unknown')}",
                    f"**Email:** {submitter.get('email', 'Not provided')}",
                    f"**Submission Type:** Anonymous submission via AccessiBotApp",
                    "",
                ]
            )

        # Add pack details
        sounds = pack_meta.get("sounds", {})
        if sounds:
            body_lines.extend(["## Pack Contents", ""])
            for sound_key, filename in sounds.items():
                body_lines.append(f"- **{sound_key}:** {filename}")
            body_lines.append("")

        body_lines.extend(
            [
                "## Submission Details",
                "- This pack has been validated using AccessiWeather's sound pack validation system",
                "- All files have been uploaded and are ready for review",
                "- This submission was created automatically via the AccessiWeather pack submission service",
                "",
                "---",
                "*This pull request was created automatically by AccessiBotApp on behalf of the community.*",
            ]
        )

        return title, "\n".join(body_lines)

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
