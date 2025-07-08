"""Toga-compatible integration tests for update service logic (UI-free)."""

import unittest
from unittest.mock import Mock
from accessiweather.services.update_service import UpdateInfo, UpdateService

class TestUpdateServiceLogic(unittest.TestCase):
    def setUp(self):
        self.update_service = UpdateService(
            config_dir="/tmp", notification_callback=Mock(), progress_callback=Mock()
        )
        self.update_info = UpdateInfo(
            version="1.0.0",
            release_url="https://github.com/Orinks/AccessiWeather/releases/tag/v1.0.0",
            release_notes="Test release with new features and bug fixes.",
            assets=[],
            published_date="2024-01-01T00:00:00Z",
            is_prerelease=False,
        )

    def test_update_info_fields(self):
        self.assertEqual(self.update_info.version, "1.0.0")
        self.assertIn("github.com", self.update_info.release_url)
        self.assertTrue(isinstance(self.update_info.release_notes, str))
        self.assertEqual(self.update_info.assets, [])
        self.assertFalse(self.update_info.is_prerelease)

    def test_update_service_initialization(self):
        self.assertIsNotNone(self.update_service)
        self.assertTrue(hasattr(self.update_service, "check_for_updates"))


if __name__ == "__main__":
    unittest.main()
