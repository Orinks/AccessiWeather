"""Tests for the update service."""

import tempfile
import unittest
from unittest.mock import Mock, patch

from accessiweather.services.update_service import UpdateInfo, UpdateService


class TestUpdateService(unittest.TestCase):
    """Test cases for UpdateService."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.notification_callback = Mock()
        self.progress_callback = Mock()

        self.update_service = UpdateService(
            config_dir=self.temp_dir,
            notification_callback=self.notification_callback,
            progress_callback=self.progress_callback,
        )

    def tearDown(self):
        """Clean up test fixtures."""
        # Stop background checking
        self.update_service.stop_background_checking()

        # Clean up temp directory
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_parse_version(self):
        """Test version parsing functionality."""
        # Test stable versions
        parts, is_dev = self.update_service._parse_version("0.9.3")
        self.assertEqual(parts, [0, 9, 3])
        self.assertFalse(is_dev)

        parts, is_dev = self.update_service._parse_version("v1.0.0")
        self.assertEqual(parts, [1, 0, 0])
        self.assertFalse(is_dev)

        # Test dev versions
        parts, is_dev = self.update_service._parse_version("0.9.4-dev")
        self.assertEqual(parts, [0, 9, 4])
        self.assertTrue(is_dev)

        parts, is_dev = self.update_service._parse_version("v1.0.0-dev")
        self.assertEqual(parts, [1, 0, 0])
        self.assertTrue(is_dev)

    def test_is_newer_version(self):
        """Test version comparison logic."""
        # Test stable channel
        self.assertTrue(self.update_service._is_newer_version("0.9.3", "0.9.4", "stable"))
        self.assertFalse(self.update_service._is_newer_version("0.9.4", "0.9.3", "stable"))
        self.assertFalse(self.update_service._is_newer_version("0.9.3", "0.9.4-dev", "stable"))

        # Test dev channel
        self.assertTrue(self.update_service._is_newer_version("0.9.3", "0.9.4-dev", "dev"))
        self.assertTrue(self.update_service._is_newer_version("0.9.3", "0.9.4", "dev"))
        self.assertTrue(self.update_service._is_newer_version("0.9.3", "0.9.3-dev", "dev"))

    def test_update_state_persistence(self):
        """Test that update state is saved and loaded correctly."""
        # Modify state
        self.update_service.update_state["test_key"] = "test_value"
        self.update_service._save_update_state()

        # Create new service instance
        new_service = UpdateService(config_dir=self.temp_dir)

        # Check that state was loaded
        self.assertEqual(new_service.update_state["test_key"], "test_value")

    def test_should_check_for_updates(self):
        """Test update check timing logic."""
        # Auto check disabled
        self.update_service.update_state["auto_check_enabled"] = False
        self.assertFalse(self.update_service.should_check_for_updates())

        # Auto check enabled, no previous check
        self.update_service.update_state["auto_check_enabled"] = True
        self.update_service.update_state["last_check"] = None
        self.assertTrue(self.update_service.should_check_for_updates())

    @patch("accessiweather.services.update_service.requests.get")
    def test_check_for_updates_success(self, mock_get):
        """Test successful update check."""
        # Mock API response
        mock_response = Mock()
        mock_response.json.return_value = [
            {
                "tag_name": "v0.9.5",
                "html_url": "https://github.com/Orinks/AccessiWeather/releases/tag/v0.9.5",
                "body": "New features and bug fixes",
                "assets": [
                    {
                        "name": "AccessiWeather-0.9.5-Setup.exe",
                        "browser_download_url": "https://github.com/Orinks/AccessiWeather/releases/download/v0.9.5/AccessiWeather-0.9.5-Setup.exe",
                    }
                ],
                "published_at": "2024-01-01T00:00:00Z",
                "prerelease": False,
                "draft": False,
            }
        ]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Mock current version to be older
        with patch("accessiweather.services.update_service.__version__", "0.9.4"):
            update_info = self.update_service.check_for_updates("stable")

        self.assertIsNotNone(update_info)
        self.assertEqual(update_info.version, "0.9.5")
        self.assertIsNotNone(update_info.installer_asset)

    @patch("accessiweather.services.update_service.requests.get")
    def test_check_for_updates_no_update(self, mock_get):
        """Test update check when no update is available."""
        # Mock API response with older version
        mock_response = Mock()
        mock_response.json.return_value = [
            {
                "tag_name": "v0.9.3",
                "html_url": "https://github.com/Orinks/AccessiWeather/releases/tag/v0.9.3",
                "body": "Old release",
                "assets": [],
                "published_at": "2024-01-01T00:00:00Z",
                "prerelease": False,
                "draft": False,
            }
        ]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Mock current version to be newer
        with patch("accessiweather.services.update_service.__version__", "0.9.4"):
            update_info = self.update_service.check_for_updates("stable")

        self.assertIsNone(update_info)

    @patch("accessiweather.services.update_service.requests.get")
    def test_check_for_updates_api_error(self, mock_get):
        """Test update check when API request fails."""
        mock_get.side_effect = Exception("Network error")

        update_info = self.update_service.check_for_updates("stable")
        self.assertIsNone(update_info)

    def test_update_settings(self):
        """Test updating service settings."""
        new_settings = {
            "auto_check_enabled": False,
            "check_interval_hours": 48,
            "update_channel": "dev",
            "auto_install_enabled": True,
        }

        self.update_service.update_settings(new_settings)

        # Check that settings were updated
        for key, value in new_settings.items():
            self.assertEqual(self.update_service.update_state[key], value)

    def test_update_info_asset_parsing(self):
        """Test UpdateInfo asset parsing."""
        assets = [
            {
                "name": "AccessiWeather-0.9.5-Setup.exe",
                "browser_download_url": "https://example.com/setup.exe",
            },
            {
                "name": "AccessiWeather-0.9.5-Portable.zip",
                "browser_download_url": "https://example.com/portable.zip",
            },
            {"name": "other-file.txt", "browser_download_url": "https://example.com/other.txt"},
        ]

        update_info = UpdateInfo(
            version="0.9.5",
            release_url="https://example.com/release",
            release_notes="Test release",
            assets=assets,
            published_date="2024-01-01T00:00:00Z",
        )

        # Check that assets were parsed correctly
        self.assertIsNotNone(update_info.installer_asset)
        self.assertEqual(update_info.installer_asset["name"], "AccessiWeather-0.9.5-Setup.exe")

        self.assertIsNotNone(update_info.portable_asset)
        self.assertEqual(update_info.portable_asset["name"], "AccessiWeather-0.9.5-Portable.zip")


class TestUpdateInfo(unittest.TestCase):
    """Test cases for UpdateInfo."""

    def test_update_info_creation(self):
        """Test UpdateInfo object creation."""
        assets = [
            {
                "name": "AccessiWeather-Setup.exe",
                "browser_download_url": "https://example.com/setup.exe",
            }
        ]

        update_info = UpdateInfo(
            version="1.0.0",
            release_url="https://example.com/release",
            release_notes="Test release notes",
            assets=assets,
            published_date="2024-01-01T00:00:00Z",
            is_prerelease=False,
        )

        self.assertEqual(update_info.version, "1.0.0")
        self.assertEqual(update_info.release_url, "https://example.com/release")
        self.assertEqual(update_info.release_notes, "Test release notes")
        self.assertEqual(len(update_info.assets), 1)
        self.assertFalse(update_info.is_prerelease)


if __name__ == "__main__":
    unittest.main()
