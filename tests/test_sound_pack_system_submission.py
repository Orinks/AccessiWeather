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

    # Test that submit_pack now raises RuntimeError for user token authentication
    with pytest.raises(RuntimeError) as exc_info:
        await svc.submit_pack(pack_dir, meta, progress_callback=progress_cb)
    
    assert "User tokens are no longer supported" in str(exc_info.value)


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

    # Test that submit_pack now raises RuntimeError for user token authentication
    with pytest.raises(RuntimeError) as exc_info:
        await svc.submit_pack(pack_dir, {"name": "Big"})
    
    assert "User tokens are no longer supported" in str(exc_info.value)


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

    # Test that submit_pack now raises RuntimeError for user token authentication
    with pytest.raises(RuntimeError) as exc_info:
        await svc.submit_pack(pack_dir, meta)
    
    assert "User tokens are no longer supported" in str(exc_info.value)
