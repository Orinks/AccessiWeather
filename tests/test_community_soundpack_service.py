"""Tests for community sound pack download hardening."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from accessiweather.services.community_soundpack_models import CommunityPack
from accessiweather.services.community_soundpack_service import CommunitySoundPackService


def _repo_pack() -> CommunityPack:
    return CommunityPack(
        name="Example",
        author="Tester",
        description="Test pack",
        version="1.0",
        download_url="",
        file_size=None,
        repository_url="https://github.com/example/repo",
        release_tag="",
        repo_path="packs/example",
    )


@pytest.mark.asyncio
async def test_download_repo_pack_rejects_path_traversal(tmp_path):
    service = CommunitySoundPackService(repo_owner="example", repo_name="repo")
    service._fetch_tree_entries = AsyncMock(
        return_value=[{"type": "blob", "path": "../escape.wav", "size": 4}]
    )

    try:
        with pytest.raises(RuntimeError, match="Unsafe path"):
            await service._download_repo_pack(_repo_pack(), tmp_path / "pack.zip", None)
    finally:
        await service.aclose()
