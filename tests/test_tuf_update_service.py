"""Unit tests for TUF update service."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import httpx
import pytest

from accessiweather.services.tuf_update_service import (
    TUFUpdateService,
    UpdateInfo,
    UpdateSettings,
)


@pytest.fixture
def temp_config_dir():
    """Create a temporary configuration directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def update_service(temp_config_dir):
    """Create an update service instance with temp config."""
    return TUFUpdateService(app_name="TestApp", config_dir=temp_config_dir)


@pytest.fixture
def mock_github_response():
    """Mock GitHub API response for releases."""
    return [
        {
            "tag_name": "v2.0.0",
            "name": "Version 2.0.0",
            "body": "New features and bug fixes",
            "prerelease": False,
            "assets": [
                {
                    "name": "TestApp-2.0.0-windows-x64.exe",
                    "browser_download_url": "https://github.com/test/repo/releases/download/v2.0.0/TestApp-2.0.0-windows-x64.exe",
                    "size": 1024000,
                }
            ],
        },
        {
            "tag_name": "v2.0.0-beta.1",
            "name": "Version 2.0.0 Beta 1",
            "body": "Beta release",
            "prerelease": True,
            "assets": [
                {
                    "name": "TestApp-2.0.0-beta.1-windows-x64.exe",
                    "browser_download_url": "https://github.com/test/repo/releases/download/v2.0.0-beta.1/TestApp-2.0.0-beta.1-windows-x64.exe",
                    "size": 1024000,
                }
            ],
        },
    ]


class TestTUFUpdateService:
    """Test the TUF update service."""

    def test_initialize_service_with_defaults(self, temp_config_dir):
        """Test service initialization with default settings."""
        service = TUFUpdateService(app_name="TestApp", config_dir=temp_config_dir)

        assert service.app_name == "TestApp"
        assert service.config_dir == temp_config_dir
        assert isinstance(service.settings, UpdateSettings)
        assert service.settings.method in ["github", "tuf"]  # Depends on TUF availability
        assert service.settings.channel == "stable"
        assert service.settings.auto_check is True
        assert service.settings.check_interval_hours == 24

        # Check that settings file was created
        assert service.settings_file.exists()

    def test_save_and_load_settings(self, update_service, temp_config_dir):
        """Test saving and loading settings from file."""
        # Update settings
        update_service.update_settings(
            method="github", channel="beta", auto_check=False, check_interval_hours=12
        )

        # Create new service instance to test loading
        new_service = TUFUpdateService(app_name="TestApp", config_dir=temp_config_dir)

        assert new_service.settings.method == "github"
        assert new_service.settings.channel == "beta"
        assert new_service.settings.auto_check is False
        assert new_service.settings.check_interval_hours == 12

    def test_handle_invalid_settings_file(self, temp_config_dir):
        """Test handling of corrupted/invalid settings file."""
        # Create invalid JSON file
        settings_file = temp_config_dir / "update_settings.json"
        settings_file.write_text("invalid json content")

        # Service should still initialize with defaults
        service = TUFUpdateService(app_name="TestApp", config_dir=temp_config_dir)

        assert isinstance(service.settings, UpdateSettings)
        assert service.settings.method in ["github", "tuf"]

    @pytest.mark.asyncio
    async def test_check_github_updates_successfully(self, update_service, mock_github_response):
        """Test successful GitHub update check."""
        mock_response = MagicMock()
        mock_response.json.return_value = mock_github_response
        mock_response.raise_for_status = MagicMock()

        with patch.object(update_service._http_client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            update_info = await update_service.check_for_updates(method="github")

            assert update_info is not None
            assert update_info.version == "2.0.0"
            assert "windows" in update_info.artifact_name.lower()
            assert update_info.download_url.startswith("https://github.com")
            assert update_info.is_prerelease is False

    @pytest.mark.asyncio
    async def test_check_github_updates_beta_channel(self, update_service, mock_github_response):
        """Test GitHub update check for beta channel."""
        update_service.update_settings(channel="beta")

        mock_response = MagicMock()
        mock_response.json.return_value = mock_github_response
        mock_response.raise_for_status = MagicMock()

        with patch.object(update_service._http_client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            update_info = await update_service.check_for_updates(method="github")

            assert update_info is not None
            assert "beta" in update_info.version
            assert update_info.is_prerelease is True

    @pytest.mark.asyncio
    async def test_handle_github_api_errors(self, update_service):
        """Test handling of GitHub API errors."""
        with patch.object(update_service._http_client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.HTTPStatusError(
                "API Error", request=MagicMock(), response=MagicMock()
            )

            update_info = await update_service.check_for_updates(method="github")

            assert update_info is None

    def test_filter_platform_specific_assets(self, update_service):
        """Test filtering assets based on current platform."""
        assets = [
            {"name": "app-linux.tar.gz"},
            {"name": "app-windows.exe"},
            {"name": "app-macos.dmg"},
        ]

        with patch("platform.system") as mock_system:
            # Test Windows
            mock_system.return_value = "Windows"
            asset = update_service._find_platform_asset(assets)
            assert "windows" in asset["name"].lower()

            # Test Linux
            mock_system.return_value = "Linux"
            asset = update_service._find_platform_asset(assets)
            assert "linux" in asset["name"].lower()

            # Test macOS
            mock_system.return_value = "Darwin"
            asset = update_service._find_platform_asset(assets)
            assert "macos" in asset["name"].lower()

    @pytest.mark.asyncio
    async def test_download_update_successfully(self, update_service, temp_config_dir):
        """Test successful update download."""
        update_info = UpdateInfo(
            version="2.0.0",
            download_url="https://example.com/update.exe",
            artifact_name="update.exe",
            release_notes="Test update",
        )

        # Mock response for download
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        # Properly mock the async iteration
        async def mock_aiter_bytes():
            for chunk in [b"test data chunk 1", b"test data chunk 2"]:
                yield chunk

        mock_response.aiter_bytes.return_value = mock_aiter_bytes()

        with (
            patch.object(update_service._http_client, "stream") as mock_stream,
            patch("builtins.open", mock_open()) as mock_file,
        ):
            mock_stream.return_value.__aenter__.return_value = mock_response

            downloaded_path = await update_service.download_update(update_info)

            assert downloaded_path is not None
            assert "update.exe" in str(downloaded_path)
            mock_file.assert_called()

    @pytest.mark.asyncio
    async def test_handle_download_failures(self, update_service):
        """Test handling of download failures."""
        update_info = UpdateInfo(
            version="2.0.0",
            download_url="https://example.com/update.exe",
            artifact_name="update.exe",
            release_notes="Test update",
        )

        with patch.object(
            update_service._http_client, "stream", new_callable=AsyncMock
        ) as mock_stream:
            mock_stream.side_effect = httpx.HTTPStatusError(
                "Download Error", request=MagicMock(), response=MagicMock()
            )

            downloaded_path = await update_service.download_update(update_info)

            assert downloaded_path is None

    def test_get_settings_dict(self, update_service):
        """Test getting settings as dictionary."""
        settings_dict = update_service.get_settings_dict()

        assert "method" in settings_dict
        assert "channel" in settings_dict
        assert "auto_check" in settings_dict
        assert "check_interval_hours" in settings_dict
        assert "tuf_available" in settings_dict
        assert "platform" in settings_dict

        platform_info = settings_dict["platform"]
        assert "system" in platform_info
        assert "machine" in platform_info
        assert "python_version" in platform_info

    def test_tuf_available_property(self, update_service):
        """Test TUF availability property."""
        # The property should reflect the global TUF_AVAILABLE constant
        from accessiweather.services.tuf_update_service import TUF_AVAILABLE

        assert update_service.tuf_available == TUF_AVAILABLE

    def test_current_method_property(self, update_service):
        """Test current method property."""
        assert update_service.current_method == update_service.settings.method

        # Update method and test again
        update_service.update_settings(method="github")
        assert update_service.current_method == "github"

    @pytest.mark.asyncio
    async def test_cleanup(self, update_service):
        """Test service cleanup."""
        with patch.object(
            update_service._http_client, "aclose", new_callable=AsyncMock
        ) as mock_aclose:
            await update_service.cleanup()
            mock_aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_updates_available(self, update_service):
        """Test when no updates are available."""
        mock_response = MagicMock()
        mock_response.json.return_value = []  # Empty releases list
        mock_response.raise_for_status = MagicMock()

        with patch.object(update_service._http_client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            update_info = await update_service.check_for_updates(method="github")

            assert update_info is None

    @pytest.mark.asyncio
    async def test_auto_method_selection(self, update_service):
        """Test automatic method selection based on channel."""
        update_service.update_settings(method="auto", channel="stable")

        # Mock TUF availability check
        with (
            patch("accessiweather.services.tuf_update_service.TUF_AVAILABLE", True),
            patch.object(update_service, "_check_tuf_updates", new_callable=AsyncMock) as mock_tuf,
        ):
            mock_tuf.return_value = None

            await update_service.check_for_updates()
            mock_tuf.assert_called_once()

    @pytest.mark.asyncio
    async def test_github_fallback_when_tuf_unavailable(self, update_service):
        """Test fallback to GitHub when TUF is unavailable."""
        update_service.update_settings(method="tuf")

        # Mock TUF as unavailable
        with (
            patch("accessiweather.services.tuf_update_service.TUF_AVAILABLE", False),
            patch.object(
                update_service, "_check_github_updates", new_callable=AsyncMock
            ) as mock_github,
        ):
            mock_github.return_value = None

            await update_service.check_for_updates()
            mock_github.assert_called_once()


class TestUpdateInfo:
    """Test the UpdateInfo dataclass."""

    def test_create_update_info(self):
        """Test creating UpdateInfo instance."""
        info = UpdateInfo(
            version="1.0.0",
            download_url="https://example.com/app.exe",
            artifact_name="app.exe",
            release_notes="Test release",
        )

        assert info.version == "1.0.0"
        assert info.download_url == "https://example.com/app.exe"
        assert info.artifact_name == "app.exe"
        assert info.release_notes == "Test release"
        assert info.is_prerelease is False
        assert info.file_size is None
        assert info.checksum is None

    def test_update_info_with_all_fields(self):
        """Test UpdateInfo with all fields."""
        info = UpdateInfo(
            version="2.0.0-beta.1",
            download_url="https://example.com/app-beta.exe",
            artifact_name="app-beta.exe",
            release_notes="Beta release",
            is_prerelease=True,
            file_size=2048000,
            checksum="abc123def456",
        )

        assert info.version == "2.0.0-beta.1"
        assert info.is_prerelease is True
        assert info.file_size == 2048000
        assert info.checksum == "abc123def456"


class TestUpdateSettings:
    """Test the UpdateSettings dataclass."""

    def test_default_settings(self):
        """Test default UpdateSettings values."""
        settings = UpdateSettings()

        assert settings.method == "github"
        assert settings.channel == "stable"
        assert settings.auto_check is True
        assert settings.check_interval_hours == 24
        assert settings.repo_owner == "joshuakitchen"
        assert settings.repo_name == "accessiweather"
        assert settings.tuf_repo_url == "https://updates.accessiweather.app"

    def test_custom_settings(self):
        """Test UpdateSettings with custom values."""
        settings = UpdateSettings(
            method="tuf",
            channel="beta",
            auto_check=False,
            check_interval_hours=12,
            repo_owner="custom_owner",
            repo_name="custom_repo",
            tuf_repo_url="https://custom.updates.com",
        )

        assert settings.method == "tuf"
        assert settings.channel == "beta"
        assert settings.auto_check is False
        assert settings.check_interval_hours == 12
        assert settings.repo_owner == "custom_owner"
        assert settings.repo_name == "custom_repo"
        assert settings.tuf_repo_url == "https://custom.updates.com"
