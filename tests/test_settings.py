import unittest
from accessiweather.gui.settings_dialog import SettingsDialog

class TestSettings(unittest.TestCase):
    def setUp(self):
        # If qtbot is required, this will need to be handled by pytest-qt or similar
        # For now, instantiate dialog directly
        self.dialog = SettingsDialog(None, {'show_nationwide': True})

    def tearDown(self):
        self.dialog.Destroy()

    def test_toggle_nationwide_visibility(self):
        # Simulate user toggling the checkbox
        self.dialog.show_nationwide_ctrl.SetValue(False)
        settings = self.dialog.get_settings()
        self.assertFalse(settings['show_nationwide'])
        self.dialog.show_nationwide_ctrl.SetValue(True)
        settings = self.dialog.get_settings()
        self.assertTrue(settings['show_nationwide'])

    def test_nationwide_hidden_in_location_list(self):
        from accessiweather.location import LocationManager
        config = {'settings': {'show_nationwide': False}}
        manager = LocationManager(config)
        locations = manager.get_all_locations()
        self.assertNotIn('Nationwide', locations)
        config['settings']['show_nationwide'] = True
        locations = manager.get_all_locations()
        self.assertIn('Nationwide', locations)

if __name__ == "__main__":
    unittest.main()
