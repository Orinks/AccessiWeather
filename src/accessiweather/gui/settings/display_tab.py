"""Display settings tab for the settings dialog."""

import logging

import wx

from accessiweather.format_string_parser import FormatStringParser
from accessiweather.utils.temperature_utils import TemperatureUnit

from .constants import (
    DEFAULT_TEMPERATURE_UNIT,
    TASKBAR_ICON_DYNAMIC_ENABLED_KEY,
    TASKBAR_ICON_TEXT_ENABLED_KEY,
    TASKBAR_ICON_TEXT_FORMAT_KEY,
    TEMPERATURE_UNIT_KEY,
)

logger = logging.getLogger(__name__)


class DisplayTab:
    """Handles the Display tab of the settings dialog."""

    def __init__(self, parent_panel):
        """Initialize the Display tab.

        Args:
            parent_panel: The parent panel for this tab
        """
        self.panel = parent_panel
        self._init_ui()

    def _init_ui(self):
        """Initialize the Display tab controls."""
        sizer = wx.BoxSizer(wx.VERTICAL)

        # --- Input Fields ---
        grid_sizer = wx.FlexGridSizer(rows=4, cols=2, vgap=10, hgap=5)
        grid_sizer.AddGrowableCol(1, 1)  # Make the input column growable

        # Measurement Unit System Selection
        temp_unit_label = wx.StaticText(self.panel, label="Measurement Units:")
        from ..ui_components import AccessibleChoice

        self.temp_unit_ctrl = AccessibleChoice(
            self.panel,
            choices=["Imperial (Fahrenheit)", "Metric (Celsius)", "Both"],
            label="Measurement Units",
        )
        tooltip_temp_unit = (
            "Select your preferred measurement unit system. "
            "Affects temperature, pressure, wind speed, and other measurements. "
            "'Both' will show temperatures in both Fahrenheit and Celsius."
        )
        self.temp_unit_ctrl.SetToolTip(tooltip_temp_unit)
        grid_sizer.Add(temp_unit_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        grid_sizer.Add(self.temp_unit_ctrl, 0, wx.EXPAND | wx.ALL, 5)

        # Taskbar Icon Text Toggle
        taskbar_text_label = "Show weather information in taskbar icon"
        self.taskbar_text_ctrl = wx.CheckBox(
            self.panel, label=taskbar_text_label, name="Taskbar Icon Text"
        )
        tooltip_taskbar = (
            "When checked, the taskbar icon will display weather information "
            "according to the format string below."
        )
        self.taskbar_text_ctrl.SetToolTip(tooltip_taskbar)
        grid_sizer.Add((1, 1), 0, wx.ALL, 5)  # Empty cell for alignment
        grid_sizer.Add(self.taskbar_text_ctrl, 0, wx.ALL, 5)

        # Dynamic Format Switching Toggle
        dynamic_format_label = "Enable dynamic format switching"
        self.dynamic_format_ctrl = wx.CheckBox(
            self.panel, label=dynamic_format_label, name="Dynamic Format Switching"
        )
        tooltip_dynamic = (
            "When ENABLED: Format automatically changes for severe weather and alerts "
            "(e.g., '⚠️ Tornado Warning: Severe'). "
            "When DISABLED: Your custom format below is always used, regardless of conditions."
        )
        self.dynamic_format_ctrl.SetToolTip(tooltip_dynamic)
        grid_sizer.Add((1, 1), 0, wx.ALL, 5)  # Empty cell for alignment
        grid_sizer.Add(self.dynamic_format_ctrl, 0, wx.ALL, 5)

        # Taskbar Icon Text Format
        taskbar_format_label = wx.StaticText(self.panel, label="Taskbar Icon Text Format:")
        self.taskbar_format_ctrl = wx.TextCtrl(self.panel, name="Taskbar Format")
        tooltip_format = (
            "Enter your preferred format with placeholders like {temp}, {condition}, etc. "
            "When dynamic switching is OFF, this format is always used. "
            "When dynamic switching is ON, this serves as the default format for normal conditions "
            "and as a fallback for severe weather/alerts."
        )
        self.taskbar_format_ctrl.SetToolTip(tooltip_format)
        grid_sizer.Add(taskbar_format_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        grid_sizer.Add(self.taskbar_format_ctrl, 1, wx.EXPAND | wx.ALL, 5)

        # Add the grid sizer to the main sizer
        sizer.Add(grid_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # Add help text for placeholders
        help_label = wx.StaticText(self.panel, label="Available Placeholders:")
        sizer.Add(help_label, 0, wx.LEFT | wx.TOP, 15)

        # Create a read-only text control for the placeholder help
        self.placeholder_help_ctrl = wx.TextCtrl(
            self.panel,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_DONTWRAP,
            size=(-1, 150),
            name="Placeholder Help",
        )

        # Get the help text from the FormatStringParser
        help_text = FormatStringParser.get_supported_placeholders_help()
        self.placeholder_help_ctrl.SetValue(help_text)

        # Add the help text control to the sizer
        sizer.Add(self.placeholder_help_ctrl, 1, wx.EXPAND | wx.ALL, 10)

        # Set the sizer for the panel
        self.panel.SetSizer(sizer)

        # Bind events
        self.taskbar_text_ctrl.Bind(wx.EVT_CHECKBOX, self._on_taskbar_text_toggle)

    def _on_taskbar_text_toggle(self, event):
        """Handle taskbar text toggle checkbox."""
        enabled = self.taskbar_text_ctrl.GetValue()
        self.taskbar_format_ctrl.Enable(enabled)
        self.dynamic_format_ctrl.Enable(enabled)

    def load_settings(self, settings):
        """Load settings into the controls.

        Args:
            settings: Dictionary containing current settings
        """
        # Load display settings
        taskbar_text_enabled = settings.get(TASKBAR_ICON_TEXT_ENABLED_KEY, False)
        taskbar_text_format = settings.get(TASKBAR_ICON_TEXT_FORMAT_KEY, "{temp} {condition}")
        taskbar_dynamic_enabled = settings.get(TASKBAR_ICON_DYNAMIC_ENABLED_KEY, True)

        self.taskbar_text_ctrl.SetValue(taskbar_text_enabled)
        self.taskbar_format_ctrl.SetValue(taskbar_text_format)
        self.dynamic_format_ctrl.SetValue(taskbar_dynamic_enabled)
        self.taskbar_format_ctrl.Enable(taskbar_text_enabled)
        self.dynamic_format_ctrl.Enable(taskbar_text_enabled)

        # Load temperature unit setting
        temperature_unit = settings.get(TEMPERATURE_UNIT_KEY, DEFAULT_TEMPERATURE_UNIT)
        # Set temperature unit dropdown
        if temperature_unit == TemperatureUnit.FAHRENHEIT.value:
            self.temp_unit_ctrl.SetSelection(0)  # Imperial (Fahrenheit)
        elif temperature_unit == TemperatureUnit.CELSIUS.value:
            self.temp_unit_ctrl.SetSelection(1)  # Metric (Celsius)
        elif temperature_unit == TemperatureUnit.BOTH.value:
            self.temp_unit_ctrl.SetSelection(2)  # Both
        else:
            # Default to Fahrenheit for unknown values
            self.temp_unit_ctrl.SetSelection(0)

    def get_settings(self):
        """Get settings from the controls.

        Returns:
            Dictionary containing the settings from this tab
        """
        # Get temperature unit selection
        temp_unit_idx = self.temp_unit_ctrl.GetSelection()
        if temp_unit_idx == 0:
            temperature_unit = TemperatureUnit.FAHRENHEIT.value
        elif temp_unit_idx == 1:
            temperature_unit = TemperatureUnit.CELSIUS.value
        elif temp_unit_idx == 2:
            temperature_unit = TemperatureUnit.BOTH.value
        else:
            temperature_unit = DEFAULT_TEMPERATURE_UNIT

        # Validate taskbar format string if enabled
        taskbar_text_enabled = self.taskbar_text_ctrl.GetValue()
        taskbar_text_format = self.taskbar_format_ctrl.GetValue()
        taskbar_dynamic_enabled = self.dynamic_format_ctrl.GetValue()

        if taskbar_text_enabled and taskbar_text_format:
            # Validate the format string
            parser = FormatStringParser()
            is_valid, error = parser.validate_format_string(taskbar_text_format)
            if not is_valid:
                # If invalid, log the error but still save (will use default format)
                logger.warning(f"Invalid taskbar format string: {error}")
                # We could show a message box here, but for now we'll just log it

        return {
            TEMPERATURE_UNIT_KEY: temperature_unit,
            TASKBAR_ICON_TEXT_ENABLED_KEY: taskbar_text_enabled,
            TASKBAR_ICON_TEXT_FORMAT_KEY: taskbar_text_format,
            TASKBAR_ICON_DYNAMIC_ENABLED_KEY: taskbar_dynamic_enabled,
        }

    def validate(self):
        """Validate the settings in this tab.

        Returns:
            Tuple of (is_valid, error_message, focus_control)
        """
        # No validation needed for display tab currently
        return True, None, None
