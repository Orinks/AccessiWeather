import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

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


@pytest.fixture()
def mock_github_client():
    """Mock GitHubAppClient for testing submission flows."""
    mock_client = AsyncMock()
    mock_client.github_request = AsyncMock()
    
    # Setup default responses for common API calls
    mock_client.github_request.side_effect = _github_request_side_effect
    
    return mock_client


def _github_request_side_effect(method: str, url: str, **kwargs):
    """Mock GitHub API responses based on request URL and method."""
    if url == "/repos/accessiweather-community/soundpacks":
        return {"full_name": "accessiweather-community/soundpacks", "default_branch": "main"}
    elif url == "/app/installations/789012":
        return {"account": {"login": "accessibot"}}
    elif url == "/repos/accessibot/soundpacks":
        return {"full_name": "accessibot/soundpacks", "fork": True, "parent": {"full_name": "accessiweather-community/soundpacks"}}
    elif url == "/repos/accessiweather-community/soundpacks/git/ref/heads/main":
        return {"object": {"sha": "abc123"}}
    elif url.startswith("/repos/accessiweather-community/soundpacks/contents/packs/"):
        # Return 404 for pack existence checks (no duplicates)
        return {}
    elif method == "POST" and url == "/repos/accessibot/soundpacks/git/refs":
        return {"ref": "refs/heads/soundpack/test-pack-jane-doe-20240101-120000"}
    elif method == "PUT" and "/contents/" in url:
        return {"commit": {"sha": "def456"}}
    elif method == "POST" and url == "/repos/accessiweather-community/soundpacks/pulls":
        return {"html_url": "https://github.com/accessiweather-community/soundpacks/pull/123", "number": 123}
    elif method == "POST" and url.endswith("/labels"):
        return {"labels": ["community-submission"]}
    else:
        return {}


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


@pytest.mark.asyncio
async def test_submit_pack_anonymous_invalid_config(tmp_pack_dir, mock_config_manager):
    """Test submit_pack_anonymous raises error when GitHub App configuration is invalid."""
    pack_dir, meta = tmp_pack_dir
    mock_config_manager.validate_github_app_config.return_value = (False, "Invalid configuration")

    svc = PackSubmissionService(repo_owner="owner", repo_name="repo", dest_subdir="packs", config_manager=mock_config_manager)

    with pytest.raises(RuntimeError) as exc_info:
        await svc.submit_pack_anonymous(pack_dir, meta, "John Doe", "john@example.com")
    
    assert "GitHub App configuration invalid: Invalid configuration" in str(exc_info.value)


@pytest.mark.asyncio
async def test_github_app_authentication_flow(tmp_pack_dir, mock_config_manager, mock_github_client):
    """Test complete GitHub App authentication flow for pack submission."""
    pack_dir, meta = tmp_pack_dir
    
    with patch('accessiweather.services.pack_submission_service.GitHubAppClient') as mock_client_class:
        mock_client_class.return_value = mock_github_client
        
        svc = PackSubmissionService(
            repo_owner="accessiweather-community", 
            repo_name="soundpacks", 
            dest_subdir="packs", 
            config_manager=mock_config_manager
        )
        
        # Test submit_pack with GitHub App authentication
        result = await svc.submit_pack(pack_dir, meta)
        
        # Verify GitHub App client was created with correct parameters
        mock_client_class.assert_called_once_with(
            app_id="123456",
            private_key_pem="-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----",
            installation_id="789012",
            user_agent="AccessiWeather/test"
        )
        
        # Verify API calls were made
        assert mock_github_client.github_request.call_count >= 5  # Multiple API calls for full flow
        assert result == "https://github.com/accessiweather-community/soundpacks/pull/123"


@pytest.mark.asyncio 
async def test_anonymous_submission_comprehensive(tmp_pack_dir, mock_config_manager, mock_github_client):
    """Test comprehensive anonymous submission flow with attribution."""
    pack_dir, meta = tmp_pack_dir
    
    with patch('accessiweather.services.pack_submission_service.GitHubAppClient') as mock_client_class:
        mock_client_class.return_value = mock_github_client
        
        svc = PackSubmissionService(
            repo_owner="accessiweather-community",
            repo_name="soundpacks", 
            dest_subdir="packs",
            config_manager=mock_config_manager
        )
        
        # Test anonymous submission with progress callback
        progress_calls = []
        
        async def progress_callback(pct, status):
            progress_calls.append((pct, status))
            return True  # Continue
            
        result = await svc.submit_pack_anonymous(
            pack_dir, meta, "Jane Smith", "jane@example.com", 
            progress_callback=progress_callback
        )
        
        # Verify progress reporting
        assert len(progress_calls) > 5
        assert progress_calls[0][1] == "Checking prerequisites..."
        assert progress_calls[-1][1].startswith("Pull request created:")
        
        # Verify result
        assert result == "https://github.com/accessiweather-community/soundpacks/pull/123"
        
        # Verify GitHub App client was created
        mock_client_class.assert_called_once()


@pytest.mark.asyncio
async def test_error_handling_scenarios(tmp_pack_dir, mock_config_manager):
    """Test various error handling scenarios in pack submission."""
    pack_dir, meta = tmp_pack_dir
    
    # Test validation failure
    with patch('accessiweather.services.pack_submission_service.validate_sound_pack') as mock_validate:
        mock_validate.return_value = (False, "Invalid pack format")
        
        svc = PackSubmissionService(config_manager=mock_config_manager)
        
        with pytest.raises(RuntimeError) as exc_info:
            await svc.submit_pack(pack_dir, meta)
        assert "Sound pack validation failed" in str(exc_info.value)
        assert "Invalid pack format" in str(exc_info.value)


@pytest.mark.asyncio
async def test_cancellation_support(tmp_pack_dir, mock_config_manager, mock_github_client):
    """Test cancellation support throughout submission process."""
    pack_dir, meta = tmp_pack_dir
    
    with patch('accessiweather.services.pack_submission_service.GitHubAppClient') as mock_client_class:
        mock_client_class.return_value = mock_github_client
        
        svc = PackSubmissionService(config_manager=mock_config_manager)
        
        # Test cancellation via progress callback
        cancel_count = 0
        
        def progress_callback(pct, status):
            nonlocal cancel_count
            cancel_count += 1
            if cancel_count >= 3:
                return False  # Cancel operation
            return True
            
        with pytest.raises(asyncio.CancelledError):
            await svc.submit_pack_anonymous(
                pack_dir, meta, "Test User", "test@example.com",
                progress_callback=progress_callback
            )


@pytest.mark.asyncio
async def test_duplicate_pack_detection(tmp_pack_dir, mock_config_manager, mock_github_client):
    """Test duplicate pack detection prevents submission."""
    pack_dir, meta = tmp_pack_dir
    
    # Mock existing pack detection
    async def mock_github_request(method, url, **kwargs):
        if url.startswith("/repos/accessiweather-community/soundpacks/contents/packs/test-pack-jane-doe"):
            return {"name": "pack.json"}  # Pack exists
        return _github_request_side_effect(method, url, **kwargs)
    
    mock_github_client.github_request.side_effect = mock_github_request
    
    with patch('accessiweather.services.pack_submission_service.GitHubAppClient') as mock_client_class:
        mock_client_class.return_value = mock_github_client
        
        svc = PackSubmissionService(config_manager=mock_config_manager)
        
        with pytest.raises(RuntimeError) as exc_info:
            await svc.submit_pack(pack_dir, meta)
        assert "already exists in the repository" in str(exc_info.value)


@pytest.mark.asyncio
async def test_fork_management_with_installation_auth(mock_config_manager, mock_github_client):
    """Test fork creation and management using installation authentication."""
    
    with patch('accessiweather.services.pack_submission_service.GitHubAppClient') as mock_client_class:
        mock_client_class.return_value = mock_github_client
        
        svc = PackSubmissionService(config_manager=mock_config_manager)
        
        # Test fork creation flow
        result = await svc._ensure_fork(mock_github_client)
        
        # Verify installation info call was made
        expected_calls = [call for call in mock_github_client.github_request.call_args_list 
                         if "/repos/accessibot/soundpacks" in str(call)]
        assert len(expected_calls) > 0
        
        assert result == "accessibot/soundpacks"


@pytest.mark.asyncio
async def test_attribution_metadata_handling(tmp_pack_dir):
    """Test proper handling of submitter attribution metadata."""
    pack_dir, meta = tmp_pack_dir
    
    svc = PackSubmissionService()
    
    # Test with attribution
    enhanced_meta = meta.copy()
    enhanced_meta["_submitter"] = {
        "name": "Community Contributor",
        "email": "contributor@example.com",
        "submission_type": "anonymous"
    }
    
    title, body = svc._build_pr_content(enhanced_meta, "test-pack", is_anonymous=True)
    
    assert title == "Add community sound pack: Test Pack"
    assert "Community Contributor" in body
    assert "contributor@example.com" in body
    assert "Anonymous submission via AccessiBot" in body
    
    # Test without attribution (regular submission)
    title, body = svc._build_pr_content(meta, "test-pack", is_anonymous=False)
    
    assert title == "Add sound pack: Test Pack by Jane-Doe"
    assert "Community Contributor" not in body
    assert "Anonymous submission" not in body
