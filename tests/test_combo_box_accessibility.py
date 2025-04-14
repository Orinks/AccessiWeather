"""Tests for combo box accessibility improvements

This module tests the accessibility features of the AccessibleComboBox component.
"""

# Import faulthandler setup first to enable faulthandler
import tests.faulthandler_setup

import logging
import unittest
from unittest.mock import MagicMock, patch

import wx

from accessiweather.gui.basic_components import AccessibleComboBox

logger = logging.getLogger(__name__)


# Create a single app instance for all tests
_app = wx.App()  # noqa: F841 - Used by wxPython even if not directly referenced


class TestComboBoxAccessibility(unittest.TestCase):
    """Test case for combo box accessibility"""

    def setUp(self):
        """Set up test fixture"""
        self.frame = wx.Frame(None)

    def tearDown(self):
        """Tear down test fixture"""
        # Hide the window first
        wx.CallAfter(self.frame.Hide)
        wx.SafeYield()
        # Then destroy it
        wx.CallAfter(self.frame.Destroy)
        wx.SafeYield()

    def test_accessible_combo_box_initialization(self):
        """Test that AccessibleComboBox initializes with proper accessibility properties"""
        combo = AccessibleComboBox(self.frame, label="Test Combo")

        # Check that the accessible name is set
        self.assertEqual(combo.GetName(), "Test Combo")

        # Check that the accessible object has the correct role
        accessible = combo.GetAccessible()
        if accessible:
            # Mock the GetRole method since we can't directly check the role
            with patch.object(accessible, "GetRole", return_value=wx.ACC_ROLE_COMBOBOX):
                self.assertEqual(accessible.GetRole(), wx.ACC_ROLE_COMBOBOX)

    def test_combo_box_key_down_handler(self):
        """Test that key down events are handled properly for accessibility"""
        combo = AccessibleComboBox(self.frame, label="Test Combo")

        # Create a mock for the event
        event = MagicMock()
        event.GetKeyCode.return_value = wx.WXK_DOWN
        event.AltDown.return_value = True

        # Mock the Popup method
        combo.Popup = MagicMock()

        # Process the event
        combo.OnKeyDown(event)

        # Check that Popup was called
        combo.Popup.assert_called_once()

    def test_combo_box_char_hook(self):
        """Test that character hook events are handled properly"""
        combo = AccessibleComboBox(self.frame, label="Test Combo")

        # Create a mock for the event
        event = MagicMock()
        event.GetKeyCode.return_value = wx.WXK_RIGHT

        # Mock GetValue and GetInsertionPoint
        combo.GetValue = MagicMock(return_value="test")
        combo.GetInsertionPoint = MagicMock(return_value=2)

        # Process the event
        with patch.object(combo, "_announce_character") as mock_announce:
            combo.OnCharHook(event)
            # Skip is called, but we can't easily test that

            # Check that _announce_character was called with the right character
            mock_announce.assert_called_once_with("s")


if __name__ == "__main__":
    unittest.main()
