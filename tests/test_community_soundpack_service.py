from __future__ import annotations

import json
import zipfile
from pathlib import Path

import httpx
import pytest

from accessiweather.services.community_soundpack_service import CommunitySoundPackService


@pytest.fixture
def mock_transport():
    pack_tree_sha = "tree-sha-123"

    async def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        host = request.url.host

        if host == "api.github.com" and path.endswith("/contents/index.json"):
            return httpx.Response(404)

        if host == "api.github.com" and path.endswith("/contents/packs"):
            data = [
                {
                    "name": "test-pack",
                    "path": "packs/test-pack",
                    "sha": pack_tree_sha,
                    "type": "dir",
                }
            ]
            return httpx.Response(200, json=data)

        if host == "api.github.com" and path.endswith("/releases"):
            return httpx.Response(200, json=[])

        if host == "api.github.com" and f"/git/trees/{pack_tree_sha}" in path:
            tree_payload = {
                "tree": [
                    {"path": "pack.json", "type": "blob", "size": 200},
                    {"path": "alert.wav", "type": "blob", "size": 3},
                ]
            }
            return httpx.Response(200, json=tree_payload)

        if host == "raw.githubusercontent.com" and path.endswith("/pack.json"):
            meta = {
                "name": "Test Pack",
                "author": "QA Team",
                "description": "Integration test pack",
                "version": "1.2.3",
            }
            return httpx.Response(200, content=json.dumps(meta).encode("utf-8"))

        if host == "raw.githubusercontent.com" and path.endswith("/alert.wav"):
            return httpx.Response(200, content=b"wav")

        return httpx.Response(404)

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_fetch_available_packs_falls_back_to_repo(mock_transport):
    service = CommunitySoundPackService(
        repo_owner="Orinks",
        repo_name="accessiweather-soundpacks",
    )
    await service._http.aclose()
    service._http = httpx.AsyncClient(transport=mock_transport)

    packs = await service.fetch_available_packs(force_refresh=True)

    assert len(packs) == 1
    pack = packs[0]
    assert pack.name == "Test Pack"
    assert pack.author == "QA Team"
    assert pack.repo_path == "packs/test-pack"
    assert pack.download_url == ""

    await service.aclose()


@pytest.mark.asyncio
async def test_download_repo_pack_creates_zip(mock_transport, tmp_path: Path):
    service = CommunitySoundPackService(
        repo_owner="Orinks",
        repo_name="accessiweather-soundpacks",
    )
    await service._http.aclose()
    service._http = httpx.AsyncClient(transport=mock_transport)

    packs = await service.fetch_available_packs(force_refresh=True)
    pack = packs[0]

    zip_path = await service.download_pack(pack, tmp_path)

    assert zip_path.exists()
    with zipfile.ZipFile(zip_path) as zf:
        assert sorted(zf.namelist()) == ["alert.wav", "pack.json"]
        with zf.open("pack.json") as fp:
            payload = json.load(fp)
            assert payload["name"] == "Test Pack"

    await service.aclose()
