"""Tests for BUILD_TAG usage in GitHubUpdateService.check_for_updates."""

from __future__ import annotations

from unittest import mock

import pytest

from accessiweather.services.update_service.github_update_service import GitHubUpdateService


@pytest.fixture
def service(tmp_path):
    """Create a GitHubUpdateService with mocked HTTP client."""
    return GitHubUpdateService(
        app_name="test",
        config_dir=str(tmp_path),
        owner="test",
        repo="test",
    )


@pytest.mark.asyncio
async def test_check_uses_build_tag_when_present(service):
    """When _build_info.BUILD_TAG is set, it should be used as current_version."""
    nightly_release = {
        "tag_name": "nightly-20260210",
        "prerelease": True,
        "body": "",
        "published_at": "2026-02-10T00:00:00Z",
        "assets": [
            {
                "name": "test.zip",
                "browser_download_url": "https://example.com/test.zip",
                "size": 100,
            }
        ],
    }

    with mock.patch.object(service, "_get_releases", return_value=[nightly_release]):
        build_info_mod = mock.MagicMock(BUILD_TAG="nightly-20260209")
        with mock.patch.dict("sys.modules", {"accessiweather._build_info": build_info_mod}):
            service.settings.channel = "dev"
            result = await service.check_for_updates()
            # Should find nightly-20260210 as newer than nightly-20260209
            assert result is not None
            assert result.version == "nightly-20260210"


@pytest.mark.asyncio
async def test_check_no_update_when_build_tag_matches(service):
    """When BUILD_TAG matches latest nightly, no update should be found."""
    nightly_release = {
        "tag_name": "nightly-20260209",
        "prerelease": True,
        "body": "",
        "published_at": "2026-02-09T00:00:00Z",
        "assets": [
            {
                "name": "test.zip",
                "browser_download_url": "https://example.com/test.zip",
                "size": 100,
            }
        ],
    }

    with mock.patch.object(service, "_get_releases", return_value=[nightly_release]):
        build_info_mod = mock.MagicMock(BUILD_TAG="nightly-20260209")
        with mock.patch.dict("sys.modules", {"accessiweather._build_info": build_info_mod}):
            service.settings.channel = "dev"
            result = await service.check_for_updates()
            # Same nightly date, no update
            assert result is None


@pytest.mark.asyncio
async def test_check_falls_back_to_version_when_no_build_tag(service):
    """When _build_info doesn't exist, should fall back to __version__."""
    stable_release = {
        "tag_name": "v99.0.0",
        "prerelease": False,
        "body": "",
        "published_at": "2026-02-09T00:00:00Z",
        "assets": [
            {
                "name": "test.zip",
                "browser_download_url": "https://example.com/test.zip",
                "size": 100,
            }
        ],
    }

    with (
        mock.patch.object(service, "_get_releases", return_value=[stable_release]),
        # Make _build_info import fail
        mock.patch.dict("sys.modules", {"accessiweather._build_info": None}),
    ):
        service.settings.channel = "stable"
        result = await service.check_for_updates()
        # v99.0.0 should be newer than any current version
        assert result is not None
        assert result.version == "99.0.0"
