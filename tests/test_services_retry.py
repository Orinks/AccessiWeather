from pathlib import Path

import httpx
import pytest

from accessiweather.services.community_soundpack_service import (
    CommunityPack,
    CommunitySoundPackService,
)
from accessiweather.services.github_backend_client import GitHubBackendClient
from accessiweather.services.update_service.downloads import DownloadManager
from accessiweather.services.update_service.releases import ReleaseManager
from accessiweather.services.update_service.settings import UpdateSettings


class DummySleepAwaitable:
    def __await__(self):
        yield


class DummyResponse:
    """Mock response for testing."""

    def __init__(self, payload, status_code: int = 200, headers: dict | None = None) -> None:
        """Initialize mock response."""
        self._payload = payload
        self.status_code = status_code
        self.headers = headers or {}

    def raise_for_status(self) -> None:
        if not (200 <= self.status_code < 300):
            raise httpx.HTTPStatusError(
                "error",
                request=httpx.Request("GET", "https://example.com"),
                response=httpx.Response(self.status_code),
            )

    def json(self):
        return self._payload


@pytest.mark.asyncio
async def test_release_manager_retries(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    attempts = {"count": 0, "failures_before_success": 3}

    async def fake_get(url, *, headers=None):
        attempts["count"] += 1
        if attempts["count"] < attempts["failures_before_success"]:
            raise httpx.ConnectError("fail", request=httpx.Request("GET", url))
        return DummyResponse([{"tag_name": "v1.0.0"}], headers={"etag": "abc"})

    class DummyClient:
        async def get(self, url, *, headers=None):
            return await fake_get(url, headers=headers)

    settings = UpdateSettings(channel="stable", owner="owner", repo="repo")
    manager = ReleaseManager(
        http_client=DummyClient(),
        owner="owner",
        repo="repo",
        cache_path=tmp_path / "releases.json",
        settings=settings,
    )

    monkeypatch.setattr(
        "accessiweather.utils.retry_utils.asyncio.sleep",
        lambda *_: DummySleepAwaitable(),
    )

    releases = await manager.get_releases()

    assert attempts["count"] == 3
    assert releases == [{"tag_name": "v1.0.0"}]


@pytest.mark.asyncio
async def test_download_manager_retries(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    attempts = {"count": 0, "failures_before_success": 3}
    payload = b"binary-data"

    class DummyStreamResponse:
        def __init__(self):
            self.status_code = 200
            self.headers = {"content-length": str(len(payload))}

        def raise_for_status(self) -> None:
            return None

        async def aiter_bytes(self):
            yield payload

    class DummyStreamCtx:
        async def __aenter__(self_inner):
            attempts["count"] += 1
            if attempts["count"] < attempts["failures_before_success"]:
                raise httpx.ReadTimeout(
                    "timeout", request=httpx.Request("GET", "https://example.com")
                )
            return DummyStreamResponse()

        async def __aexit__(self_inner, exc_type, exc, tb):
            return False

    class DummyHttpClient:
        def stream(self, method, url, **kwargs):
            return DummyStreamCtx()

    manager = DownloadManager(
        http_client=DummyHttpClient(),
        config_dir=tmp_path,
        app_name="TestApp",
    )

    monkeypatch.setattr(
        "accessiweather.utils.retry_utils.asyncio.sleep",
        lambda *_: DummySleepAwaitable(),
    )

    dest = tmp_path / "download.zip"
    result = await manager._download_asset("https://example.com/file.zip", dest)

    assert attempts["count"] == 3
    assert Path(result).exists()
    assert dest.read_bytes() == payload


@pytest.mark.asyncio
async def test_github_backend_client_upload_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = {"count": 0, "failures_before_success": 2}

    class DummyClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, json=None, headers=None):
            attempts["count"] += 1
            if attempts["count"] < attempts["failures_before_success"]:
                raise httpx.ConnectError("fail", request=httpx.Request("POST", url))
            response = DummyResponse({"result": "ok"})
            response.status_code = 200
            return response

    monkeypatch.setattr("httpx.AsyncClient", lambda *args, **kwargs: DummyClient())
    monkeypatch.setattr(
        "accessiweather.utils.retry_utils.asyncio.sleep",
        lambda *_: DummySleepAwaitable(),
    )

    client = GitHubBackendClient("https://backend.example.com")
    result = await client.upload_pack_json_only({"name": "Test"})

    assert attempts["count"] == 2
    assert result == {"result": "ok"}


@pytest.mark.asyncio
async def test_community_soundpack_fetch_tree_entries_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = {"count": 0, "failures_before_success": 2}

    class DummyHttpClient:
        async def get(self, url):
            attempts["count"] += 1
            if attempts["count"] < attempts["failures_before_success"]:
                raise httpx.ConnectError("fail", request=httpx.Request("GET", url))
            return DummyResponse({"tree": [{"path": "packs/test/file", "type": "blob", "size": 1}]})

    service = CommunitySoundPackService(timeout=1.0)
    service._http = DummyHttpClient()

    monkeypatch.setattr(
        "accessiweather.utils.retry_utils.asyncio.sleep",
        lambda *_: DummySleepAwaitable(),
    )

    pack = CommunityPack(
        name="Test",
        author="Author",
        description="Desc",
        version="1.0",
        download_url="",
        file_size=None,
        repository_url="https://example.com/repo",
        release_tag="main",
        download_count=None,
        created_date=None,
        preview_image_url=None,
        repo_path="packs/test",
        tree_sha="abc123",
        ref="main",
    )

    tree = await service._fetch_tree_entries(pack)

    assert attempts["count"] == 2
    assert tree and tree[0]["path"] == "packs/test/file"
