import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from accessiweather.services.pack_submission_service import PackSubmissionService


@pytest.fixture()
def tmp_pack_dir(tmp_path: Path):
    # Create a temporary sound pack with two files (one containing a space to test encoding)
    pack_dir = tmp_path / "my-pack"
    pack_dir.mkdir(parents=True, exist_ok=True)

    (pack_dir / "alert.wav").write_bytes(b"x")
    (pack_dir / "notify sound.wav").write_bytes(b"y")

    meta = {
        "name": "Test Pack",
        "author": "Jane-Doe",
        "description": "Test pack",
        "sounds": {"alert": "alert.wav", "notify": "notify sound.wav"},
    }
    (pack_dir / "pack.json").write_text(json.dumps(meta), encoding="utf-8")

    return pack_dir, meta


@pytest.mark.asyncio
async def test_submit_pack_happy_path(tmp_pack_dir, monkeypatch):
    pack_dir, meta = tmp_pack_dir

    # Collect progress
    progress_calls: list[tuple[float, str]] = []

    def progress_cb(p, s):
        progress_calls.append((round(p, 1), s))

    # Service under test
    svc = PackSubmissionService(repo_owner="owner", repo_name="repo", dest_subdir="packs")

    # Environment token
    monkeypatch.setenv("ACCESSIWEATHER_GITHUB_TOKEN", "dummy")

    # Stub helpers to avoid real network
    async def _repo_info(client, cancel_event=None):
        await asyncio.sleep(0)
        return {"default_branch": "main"}

    async def _user_login(client, cancel_event=None):
        await asyncio.sleep(0)
        return "user"

    async def _ensure_fork(client, login, cancel_event=None):
        await asyncio.sleep(0)
        return "user/repo"

    monkeypatch.setattr(svc, "_get_repo_info", _repo_info)
    monkeypatch.setattr(svc, "_get_user_login", _user_login)
    monkeypatch.setattr(svc, "_ensure_fork", _ensure_fork)

    base_sha_calls: list[tuple[str, str]] = []

    async def _get_branch_sha(client, full_name, branch):
        base_sha_calls.append((full_name, branch))
        return "abc123"

    monkeypatch.setattr(svc, "_get_branch_sha", _get_branch_sha)
    monkeypatch.setattr(
        svc, "_create_branch", lambda client, full_name, branch, sha: asyncio.sleep(0)
    )
    monkeypatch.setattr(
        svc,
        "_path_exists",
        lambda client, full_name, path, ref, cancel_event=None: asyncio.sleep(0) or False,
    )

    uploaded_paths: list[str] = []

    async def _upload_file(client, full_name, path, content, message, branch, cancel_event=None):
        # Ensure we get paths as provided (encoding is done inside helper when hitting API)
        uploaded_paths.append(path)

    monkeypatch.setattr(svc, "_upload_file", _upload_file)

    async def _create_pr(client, upstream_full_name, title, body, head, base, label=None):
        await asyncio.sleep(0)
        return "https://github.com/owner/repo/pull/1"

    monkeypatch.setattr(svc, "_create_pull_request", _create_pr)

    # Provide a dummy async client context manager
    class _DummyClient:
        async def __aenter__(self):
            return SimpleNamespace()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(svc, "_get_auth_client", lambda token: _DummyClient())

    pr_url = await svc.submit_pack(pack_dir, meta, progress_callback=progress_cb)

    assert pr_url.endswith("/pull/1")
    # Uploaded files include the audio files and pack.json
    assert set(uploaded_paths) == {
        "packs/test-pack-jane-doe/alert.wav",
        "packs/test-pack-jane-doe/notify sound.wav",
        "packs/test-pack-jane-doe/pack.json",
    }

    # Verify progress mapping: uploads reported within 40..90 and final 100
    upload_reports = [p for p in progress_calls if p[1].startswith("Uploaded ")]
    assert upload_reports, "No upload progress reported"
    pcts = [p[0] for p in upload_reports]
    assert min(pcts) >= 40.0 and max(pcts) <= 90.0
    assert any(p[0] == 100.0 for p in progress_calls)

    # Verify fork-first base sha call order
    assert base_sha_calls and base_sha_calls[0][0] == "user/repo"


@pytest.mark.asyncio
async def test_pack_id_generation():
    svc = PackSubmissionService()
    pid = svc._derive_pack_id(Path("/x/Test Pack"), {"name": "Test Pack", "author": "Jane-Doe"})
    assert pid == "test-pack-jane-doe"


@pytest.mark.asyncio
async def test_size_guard(tmp_path, monkeypatch):
    # Pack with one big file triggers size check
    pack_dir = tmp_path / "bigpack"
    pack_dir.mkdir()
    (pack_dir / "pack.json").write_text(
        json.dumps({"name": "Big", "sounds": {"alert": "big.bin"}}), encoding="utf-8"
    )
    big_file = pack_dir / "big.bin"
    big_file.write_bytes(b"x")

    svc = PackSubmissionService(repo_owner="owner", repo_name="repo")
    monkeypatch.setenv("ACCESSIWEATHER_GITHUB_TOKEN", "dummy")

    # Stubs to get to upload step
    async def _repo_info_sz(client, cancel_event=None):
        return {"default_branch": "main"}

    async def _user_login_sz(client, cancel_event=None):
        return "user"

    async def _ensure_fork_sz(client, login, cancel_event=None):
        return "user/repo"

    async def _get_branch_sha_sz(client, full_name, branch):
        return "abc123"

    async def _create_branch_sz(client, full_name, branch, sha):
        return None

    async def _path_exists_sz(client, full_name, path, ref, cancel_event=None):
        return False

    monkeypatch.setattr(svc, "_get_repo_info", _repo_info_sz)
    monkeypatch.setattr(svc, "_get_user_login", _user_login_sz)
    monkeypatch.setattr(svc, "_ensure_fork", _ensure_fork_sz)
    monkeypatch.setattr(svc, "_get_branch_sha", _get_branch_sha_sz)
    monkeypatch.setattr(svc, "_create_branch", _create_branch_sz)
    monkeypatch.setattr(svc, "_path_exists", _path_exists_sz)

    # Monkeypatch read_bytes to simulate >100MB size for this file only
    orig_read = Path.read_bytes

    def fake_read_bytes(self: Path) -> bytes:
        if self == big_file:
            return b"0" * (100 * 1024 * 1024 + 1)
        return orig_read(self)

    monkeypatch.setattr(Path, "read_bytes", fake_read_bytes)

    with pytest.raises(RuntimeError) as ei:
        await svc.submit_pack(pack_dir, {"name": "Big"})
    assert "100MB" in str(ei.value)


@pytest.mark.asyncio
async def test_url_encoding_in_helpers(monkeypatch):
    svc = PackSubmissionService(repo_owner="owner", repo_name="repo")

    captured: dict[str, Any] = {}

    async def fake_github_request(
        client, method, url, *, json=None, params=None, expected=(200, 201), cancel_event=None
    ):
        captured["url"] = url
        # Return 404 path not found fallback
        return {}

    monkeypatch.setattr(svc, "_github_request", fake_github_request)

    # Path with a space should be encoded when checking existence
    await svc._path_exists(SimpleNamespace(), "owner/repo", "packs/test/notify sound.wav", "main")
    assert "%20" in captured.get("url", "")

    # For upload_file, verify encoded URL too
    async def fake_github_request_upload(
        client, method, url, *, json=None, params=None, expected=(200, 201), cancel_event=None
    ):
        captured["upload_url"] = url
        return {"content": {}}

    monkeypatch.setattr(svc, "_github_request", fake_github_request_upload)
    await svc._upload_file(
        SimpleNamespace(), "owner/repo", "packs/test/notify sound.wav", b"x", "msg", "branch"
    )
    assert "%20" in captured.get("upload_url", "")


@pytest.mark.asyncio
async def test_branch_base_sha_fallback(monkeypatch, tmp_pack_dir):
    pack_dir, meta = tmp_pack_dir

    svc = PackSubmissionService(repo_owner="owner", repo_name="repo")
    monkeypatch.setenv("ACCESSIWEATHER_GITHUB_TOKEN", "dummy")

    order: list[str] = []

    # Stubs
    async def _repo_info_fb(client, cancel_event=None):
        return {"default_branch": "main"}

    async def _user_login_fb(client, cancel_event=None):
        return "user"

    async def _ensure_fork_fb(client, login, cancel_event=None):
        return "user/repo"

    monkeypatch.setattr(svc, "_get_repo_info", _repo_info_fb)
    monkeypatch.setattr(svc, "_get_user_login", _user_login_fb)
    monkeypatch.setattr(svc, "_ensure_fork", _ensure_fork_fb)

    async def _get_branch_sha(client, full_name, branch):
        order.append(full_name)
        if full_name == "user/repo":
            raise RuntimeError("not found in fork")
        return "upstream-sha"

    monkeypatch.setattr(svc, "_get_branch_sha", _get_branch_sha)

    created = {}

    async def _create_branch_fb(client, full_name, branch, sha):
        created.setdefault("sha", sha)

    monkeypatch.setattr(svc, "_create_branch", _create_branch_fb)

    class _DummyClient2:
        async def __aenter__(self):
            return SimpleNamespace()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(svc, "_get_auth_client", lambda token: _DummyClient2())

    async def _path_exists_fb(client, full_name, path, ref, cancel_event=None):
        return False

    monkeypatch.setattr(svc, "_path_exists", _path_exists_fb)

    async def _upload_file_fb(*a, **k):
        return None

    monkeypatch.setattr(svc, "_upload_file", _upload_file_fb)

    async def _create_pr_fb(*a, **k):
        return "https://github.com/owner/repo/pull/2"

    monkeypatch.setattr(svc, "_create_pull_request", _create_pr_fb)

    class _DummyClient3:
        async def __aenter__(self):
            return SimpleNamespace()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(svc, "_get_auth_client", lambda token: _DummyClient3())

    url = await svc.submit_pack(pack_dir, meta)
    assert url.endswith("/pull/2")
    assert order[:2] == ["user/repo", "owner/repo"], "Should try fork first, then upstream"
    assert created.get("sha") == "upstream-sha"
