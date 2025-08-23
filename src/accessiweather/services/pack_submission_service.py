from __future__ import annotations

import asyncio
import base64
import logging
import os
import re
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from accessiweather.config import ConfigManager

from accessiweather.notifications.sound_player import validate_sound_pack
from accessiweather.services.github_app_client import GitHubAppClient
from accessiweather.version import __version__ as APP_VERSION

logger = logging.getLogger(__name__)


class PackSubmissionService:
    """Service to validate a sound pack and submit it to the community repo via GitHub REST API.

    This service uses GitHub App authentication for all API operations, providing
    secure and authenticated access to the GitHub API without requiring user tokens.
    """

    def __init__(
        self,
        repo_owner: str = "accessiweather-community",
        repo_name: str = "soundpacks",
        dest_subdir: str = "packs",
        user_agent: str | None = None,
        default_base_branch: str = "main",
        config_manager: "ConfigManager" | None = None,
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
        """Validate, prepare, and submit a sound pack as a GitHub PR using GitHub App authentication.

        This implementation uses GitHub App authentication via GitHubAppClient for all
        GitHub API operations, maintaining existing progress reporting and cancellation behavior.

        Args:
            pack_path: Path to the sound pack directory
            pack_meta: Pack metadata dictionary
            progress_callback: Optional progress callback function
            cancel_event: Optional cancellation event

        Returns:
            URL of the created pull request

        Raises:
            RuntimeError: If GitHub App configuration is invalid or API calls fail
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

        # Verify GitHub App configuration
        await report(7.0, "Verifying GitHub App authentication...")
        
        if not self.config_manager:
            raise RuntimeError("No configuration manager provided for GitHub App authentication")
        
        is_valid, message = self.config_manager.validate_github_app_config()
        if not is_valid:
            raise RuntimeError(f"GitHub App configuration invalid: {message}")

        # Get GitHub App configuration
        app_id, private_key, installation_id = self.config_manager.get_github_app_config()

        # Create GitHub App client
        github_client = GitHubAppClient(
            app_id=app_id,
            private_key_pem=private_key,
            installation_id=installation_id,
            user_agent=self.user_agent,
        )

        await report(10.0, "Validating sound pack...")
        
        # Validate pack
        if not validate_sound_pack(pack_path):
            raise RuntimeError(f"Sound pack validation failed for {pack_path}")

        # Rest of implementation follows existing pattern with GitHub App client
        return await self._submit_pack_with_github_client(
            github_client, pack_path, pack_meta, report, cancel_event
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
        """Submit a sound pack anonymously with submitter attribution using GitHub App authentication.

        This method allows users to submit packs without requiring their own GitHub account,
        using AccessiBot (GitHub App) credentials for all operations while properly attributing
        the submitter in the pull request description.

        Args:
            pack_path: Path to the sound pack directory
            pack_meta: Pack metadata dictionary
            submitter_name: Name of the person submitting the pack
            submitter_email: Email of the person submitting the pack
            progress_callback: Optional progress callback function
            cancel_event: Optional cancellation event

        Returns:
            URL of the created pull request

        Raises:
            RuntimeError: If GitHub App configuration is invalid or API calls fail
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

        # Verify GitHub App configuration
        await report(7.0, "Verifying GitHub App authentication...")
        
        if not self.config_manager:
            raise RuntimeError("No configuration manager provided for GitHub App authentication")
        
        is_valid, message = self.config_manager.validate_github_app_config()
        if not is_valid:
            raise RuntimeError(f"GitHub App configuration invalid: {message}")

        # Get GitHub App configuration
        app_id, private_key, installation_id = self.config_manager.get_github_app_config()

        # Create GitHub App client
        github_client = GitHubAppClient(
            app_id=app_id,
            private_key_pem=private_key,
            installation_id=installation_id,
            user_agent=self.user_agent,
        )

        await report(10.0, "Validating sound pack...")
        
        # Validate pack
        if not validate_sound_pack(pack_path):
            raise RuntimeError(f"Sound pack validation failed for {pack_path}")

        # Create enhanced metadata with submitter attribution
        enhanced_meta = pack_meta.copy()
        enhanced_meta["_submitter"] = {
            "name": submitter_name,
            "email": submitter_email,
            "submission_type": "anonymous"
        }

        # Rest of implementation follows existing pattern with GitHub App client
        return await self._submit_pack_with_github_client(
            github_client, pack_path, enhanced_meta, report, cancel_event, is_anonymous=True
        )

    async def _submit_pack_with_github_client(
        self,
        github_client: GitHubAppClient,
        pack_path: Path,
        pack_meta: dict,
        report: Callable[[float, str], None],
        cancel_event: asyncio.Event,
        is_anonymous: bool = False,
    ) -> str:
        """Internal method to handle pack submission with an authenticated GitHub client.

        This method implements the actual pack submission workflow using the GitHub App client.
        """
        await report(15.0, "Connecting to GitHub...")

        # Get repository information
        upstream_full_name = f"{self.repo_owner}/{self.repo_name}"
        repo = await github_client.github_request(
            "GET", f"/repos/{upstream_full_name}", cancel_event=cancel_event
        )
        if not repo:
            raise RuntimeError(f"Repository {upstream_full_name} not found or not accessible")

        await report(20.0, "Getting AccessiBot user info...")
        
        # Get the authenticated user (AccessiBot)
        me = await github_client.github_request("GET", "/user", cancel_event=cancel_event)
        bot_login = me.get("login")
        if not bot_login:
            raise RuntimeError("Unable to determine authenticated user login")

        await report(25.0, "Ensuring fork exists...")
        
        # Ensure fork exists
        fork_full_name = await self._ensure_fork(github_client, bot_login, cancel_event)
        
        await report(35.0, "Preparing pack submission...")
        
        # Derive pack ID and branch name
        pack_id = self._derive_pack_id(pack_path, pack_meta)
        branch_name = self._build_branch_name(pack_id)
        
        await report(40.0, f"Creating branch '{branch_name}'...")
        
        # Get base branch SHA
        base_sha = await self._get_branch_sha(github_client, upstream_full_name, self.default_base_branch)
        
        # Create new branch
        await self._create_branch(github_client, fork_full_name, branch_name, base_sha)
        
        await report(50.0, "Uploading pack files...")
        
        # Upload pack files
        await self._upload_pack_files(github_client, fork_full_name, pack_path, pack_id, branch_name, cancel_event, report)
        
        await report(80.0, "Creating pull request...")
        
        # Create pull request
        pr_title, pr_body = self._build_pr_content(pack_meta, pack_id, is_anonymous)
        head = f"{bot_login}:{branch_name}"
        
        pr_url = await self._create_pull_request(
            github_client,
            upstream_full_name,
            pr_title,
            pr_body,
            head,
            self.default_base_branch,
            label="community-submission",
        )
        
        await report(100.0, f"Pull request created: {pr_url}")
        return pr_url

    def _raise_if_cancelled(self, cancel_event: asyncio.Event | None) -> None:
        """Check cancellation and raise if cancelled."""
        if cancel_event and cancel_event.is_set():
            raise asyncio.CancelledError("Operation cancelled by user")

    async def _ensure_fork(
        self, github_client: GitHubAppClient, login: str, cancel_event: asyncio.Event | None = None
    ) -> str:
        # Try to get fork; if missing, create
        fork_name = f"{login}/{self.repo_name}"
        repo = await github_client.github_request(
            "GET", f"/repos/{fork_name}", expected=(200, 404), cancel_event=cancel_event
        )
        if (
            repo.get("fork")
            and repo.get("parent", {}).get("full_name") == f"{self.repo_owner}/{self.repo_name}"
        ):
            return repo["full_name"]
        # Create fork
        await github_client.github_request(
            "POST",
            f"/repos/{self.repo_owner}/{self.repo_name}/forks",
            expected=(202, 201),
            cancel_event=cancel_event,
        )
        # Fork creation can be asynchronous; poll a few times
        for _ in range(10):
            self._raise_if_cancelled(cancel_event)
            await asyncio.sleep(1)
            repo = await github_client.github_request(
                "GET", f"/repos/{fork_name}", expected=(200, 404), cancel_event=cancel_event
            )
            if repo.get("full_name"):
                return repo["full_name"]
        raise RuntimeError("Timed out waiting for fork to become available")

    async def _get_branch_sha(self, github_client: GitHubAppClient, full_name: str, branch: str) -> str:
        ref = await github_client.github_request(
            "GET", f"/repos/{full_name}/git/ref/heads/{branch}", expected=(200,)
        )
        obj = ref.get("object") or {}
        sha = obj.get("sha")
        if not sha:
            raise RuntimeError(f"Unable to resolve branch SHA for {full_name}@{branch}")
        return sha

    async def _create_branch(
        self, github_client: GitHubAppClient, full_name: str, branch: str, base_sha: str
    ) -> None:
        await github_client.github_request(
            "POST",
            f"/repos/{full_name}/git/refs",
            json={"ref": f"refs/heads/{branch}", "sha": base_sha},
            expected=(201,),
        )

    async def _upload_file(
        self,
        github_client: GitHubAppClient,
        full_name: str,
        path: str,
        content: bytes,
        message: str,
        branch: str,
    ) -> None:
        import urllib.parse

        b64 = base64.b64encode(content).decode("ascii")
        encoded_path = urllib.parse.quote(path, safe="/")
        await github_client.github_request(
            "PUT",
            f"/repos/{full_name}/contents/{encoded_path}",
            json={"message": message, "content": b64, "branch": branch},
            expected=(201, 200),
        )

    async def _create_pull_request(
        self,
        github_client: GitHubAppClient,
        upstream_full_name: str,
        title: str,
        body: str,
        head: str,
        base: str,
        label: str | None = None,
    ) -> str:
        pr = await github_client.github_request(
            "POST",
            f"/repos/{upstream_full_name}/pulls",
            json={"title": title, "body": body, "head": head, "base": base},
            expected=(201,),
        )
        # Optionally add label
        if label:
            from contextlib import suppress

            with suppress(Exception):
                await github_client.github_request(
                    "POST",
                    f"/repos/{upstream_full_name}/issues/{pr['number']}/labels",
                    json={"labels": [label]},
                    expected=(200,),
                )
        return pr.get("html_url") or ""

    async def _path_exists(
        self,
        github_client: GitHubAppClient,
        full_name: str,
        path: str,
        ref: str,
        cancel_event: asyncio.Event | None = None,
    ) -> bool:
        import urllib.parse

        encoded_path = urllib.parse.quote(path, safe="/")
        result = await github_client.github_request(
            "GET",
            f"/repos/{full_name}/contents/{encoded_path}",
            params={"ref": ref},
            expected=(200, 404),
            cancel_event=cancel_event,
        )
        return bool(result)  # Empty dict for 404, non-empty for 200

    async def _upload_pack_files(
        self,
        github_client: GitHubAppClient,
        fork_full_name: str,
        pack_path: Path,
        pack_id: str,
        branch_name: str,
        cancel_event: asyncio.Event,
        report: Callable[[float, str], None],
    ) -> None:
        """Upload all pack files to the repository."""
        # Get all files in the pack directory
        pack_files = list(pack_path.rglob("*"))
        pack_files = [f for f in pack_files if f.is_file()]
        
        if not pack_files:
            raise RuntimeError(f"No files found in pack directory: {pack_path}")
        
        total_files = len(pack_files)
        for i, file_path in enumerate(pack_files):
            self._raise_if_cancelled(cancel_event)
            
            # Calculate progress (50% to 75% range for file uploads)
            progress = 50 + (25 * i / total_files)
            await report(progress, f"Uploading {file_path.name}...")
            
            # Read file content
            try:
                content = file_path.read_bytes()
            except Exception as e:
                raise RuntimeError(f"Failed to read file {file_path}: {e}")
            
            # Calculate relative path within pack
            rel_path = file_path.relative_to(pack_path)
            
            # Build destination path in repository
            dest_path = f"{self.dest_subdir}/{pack_id}/{rel_path.as_posix()}"
            
            # Upload file
            commit_message = f"Add {file_path.name} for {pack_id} pack"
            await self._upload_file(
                github_client, fork_full_name, dest_path, content, commit_message, branch_name
            )

    def _build_pr_content(self, pack_meta: dict, pack_id: str, is_anonymous: bool = False) -> tuple[str, str]:
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
            body_lines.extend([
                "## Submitter Information",
                f"**Submitted by:** {submitter.get('name', 'Unknown')}",
                f"**Email:** {submitter.get('email', 'Not provided')}",
                f"**Submission Type:** Anonymous submission via AccessiBot",
                "",
            ])
        
        # Add pack details
        sounds = pack_meta.get("sounds", {})
        if sounds:
            body_lines.extend([
                "## Pack Contents",
                ""
            ])
            for sound_key, filename in sounds.items():
                body_lines.append(f"- **{sound_key}:** {filename}")
            body_lines.append("")
        
        body_lines.extend([
            "## Submission Details",
            "- This pack has been validated using AccessiWeather's sound pack validation system",
            "- All files have been uploaded and are ready for review",
            "- This submission was created automatically via the AccessiWeather pack submission service",
            "",
            "---",
            "*This pull request was created automatically by AccessiBot on behalf of the community.*"
        ])
        
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
