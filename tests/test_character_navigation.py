"""Tests for character navigation in combo boxes

This module tests the character navigation features of the combo box components.
"""

# Import faulthandler setup first to enable faulthandler
import tests.faulthandler_setup

import logging
from unittest.mock import MagicMock

import pytest
import wx

from accessiweather.gui.basic_components import AccessibleComboBox

logger = logging.getLogger(__name__)


# We'll use pytest fixtures instead of unittest
@pytest.fixture
def frame(wx_app):
    """Create a frame for testing."""
    # Create the frame
    frame = wx.Frame(None)

    # Yield the frame for the test
    yield frame

    # Hide the window first
    wx.CallAfter(frame.Hide)
    wx.SafeYield()
    # Then destroy it
    wx.CallAfter(frame.Destroy)
    wx.SafeYield()


def test_left_arrow_navigation(frame):
    """Test that left arrow key navigation announces characters"""
    combo = AccessibleComboBox(frame, label="Test Combo")
    combo.SetValue("test")

    # Set insertion point to position 2 (after 'e')
    combo.SetInsertionPoint(2)

    # Mock the accessible object
    accessible = MagicMock()
    combo.GetAccessible = MagicMock(return_value=accessible)

    # Create a mock event for left arrow key
    event = MagicMock()
    event.GetKeyCode.return_value = wx.WXK_LEFT

    # Process the event
    combo.OnCharHook(event)

    # Check that the character 'e' was announced
    accessible.SetDescription.assert_called_with("e")


def test_right_arrow_navigation(frame):
    """Test that right arrow key navigation announces characters"""
    combo = AccessibleComboBox(frame, label="Test Combo")
    combo.SetValue("test")

    # Set insertion point to position 1 (after 't')
    combo.SetInsertionPoint(1)

    # Mock the accessible object
    accessible = MagicMock()
    combo.GetAccessible = MagicMock(return_value=accessible)

    # Create a mock event for right arrow key
    event = MagicMock()
    event.GetKeyCode.return_value = wx.WXK_RIGHT

    # Process the event
    combo.OnCharHook(event)

    # Check that the character 'e' was announced
    accessible.SetDescription.assert_called_with("e")


def test_home_key_navigation(frame):
    """Test that home key navigation announces beginning of text"""
    combo = AccessibleComboBox(frame, label="Test Combo")
    combo.SetValue("test")

    # Set insertion point to position 2 (after 'e')
    combo.SetInsertionPoint(2)

    # Mock the accessible object
    accessible = MagicMock()
    combo.GetAccessible = MagicMock(return_value=accessible)

    # Create a mock event for home key
    event = MagicMock()
    event.GetKeyCode.return_value = wx.WXK_HOME

    # Process the event
    combo.OnCharHook(event)

    # Check that "Beginning of text" was announced
    accessible.SetDescription.assert_called_with("Beginning of text")


def test_end_key_navigation(frame):
    """Test that end key navigation announces end of text"""
    combo = AccessibleComboBox(frame, label="Test Combo")
    combo.SetValue("test")

    # Set insertion point to position 2 (after 'e')
    combo.SetInsertionPoint(2)

    # Mock the accessible object
    accessible = MagicMock()
    combo.GetAccessible = MagicMock(return_value=accessible)

    # Create a mock event for end key
    event = MagicMock()
    event.GetKeyCode.return_value = wx.WXK_END

    # Process the event
    combo.OnCharHook(event)

    # Check that "End of text" was announced
    accessible.SetDescription.assert_called_with("End of text")


def test_special_character_announcement(frame):
    """Test that special characters are announced properly"""
    combo = AccessibleComboBox(frame, label="Test Combo")
    combo.SetValue("test space")

    # Set insertion point to position 4 (before the space)
    combo.SetInsertionPoint(4)

    # Mock the accessible object
    accessible = MagicMock()
    combo.GetAccessible = MagicMock(return_value=accessible)

    # Create a mock event for right arrow key
    event = MagicMock()
    event.GetKeyCode.return_value = wx.WXK_RIGHT

    # Process the event
    combo.OnCharHook(event)

    # Check that "space" was announced
    accessible.SetDescription.assert_called_with("space")
