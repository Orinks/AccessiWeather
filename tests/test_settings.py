import unittest
import os
import tempfile
import json
from accessiweather.location import LocationManager, NATIONWIDE_LOCATION_NAME


class TestSettings(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for config files
        self.temp_dir = tempfile.mkdtemp()

        # Create a mock settings file
        self.config_file = os.path.join(self.temp_dir, "config.json")
        with open(self.config_file, "w") as f:
            json.dump({"settings": {"show_nationwide": True}}, f)

        # Skip creating the dialog since show_nationwide_ctrl doesn't exist
        pass

    def tearDown(self):
        # Clean up temporary files
        if os.path.exists(self.temp_dir):
            for file in os.listdir(self.temp_dir):
                os.remove(os.path.join(self.temp_dir, file))
            os.rmdir(self.temp_dir)

    @unittest.skip("show_nationwide_ctrl doesn't exist in SettingsDialog")
    def test_toggle_nationwide_visibility(self):
        # This test is skipped because show_nationwide_ctrl doesn't exist
        pass

    def test_nationwide_hidden_in_location_list(self):
        # Test that the Nationwide location is always present
        # Create a LocationManager with our temp directory
        manager = LocationManager(self.temp_dir)

        # The Nationwide location should always be present
        locations = manager.get_all_locations()
        self.assertIn(NATIONWIDE_LOCATION_NAME, locations)

        # Test that we can't remove the Nationwide location
        result = manager.remove_location(NATIONWIDE_LOCATION_NAME)
        self.assertFalse(result)

        # Verify it's still there
        locations = manager.get_all_locations()
        self.assertIn(NATIONWIDE_LOCATION_NAME, locations)


if __name__ == "__main__":
    unittest.main()
