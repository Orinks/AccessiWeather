"""Tests for the AccessibleComboBox component"""

# Import faulthandler setup first to enable faulthandler
import unittest
from unittest.mock import MagicMock
import wx

# Import for side effects (enables faulthandler)
import tests.faulthandler_setup  # noqa: F401

# Import before creating wx.App
from accessiweather.gui.ui_components import AccessibleComboBox

class TestAccessibleComboBox(unittest.TestCase):
    """Test suite for AccessibleComboBox"""

    def setUp(self):
        # Ensure wx.App exists
        if not wx.App.Get():
            self.app = wx.App(False)
        else:
            self.app = wx.App.Get()
        self.frame = wx.Frame(None)

    def tearDown(self):
        wx.CallAfter(self.frame.Hide)
        wx.SafeYield()
        wx.CallAfter(self.frame.Destroy)
        wx.SafeYield()

    def test_init(self):
        """Test initialization with different parameters"""
        # Test with empty choices
        combo = AccessibleComboBox(self.frame, label="Test Combo")
        try:
            self.assertEqual(combo.GetName(), "Test Combo")
            self.assertEqual(combo.GetCount(), 0)
        finally:
            wx.CallAfter(combo.Destroy)

        # Test with choices
        choices = ["Option 1", "Option 2", "Option 3"]
        combo = AccessibleComboBox(self.frame, choices=choices, label="Test Combo")
        try:
            self.assertEqual(combo.GetName(), "Test Combo")
            self.assertEqual(combo.GetCount(), 3)
            for i, choice in enumerate(choices):
                self.assertEqual(combo.GetString(i), choice)
        finally:
            wx.CallAfter(combo.Destroy)

    def test_set_label(self):
        """Test setting accessible label"""
        combo = AccessibleComboBox(self.frame, label="Initial Label")
        try:
            self.assertEqual(combo.GetName(), "Initial Label")
            # Change label
            combo.SetLabel("New Label")
            self.assertEqual(combo.GetName(), "New Label")
        finally:
            wx.CallAfter(combo.Destroy)

    def test_add_items(self):
        """Test adding items to combo box"""
        combo = AccessibleComboBox(self.frame, label="Test Combo")
        try:
            # Add single item
            combo.Append("Option 1")
            self.assertEqual(combo.GetCount(), 1)
            self.assertEqual(combo.GetString(0), "Option 1")
            # Add multiple items
            combo.Append(["Option 2", "Option 3"])
            self.assertEqual(combo.GetCount(), 3)
            self.assertEqual(combo.GetString(1), "Option 2")
            self.assertEqual(combo.GetString(2), "Option 3")
        finally:
            wx.CallAfter(combo.Destroy)

    def test_get_set_value(self):
        """Test getting and setting value"""
        choices = ["Option 1", "Option 2", "Option 3"]
        combo = AccessibleComboBox(self.frame, choices=choices, label="Test Combo")
        try:
            # Set by index
            combo.SetSelection(1)
            self.assertEqual(combo.GetValue(), "Option 2")
            self.assertEqual(combo.GetSelection(), 1)
            # Set by string
            combo.SetValue("Option 3")
            self.assertEqual(combo.GetValue(), "Option 3")
            self.assertEqual(combo.GetSelection(), 2)
            # Set custom text
            combo.SetValue("Custom Text")
            self.assertEqual(combo.GetValue(), "Custom Text")
            self.assertEqual(combo.GetSelection(), wx.NOT_FOUND)
        finally:
            wx.CallAfter(combo.Destroy)

    def test_events(self):
        """Test that events are properly triggered"""
        choices = ["Option 1", "Option 2", "Option 3"]
        combo = AccessibleComboBox(self.frame, choices=choices, label="Test Combo")

        try:
            # Mock event handlers
            on_combobox = MagicMock()
            on_text = MagicMock()

            # Bind events
            combo.Bind(wx.EVT_COMBOBOX, on_combobox)
            combo.Bind(wx.EVT_TEXT, on_text)

            # Simulate selection event
            event = wx.CommandEvent(wx.wxEVT_COMBOBOX, combo.GetId())
            combo.GetEventHandler().ProcessEvent(event)
            on_combobox.assert_called_once()
            # Simulate text event
            event = wx.CommandEvent(wx.wxEVT_TEXT, combo.GetId())
            combo.GetEventHandler().ProcessEvent(event)
            on_text.assert_called_once()
        finally:
            wx.CallAfter(combo.Destroy)

