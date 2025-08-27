"""Tests for GitHubBackendClient."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from accessiweather.services.github_backend_client import GitHubBackendClient


@pytest.mark.asyncio
async def test_create_pull_request_with_pack_data():
    """Test that create_pull_request sends pack data in the request body."""
    backend_url = "https://api.example.com"
    client = GitHubBackendClient(backend_url)

    pack_data = {
        "name": "Test Pack",
        "author": "Test Author",
        "description": "Test description",
        "sounds": {"alert": "alert.wav", "notify": "notify.wav"},
        "_submitter": {
            "name": "Submitter Name",
            "email": "submitter@example.com",
            "submission_type": "anonymous",
        },
    }

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "html_url": "https://github.com/owner/repo/pull/123",
        "number": 123,
    }

    with patch("httpx.AsyncClient") as mock_httpx:
        mock_client = AsyncMock()
        mock_httpx.return_value.__aenter__.return_value = mock_client
        mock_client.post.return_value = mock_response

        result = await client.create_pull_request(
            branch="test-branch",
            title="Test PR",
            body="Test body",
            pack_data=pack_data,
            head_owner="accessibotapp",
        )

        # Verify the request was made with correct parameters
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args

        # Check URL
        assert call_args[0][0] == f"{backend_url}/create-pr"

        # Check JSON body contains pack data
        json_body = call_args[1]["json"]
        assert json_body["branch"] == "test-branch"
        assert json_body["title"] == "Test PR"
        assert json_body["body"] == "Test body"
        assert json_body["pack_data"] == pack_data
        assert json_body["head_owner"] == "accessibotapp"

        # Check headers
        headers = call_args[1]["headers"]
        assert headers["Content-Type"] == "application/json"
        assert "User-Agent" in headers

        # Check result
        assert result["html_url"] == "https://github.com/owner/repo/pull/123"


@pytest.mark.asyncio
async def test_create_pull_request_without_pack_data():
    """Test that create_pull_request works without pack data."""
    backend_url = "https://api.example.com"
    client = GitHubBackendClient(backend_url)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "html_url": "https://github.com/owner/repo/pull/123",
        "number": 123,
    }

    with patch("httpx.AsyncClient") as mock_httpx:
        mock_client = AsyncMock()
        mock_httpx.return_value.__aenter__.return_value = mock_client
        mock_client.post.return_value = mock_response

        result = await client.create_pull_request(
            branch="test-branch", title="Test PR", body="Test body"
        )

        # Verify the request was made with correct parameters
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args

        # Check JSON body does not contain pack_data or head_owner
        json_body = call_args[1]["json"]
        assert json_body["branch"] == "test-branch"
        assert json_body["title"] == "Test PR"
        assert json_body["body"] == "Test body"
        assert "pack_data" not in json_body
        assert "head_owner" not in json_body

        # Check result
        assert result["html_url"] == "https://github.com/owner/repo/pull/123"


@pytest.mark.asyncio
async def test_create_pull_request_error_handling():
    """Test error handling in create_pull_request."""
    backend_url = "https://api.example.com"
    client = GitHubBackendClient(backend_url)

    mock_response = MagicMock()
    mock_response.status_code = 422
    mock_response.json.return_value = {
        "detail": [{"type": "missing", "loc": ["body"], "msg": "Field required"}]
    }
    mock_response.text = "Validation error"

    with patch("httpx.AsyncClient") as mock_httpx:
        mock_client = AsyncMock()
        mock_httpx.return_value.__aenter__.return_value = mock_client
        mock_client.post.return_value = mock_response

        with pytest.raises(RuntimeError) as exc_info:
            await client.create_pull_request(
                branch="test-branch", title="Test PR", body="Test body"
            )

        assert "Backend service error (HTTP 422)" in str(exc_info.value)


@pytest.mark.asyncio
async def test_create_pull_request_cancellation():
    """Test cancellation support in create_pull_request."""
    backend_url = "https://api.example.com"
    client = GitHubBackendClient(backend_url)

    cancel_event = asyncio.Event()
    cancel_event.set()  # Pre-cancel the event

    with pytest.raises(asyncio.CancelledError):
        await client.create_pull_request(
            branch="test-branch", title="Test PR", body="Test body", cancel_event=cancel_event
        )
