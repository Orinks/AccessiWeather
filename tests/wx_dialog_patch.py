"""Utilities for patching wxPython dialogs to prevent segmentation faults.

This module provides utilities for patching wxPython dialogs to prevent
segmentation faults during testing.
"""

import logging
import os
from unittest.mock import MagicMock, patch

import wx

logger = logging.getLogger(__name__)


def is_testing_environment():
    """Check if we're running in a testing environment.

    Returns:
        bool: True if we're running in a testing environment, False otherwise.
    """
    return os.environ.get("ACCESSIWEATHER_TESTING", "0") == "1"


class SafeMessageDialog:
    """A safe replacement for wx.MessageDialog that doesn't cause segmentation faults."""

    def __init__(self, parent, message, caption="Message", style=wx.OK):
        """Initialize the safe message dialog.

        Args:
            parent: Parent window
            message: Dialog message
            caption: Dialog caption
            style: Dialog style
        """
        self.parent = parent
        self.message = message
        self.caption = caption
        self.style = style
        logger.debug(f"SafeMessageDialog created: {message}")

    def ShowModal(self):
        """Show the dialog modally.

        Returns:
            int: wx.ID_OK
        """
        logger.debug(f"SafeMessageDialog.ShowModal called: {self.message}")
        # Always return OK in testing environment
        return wx.ID_OK

    def Destroy(self):
        """Destroy the dialog."""
        logger.debug("SafeMessageDialog.Destroy called")
        # No-op in testing environment


class SafeSettingsDialog:
    """A safe replacement for SettingsDialog that doesn't cause segmentation faults."""

    def __init__(self, parent, current_settings):
        """Initialize the safe settings dialog.

        Args:
            parent: Parent window
            current_settings: Current settings
        """
        self.parent = parent
        self.current_settings = current_settings
        logger.debug(f"SafeSettingsDialog created: {current_settings}")

        # Create mock controls that mimic the real SettingsDialog
        self.api_contact_ctrl = self._create_mock_control(
            current_settings.get("api_contact", "")
        )
        self.update_interval_ctrl = self._create_mock_control(
            current_settings.get("update_interval_minutes", 30)
        )
        self.alert_radius_ctrl = self._create_mock_control(
            current_settings.get("alert_radius_miles", 25)
        )
        self.precise_location_alerts_ctrl = self._create_mock_control(
            current_settings.get("precise_location_alerts", True)
        )

    def ShowModal(self):
        """Show the dialog modally.

        Returns:
            int: wx.ID_OK
        """
        logger.debug("SafeSettingsDialog.ShowModal called")
        # Always return OK in testing environment
        return wx.ID_OK

    def Destroy(self):
        """Destroy the dialog."""
        logger.debug("SafeSettingsDialog.Destroy called")
        # No-op in testing environment

    def _create_mock_control(self, initial_value):
        """Create a mock control with GetValue and SetValue methods.

        Args:
            initial_value: Initial value for the control

        Returns:
            MagicMock: Mock control
        """
        mock_control = MagicMock()
        mock_control._value = initial_value

        # Define GetValue method
        def get_value():
            return mock_control._value
        mock_control.GetValue = get_value

        # Define SetValue method
        def set_value(value):
            mock_control._value = value
        mock_control.SetValue = set_value

        return mock_control

    def get_settings(self):
        """Get the settings from the dialog.

        Returns:
            dict: Settings dictionary
        """
        logger.debug("SafeSettingsDialog.get_settings called")
        # Return the current settings with updated values from controls
        return {
            "api_contact": self.api_contact_ctrl.GetValue(),
            "update_interval_minutes": self.update_interval_ctrl.GetValue(),
            "alert_radius_miles": self.alert_radius_ctrl.GetValue(),
            "precise_location_alerts": self.precise_location_alerts_ctrl.GetValue(),
        }

    def get_api_settings(self):
        """Get the API settings from the dialog.

        Returns:
            dict: API settings dictionary
        """
        logger.debug("SafeSettingsDialog.get_api_settings called")
        # Return API settings with api_contact set
        return {
            "api_contact": self.api_contact_ctrl.GetValue(),
            "precise_location_alerts": self.precise_location_alerts_ctrl.GetValue(),
        }


def patch_wx_dialogs():
    """Patch wxPython dialogs to prevent segmentation faults.

    This function patches wx.MessageDialog and SettingsDialog to use safe
    replacements that don't cause segmentation faults.

    Returns:
        list: List of patches that were applied
    """
    if not is_testing_environment():
        logger.debug("Not patching wxPython dialogs (not in testing environment)")
        return []

    logger.info("Patching wxPython dialogs for testing environment")
    patches = []

    # Patch wx.MessageDialog
    message_dialog_patch = patch("wx.MessageDialog", SafeMessageDialog)
    message_dialog_patch.start()
    patches.append(message_dialog_patch)

    # Patch SettingsDialog
    try:
        from accessiweather.gui.settings_dialog import SettingsDialog
        settings_dialog_patch = patch("accessiweather.gui.settings_dialog.SettingsDialog", SafeSettingsDialog)
        settings_dialog_patch.start()
        patches.append(settings_dialog_patch)
    except ImportError:
        logger.warning("Could not patch SettingsDialog (module not found)")

    # Patch SettingsDialog in weather_app.py
    try:
        settings_dialog_patch = patch("accessiweather.gui.weather_app.SettingsDialog", SafeSettingsDialog)
        settings_dialog_patch.start()
        patches.append(settings_dialog_patch)
    except ImportError:
        logger.warning("Could not patch SettingsDialog in weather_app.py (module not found)")

    return patches


def unpatch_wx_dialogs(patches):
    """Unpatch wxPython dialogs.

    Args:
        patches: List of patches to stop
    """
    for p in patches:
        p.stop()
    logger.info(f"Stopped {len(patches)} wxPython dialog patches")
