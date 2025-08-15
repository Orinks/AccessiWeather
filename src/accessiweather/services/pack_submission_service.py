from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import re
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from accessiweather.notifications.sound_player import validate_sound_pack
from accessiweather.version import __version__ as APP_VERSION

logger = logging.getLogger(__name__)


@dataclass
class SubmissionResult:
    pr_url: str
    branch: str
    repo_dir: Path


class PackSubmissionService:
    """Service to validate a sound pack and submit it to the community repo via GitHub CLI.

    This uses git and gh CLI tools. It performs operations in a temporary working
    directory and cleans up afterwards.
    """

    def __init__(
        self,
        repo_owner: str = "accessiweather-community",
        repo_name: str = "soundpacks",
        user_agent: str | None = None,
        default_base_branch: str = "main",
        command_timeout: float = 120.0,
    ) -> None:
        """Initialize the submission service.

        Args:
            repo_owner: GitHub org/user that hosts community packs
            repo_name: Repository name for packs
            user_agent: Optional user-agent string
            default_base_branch: The base branch to target PRs against
            command_timeout: Timeout in seconds for subprocess commands

        """
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.default_base_branch = default_base_branch
        self.command_timeout = command_timeout
        self.user_agent = user_agent or f"AccessiWeather/{APP_VERSION}"

    async def submit_pack(
        self,
        pack_path: Path,
        pack_meta: dict,
        progress_callback: Callable[[float, str], bool | None] | None = None,
    ) -> str:
        """Validate, prepare, and submit a sound pack as a GitHub PR.

        Args:
            pack_path: Path to the directory containing pack.json and audio files
            pack_meta: Parsed metadata from pack.json
            progress_callback: Optional callback(progress_percent, status_text) -> bool | None.
                If it returns False, the operation will be cancelled.
                The callback should be synchronous and return immediately.

        Returns:
            The URL of the created Pull Request.

        Note:
            This method handles git operations, GitHub authentication, and PR creation.
            On cancellation, any running subprocess will be terminated.

        """

        def report(pct: float, status: str) -> None:
            try:
                if progress_callback is not None:
                    res = progress_callback(pct, status)
                    if asyncio.iscoroutine(res):
                        # Best-effort await if a coroutine is returned
                        # (callers should pass sync callbacks ideally)
                        # Use create_task to avoid awaiting inside report
                        asyncio.create_task(res)  # type: ignore[arg-type]
                    elif res is False:
                        raise asyncio.CancelledError("Operation cancelled by user")
            except asyncio.CancelledError:
                raise
            except Exception:
                pass

        report(5.0, "Checking prerequisites...")
        await self._ensure_tools_available()

        # Ensure GitHub CLI is authenticated early
        report(7.0, "Verifying GitHub authentication...")
        await self._ensure_gh_authenticated(None)

        # Basic local validation first
        report(10.0, "Validating pack locally...")
        ok, msg = validate_sound_pack(pack_path)
        if not ok:
            raise RuntimeError(f"Pack validation failed: {msg}")

        pack_name = (pack_meta.get("name") or pack_path.name).strip()
        author = (pack_meta.get("author") or "Unknown").strip()
        pack_id = self._derive_pack_id(pack_path, pack_meta)

        # Work inside a temp directory
        with tempfile.TemporaryDirectory(prefix="aw-pack-submit-") as tmpdir:
            workdir = Path(tmpdir)

            # Clone
            report(20.0, "Cloning community repository...")
            await self._run_cmd(
                [
                    "git",
                    "clone",
                    "--depth=1",
                    f"https://github.com/{self.repo_owner}/{self.repo_name}.git",
                    ".",
                ],
                cwd=workdir,
            )

            # Create branch
            branch = self._build_branch_name(pack_id)
            report(30.0, f"Creating branch {branch}...")
            await self._run_cmd(["git", "checkout", "-b", branch], cwd=workdir)

            # Copy pack directory into repo (packs/<pack_id>)
            dest_dir = workdir / "packs" / pack_id
            report(40.0, "Copying pack files into repository...")
            dest_dir.parent.mkdir(parents=True, exist_ok=True)
            if dest_dir.exists():
                # Clean any existing directory
                shutil.rmtree(dest_dir)
            shutil.copytree(pack_path, dest_dir)

            # Validate the copied pack again (defensive)
            report(55.0, "Running validation on copied files...")
            ok2, msg2 = validate_sound_pack(dest_dir)
            if not ok2:
                raise RuntimeError(f"Validation after copy failed: {msg2}")

            # Stage + commit
            report(65.0, "Staging changes...")
            await self._run_cmd(["git", "add", "-A"], cwd=workdir)

            # Ensure git identity is configured before committing
            report(67.0, "Configuring git identity...")
            try:
                await self._run_cmd(["git", "config", "user.email"], cwd=workdir)
                await self._run_cmd(["git", "config", "user.name"], cwd=workdir)
            except Exception:
                await self._run_cmd(
                    ["git", "config", "user.email", "accessiweather@users.noreply.github.com"],
                    cwd=workdir,
                )
                await self._run_cmd(
                    ["git", "config", "user.name", author or pack_name], cwd=workdir
                )

            commit_msg = f"Add sound pack: {pack_name} by {author}"
            report(70.0, "Committing changes...")
            await self._run_cmd(["git", "commit", "-m", commit_msg], cwd=workdir)

            # Create PR via gh CLI (gh will handle forking and pushing automatically)
            report(75.0, "Creating pull request via GitHub CLI...")
            pr_title = commit_msg
            pr_body = (
                f"This PR submits the sound pack '{pack_name}' by {author}.\n\n"
                f"Submitted via AccessiWeather {APP_VERSION}."
            )

            # Fork the repository if needed (non-interactive)
            report(80.0, "Ensuring repository fork...")
            with contextlib.suppress(RuntimeError):
                # Fork may already exist or user has write access, continue on error
                await self._run_cmd(
                    ["gh", "repo", "fork", "--remote=false", "--clone=false"], cwd=workdir
                )

            # Create PR with automatic head detection
            pr_url = await self._create_pr(workdir, pr_title, pr_body, label="soundpack")

            report(100.0, "Submission complete.")
            return pr_url

    # Internal helpers

    async def _ensure_tools_available(self) -> None:
        # git
        await self._run_cmd(["git", "--version"], cwd=None)
        # gh
        await self._run_cmd(["gh", "--version"], cwd=None)

    async def _ensure_gh_authenticated(self, cwd: Path | None) -> None:
        try:
            await self._run_cmd(["gh", "auth", "status"], cwd=cwd)
        except RuntimeError as e:
            raise RuntimeError(
                "GitHub CLI is not authenticated. Run 'gh auth login' and try again."
            ) from e

    async def _create_pr(
        self,
        cwd: Path,
        title: str,
        body: str,
        label: str | None = None,
    ) -> str:
        args = [
            "gh",
            "pr",
            "create",
            "--title",
            title,
            "--body",
            body,
            "--base",
            self.default_base_branch,
            "--fill",  # Avoid editor prompts if PR template exists
        ]
        if label:
            args += ["--label", label]

        code, out, _ = await self._run_cmd(args, cwd=cwd, return_all=True)
        # gh prints the PR URL in stdout on success
        url = self._extract_url(out)
        if not url:
            raise RuntimeError("Failed to create PR: No URL returned by gh CLI.")
        return url

    async def _run_cmd(
        self,
        args: list[str],
        cwd: Path | None,
        timeout: float | None = None,
        return_all: bool = False,
    ) -> tuple[int, str, str] | str:
        """Run a subprocess command asynchronously.

        If return_all is False (default), raises on non-zero exit and returns stdout string.
        If return_all is True, returns (code, stdout, stderr).
        """
        timeout = timeout or self.command_timeout
        logger.debug(f"Running command: {' '.join(args)} (cwd={cwd})")
        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(cwd) if cwd else None,
                env=self._build_env(),
            )
            try:
                stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except TimeoutError as e:
                with contextlib.suppress(ProcessLookupError):
                    proc.kill()
                raise RuntimeError(f"Command timed out: {' '.join(args)}") from e

            code = proc.returncode or 0
            stdout = stdout_b.decode(errors="ignore") if stdout_b else ""
            stderr = stderr_b.decode(errors="ignore") if stderr_b else ""

            if return_all:
                return code, stdout, stderr

            if code != 0:
                raise RuntimeError(
                    f"Command failed ({code}): {' '.join(args)}\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
                )
            return stdout
        except FileNotFoundError as e:
            raise RuntimeError(f"Required tool not found: {args[0]}") from e

    def _build_env(self) -> dict[str, str]:
        env = os.environ.copy()
        env.setdefault("GITHUB_TOKEN", os.environ.get("GH_TOKEN", ""))
        env.setdefault("GH_PAGER", "cat")
        env.setdefault("GLAMOUR_STYLE", "plain")
        env.setdefault("GH_PROMPT_DISABLED", "1")  # Disable interactive prompts
        # User-Agent for potential HTTP operations by gh
        env.setdefault("HTTP_USER_AGENT", self.user_agent)
        return env

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
        s = s.replace(" ", "_").replace("-", "_")
        s = re.sub(r"[^a-z0-9_]+", "", s)
        return s or "pack"

    @staticmethod
    def _build_branch_name(pack_id: str) -> str:
        import time as _time

        ts = _time.strftime("%Y%m%d-%H%M%S")
        return f"soundpack/{pack_id}-{ts}"

    @staticmethod
    def _extract_url(text: str) -> str | None:
        if not text:
            return None
        m = re.search(r"https?://\S+", text)
        return m.group(0) if m else None
