import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

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


@pytest.fixture()
def mock_config_manager():
    """Mock ConfigManager with valid GitHub App configuration."""
    mock_config = MagicMock()
    mock_config.validate_github_app_config.return_value = (True, "GitHub App configuration is valid")
    mock_config.get_github_app_config.return_value = ("123456", "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----", "789012")
    return mock_config


@pytest.mark.asyncio
async def test_submit_pack_no_config_manager(tmp_pack_dir):
    """Test submit_pack raises error when no config manager is provided."""
    pack_dir, meta = tmp_pack_dir

    svc = PackSubmissionService(repo_owner="owner", repo_name="repo", dest_subdir="packs")

    with pytest.raises(RuntimeError) as exc_info:
        await svc.submit_pack(pack_dir, meta)
    
    assert "No configuration manager provided" in str(exc_info.value)


@pytest.mark.asyncio
async def test_submit_pack_invalid_config(tmp_pack_dir, mock_config_manager):
    """Test submit_pack raises error when GitHub App configuration is invalid."""
    pack_dir, meta = tmp_pack_dir
    mock_config_manager.validate_github_app_config.return_value = (False, "Invalid configuration")

    svc = PackSubmissionService(repo_owner="owner", repo_name="repo", dest_subdir="packs", config_manager=mock_config_manager)

    with pytest.raises(RuntimeError) as exc_info:
        await svc.submit_pack(pack_dir, meta)
    
    assert "GitHub App configuration invalid: Invalid configuration" in str(exc_info.value)


@pytest.mark.asyncio
async def test_submit_pack_anonymous_no_config_manager(tmp_pack_dir):
    """Test submit_pack_anonymous raises error when no config manager is provided."""
    pack_dir, meta = tmp_pack_dir

    svc = PackSubmissionService(repo_owner="owner", repo_name="repo", dest_subdir="packs")

    with pytest.raises(RuntimeError) as exc_info:
        await svc.submit_pack_anonymous(pack_dir, meta, "John Doe", "john@example.com")
    
    assert "No configuration manager provided" in str(exc_info.value)


@pytest.mark.asyncio
async def test_pack_id_generation():
    svc = PackSubmissionService()
    pid = svc._derive_pack_id(Path("/x/Test Pack"), {"name": "Test Pack", "author": "Jane-Doe"})
    assert pid == "test-pack-jane-doe"


@pytest.mark.asyncio
async def test_build_pr_content_anonymous():
    """Test _build_pr_content method for anonymous submissions."""
    svc = PackSubmissionService()
    meta = {
        "name": "Test Pack",
        "author": "Jane Doe",
        "description": "A test sound pack",
        "sounds": {"alert": "alert.wav", "notify": "notify.wav"},
        "_submitter": {
            "name": "John Smith", 
            "email": "john@example.com",
            "submission_type": "anonymous"
        }
    }
    
    title, body = svc._build_pr_content(meta, "test-pack", is_anonymous=True)
    
    assert title == "Add community sound pack: Test Pack"
    assert "## Submitter Information" in body
    assert "**Submitted by:** John Smith" in body
    assert "**Email:** john@example.com" in body
    assert "Anonymous submission via AccessiBot" in body


@pytest.mark.asyncio
async def test_build_pr_content_regular():
    """Test _build_pr_content method for regular submissions."""
    svc = PackSubmissionService()
    meta = {
        "name": "Test Pack",
        "author": "Jane Doe",
        "description": "A test sound pack",
        "sounds": {"alert": "alert.wav", "notify": "notify.wav"}
    }
    
    title, body = svc._build_pr_content(meta, "test-pack", is_anonymous=False)
    
    assert title == "Add sound pack: Test Pack by Jane Doe"
    assert "## Submitter Information" not in body
    assert "Anonymous submission" not in body


@pytest.mark.asyncio
async def test_sanitize_id():
    """Test ID sanitization."""
    assert PackSubmissionService._sanitize_id("Test Pack Name!") == "test-pack-name"
    assert PackSubmissionService._sanitize_id("Special@Characters#123") == "specialcharacters123"
    assert PackSubmissionService._sanitize_id("") == "pack"


@pytest.mark.asyncio
async def test_build_branch_name():
    """Test branch name generation."""
    branch = PackSubmissionService._build_branch_name("test-pack")
    assert branch.startswith("soundpack/test-pack-")
    assert len(branch.split("-")) >= 3  # soundpack/test-pack-YYYYMMDD-HHMMSS
