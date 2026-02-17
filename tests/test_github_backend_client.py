"""Tests for GitHubBackendClient."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from accessiweather.services.github_backend_client import GitHubBackendClient
from accessiweather.utils.url_validation import SSRFError


class TestGitHubBackendClientInit:
    """Tests for GitHubBackendClient initialization."""

    def test_init_with_valid_url(self):
        client = GitHubBackendClient("https://api.example.com")
        assert client.backend_url == "https://api.example.com"
        assert client.timeout == 30.0
        assert "AccessiWeather" in client.user_agent

    def test_init_strips_trailing_slash(self):
        client = GitHubBackendClient("https://api.example.com/")
        assert client.backend_url == "https://api.example.com"

    def test_init_custom_user_agent(self):
        client = GitHubBackendClient("https://api.example.com", user_agent="Custom/1.0")
        assert client.user_agent == "Custom/1.0"

    def test_init_custom_timeout(self):
        client = GitHubBackendClient("https://api.example.com", timeout=60.0)
        assert client.timeout == 60.0

    def test_init_invalid_url_raises_ssrf_error(self):
        with pytest.raises(SSRFError):
            GitHubBackendClient("")

    def test_init_localhost_raises_ssrf_error(self):
        with pytest.raises(SSRFError):
            GitHubBackendClient("http://127.0.0.1/api")


class TestUploadZip:
    """Tests for upload_zip method."""

    @pytest.fixture
    def client(self):
        return GitHubBackendClient("https://api.example.com")

    @pytest.mark.asyncio
    async def test_upload_zip_success(self, client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"pr_url": "https://github.com/pr/1"}

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.post.return_value = mock_response
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_http

            result = await client.upload_zip(b"fake-zip-bytes", "test.zip")
            assert result == {"pr_url": "https://github.com/pr/1"}
            mock_http.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_zip_cancelled_before_request(self, client):
        cancel_event = asyncio.Event()
        cancel_event.set()

        with pytest.raises(asyncio.CancelledError):
            await client.upload_zip(b"data", cancel_event=cancel_event)

    @pytest.mark.asyncio
    async def test_upload_zip_http_error(self, client):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"detail": "Internal Server Error"}
        mock_response.text = "Internal Server Error"

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.post.return_value = mock_response
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_http

            with pytest.raises(RuntimeError, match="Backend service error.*500"):
                await client.upload_zip(b"data")

    @pytest.mark.asyncio
    async def test_upload_zip_http_error_non_json_body(self, client):
        mock_response = MagicMock()
        mock_response.status_code = 502
        mock_response.json.side_effect = Exception("not json")
        mock_response.text = "Bad Gateway"

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.post.return_value = mock_response
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_http

            with pytest.raises(RuntimeError, match="Bad Gateway"):
                await client.upload_zip(b"data")

    @pytest.mark.asyncio
    async def test_upload_zip_timeout(self, client):
        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.post.side_effect = httpx.TimeoutException("timed out")
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_http

            with pytest.raises(RuntimeError, match="timeout"):
                await client.upload_zip(b"data")

    @pytest.mark.asyncio
    async def test_upload_zip_connection_error(self, client):
        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.post.side_effect = httpx.ConnectError("refused")
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_http

            with pytest.raises(RuntimeError, match="Failed to connect"):
                await client.upload_zip(b"data")

    @pytest.mark.asyncio
    async def test_upload_zip_cancelled_after_post(self, client):
        cancel_event = asyncio.Event()

        mock_response = MagicMock()
        mock_response.status_code = 200

        async def post_side_effect(*args, **kwargs):
            cancel_event.set()
            return mock_response

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.post.side_effect = post_side_effect
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_http

            with pytest.raises(asyncio.CancelledError):
                await client.upload_zip(b"data", cancel_event=cancel_event)


class TestUploadPackJsonOnly:
    """Tests for upload_pack_json_only method."""

    @pytest.fixture
    def client(self):
        return GitHubBackendClient("https://api.example.com")

    @pytest.mark.asyncio
    async def test_upload_pack_json_success(self, client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"pr_url": "https://github.com/pr/2"}

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.post.return_value = mock_response
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_http

            result = await client.upload_pack_json_only({"name": "test-pack"})
            assert result == {"pr_url": "https://github.com/pr/2"}

    @pytest.mark.asyncio
    async def test_upload_pack_json_cancelled(self, client):
        cancel_event = asyncio.Event()
        cancel_event.set()

        with pytest.raises(asyncio.CancelledError):
            await client.upload_pack_json_only({"name": "test"}, cancel_event=cancel_event)

    @pytest.mark.asyncio
    async def test_upload_pack_json_http_error(self, client):
        mock_response = MagicMock()
        mock_response.status_code = 422
        mock_response.json.return_value = {"detail": "Validation error"}
        mock_response.text = "Validation error"

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.post.return_value = mock_response
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_http

            with pytest.raises(RuntimeError, match="422"):
                await client.upload_pack_json_only({"name": "test"})

    @pytest.mark.asyncio
    async def test_upload_pack_json_timeout(self, client):
        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.post.side_effect = httpx.TimeoutException("timed out")
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_http

            with pytest.raises(RuntimeError, match="timeout"):
                await client.upload_pack_json_only({"name": "test"})


class TestHealthCheck:
    """Tests for health_check method."""

    @pytest.fixture
    def client(self):
        return GitHubBackendClient("https://api.example.com")

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, client):
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.get.return_value = mock_response
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_http

            result = await client.health_check()
            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self, client):
        mock_response = MagicMock()
        mock_response.status_code = 503

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.get.return_value = mock_response
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_http

            result = await client.health_check()
            assert result is False

    @pytest.mark.asyncio
    async def test_health_check_cancelled(self, client):
        cancel_event = asyncio.Event()
        cancel_event.set()

        result = await client.health_check(cancel_event=cancel_event)
        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_timeout(self, client):
        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.get.side_effect = httpx.TimeoutException("timed out")
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_http

            with pytest.raises(RuntimeError, match="timed out"):
                await client.health_check()

    @pytest.mark.asyncio
    async def test_health_check_connection_error(self, client):
        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.get.side_effect = httpx.ConnectError("refused")
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_http

            with pytest.raises(RuntimeError, match="request failed"):
                await client.health_check()
