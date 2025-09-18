"""Tests for GitHubUpdateService.

Covers: initialization, releases fetching with ETag/pagination, channel filtering,
latest version selection, platform asset selection (Windows), download flow,
checksum verification, diagnostics, and settings save/load.
"""

import asyncio
import hashlib
import sys
import time
import types
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio

# Add src to path for proper imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

# Provide minimal stubs to avoid requiring external deps during collection
# httpx stub with AsyncClient and exception types used by the service
_httpx_stub = types.ModuleType("httpx")


class _AsyncClientStub:
    def __init__(self, *args, **kwargs):
        pass

    async def get(self, *args, **kwargs):  # pragma: no cover - not used directly
        raise NotImplementedError

    def stream(self, *args, **kwargs):  # pragma: no cover - replaced by tests
        class _Ctx:
            async def __aenter__(self):
                raise NotImplementedError

            async def __aexit__(self, exc_type, exc, tb):
                return False

        return _Ctx()

    async def aclose(self):
        return None


class _TimeoutException(Exception):
    pass


class _RequestError(Exception):
    pass


class _HTTPStatusError(Exception):
    pass


_httpx_stub.AsyncClient = _AsyncClientStub
_httpx_stub.TimeoutException = _TimeoutException
_httpx_stub.RequestError = _RequestError
_httpx_stub.HTTPStatusError = _HTTPStatusError
sys.modules.setdefault("httpx", _httpx_stub)

# packaging.version.Version stub with simple comparison logic sufficient for tests
_packaging_stub = types.ModuleType("packaging")
_version_mod = types.ModuleType("version")


class _Version:
    def __init__(self, s: str):
        s = s.lstrip("vV")
        if "-" in s:
            base, _pre = s.split("-", 1)
            self._prerelease = True
        else:
            base = s
            self._prerelease = False
        parts = base.split(".")
        nums = []
        for p in parts:
            try:
                nums.append(int(p))
            except ValueError:
                # strip trailing non-digits, best-effort
                num = "".join(ch for ch in p if ch.isdigit()) or "0"
                nums.append(int(num))
        # normalize length
        while len(nums) < 3:
            nums.append(0)
        self._tuple = tuple(nums[:3])

    def _cmp_key(self):
        # Stable releases sort higher than pre-releases with same base
        return (*self._tuple, 0 if self._prerelease else 1)

    def __lt__(self, other):
        return self._cmp_key() < other._cmp_key()

    def __gt__(self, other):
        return self._cmp_key() > other._cmp_key()

    def __eq__(self, other):
        return self._cmp_key() == other._cmp_key()


_version_mod.Version = _Version
_packaging_stub.version = _version_mod
sys.modules.setdefault("packaging", _packaging_stub)
sys.modules.setdefault("packaging.version", _version_mod)

# Import the service module normally
from accessiweather.services.github_update_service import (  # noqa: E402
    GitHubUpdateService,
    UpdateInfo,
)


# -----------------------------
# Simple mock utilities
# -----------------------------
class MockResponse:
    def __init__(
        self,
        *,
        status_code: int = 200,
        json_data: Any = None,
        headers: dict | None = None,
        text: str = "",
    ):
        """Initialize mock response."""
        self.status_code = status_code
        self._json = json_data
        self.headers = headers or {}
        self.text = text

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx

            raise httpx.HTTPStatusError(f"HTTP {self.status_code}", request=None, response=None)


class MockStreamResponse:
    def __init__(
        self,
        *,
        status_code: int = 200,
        headers: dict | None = None,
        chunks: Iterable[bytes] = (b"",),
    ):
        """Initialize mock stream response."""
        self.status_code = status_code
        self.headers = headers or {}
        self._chunks = list(chunks)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx

            raise httpx.HTTPStatusError(f"HTTP {self.status_code}", request=None, response=None)

    async def aiter_bytes(self):
        for c in self._chunks:
            await asyncio.sleep(0)  # let loop switch
            yield c


class QueueHttpClient:
    """Minimal async http client stub supporting get() and stream().

    - get() returns queued responses in order
    - stream() returns a configured MockStreamResponse
    """

    def __init__(
        self,
        get_responses: list[MockResponse] | None = None,
        stream_resp: MockStreamResponse | None = None,
    ):
        """Initialize queue-based http client stub."""
        self._get_responses = list(get_responses or [])
        self._get_calls = []
        self._stream_resp = stream_resp or MockStreamResponse()

    async def get(self, url: str, headers: dict | None = None):
        self._get_calls.append({"url": url, "headers": dict(headers or {})})
        if self._get_responses:
            return self._get_responses.pop(0)
        # default empty list
        return MockResponse(status_code=200, json_data=[])

    def stream(self, method: str, url: str):
        assert method == "GET"
        # return an async context manager
        return self._stream_resp

    async def aclose(self):
        return None


# -----------------------------
# Fixtures
# -----------------------------
@pytest.fixture(autouse=True)
def version_fixture(monkeypatch):
    """Fixture to set version for tests."""
    monkeypatch.setattr("accessiweather.__version__", "0.0.0-test", raising=False)
    yield


@pytest.fixture
def svc_sync(tmp_path):
    """Create synchronous service fixture for non-async tests."""
    return GitHubUpdateService(app_name="AccessiWeatherTest", config_dir=str(tmp_path))


@pytest_asyncio.fixture
async def svc(tmp_path):
    """Reusable async service fixture that properly cleans up AsyncClient."""
    s = GitHubUpdateService(app_name="AccessiWeatherTest", config_dir=str(tmp_path))
    try:
        yield s
    finally:
        await s.cleanup()


@pytest.fixture
def windows_platform(monkeypatch):
    monkeypatch.setattr("platform.system", lambda: "Windows")
    yield


@pytest.fixture
def linux_platform(monkeypatch):
    monkeypatch.setattr("platform.system", lambda: "Linux")
    yield


@pytest.fixture
def macos_platform(monkeypatch):
    monkeypatch.setattr("platform.system", lambda: "Darwin")
    yield


@pytest.fixture
def sample_releases():
    # 3 releases: older stable, newer stable, prerelease beta
    return [
        {
            "tag_name": "v0.9.3",
            "published_at": "2024-01-01T00:00:00Z",
            "prerelease": False,
            "assets": [
                {
                    "name": "AccessiWeather-0.9.3-win.msi",
                    "browser_download_url": "https://example.com/0.9.3.msi",
                    "size": 123,
                },
                {
                    "name": "AccessiWeather-0.9.3-linux.tar.gz",
                    "browser_download_url": "https://example.com/0.9.3.tar.gz",
                    "size": 456,
                },
            ],
            "body": "Changelog 0.9.3",
        },
        {
            "tag_name": "v0.9.5",
            "published_at": "2024-03-05T12:00:00Z",
            "prerelease": False,
            "assets": [
                {
                    "name": "AccessiWeather-0.9.5-win64.exe",
                    "browser_download_url": "https://example.com/0.9.5.exe",
                    "size": 789,
                },
                {
                    "name": "AccessiWeather-0.9.5-linux.deb",
                    "browser_download_url": "https://example.com/0.9.5.deb",
                    "size": 321,
                },
                {
                    "name": "AccessiWeather-0.9.5-macos.pkg",
                    "browser_download_url": "https://example.com/0.9.5.pkg",
                    "size": 654,
                },
            ],
            "body": "Changelog 0.9.5",
        },
        {
            "tag_name": "v0.9.6-beta",
            "published_at": "2024-03-10T12:00:00Z",
            "prerelease": True,
            "assets": [
                {
                    "name": "AccessiWeather-0.9.6-beta-win.msi",
                    "browser_download_url": "https://example.com/0.9.6-beta.msi",
                    "size": 999,
                }
            ],
            "body": "Beta notes",
        },
    ]


# -----------------------------
# Tests
# -----------------------------
@pytest.mark.asyncio
async def test_check_for_updates_stable_selects_latest_windows(
    windows_platform, sample_releases, svc
):
    # Queue a single GET response with sample releases
    client = QueueHttpClient(get_responses=[MockResponse(json_data=sample_releases)])
    svc.http_client = client

    info = await svc.check_for_updates(current_version="0.9.4")
    assert isinstance(info, UpdateInfo)
    assert info.version == "0.9.5"
    assert info.is_prerelease is False
    assert info.artifact_name.endswith(".exe") or info.artifact_name.endswith(".msi")
    assert info.download_url == "https://example.com/0.9.5.exe"
    # Ensure ETag header not set unless from cache; first call should not set If-None-Match
    assert client._get_calls[0]["headers"].get("If-None-Match") is None


@pytest.mark.asyncio
async def test_get_releases_uses_etag_304_returns_cached(windows_platform, sample_releases, svc):
    # Preload cache with past releases and etag
    svc._cache = {
        "last_check": time.time() - 7200,  # expired but present
        "releases": sample_releases,
        "etag": 'W/"etag-123"',
        "channel": svc.settings.channel,
        "owner": svc.owner,
        "repo": svc.repo,
    }

    # First GET returns 304 Not Modified -> should return cached releases and update last_check
    client = QueueHttpClient(
        get_responses=[MockResponse(status_code=304, headers={"etag": 'W/"etag-123"'})]
    )
    svc.http_client = client

    releases = await svc._get_releases()
    assert releases == sample_releases
    assert "If-None-Match" in client._get_calls[0]["headers"]


@pytest.mark.asyncio
async def test_get_releases_pagination_aggregates(windows_platform, svc):
    page1 = [
        {
            "tag_name": "v0.9.1",
            "published_at": "2024-01-01T00:00:00Z",
            "prerelease": False,
            "assets": [],
        }
    ]
    page2 = [
        {
            "tag_name": "v0.9.2",
            "published_at": "2024-02-01T00:00:00Z",
            "prerelease": False,
            "assets": [],
        }
    ]
    link_header = (
        '<https://api.github.com/repos/o/r/releases?page=2>; rel="next", <...>; rel="last"'
    )

    client = QueueHttpClient(
        get_responses=[
            MockResponse(json_data=page1, headers={"Link": link_header, "etag": 'W/"x"'}),
            MockResponse(json_data=page2, headers={}),
        ]
    )
    svc.http_client = client

    releases = await svc._get_releases()
    assert len(releases) == 2
    assert releases[0]["tag_name"] == "v0.9.1"
    assert releases[1]["tag_name"] == "v0.9.2"


def test_channel_filtering(sample_releases, svc_sync):
    stable = svc_sync._filter_releases_by_channel(sample_releases, "stable")
    beta = svc_sync._filter_releases_by_channel(sample_releases, "beta")
    dev = svc_sync._filter_releases_by_channel(sample_releases, "dev")

    # Stable channel: only non-prerelease versions
    assert all(not r.get("prerelease", False) for r in stable)

    # Beta channel: stable releases + beta/rc prereleases (hierarchical)
    # Should include all stable releases
    stable_in_beta = [r for r in beta if not r.get("prerelease", False)]
    assert len(stable_in_beta) == len(stable)  # All stable releases included

    # Should include beta/rc prereleases but not other prereleases
    prerelease_in_beta = [r for r in beta if r.get("prerelease", False)]
    assert all(
        "beta" in r.get("tag_name", "").lower() or "rc" in r.get("tag_name", "").lower()
        for r in prerelease_in_beta
    )

    # Dev channel: includes all releases
    assert len(dev) == len(sample_releases)


@pytest.mark.asyncio
async def test_download_update_success_with_progress_and_cancel(windows_platform, svc):
    # Stream 3 chunks
    chunks = [b"A" * 10, b"B" * 5, b"C" * 15]
    client = QueueHttpClient(
        stream_resp=MockStreamResponse(
            headers={"content-length": str(sum(len(c) for c in chunks))}, chunks=chunks
        )
    )
    svc.http_client = client

    progress = []

    def on_progress(downloaded, total):
        progress.append((downloaded, total))

    info = UpdateInfo(
        version="0.9.9", download_url="https://example.com/file.exe", artifact_name="file.exe"
    )
    dest = await svc.download_update(info, progress_callback=on_progress)

    assert isinstance(dest, str)
    path = Path(dest)
    assert path.exists()
    assert path.stat().st_size == sum(len(c) for c in chunks)
    # Ensure progress was called incrementally
    assert progress[-1][0] == sum(len(c) for c in chunks)


@pytest.mark.asyncio
async def test_download_update_sha256_mismatch_returns_false_and_removes(windows_platform, svc):
    content = b"abc1234567"
    good_digest = hashlib.sha256(content).hexdigest()
    wrong_digest = "0" * 64 if good_digest[0] != "0" else "f" * 64

    client = QueueHttpClient(
        stream_resp=MockStreamResponse(
            headers={"content-length": str(len(content))}, chunks=[content]
        )
    )
    svc.http_client = client

    info = UpdateInfo(
        version="0.9.9", download_url="https://example.com/file.exe", artifact_name="file.exe"
    )
    dest = await svc.download_update(info, expected_sha256=wrong_digest)
    assert dest is False

    # Ensure file cleaned up
    updates_dir = Path(svc.config_dir) / "updates"
    files = list(updates_dir.glob("*.exe"))
    assert not files  # removed due to mismatch


@pytest.mark.asyncio
async def test_get_github_diagnostics(windows_platform, svc):
    client = QueueHttpClient(get_responses=[MockResponse(status_code=200)])
    svc.http_client = client

    info = await svc.get_github_diagnostics()
    assert info["repo"].endswith(f"{svc.owner}/{svc.repo}")
    assert info["channel"] == svc.settings.channel
    assert info["platform"] == "Windows"
    assert info["api_status"] == 200


def test_save_and_load_settings(tmp_path, windows_platform):
    svc = GitHubUpdateService(app_name="AccessiWeatherTest", config_dir=str(tmp_path))

    # Update settings and save
    svc.settings.channel = "beta"
    svc.settings.owner = "foo"
    svc.settings.repo = "bar"
    svc.save_settings()

    # New service should load saved settings
    svc2 = GitHubUpdateService(app_name="AccessiWeatherTest", config_dir=str(tmp_path))
    assert svc2.settings.channel == "beta"
    assert svc2.settings.owner == "foo"
    assert svc2.settings.repo == "bar"


# -----------------------------
# Additional tests for verification comments
# -----------------------------


# Platform asset selection tests
@pytest.mark.asyncio
async def test_platform_asset_selection_linux(linux_platform, sample_releases, svc):
    """Test Linux platform selects .tar.gz or .deb assets."""
    client = QueueHttpClient(get_responses=[MockResponse(json_data=sample_releases)])
    svc.http_client = client

    info = await svc.check_for_updates(current_version="0.9.4")
    assert isinstance(info, UpdateInfo)
    assert info.version == "0.9.5"
    assert info.artifact_name.endswith(".deb") or info.artifact_name.endswith(".tar.gz")


@pytest.mark.asyncio
async def test_platform_asset_selection_macos(macos_platform, sample_releases, svc):
    """Test macOS platform selects .dmg or .pkg assets."""
    client = QueueHttpClient(get_responses=[MockResponse(json_data=sample_releases)])
    svc.http_client = client

    info = await svc.check_for_updates(current_version="0.9.4")
    assert isinstance(info, UpdateInfo)
    assert info.version == "0.9.5"
    assert info.artifact_name.endswith(".pkg") or info.artifact_name.endswith(".dmg")


@pytest.mark.asyncio
async def test_no_suitable_asset_fallback(windows_platform, svc):
    """Test fallback to first asset when no platform-specific asset found."""
    releases_no_match = [
        {
            "tag_name": "v0.9.5",
            "published_at": "2024-03-05T12:00:00Z",
            "prerelease": False,
            "assets": [
                {
                    "name": "AccessiWeather-0.9.5-source.txt",
                    "browser_download_url": "https://example.com/0.9.5.txt",
                    "size": 100,
                }
            ],
            "body": "Changelog 0.9.5",
        }
    ]

    client = QueueHttpClient(get_responses=[MockResponse(json_data=releases_no_match)])
    svc.http_client = client

    info = await svc.check_for_updates(current_version="0.9.4")
    # Should fallback to first asset when no platform-specific asset found
    assert isinstance(info, UpdateInfo)
    assert info.artifact_name == "AccessiWeather-0.9.5-source.txt"


@pytest.mark.asyncio
async def test_no_assets_returns_none(windows_platform, svc):
    """Test that releases with no assets return None."""
    releases_no_assets = [
        {
            "tag_name": "v0.9.5",
            "published_at": "2024-03-05T12:00:00Z",
            "prerelease": False,
            "assets": [],  # No assets
            "body": "Changelog 0.9.5",
        }
    ]

    client = QueueHttpClient(get_responses=[MockResponse(json_data=releases_no_assets)])
    svc.http_client = client

    info = await svc.check_for_updates(current_version="0.9.4")
    # Should return None when no assets are found
    assert info is None


@pytest.mark.asyncio
async def test_no_update_available_current_is_latest(windows_platform, sample_releases, svc):
    """Test no update when current version is latest or higher."""
    client = QueueHttpClient(get_responses=[MockResponse(json_data=sample_releases)])
    svc.http_client = client

    # Current version is same as latest
    info = await svc.check_for_updates(current_version="0.9.5")
    assert info is None

    # Current version is higher than latest
    info = await svc.check_for_updates(current_version="0.9.6")
    assert info is None


@pytest.mark.asyncio
async def test_download_update_with_cancellation(windows_platform, svc):
    """Test that download can be cancelled and partial file is removed."""
    chunks = [b"A" * 100, b"B" * 100, b"C" * 100]
    client = QueueHttpClient(
        stream_resp=MockStreamResponse(
            headers={"content-length": str(sum(len(c) for c in chunks))}, chunks=chunks
        )
    )
    svc.http_client = client

    cancel_event = asyncio.Event()
    progress_calls = []

    def on_progress(downloaded, total):
        progress_calls.append((downloaded, total))
        # Cancel after first chunk
        if downloaded >= 100:
            cancel_event.set()

    info = UpdateInfo(
        version="0.9.9", download_url="https://example.com/file.exe", artifact_name="file.exe"
    )
    result = await svc.download_update(
        info, progress_callback=on_progress, cancel_event=cancel_event
    )

    assert result is False
    # Ensure partial file is removed
    updates_dir = Path(svc.config_dir) / "updates"
    files = list(updates_dir.glob("*.exe"))
    assert not files


# Caching tests
@pytest.mark.asyncio
async def test_cache_validation_with_matching_settings(windows_platform, sample_releases, svc):
    """Test cache is used when settings match."""
    import json

    # Write valid cache with matching settings
    cache_data = {
        "last_check": time.time() - 1800,  # 30 minutes ago, within expiry
        "releases": sample_releases,
        "etag": 'W/"test-etag"',
        "channel": svc.settings.channel,
        "owner": svc.owner,
        "repo": svc.repo,
    }
    svc.cache_path.write_text(json.dumps(cache_data), encoding="utf-8")

    # Should return cached data without HTTP call
    releases = await svc._get_releases()
    assert releases == sample_releases


@pytest.mark.asyncio
async def test_cache_invalidation_on_channel_change(windows_platform, sample_releases, svc):
    """Test cache is bypassed when channel changes."""
    import json

    # Write cache with different channel
    cache_data = {
        "last_check": time.time() - 1800,
        "releases": sample_releases,
        "etag": 'W/"test-etag"',
        "channel": "beta",  # Different from default "stable"
        "owner": svc.owner,
        "repo": svc.repo,
    }
    svc.cache_path.write_text(json.dumps(cache_data), encoding="utf-8")

    # Should make HTTP call and ignore cache
    client = QueueHttpClient(get_responses=[MockResponse(json_data=sample_releases)])
    svc.http_client = client

    await svc._get_releases()
    assert len(client._get_calls) == 1  # HTTP call was made


@pytest.mark.asyncio
async def test_corrupted_cache_graceful_handling(windows_platform, svc):
    """Test graceful handling of corrupted cache file."""
    # Write corrupted JSON
    svc.cache_path.write_text("invalid json content", encoding="utf-8")

    client = QueueHttpClient(get_responses=[MockResponse(json_data=[])])
    svc.http_client = client

    # Should handle gracefully and make HTTP call
    releases = await svc._get_releases()
    assert releases == []
    assert len(client._get_calls) == 1


@pytest.mark.asyncio
async def test_cache_invalidation_on_owner_change(windows_platform, sample_releases, svc):
    """Test cache is bypassed when owner changes."""
    import json

    # Write cache with current settings
    cache_data = {
        "last_check": time.time() - 1800,  # 30 minutes ago, within expiry
        "releases": sample_releases,
        "etag": 'W/"test-etag"',
        "channel": svc.settings.channel,
        "owner": svc.owner,
        "repo": svc.repo,
    }
    svc.cache_path.write_text(json.dumps(cache_data), encoding="utf-8")

    # Change owner without calling save_settings() to avoid cache clearing
    svc.owner = svc.owner + "-changed"

    # Should make HTTP call and ignore cache due to owner mismatch
    client = QueueHttpClient(get_responses=[MockResponse(json_data=[])])
    svc.http_client = client

    await svc._get_releases()
    assert len(client._get_calls) == 1  # HTTP call was made


@pytest.mark.asyncio
async def test_cache_invalidation_on_repo_change(windows_platform, sample_releases, svc):
    """Test cache is bypassed when repo changes."""
    import json

    # Write cache with current settings
    cache_data = {
        "last_check": time.time() - 1800,  # 30 minutes ago, within expiry
        "releases": sample_releases,
        "etag": 'W/"test-etag"',
        "channel": svc.settings.channel,
        "owner": svc.owner,
        "repo": svc.repo,
    }
    svc.cache_path.write_text(json.dumps(cache_data), encoding="utf-8")

    # Change repo without calling save_settings() to avoid cache clearing
    svc.repo = svc.repo + "-changed"

    # Should make HTTP call and ignore cache due to repo mismatch
    client = QueueHttpClient(get_responses=[MockResponse(json_data=[])])
    svc.http_client = client

    await svc._get_releases()
    assert len(client._get_calls) == 1  # HTTP call was made


# -----------------------------
# Error handling tests for _get_releases()
# -----------------------------


class RaisingClient:
    """Mock client that raises specific exceptions."""

    def __init__(self, exception_to_raise):
        """Initialize raising client with the provided exception."""
        self.exception_to_raise = exception_to_raise

    async def get(self, url: str, headers: dict | None = None):
        raise self.exception_to_raise

    async def aclose(self):
        return None


@pytest.mark.asyncio
async def test_get_releases_rate_limit_fallback(sample_releases, svc):
    """Test rate limit fallback returns cached releases."""
    # Preload cache with sample releases
    svc._cache = {"releases": sample_releases}

    # Set up client to return 403 rate limit response
    client = QueueHttpClient(
        get_responses=[MockResponse(status_code=403, headers={"X-RateLimit-Reset": "123"})]
    )
    svc.http_client = client

    # Call _get_releases() and assert it returns cached releases
    releases = await svc._get_releases()
    assert releases == sample_releases


@pytest.mark.asyncio
async def test_get_releases_timeout_fallback(sample_releases, svc):
    """Test timeout fallback returns cached releases."""
    # Preload cache with sample releases
    svc._cache = {"releases": sample_releases}

    # Set up client that raises TimeoutException
    import httpx

    svc.http_client = RaisingClient(httpx.TimeoutException("timeout"))

    # Call _get_releases() and assert it returns cached releases
    releases = await svc._get_releases()
    assert releases == sample_releases


@pytest.mark.asyncio
async def test_get_releases_request_error_fallback(sample_releases, svc):
    """Test RequestError fallback returns cached releases if available, else empty list."""
    # Test with cache available
    svc._cache = {"releases": sample_releases}

    # Set up client that raises RequestError
    import httpx

    svc.http_client = RaisingClient(httpx.RequestError("boom"))

    # Call _get_releases() and assert it returns cached releases
    releases = await svc._get_releases()
    assert releases == sample_releases

    # Test without cache - should return empty list
    svc._cache = None
    releases = await svc._get_releases()
    assert releases == []


# -----------------------------
# Download tests with checksums
# -----------------------------


@pytest.mark.asyncio
async def test_legacy_download_success(windows_platform, svc, tmp_path):
    """Test legacy download_update with URL and dest_path using QueueHttpClient with MockStreamResponse."""
    # Create two chunks of data
    chunk1 = b"Hello, "
    chunk2 = b"World!"
    chunks = [chunk1, chunk2]
    total_size = len(chunk1) + len(chunk2)

    # Set up QueueHttpClient with MockStreamResponse
    client = QueueHttpClient(
        stream_resp=MockStreamResponse(headers={"content-length": str(total_size)}, chunks=chunks)
    )
    svc.http_client = client

    # Call legacy download_update with URL and dest_path
    dest_file = tmp_path / "file.bin"
    result = await svc.download_update("https://example.com/file.bin", dest_path=str(dest_file))

    # Assert returned value equals the string path
    assert result == str(dest_file)

    # Assert file exists and size matches sum of chunks
    assert dest_file.exists()
    assert dest_file.stat().st_size == total_size

    # Verify file content
    assert dest_file.read_bytes() == chunk1 + chunk2


@pytest.mark.asyncio
async def test_download_with_checksums_txt_success(windows_platform, svc, tmp_path):
    """Test download via UpdateInfo with checksums.txt verification success."""
    import hashlib

    # Create test data
    content = b"Test file content for checksum verification"
    sha256_hash = hashlib.sha256(content).hexdigest()

    # Set up QueueHttpClient with MockStreamResponse for download
    client = QueueHttpClient(
        stream_resp=MockStreamResponse(
            headers={"content-length": str(len(content))}, chunks=[content]
        )
    )

    # Create UpdateInfo
    info = UpdateInfo(
        version="1.0.0", download_url="https://example.com/file.exe", artifact_name="file.exe"
    )

    # After streaming completes, configure get_responses for checksums.txt
    checksums_content = f"{sha256_hash} file.exe\n"
    client._get_responses = [MockResponse(status_code=200, text=checksums_content)]

    svc.http_client = client

    # Call download_update with checksums_url
    result = await svc.download_update(info, checksums_url="https://example.com/checksums.txt")

    # Assert returns string path
    assert isinstance(result, str)

    # Assert file remains and exists
    file_path = Path(result)
    assert file_path.exists()
    assert file_path.read_bytes() == content


@pytest.mark.asyncio
async def test_download_with_checksums_txt_mismatch(windows_platform, svc, tmp_path):
    """Test download via UpdateInfo with checksums.txt verification failure."""
    import hashlib

    # Create test data
    content = b"Test file content for checksum verification"
    correct_sha256 = hashlib.sha256(content).hexdigest()
    wrong_sha256 = "0" * 64 if correct_sha256[0] != "0" else "f" * 64

    # Set up QueueHttpClient with MockStreamResponse for download
    client = QueueHttpClient(
        stream_resp=MockStreamResponse(
            headers={"content-length": str(len(content))}, chunks=[content]
        )
    )

    # Create UpdateInfo
    info = UpdateInfo(
        version="1.0.0", download_url="https://example.com/file.exe", artifact_name="file.exe"
    )

    # Configure get_responses with wrong checksum in checksums.txt
    checksums_content = f"{wrong_sha256} file.exe\n"
    client._get_responses = [MockResponse(status_code=200, text=checksums_content)]

    svc.http_client = client

    # Call download_update with checksums_url
    result = await svc.download_update(info, checksums_url="https://example.com/checksums.txt")

    # Assert the function returns False
    assert result is False

    # Assert the file under updates is removed
    updates_dir = Path(svc.config_dir) / "updates"
    files = list(updates_dir.glob("*.exe"))
    assert not files  # File should be removed due to checksum mismatch
