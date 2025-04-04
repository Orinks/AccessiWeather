"""Tests for the AccessibleComboBox component"""

import os  # Import os module
from unittest.mock import MagicMock  # Removed unused 'patch'

import pytest
import wx

# Import project components after wx.App might be needed
from accessiweather.gui.accessible_widgets import AccessibleComboBox


# Create a wx App fixture for testing
@pytest.fixture(scope="module", autouse=True)
def wx_app():
    """Create a wx App for testing"""
    app = wx.App(False)
    yield app


# Skip GUI tests in CI environment
@pytest.mark.skipif(
    os.environ.get("ACCESSIWEATHER_TESTING") == "1",
    reason="GUI test skipped in CI",
)
class TestAccessibleComboBox:
    """Test suite for AccessibleComboBox"""

    def setup_method(self):
        """Set up test fixture"""
        # Create parent frame
        self.frame = wx.Frame(None)

    def teardown_method(self):
        """Tear down test fixture"""
        # Destroy frame
        wx.CallAfter(self.frame.Destroy)

    def test_init(self):
        """Test initialization with different parameters"""
        # Test with empty choices
        combo = AccessibleComboBox(self.frame, label="Test Combo")
        try:
            assert combo.GetName() == "Test Combo"
            assert combo.GetCount() == 0
        finally:
            wx.CallAfter(combo.Destroy)

        # Test with choices
        choices = ["Option 1", "Option 2", "Option 3"]
        combo = AccessibleComboBox(
            self.frame, choices=choices, label="Test Combo"
        )
        try:
            assert combo.GetName() == "Test Combo"
            assert combo.GetCount() == 3
            for i, choice in enumerate(choices):
                assert combo.GetString(i) == choice
        finally:
            wx.CallAfter(combo.Destroy)

    def test_set_label(self):
        """Test setting accessible label"""
        combo = AccessibleComboBox(self.frame, label="Initial Label")
        try:
            assert combo.GetName() == "Initial Label"

            # Change label
            combo.SetLabel("New Label")
            assert combo.GetName() == "New Label"
        finally:
            wx.CallAfter(combo.Destroy)

    def test_add_items(self):
        """Test adding items to combo box"""
        combo = AccessibleComboBox(self.frame, label="Test Combo")
        try:
            # Add single item
            combo.Append("Option 1")
            assert combo.GetCount() == 1
            assert combo.GetString(0) == "Option 1"

            # Add multiple items
            combo.Append(["Option 2", "Option 3"])
            assert combo.GetCount() == 3
            assert combo.GetString(1) == "Option 2"
            assert combo.GetString(2) == "Option 3"
        finally:
            wx.CallAfter(combo.Destroy)

    def test_get_set_value(self):
        """Test getting and setting value"""
        choices = ["Option 1", "Option 2", "Option 3"]
        combo = AccessibleComboBox(
            self.frame, choices=choices, label="Test Combo"
        )
        try:
            # Set by index
            combo.SetSelection(1)
            assert combo.GetValue() == "Option 2"
            assert combo.GetSelection() == 1

            # Set by string
            combo.SetValue("Option 3")
            assert combo.GetValue() == "Option 3"
            assert combo.GetSelection() == 2

            # Set custom text
            combo.SetValue("Custom Text")
            assert combo.GetValue() == "Custom Text"
            assert combo.GetSelection() == wx.NOT_FOUND
        finally:
            wx.CallAfter(combo.Destroy)

    def test_events(self):
        """Test that events are properly triggered"""
        choices = ["Option 1", "Option 2", "Option 3"]
        combo = AccessibleComboBox(
            self.frame, choices=choices, label="Test Combo"
        )

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
