"""Tests for the WeatherAppDialogHandlers class."""

import unittest
from unittest.mock import MagicMock, patch

import wx

from accessiweather.gui.handlers.dialog_handlers import WeatherAppDialogHandlers


class TestWeatherAppDialogHandlers(unittest.TestCase):
    """Tests for the WeatherAppDialogHandlers class."""

    def setUp(self):
        """Set up the test."""
        # Create a mock wx.Frame to use as the parent
        self.app = wx.App()
        self.frame = wx.Frame(None)
        # Create a mock handler class that inherits from WeatherAppDialogHandlers

        class TestHandler(WeatherAppDialogHandlers):
            def __init__(self, parent):
                self.parent = parent

        # Create an instance of the handler
        self.handler = TestHandler(self.frame)

    def tearDown(self):
        """Clean up after the test."""
        self.frame.Destroy()
        self.app.Destroy()

    @patch("wx.MessageBox")
    def test_show_message_dialog(self, mock_message_box):
        """Test the ShowMessageDialog method."""
        # Set up the mock
        mock_message_box.return_value = wx.ID_OK

        # Call the method
        result = self.handler.ShowMessageDialog(
            "Test message", "Test title", wx.OK | wx.ICON_INFORMATION
        )

        # Check the result
        self.assertEqual(result, wx.ID_OK)

        # Check that MessageBox was called with the correct arguments
        mock_message_box.assert_called_once_with(
            "Test message", "Test title", wx.OK | wx.ICON_INFORMATION, self.handler
        )

    @patch("wx.MessageBox")
    def test_show_confirm_dialog(self, mock_message_box):
        """Test the ShowConfirmDialog method."""
        # Test with Yes response
        mock_message_box.return_value = wx.ID_YES
        result = self.handler.ShowConfirmDialog("Test confirm?", "Test Confirm")
        self.assertTrue(result)

        # Test with No response
        mock_message_box.return_value = wx.ID_NO
        result = self.handler.ShowConfirmDialog("Test confirm?", "Test Confirm")
        self.assertFalse(result)

    @patch("accessiweather.gui.handlers.dialog_handlers.wx.ProgressDialog")
    def test_show_progress_dialog(self, mock_progress_dialog):
        """Test the ShowProgressDialog method."""
        # Set up the mock
        mock_dialog = MagicMock()
        mock_progress_dialog.return_value = mock_dialog

        # Call the method
        result = self.handler.ShowProgressDialog("Test Progress", "Test message", 100, self.frame)

        # Check the result
        self.assertEqual(result, mock_dialog)

        # Check that ProgressDialog was created with the correct arguments
        mock_progress_dialog.assert_called_once_with(
            "Test Progress", "Test message", 100, self.frame, wx.PD_APP_MODAL | wx.PD_AUTO_HIDE
        )

    @patch("accessiweather.gui.handlers.dialog_handlers.wx.SingleChoiceDialog")
    def test_show_single_choice_dialog(self, mock_dialog):
        """Test the ShowSingleChoiceDialog method."""
        # Set up the mock
        mock_instance = MagicMock()
        mock_dialog.return_value = mock_instance
        mock_instance.ShowModal.return_value = wx.ID_OK
        mock_instance.GetSelection.return_value = 1

        # Call the method
        result, selection = self.handler.ShowSingleChoiceDialog(
            "Choose one:", "Test Choices", ["Option 1", "Option 2", "Option 3"]
        )

        # Check the results
        self.assertEqual(result, wx.ID_OK)
        self.assertEqual(selection, 1)

        # Test with cancel
        mock_instance.ShowModal.return_value = wx.ID_CANCEL
        result, selection = self.handler.ShowSingleChoiceDialog(
            "Choose one:", "Test Choices", ["Option 1", "Option 2", "Option 3"]
        )

        # Check the results
        self.assertEqual(result, wx.ID_CANCEL)
        self.assertIsNone(selection)

    @patch("accessiweather.gui.handlers.dialog_handlers.wx.TextEntryDialog")
    def test_show_text_entry_dialog(self, mock_dialog):
        """Test the ShowTextEntryDialog method."""
        # Set up the mock
        mock_instance = MagicMock()
        mock_dialog.return_value = mock_instance
        mock_instance.ShowModal.return_value = wx.ID_OK
        mock_instance.GetValue.return_value = "Test input"

        # Call the method
        result, value = self.handler.ShowTextEntryDialog("Enter text:", "Test Input", "Default")

        # Check the results
        self.assertEqual(result, wx.ID_OK)
        self.assertEqual(value, "Test input")

        # Test with cancel
        mock_instance.ShowModal.return_value = wx.ID_CANCEL
        result, value = self.handler.ShowTextEntryDialog("Enter text:", "Test Input", "Default")

        # Check the results
        self.assertEqual(result, wx.ID_CANCEL)
        self.assertEqual(value, "")


if __name__ == "__main__":
    unittest.main()
