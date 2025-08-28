import asyncio
import json
from pathlib import Path
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
    mock_config.validate_github_app_config.return_value = (
        True,
        "GitHub App configuration is valid",
    )
    mock_config.get_github_app_config.return_value = (
        "123456",
        "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----",
        "789012",
    )
    mock_config.get_github_backend_url.return_value = "https://api.example.com"
    return mock_config


@pytest.fixture()
def mock_github_client():
    """Mock GitHubAppClient for testing submission flows."""
    mock_client = AsyncMock()
    mock_client.github_request = AsyncMock()

    # Setup default responses for common API calls
    mock_client.github_request.side_effect = _github_request_side_effect

    # Mock private methods used by _ensure_fork
    mock_client._generate_jwt = MagicMock(return_value="mock-jwt-token")

    # Mock _get_app_client to return an async context manager
    mock_app_client = AsyncMock()
    mock_app_client.get = AsyncMock(
        return_value=AsyncMock(
            status_code=200, json=MagicMock(return_value={"account": {"login": "accessibot"}})
        )
    )

    class MockAppClientContext:
        async def __aenter__(self):
            return mock_app_client

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    def mock_get_app_client(jwt_token):
        return MockAppClientContext()

    mock_client._get_app_client = mock_get_app_client

    return mock_client


def _github_request_side_effect(method: str, url: str, **kwargs):
    """Mock GitHub API responses based on request URL and method."""
    if url == "/repos/orinks/accessiweather-soundpacks":
        return {"full_name": "orinks/accessiweather-soundpacks", "default_branch": "main"}
    if url == "/app/installations/789012":
        return {"account": {"login": "accessibot"}}
    if url == "/repos/accessibot/accessiweather-soundpacks":
        return {
            "full_name": "accessibot/accessiweather-soundpacks",
            "fork": True,
            "parent": {"full_name": "orinks/accessiweather-soundpacks"},
        }
    if url == "/repos/orinks/accessiweather-soundpacks/git/ref/heads/main":
        return {"object": {"sha": "abc123"}}
    if url.startswith("/repos/orinks/accessiweather-soundpacks/contents/packs/"):
        # Return 404 for pack existence checks (no duplicates)
        return {}
    if method == "POST" and url == "/repos/accessibot/accessiweather-soundpacks/git/refs":
        return {"ref": "refs/heads/soundpack/test-pack-jane-doe-20240101-120000"}
    if method == "PUT" and "/contents/" in url:
        return {"commit": {"sha": "def456"}}
    if method == "POST" and url == "/repos/orinks/accessiweather-soundpacks/pulls":
        return {
            "html_url": "https://github.com/orinks/accessiweather-soundpacks/pull/123",
            "number": 123,
        }
    if method == "POST" and url.endswith("/labels"):
        return {"labels": ["community-submission"]}
    return {}


@pytest.mark.asyncio
async def test_submit_pack_no_config_manager(tmp_pack_dir):
    """Test submit_pack works without config manager using default backend URL.

    We mock the backend client to avoid real network calls and assert success.
    """
    pack_dir, meta = tmp_pack_dir

    svc = PackSubmissionService(repo_owner="owner", repo_name="repo", dest_subdir="packs")

    mock_backend_client = AsyncMock()
    mock_backend_client.upload_zip = AsyncMock(
        return_value={"html_url": "https://github.com/owner/repo/pull/999"}
    )

    with patch(
        "accessiweather.services.pack_submission_service.GitHubBackendClient"
    ) as mock_backend_class:
        mock_backend_class.return_value = mock_backend_client

        pr_url = await svc.submit_pack(pack_dir, meta)

        mock_backend_class.assert_called_once()
        mock_backend_client.upload_zip.assert_called_once()
        assert pr_url == "https://github.com/owner/repo/pull/999"


@pytest.mark.asyncio
async def test_submit_pack_with_config_manager(tmp_pack_dir, mock_config_manager):
    """Test submit_pack works with config manager using backend service."""
    pack_dir, meta = tmp_pack_dir
    mock_config_manager.get_github_backend_url.return_value = "https://test-backend.example.com"

    svc = PackSubmissionService(
        repo_owner="owner",
        repo_name="repo",
        dest_subdir="packs",
        config_manager=mock_config_manager,
    )

    # This should now work with the backend service, but will fail due to invalid test data
    with pytest.raises(RuntimeError) as exc_info:
        await svc.submit_pack(pack_dir, meta)

    # Should get a backend service error, not a config manager error
    assert "Failed to connect to backend service" in str(exc_info.value)


@pytest.mark.asyncio
async def test_submit_pack_anonymous_no_config_manager(tmp_pack_dir):
    """Test submit_pack_anonymous works without config manager using default backend URL."""
    pack_dir, meta = tmp_pack_dir

    svc = PackSubmissionService(repo_owner="owner", repo_name="repo", dest_subdir="packs")

    # This should now work with the backend service, but will fail due to invalid test data
    with pytest.raises(RuntimeError) as exc_info:
        await svc.submit_pack_anonymous(pack_dir, meta, "John Doe", "john@example.com")

    # Should get a backend service error, not a config manager error
    assert "Backend service error" in str(exc_info.value)


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
            "submission_type": "anonymous",
        },
    }

    title, body = svc._build_pr_content(meta, "test-pack", is_anonymous=True)

    assert title == "Add community sound pack: Test Pack"
    assert "## Submitter Information" in body
    assert "**Submitted by:** John Smith" in body
    assert "**Email:** john@example.com" in body
    assert "Anonymous submission via AccessiBotApp" in body


@pytest.mark.asyncio
async def test_build_pr_content_regular():
    """Test _build_pr_content method for regular submissions."""
    svc = PackSubmissionService()
    meta = {
        "name": "Test Pack",
        "author": "Jane Doe",
        "description": "A test sound pack",
        "sounds": {"alert": "alert.wav", "notify": "notify.wav"},
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
    """Test submit_pack_anonymous raises error when backend URL is invalid."""
    pack_dir, meta = tmp_pack_dir
    # Return an invalid URL that will cause httpx to fail
    mock_config_manager.get_github_backend_url.return_value = "invalid-url"

    svc = PackSubmissionService(
        repo_owner="owner",
        repo_name="repo",
        dest_subdir="packs",
        config_manager=mock_config_manager,
    )

    with pytest.raises(RuntimeError) as exc_info:
        await svc.submit_pack_anonymous(pack_dir, meta, "John Doe", "john@example.com")

    assert "Failed to connect to backend service" in str(exc_info.value)


@pytest.mark.asyncio
async def test_submit_pack_backend_flow(tmp_pack_dir, mock_config_manager):
    """Test complete backend service flow for pack submission."""
    pack_dir, meta = tmp_pack_dir

    # Mock the backend client
    mock_backend_client = AsyncMock()
    mock_backend_client.upload_zip = AsyncMock(
        return_value={"html_url": "https://github.com/orinks/accessiweather-soundpacks/pull/123"}
    )

    with patch(
        "accessiweather.services.pack_submission_service.GitHubBackendClient"
    ) as mock_backend_class:
        mock_backend_class.return_value = mock_backend_client

        svc = PackSubmissionService(
            repo_owner="orinks",
            repo_name="accessiweather-soundpacks",
            dest_subdir="packs",
            config_manager=mock_config_manager,
        )

        # Test submit_pack with backend service
        result = await svc.submit_pack(pack_dir, meta)

        # Verify backend client was created and called
        mock_backend_class.assert_called_once()
        mock_backend_client.upload_zip.assert_called_once()

        # Verify result
        assert result == "https://github.com/orinks/accessiweather-soundpacks/pull/123"


@pytest.mark.asyncio
async def test_anonymous_submission_comprehensive(
    tmp_pack_dir, mock_config_manager, mock_github_client
):
    """Test comprehensive anonymous submission flow with attribution."""
    pack_dir, meta = tmp_pack_dir

    # Mock the backend client
    mock_backend_client = AsyncMock()
    mock_backend_client.upload_zip = AsyncMock(
        return_value={"html_url": "https://github.com/orinks/accessiweather-soundpacks/pull/123"}
    )

    with patch(
        "accessiweather.services.pack_submission_service.GitHubBackendClient"
    ) as mock_backend_class:
        mock_backend_class.return_value = mock_backend_client

        svc = PackSubmissionService(
            repo_owner="orinks",
            repo_name="accessiweather-soundpacks",
            dest_subdir="packs",
            config_manager=mock_config_manager,
        )

        # Test anonymous submission with progress callback
        progress_calls = []

        async def progress_callback(pct, status):
            progress_calls.append((pct, status))
            return True  # Continue

        result = await svc.submit_pack_anonymous(
            pack_dir, meta, "Jane Smith", "jane@example.com", progress_callback=progress_callback
        )

        # Verify progress reporting
        assert len(progress_calls) > 5
        assert progress_calls[0][1] == "Checking prerequisites..."
        assert progress_calls[-1][1].startswith("Pull request created:")

        # Verify result
        assert result == "https://github.com/orinks/accessiweather-soundpacks/pull/123"

        # Verify backend client was created and called
        mock_backend_class.assert_called_once()
        mock_backend_client.upload_zip.assert_called_once()


@pytest.mark.asyncio
async def test_error_handling_scenarios(tmp_pack_dir, mock_config_manager):
    """Test various error handling scenarios in pack submission."""
    pack_dir, meta = tmp_pack_dir

    # Test validation failure
    with patch(
        "accessiweather.services.pack_submission_service.validate_sound_pack"
    ) as mock_validate:
        mock_validate.return_value = (False, "Invalid pack format")

        svc = PackSubmissionService(config_manager=mock_config_manager)

        with pytest.raises(RuntimeError) as exc_info:
            await svc.submit_pack(pack_dir, meta)
        assert "Sound pack validation failed" in str(exc_info.value)
        assert "Invalid pack format" in str(exc_info.value)


@pytest.mark.asyncio
async def test_cancellation_support(tmp_pack_dir, mock_config_manager):
    """Test cancellation support throughout submission process."""
    pack_dir, meta = tmp_pack_dir

    # Mock the backend client to simulate cancellation
    mock_backend_client = AsyncMock()

    def progress_callback(pct, status):
        # Return False to trigger cancellation
        return False

    mock_backend_client.upload_zip = AsyncMock(side_effect=asyncio.CancelledError())

    with patch(
        "accessiweather.services.pack_submission_service.GitHubBackendClient"
    ) as mock_backend_class:
        mock_backend_class.return_value = mock_backend_client

        svc = PackSubmissionService(config_manager=mock_config_manager)

        with pytest.raises(asyncio.CancelledError):
            await svc.submit_pack_anonymous(
                pack_dir, meta, "Test User", "test@example.com", progress_callback=progress_callback
            )


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
        "submission_type": "anonymous",
    }

    title, body = svc._build_pr_content(enhanced_meta, "test-pack", is_anonymous=True)

    assert title == "Add community sound pack: Test Pack"
    assert "Community Contributor" in body
    assert "contributor@example.com" in body
    assert "Anonymous submission via AccessiBotApp" in body

    # Test without attribution (regular submission)
    title, body = svc._build_pr_content(meta, "test-pack", is_anonymous=False)

    assert title == "Add sound pack: Test Pack by Jane-Doe"
    assert "Community Contributor" not in body
    assert "Anonymous submission" not in body
