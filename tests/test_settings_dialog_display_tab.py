"""Tests for the Display tab in the settings dialog."""

import pytest
import wx

from accessiweather.gui.settings import DEFAULT_TEMPERATURE_UNIT, TEMPERATURE_UNIT_KEY
from accessiweather.gui.settings_dialog import SettingsDialog
from accessiweather.utils.temperature_utils import TemperatureUnit


class TestSettingsDialogDisplayTab:
    """Test the Display tab in the settings dialog."""

    @pytest.fixture
    def app(self):
        """Create a wx App for testing."""
        app = wx.App()
        yield app
        app.Destroy()

    @pytest.fixture
    def settings_dialog(self, app):
        """Create a settings dialog for testing."""
        parent = wx.Frame(None)
        current_settings = {
            TEMPERATURE_UNIT_KEY: DEFAULT_TEMPERATURE_UNIT,
        }
        dialog = SettingsDialog(parent, current_settings)
        yield dialog
        dialog.Destroy()
        parent.Destroy()

    def test_display_tab_exists(self, settings_dialog):
        """Test that the Display tab exists."""
        # Check that the notebook has at least 3 pages (General, Display, Advanced)
        assert settings_dialog.notebook.GetPageCount() >= 3

        # Check that one of the pages is named "Display"
        page_names = [
            settings_dialog.notebook.GetPageText(i)
            for i in range(settings_dialog.notebook.GetPageCount())
        ]
        assert "Display" in page_names

        # Get the index of the Display tab
        display_tab_index = page_names.index("Display")

        # Check that the Display tab has the measurement unit control
        display_panel = settings_dialog.notebook.GetPage(display_tab_index)
        temp_unit_ctrl = None
        for child in display_panel.GetChildren():
            if isinstance(child, wx.Choice) and child.GetName() == "Measurement Units":
                temp_unit_ctrl = child
                break

        assert temp_unit_ctrl is not None
        assert temp_unit_ctrl.GetCount() == 3
        assert temp_unit_ctrl.GetString(0) == "Imperial (Fahrenheit)"
        assert temp_unit_ctrl.GetString(1) == "Metric (Celsius)"
        assert temp_unit_ctrl.GetString(2) == "Both"

    def test_load_fahrenheit_setting(self, settings_dialog):
        """Test loading Fahrenheit temperature unit setting."""
        # Set the current settings to use Fahrenheit
        settings_dialog.current_settings[TEMPERATURE_UNIT_KEY] = TemperatureUnit.FAHRENHEIT.value

        # Load the settings
        settings_dialog.data_handler.load_settings(settings_dialog.current_settings)

        # Check that the temperature unit control is set to Fahrenheit
        assert settings_dialog.temp_unit_ctrl.GetSelection() == 0

    def test_load_celsius_setting(self, settings_dialog):
        """Test loading Celsius temperature unit setting."""
        # Set the current settings to use Celsius
        settings_dialog.current_settings[TEMPERATURE_UNIT_KEY] = TemperatureUnit.CELSIUS.value

        # Load the settings
        settings_dialog.data_handler.load_settings(settings_dialog.current_settings)

        # Check that the temperature unit control is set to Celsius
        assert settings_dialog.temp_unit_ctrl.GetSelection() == 1

    def test_load_both_setting(self, settings_dialog):
        """Test loading Both temperature unit setting."""
        # Set the current settings to use Both
        settings_dialog.current_settings[TEMPERATURE_UNIT_KEY] = TemperatureUnit.BOTH.value

        # Load the settings
        settings_dialog.data_handler.load_settings(settings_dialog.current_settings)

        # Check that the temperature unit control is set to Both
        assert settings_dialog.temp_unit_ctrl.GetSelection() == 2

    def test_get_settings_fahrenheit(self, settings_dialog):
        """Test getting Fahrenheit temperature unit setting."""
        # Set the temperature unit control to Fahrenheit
        settings_dialog.temp_unit_ctrl.SetSelection(0)

        # Get the settings
        settings = settings_dialog.get_settings()

        # Check that the temperature unit setting is Fahrenheit
        assert settings[TEMPERATURE_UNIT_KEY] == TemperatureUnit.FAHRENHEIT.value

    def test_get_settings_celsius(self, settings_dialog):
        """Test getting Celsius temperature unit setting."""
        # Set the temperature unit control to Celsius
        settings_dialog.temp_unit_ctrl.SetSelection(1)

        # Get the settings
        settings = settings_dialog.get_settings()

        # Check that the temperature unit setting is Celsius
        assert settings[TEMPERATURE_UNIT_KEY] == TemperatureUnit.CELSIUS.value

    def test_get_settings_both(self, settings_dialog):
        """Test getting Both temperature unit setting."""
        # Set the temperature unit control to Both
        settings_dialog.temp_unit_ctrl.SetSelection(2)

        # Get the settings
        settings = settings_dialog.get_settings()

        # Check that the temperature unit setting is Both
        assert settings[TEMPERATURE_UNIT_KEY] == TemperatureUnit.BOTH.value
