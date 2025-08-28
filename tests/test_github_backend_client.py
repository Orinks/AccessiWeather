"""Tests for GitHubBackendClient (new endpoints)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from accessiweather.services.github_backend_client import GitHubBackendClient


@pytest.mark.asyncio
async def test_upload_pack_json_only_success():
    """Test that upload_pack_json_only sends JSON to /share-pack."""
    backend_url = "https://api.example.com"
    client = GitHubBackendClient(backend_url)

    pack_data = {
        "name": "Test Pack",
        "author": "Test Author",
        "description": "Test description",
        "sounds": {"alert": "alert.wav", "notify": "notify.wav"},
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

        result = await client.upload_pack_json_only(pack_data)

        # Verify the request was made with correct parameters
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args

        # Check URL
        assert call_args[0][0] == f"{backend_url}/share-pack"

        # Check JSON body contains pack data
        json_body = call_args[1]["json"]
        assert json_body == pack_data

        # Check headers
        headers = call_args[1]["headers"]
        assert headers["Content-Type"] == "application/json"
        assert "User-Agent" in headers

        # Check result
        assert result["html_url"] == "https://github.com/owner/repo/pull/123"


@pytest.mark.asyncio
async def test_upload_zip_success():
    """Test that upload_zip sends multipart data to /upload-zip."""
    backend_url = "https://api.example.com"
    client = GitHubBackendClient(backend_url)

    zip_bytes = b"PK\x03\x04..."  # dummy zip header bytes

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "html_url": "https://github.com/owner/repo/pull/456",
        "number": 456,
    }

    with patch("httpx.AsyncClient") as mock_httpx:
        mock_client = AsyncMock()
        mock_httpx.return_value.__aenter__.return_value = mock_client
        mock_client.post.return_value = mock_response

        result = await client.upload_zip(zip_bytes, filename="testpack.zip")

        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args

        # URL
        assert call_args[0][0] == f"{backend_url}/upload-zip"

        # Files
        files = call_args[1]["files"]
        assert "zip_file" in files
        name, data, content_type = files["zip_file"]
        assert name == "testpack.zip"
        assert data == zip_bytes
        assert content_type == "application/zip"

        # Headers
        headers = call_args[1]["headers"]
        assert "User-Agent" in headers

        assert result["html_url"] == "https://github.com/owner/repo/pull/456"


@pytest.mark.asyncio
async def test_upload_pack_json_only_error_handling():
    """Test error handling for JSON-only endpoint."""
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
            await client.upload_pack_json_only({})

        assert "Backend service error (HTTP 422)" in str(exc_info.value)


@pytest.mark.asyncio
async def test_upload_zip_cancellation():
    """Test cancellation support in upload_zip."""
    backend_url = "https://api.example.com"
    client = GitHubBackendClient(backend_url)

    cancel_event = asyncio.Event()
    cancel_event.set()  # Pre-cancel the event

    with pytest.raises(asyncio.CancelledError):
        await client.upload_zip(b"123", cancel_event=cancel_event)
