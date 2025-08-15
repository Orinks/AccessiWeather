from __future__ import annotations

import asyncio
import contextlib
import inspect
import logging
import os
import re
import shutil
import tempfile
from collections.abc import Awaitable, Callable
from pathlib import Path

from accessiweather.notifications.sound_player import validate_sound_pack
from accessiweather.version import __version__ as APP_VERSION

logger = logging.getLogger(__name__)


class PackSubmissionService:
    """Service to validate a sound pack and submit it to the community repo via GitHub CLI.

    This uses git and gh CLI tools. It performs operations in a temporary working
    directory and cleans up afterwards.
    """

    def __init__(
        self,
        repo_owner: str = "accessiweather-community",
        repo_name: str = "soundpacks",
        dest_subdir: str = "packs",
        user_agent: str | None = None,
        default_base_branch: str = "main",
        command_timeout: float = 600.0,
    ) -> None:
        """Initialize the submission service.

        Args:
            repo_owner: GitHub org/user that hosts community packs
            repo_name: Repository name for packs
            dest_subdir: Subdirectory within repo to place packs
            user_agent: Optional user-agent string
            default_base_branch: The base branch to target PRs against
            command_timeout: Timeout in seconds for subprocess commands

        """
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.dest_subdir = dest_subdir
        self.default_base_branch = default_base_branch
        self.command_timeout = command_timeout
        self.user_agent = user_agent or f"AccessiWeather/{APP_VERSION}"

    async def submit_pack(
        self,
        pack_path: Path,
        pack_meta: dict,
        progress_callback: Callable[[float, str], bool | None] | None = None,
        cancel_event: asyncio.Event | None = None,
    ) -> str:
        """Validate, prepare, and submit a sound pack as a GitHub PR.

        Args:
            pack_path: Path to the directory containing pack.json and audio files
            pack_meta: Parsed metadata from pack.json
            progress_callback: Optional callback(progress_percent, status_text) -> bool | None.
                If it returns False, the operation will be cancelled.
                The callback should be synchronous and return immediately.
            cancel_event: Optional asyncio.Event to signal cancellation

        Returns:
            The URL of the created Pull Request.

        Note:
            This method handles git operations, GitHub authentication, and PR creation.
            On cancellation, any running subprocess will be terminated.

        """
        if cancel_event is None:
            cancel_event = asyncio.Event()

        async def report(pct: float, status: str) -> None:
            try:
                if progress_callback is not None:
                    res = progress_callback(pct, status)
                    if asyncio.iscoroutine(res):
                        # Await the coroutine properly
                        res = await res
                    if res is False:
                        cancel_event.set()
                        raise asyncio.CancelledError("Operation cancelled by user")
            except asyncio.CancelledError:
                raise
            except Exception:
                pass

        await report(5.0, "Checking prerequisites...")
        await self._ensure_tools_available()

        # Ensure GitHub CLI is authenticated early
        await report(7.0, "Verifying GitHub authentication...")
        await self._ensure_gh_authenticated(None)

        # Resolve the default branch of the target repository
        await report(8.0, "Resolving repository default branch...")
        await self._resolve_default_branch()

        # Basic local validation first
        await report(10.0, "Validating pack locally...")
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
            await report(20.0, "Cloning community repository...")
            await self._run_cmd(
                [
                    "git",
                    "clone",
                    "--depth=1",
                    f"https://github.com/{self.repo_owner}/{self.repo_name}.git",
                    "repo",
                ],
                cwd=workdir,
                cancel_event=cancel_event,
            )

            # Set repo_dir for subsequent operations
            repo_dir = workdir / "repo"

            # Create branch
            branch = self._build_branch_name(pack_id)
            await report(30.0, f"Creating branch {branch}...")
            await self._run_cmd(
                ["git", "checkout", "-b", branch], cwd=repo_dir, cancel_event=cancel_event
            )

            # Copy pack directory into repo (<dest_subdir>/<pack_id>)
            dest_dir = repo_dir / self.dest_subdir / pack_id
            await report(40.0, "Copying pack files into repository...")
            dest_dir.parent.mkdir(parents=True, exist_ok=True)
            if dest_dir.exists():
                raise RuntimeError(
                    "A pack with this ID already exists in the community repository. Please rename your pack or adjust metadata to produce a unique ID."
                )

            async def copy_progress_cb(p: float) -> None:
                await report(40.0 + (p / 100.0) * 10.0, "Copying pack files...")

            await self._copy_pack(
                pack_path,
                dest_dir,
                cancel_event,
                copy_progress_cb,
            )

            # Validate the copied pack again (defensive)
            await report(55.0, "Running validation on copied files...")
            ok2, msg2 = validate_sound_pack(dest_dir)
            if not ok2:
                raise RuntimeError(f"Validation after copy failed: {msg2}")

            # Stage + commit
            await report(60.0, "Staging changes...")
            await self._run_cmd(["git", "add", "-A"], cwd=repo_dir, cancel_event=cancel_event)

            # Ensure git identity is configured before committing
            await report(65.0, "Configuring git identity...")
            try:
                await self._run_cmd(
                    ["git", "config", "user.email"], cwd=repo_dir, cancel_event=cancel_event
                )
                await self._run_cmd(
                    ["git", "config", "user.name"], cwd=repo_dir, cancel_event=cancel_event
                )
            except Exception:
                await self._run_cmd(
                    ["git", "config", "user.email", "accessiweather@users.noreply.github.com"],
                    cwd=repo_dir,
                    cancel_event=cancel_event,
                )
                await self._run_cmd(
                    ["git", "config", "user.name", author or pack_name],
                    cwd=repo_dir,
                    cancel_event=cancel_event,
                )

            commit_msg = f"Add sound pack: {pack_name} by {author}"
            await report(75.0, "Committing changes...")
            await self._run_cmd(
                ["git", "commit", "-m", commit_msg], cwd=repo_dir, cancel_event=cancel_event
            )

            # Create PR via gh CLI (gh will handle forking and pushing automatically)
            await report(90.0, "Creating pull request via GitHub CLI...")
            pr_title = commit_msg

            # Build enhanced PR body with pack metadata
            pr_body_parts = [f"This PR submits the sound pack '{pack_name}' by {author}."]

            # Add description if available
            description = pack_meta.get("description", "").strip()
            if description:
                pr_body_parts.append(f"\n**Description:** {description}")

            # Add number of mapped sounds
            sounds = pack_meta.get("sounds") or {}
            if isinstance(sounds, dict):
                sound_count = len(sounds)
                pr_body_parts.append(f"\n**Mapped sounds:** {sound_count}")

            pr_body_parts.append(f"\n\nSubmitted via AccessiWeather {APP_VERSION}.")
            pr_body = "".join(pr_body_parts)

            # Fork the repository if needed (non-interactive)
            await report(92.0, "Ensuring repository fork and pushing branch...")
            with contextlib.suppress(RuntimeError):
                # Fork may already exist or user has write access, continue on error
                await self._run_cmd(
                    ["gh", "repo", "fork", "--remote=true", "--clone=false"],
                    cwd=repo_dir,
                    cancel_event=cancel_event,
                )

            # Configure git to use GitHub CLI for authentication
            await self._run_cmd(
                ["gh", "auth", "setup-git"], cwd=repo_dir, cancel_event=cancel_event
            )

            # Simplified push logic: always attempt to push to fork remote first
            try:
                await self._run_cmd(
                    ["git", "push", "-u", "fork", branch], cwd=repo_dir, cancel_event=cancel_event
                )
            except RuntimeError:
                # If fork remote is missing, create it and push to it
                try:
                    login = await self._run_cmd(
                        ["gh", "api", "user", "-q", ".login"],
                        cwd=repo_dir,
                        cancel_event=cancel_event,
                    )
                    expected_fork_url = f"https://github.com/{login.strip()}/{self.repo_name}.git"

                    await self._run_cmd(
                        ["git", "remote", "add", "fork", expected_fork_url],
                        cwd=repo_dir,
                        cancel_event=cancel_event,
                    )
                    await self._run_cmd(
                        ["git", "push", "-u", "fork", branch],
                        cwd=repo_dir,
                        cancel_event=cancel_event,
                    )
                except RuntimeError:
                    # Fall back to pushing to origin
                    await self._run_cmd(
                        ["git", "push", "-u", "origin", branch],
                        cwd=repo_dir,
                        cancel_event=cancel_event,
                    )

            # Optionally resolve login to construct explicit head ref
            head_ref: str | None = None
            try:
                login = await self._run_cmd(
                    ["gh", "api", "user", "-q", ".login"], cwd=repo_dir, cancel_event=cancel_event
                )
                head_ref = f"{login.strip()}:{branch}"
            except Exception:
                head_ref = None

            # Create PR with explicit base and optional head
            pr_url = await self._create_pr(
                repo_dir,
                pr_title,
                pr_body,
                label="soundpack",
                head=head_ref,
                cancel_event=cancel_event,
            )

            await report(100.0, "Submission complete.")
            return pr_url

    # Internal helpers

    async def _resolve_default_branch(self) -> None:
        """Resolve the default branch of the target repository."""
        try:
            result = await self._run_cmd(
                [
                    "gh",
                    "repo",
                    "view",
                    "-R",
                    f"{self.repo_owner}/{self.repo_name}",
                    "--json",
                    "defaultBranchRef",
                    "-q",
                    ".defaultBranchRef.name",
                ],
                cwd=None,
            )
            self.default_base_branch = result.strip()
        except Exception:
            # Fall back to 'main' if we can't determine the default branch
            self.default_base_branch = "main"

    async def _ensure_tools_available(self) -> None:
        # git
        try:
            await self._run_cmd(["git", "--version"], cwd=None)
        except RuntimeError as e:
            raise RuntimeError(
                "Git is not installed or not in PATH. Please install Git from https://git-scm.com/ and try again."
            ) from e

        # gh
        try:
            await self._run_cmd(["gh", "--version"], cwd=None)
        except RuntimeError as e:
            raise RuntimeError(
                "GitHub CLI (gh) is not installed or not in PATH. Please install it from https://cli.github.com/ and try again."
            ) from e

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
        head: str | None = None,
        cancel_event: asyncio.Event | None = None,
    ) -> str:
        args = [
            "gh",
            "pr",
            "create",
            "-R",
            f"{self.repo_owner}/{self.repo_name}",
            "--title",
            title,
            "--body",
            body,
            "--base",
            self.default_base_branch,
        ]
        if label:
            args += ["--label", label]
        if head:
            args += ["--head", head]

        code, out, err = await self._run_cmd(
            args, cwd=cwd, return_all=True, cancel_event=cancel_event
        )

        # Check for non-zero exit code and handle label errors
        if code != 0:
            error_msg = err.strip() if err.strip() else out.strip()

            # If label doesn't exist, retry without label
            if label and "label" in error_msg.lower() and "exist" in error_msg.lower():
                # Retry without the label argument
                args_no_label = [
                    "gh",
                    "pr",
                    "create",
                    "-R",
                    f"{self.repo_owner}/{self.repo_name}",
                    "--title",
                    title,
                    "--body",
                    body,
                    "--base",
                    self.default_base_branch,
                ]
                if head:
                    args_no_label += ["--head", head]

                code, out, err = await self._run_cmd(
                    args_no_label, cwd=cwd, return_all=True, cancel_event=cancel_event
                )

                if code != 0:
                    error_msg = err.strip() if err.strip() else out.strip()
                    raise RuntimeError(f"Failed to create PR (exit code {code}): {error_msg}")
            else:
                raise RuntimeError(f"Failed to create PR (exit code {code}): {error_msg}")

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
        cancel_event: asyncio.Event | None = None,
    ) -> tuple[int, str, str] | str:
        """Run a subprocess command asynchronously.

        If return_all is False (default), raises on non-zero exit and returns stdout string.
        If return_all is True, returns (code, stdout, stderr).

        Args:
            args: Command and arguments to execute
            cwd: Working directory for the command
            timeout: Timeout in seconds (uses default if None)
            return_all: If True, return (code, stdout, stderr); if False, return stdout only
            cancel_event: Optional event that when set will cancel the subprocess

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
                if cancel_event is not None:
                    # Wait for either process completion or cancellation
                    comm_task = asyncio.create_task(proc.communicate())
                    cancel_task = asyncio.create_task(cancel_event.wait())

                    done, pending = await asyncio.wait(
                        [comm_task, cancel_task],
                        timeout=timeout,
                        return_when=asyncio.FIRST_COMPLETED,
                    )

                    # Cancel any pending tasks
                    for task in pending:
                        task.cancel()
                        with contextlib.suppress(asyncio.CancelledError):
                            await task

                    if cancel_task in done:
                        # Cancellation was requested
                        with contextlib.suppress(ProcessLookupError):
                            proc.kill()
                        with contextlib.suppress(Exception):
                            await proc.wait()
                        raise asyncio.CancelledError("Operation cancelled by cancel_event")

                    if not done:
                        # Timeout occurred
                        with contextlib.suppress(ProcessLookupError):
                            proc.kill()
                        raise RuntimeError(f"Command timed out: {' '.join(args)}")

                    stdout_b, stderr_b = await comm_task
                else:
                    # Standard execution without cancellation support
                    stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except TimeoutError as e:
                with contextlib.suppress(ProcessLookupError):
                    proc.kill()
                raise RuntimeError(f"Command timed out: {' '.join(args)}") from e
            except asyncio.CancelledError:
                with contextlib.suppress(ProcessLookupError):
                    proc.kill()
                # Wait for process termination to avoid zombie processes
                with contextlib.suppress(Exception):
                    await proc.wait()
                raise

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
        # Keep GH_TOKEN if already set; do not rewrite/move it.
        env.setdefault("GH_PAGER", "cat")
        env.setdefault("GLAMOUR_STYLE", "plain")
        env.setdefault("GH_PROMPT_DISABLED", "1")  # Disable interactive prompts
        # User-Agent for potential HTTP operations by gh
        env.setdefault("HTTP_USER_AGENT", self.user_agent)
        return env

    @staticmethod
    def _derive_pack_id(pack_path: Path, meta: dict) -> str:
        import hashlib
        import json

        # Prefer metadata name, then directory name, with optional author for uniqueness
        name = (meta.get("name") or pack_path.name or "pack").strip()
        author = (meta.get("author") or "").strip()

        # Include author if available to reduce collision risk
        pack_id = f"{name}-{author}" if author and author.lower() != "unknown" else name

        # Add a short hash from pack.json content (or meta dict) instead of pack_path
        # This makes the ID stable across machines and directories
        hash_input = json.dumps(meta, sort_keys=True).encode()
        short_hash = hashlib.md5(hash_input).hexdigest()[:6]
        pack_id_with_hash = f"{pack_id}-{short_hash}"

        return PackSubmissionService._sanitize_id(pack_id_with_hash)

    @staticmethod
    def _sanitize_id(text: str) -> str:
        s = text.strip().lower()
        s = s.replace(" ", "_").replace("-", "_")
        s = re.sub(r"[^a-z0-9_]+", "", s)
        return s or "pack"

    async def _copy_pack(
        self,
        src: Path,
        dst: Path,
        cancel_event: asyncio.Event,
        progress_cb: Callable[[float], None] | Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        """Copy a pack directory with cancellation support and progress reporting.

        Args:
            src: Source directory path
            dst: Destination directory path
            cancel_event: Event that when set will cancel the operation
            progress_cb: Optional callback to report progress (0-100)

        """
        import os

        # First, walk the source to count total files for progress
        total_files = 0
        for _root, _dirs, files in os.walk(src):
            total_files += len(files)

        if total_files == 0:
            if progress_cb:
                res = progress_cb(100.0)
                if inspect.isawaitable(res):
                    await res
            return

        # Create destination directory
        dst.mkdir(parents=True, exist_ok=True)

        # Copy files with progress tracking
        copied_files = 0

        for root, _dirs, files in os.walk(src):
            # Check for cancellation
            if cancel_event.is_set():
                raise asyncio.CancelledError("Copy operation cancelled")

            # Create subdirectories
            rel_root = Path(root).relative_to(src)
            dst_root = dst / rel_root
            dst_root.mkdir(parents=True, exist_ok=True)

            # Copy files in this directory
            for file in files:
                if cancel_event.is_set():
                    raise asyncio.CancelledError("Copy operation cancelled")

                src_file = Path(root) / file
                dst_file = dst_root / file

                # Copy file using asyncio.to_thread for non-blocking operation
                await asyncio.to_thread(shutil.copy2, src_file, dst_file)

                copied_files += 1

                # Report progress and yield control
                if progress_cb:
                    progress = (copied_files / total_files) * 100.0
                    res = progress_cb(progress)
                    if inspect.isawaitable(res):
                        await res

                # Yield control to allow cancellation checks
                await asyncio.sleep(0)

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
