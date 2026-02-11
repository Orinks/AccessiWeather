"""
Regression tests for update download integrity verification (fix-002).

These tests verify that downloaded update artifacts are checked against
checksums and that tampered/corrupted downloads are rejected.
"""

from __future__ import annotations

import hashlib
from unittest.mock import AsyncMock, MagicMock

import pytest

from accessiweather.services.simple_update import (
    ChecksumVerificationError,
    UpdateInfo,
    UpdateService,
    find_checksum_asset,
    parse_checksum_file,
    verify_file_checksum,
)


def _release_with_checksum_assets():
    """Create a release with both an artifact and its checksum file."""
    return {
        "tag_name": "v1.0.0",
        "prerelease": False,
        "body": "",
        "published_at": "2025-01-01T00:00:00Z",
        "assets": [
            {
                "name": "AccessiWeather_Portable_v1.0.0.zip",
                "browser_download_url": "https://example.com/AccessiWeather_Portable_v1.0.0.zip",
            },
            {
                "name": "AccessiWeather_Portable_v1.0.0.zip.sha256",
                "browser_download_url": "https://example.com/AccessiWeather_Portable_v1.0.0.zip.sha256",
            },
        ],
    }


# --- find_checksum_asset tests ---


def test_find_checksum_asset_exact_match():
    release = _release_with_checksum_assets()
    result = find_checksum_asset(release, "AccessiWeather_Portable_v1.0.0.zip")
    assert result is not None
    assert result["name"] == "AccessiWeather_Portable_v1.0.0.zip.sha256"


def test_find_checksum_asset_no_match():
    release = {
        "assets": [
            {"name": "app.zip", "browser_download_url": "https://example.com/app.zip"},
        ]
    }
    assert find_checksum_asset(release, "app.zip") is None


def test_find_checksum_asset_generic_checksums_file():
    release = {
        "assets": [
            {"name": "app.zip", "browser_download_url": "https://example.com/app.zip"},
            {
                "name": "checksums.sha256",
                "browser_download_url": "https://example.com/checksums.sha256",
            },
        ]
    }
    result = find_checksum_asset(release, "app.zip")
    assert result is not None
    assert result["name"] == "checksums.sha256"


# --- parse_checksum_file tests ---


def test_parse_checksum_file_single_hash():
    content = "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890\n"
    result = parse_checksum_file(content, "anything.zip")
    assert result is not None
    algo, hash_val = result
    assert algo == "sha256"
    assert hash_val == "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"


def test_parse_checksum_file_multi_entry():
    content = (
        "aaaa1234567890abcdef1234567890abcdef1234567890abcdef1234567890ab  other.zip\n"
        "bbbb1234567890abcdef1234567890abcdef1234567890abcdef1234567890ab  target.zip\n"
    )
    result = parse_checksum_file(content, "target.zip")
    assert result is not None
    algo, hash_val = result
    assert hash_val.startswith("bbbb")
    assert algo == "sha256"


def test_parse_checksum_file_no_match():
    content = "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890  other.zip\n"
    result = parse_checksum_file(content, "target.zip")
    assert result is None


# --- verify_file_checksum tests ---


def test_verify_file_checksum_valid(tmp_path):
    file_path = tmp_path / "test.bin"
    file_path.write_bytes(b"hello world")
    expected = hashlib.sha256(b"hello world").hexdigest()
    assert verify_file_checksum(file_path, "sha256", expected) is True


def test_verify_file_checksum_tampered(tmp_path):
    file_path = tmp_path / "test.bin"
    file_path.write_bytes(b"tampered content")
    wrong_hash = hashlib.sha256(b"original content").hexdigest()
    assert verify_file_checksum(file_path, "sha256", wrong_hash) is False


# --- Integration: download_update rejects tampered artifact ---


@pytest.mark.asyncio
async def test_download_update_should_reject_tampered_artifact(tmp_path):
    """Regression test: a tampered download must be rejected when checksum mismatches."""
    artifact_content = b"this is a tampered artifact"
    correct_hash = hashlib.sha256(b"this is the real artifact").hexdigest()
    checksum_file_content = f"{correct_hash}  update.zip"

    # Mock streaming download of the artifact
    mock_stream_response = MagicMock()
    mock_stream_response.headers = {"content-length": str(len(artifact_content))}
    mock_stream_response.raise_for_status = MagicMock()

    async def mock_aiter_bytes(chunk_size=None):
        yield artifact_content

    mock_stream_response.aiter_bytes = mock_aiter_bytes
    mock_stream_response.__aenter__ = AsyncMock(return_value=mock_stream_response)
    mock_stream_response.__aexit__ = AsyncMock(return_value=None)

    # Mock checksum file download
    checksum_response = MagicMock()
    checksum_response.raise_for_status = MagicMock()
    checksum_response.text = checksum_file_content

    mock_client = MagicMock()
    mock_client.stream = MagicMock(return_value=mock_stream_response)
    mock_client.get = AsyncMock(return_value=checksum_response)

    service = UpdateService("TestApp", http_client=mock_client)

    update_info = UpdateInfo(
        version="1.0.0",
        download_url="https://example.com/update.zip",
        artifact_name="update.zip",
        release_notes="",
        commit_hash=None,
        is_nightly=False,
        is_prerelease=False,
    )

    release = {
        "assets": [
            {"name": "update.zip", "browser_download_url": "https://example.com/update.zip"},
            {
                "name": "update.zip.sha256",
                "browser_download_url": "https://example.com/update.zip.sha256",
            },
        ]
    }

    with pytest.raises(ChecksumVerificationError, match="Checksum verification failed"):
        await service.download_update(update_info, tmp_path, release=release)

    # The tampered file should have been deleted
    assert not (tmp_path / "update.zip").exists()


@pytest.mark.asyncio
async def test_download_update_should_accept_valid_artifact(tmp_path):
    """Valid artifact with matching checksum should succeed."""
    artifact_content = b"valid artifact content"
    correct_hash = hashlib.sha256(artifact_content).hexdigest()
    checksum_file_content = f"{correct_hash}  update.zip"

    mock_stream_response = MagicMock()
    mock_stream_response.headers = {"content-length": str(len(artifact_content))}
    mock_stream_response.raise_for_status = MagicMock()

    async def mock_aiter_bytes(chunk_size=None):
        yield artifact_content

    mock_stream_response.aiter_bytes = mock_aiter_bytes
    mock_stream_response.__aenter__ = AsyncMock(return_value=mock_stream_response)
    mock_stream_response.__aexit__ = AsyncMock(return_value=None)

    checksum_response = MagicMock()
    checksum_response.raise_for_status = MagicMock()
    checksum_response.text = checksum_file_content

    mock_client = MagicMock()
    mock_client.stream = MagicMock(return_value=mock_stream_response)
    mock_client.get = AsyncMock(return_value=checksum_response)

    service = UpdateService("TestApp", http_client=mock_client)

    update_info = UpdateInfo(
        version="1.0.0",
        download_url="https://example.com/update.zip",
        artifact_name="update.zip",
        release_notes="",
        commit_hash=None,
        is_nightly=False,
        is_prerelease=False,
    )

    release = {
        "assets": [
            {"name": "update.zip", "browser_download_url": "https://example.com/update.zip"},
            {
                "name": "update.zip.sha256",
                "browser_download_url": "https://example.com/update.zip.sha256",
            },
        ]
    }

    result = await service.download_update(update_info, tmp_path, release=release)
    assert result.exists()
    assert result.read_bytes() == artifact_content
