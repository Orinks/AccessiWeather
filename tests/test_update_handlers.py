"""Tests for the update handlers functionality."""

import tempfile
import unittest
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import wx

from accessiweather.gui.handlers.update_handlers import WeatherAppUpdateHandlers
from accessiweather.services.update_service import UpdateService


class MockWeatherApp(wx.Frame, WeatherAppUpdateHandlers):
    """Mock WeatherApp for testing update handlers."""

    def __init__(self):
        super().__init__(None, title="Mock Weather App")
        self.temp_dir = tempfile.mkdtemp()
        self.update_service = UpdateService(
            config_dir=self.temp_dir,
            notification_callback=MagicMock(),
            progress_callback=MagicMock(),
        )
        self.config: Dict[str, Any] = {"settings": {}}

    def Close(self, force=False):
        """Mock method."""
        super().Close()


class TestUpdateHandlers(unittest.TestCase):
    """Tests for the update handlers."""

    def setUp(self):
        """Set up test fixtures."""
        self.app = wx.App()
        self.mock_weather_app = MockWeatherApp()

    def tearDown(self):
        """Tear down test fixtures."""
        if (
            hasattr(self.mock_weather_app, "update_service")
            and self.mock_weather_app.update_service
        ):
            self.mock_weather_app.update_service.stop_background_checking()
        self.mock_weather_app.Destroy()
        self.app.Destroy()

    @patch("wx.MessageBox")
    def test_on_check_for_updates_no_service(self, mock_message_box):
        """Test OnCheckForUpdates when update service is not available."""
        # Remove update service
        self.mock_weather_app.update_service = None

        # Create a mock event
        event = MagicMock()

        # Call OnCheckForUpdates
        self.mock_weather_app.OnCheckForUpdates(event)

        # Verify error message was shown
        mock_message_box.assert_called_once_with(
            "Update service is not available.",
            "Update Check Failed",
            wx.OK | wx.ICON_ERROR,
            self.mock_weather_app,
        )

    @patch("accessiweather.gui.handlers.update_handlers.UpdateProgressDialog")
    @patch("accessiweather.gui.handlers.update_handlers.SimpleMessageDialog")
    def test_on_check_for_updates_no_update_available(
        self, mock_message_dialog, mock_progress_dialog
    ):
        """Test OnCheckForUpdates when no update is available."""
        # Mock progress dialog
        mock_dialog_instance = MagicMock()
        mock_progress_dialog.return_value = mock_dialog_instance

        # Mock message dialog
        mock_message_dialog_instance = MagicMock()
        mock_message_dialog.return_value = mock_message_dialog_instance

        # Mock update service to return None (no update available)
        self.mock_weather_app.update_service.check_for_updates = MagicMock(return_value=None)

        # Create a mock event
        event = MagicMock()

        # Call OnCheckForUpdates
        self.mock_weather_app.OnCheckForUpdates(event)

        # Wait a bit for the background thread to complete
        import time

        time.sleep(0.1)

        # Process any pending wx.CallAfter calls
        wx.GetApp().ProcessPendingEvents()

        # Verify progress dialog was created and shown
        mock_progress_dialog.assert_called_once_with(self.mock_weather_app, "Checking for Updates")
        mock_dialog_instance.Show.assert_called_once()

        # Verify update service was called
        self.mock_weather_app.update_service.check_for_updates.assert_called_once()

        # Verify progress dialog was destroyed
        mock_dialog_instance.Destroy.assert_called_once()

        # Verify "no update available" modal dialog was shown with main window as parent
        # (no settings dialog present)
        mock_message_dialog.assert_called_once_with(
            self.mock_weather_app,
            "You are running the latest version of AccessiWeather.",
            "No Updates Available",
            wx.OK | wx.ICON_INFORMATION,
        )
        mock_message_dialog_instance.ShowModal.assert_called_once()
        mock_message_dialog_instance.Destroy.assert_called_once()

    @patch("accessiweather.gui.handlers.update_handlers.UpdateProgressDialog")
    @patch("accessiweather.gui.handlers.update_handlers.SimpleMessageDialog")
    def test_on_check_for_updates_error(self, mock_message_dialog, mock_progress_dialog):
        """Test OnCheckForUpdates when an error occurs during check."""
        # Mock progress dialog
        mock_dialog_instance = MagicMock()
        mock_progress_dialog.return_value = mock_dialog_instance

        # Mock message dialog
        mock_message_dialog_instance = MagicMock()
        mock_message_dialog.return_value = mock_message_dialog_instance

        # Mock update service to raise an exception
        error_message = "Network error"
        self.mock_weather_app.update_service.check_for_updates = MagicMock(
            side_effect=Exception(error_message)
        )

        # Create a mock event
        event = MagicMock()

        # Call OnCheckForUpdates
        self.mock_weather_app.OnCheckForUpdates(event)

        # Wait a bit for the background thread to complete
        import time

        time.sleep(0.1)

        # Process any pending wx.CallAfter calls
        wx.GetApp().ProcessPendingEvents()

        # Verify progress dialog was created and shown
        mock_progress_dialog.assert_called_once_with(self.mock_weather_app, "Checking for Updates")
        mock_dialog_instance.Show.assert_called_once()

        # Verify update service was called
        self.mock_weather_app.update_service.check_for_updates.assert_called_once()

        # Verify progress dialog was destroyed
        mock_dialog_instance.Destroy.assert_called_once()

        # Verify error message was shown with main window as parent
        # (no settings dialog present)
        mock_message_dialog.assert_called_once_with(
            self.mock_weather_app,
            f"Failed to check for updates:\n\n{error_message}",
            "Update Check Failed",
            wx.OK | wx.ICON_ERROR,
        )
        mock_message_dialog_instance.ShowModal.assert_called_once()
        mock_message_dialog_instance.Destroy.assert_called_once()

    def test_on_manual_check_complete_no_update(self):
        """Test _on_manual_check_complete when no update is available."""
        # Create a mock progress dialog
        mock_progress_dialog = MagicMock()

        with patch(
            "accessiweather.gui.handlers.update_handlers.SimpleMessageDialog"
        ) as mock_message_dialog:
            # Mock message dialog instance
            mock_message_dialog_instance = MagicMock()
            mock_message_dialog.return_value = mock_message_dialog_instance

            # Call _on_manual_check_complete with None (no update)
            self.mock_weather_app._on_manual_check_complete(mock_progress_dialog, None)

            # Verify progress dialog was destroyed
            mock_progress_dialog.Destroy.assert_called_once()

            # Verify "no update available" modal dialog was shown
            mock_message_dialog.assert_called_once_with(
                self.mock_weather_app,
                "You are running the latest version of AccessiWeather.",
                "No Updates Available",
                wx.OK | wx.ICON_INFORMATION,
            )
            mock_message_dialog_instance.ShowModal.assert_called_once()
            mock_message_dialog_instance.Destroy.assert_called_once()

    def test_on_manual_check_error(self):
        """Test _on_manual_check_error method."""
        # Create a mock progress dialog
        mock_progress_dialog = MagicMock()
        error_message = "Test error message"

        with patch(
            "accessiweather.gui.handlers.update_handlers.SimpleMessageDialog"
        ) as mock_message_dialog:
            # Mock message dialog instance
            mock_message_dialog_instance = MagicMock()
            mock_message_dialog.return_value = mock_message_dialog_instance

            # Call _on_manual_check_error
            self.mock_weather_app._on_manual_check_error(mock_progress_dialog, error_message)

            # Verify progress dialog was destroyed
            mock_progress_dialog.Destroy.assert_called_once()

            # Verify error modal dialog was shown
            mock_message_dialog.assert_called_once_with(
                self.mock_weather_app,
                f"Failed to check for updates:\n\n{error_message}",
                "Update Check Failed",
                wx.OK | wx.ICON_ERROR,
            )
            mock_message_dialog_instance.ShowModal.assert_called_once()
            mock_message_dialog_instance.Destroy.assert_called_once()

    def test_on_manual_check_complete_with_settings_dialog(self):
        """Test _on_manual_check_complete uses settings dialog as parent when available."""
        # Create mock dialogs
        mock_progress_dialog = MagicMock()
        mock_settings_dialog = MagicMock()
        mock_settings_dialog.IsShown.return_value = True

        # Set up the settings dialog reference
        self.mock_weather_app._last_settings_dialog = mock_settings_dialog

        with patch(
            "accessiweather.gui.handlers.update_handlers.SimpleMessageDialog"
        ) as mock_message_dialog:
            # Mock message dialog instance
            mock_message_dialog_instance = MagicMock()
            mock_message_dialog.return_value = mock_message_dialog_instance

            # Call _on_manual_check_complete with None (no update)
            self.mock_weather_app._on_manual_check_complete(mock_progress_dialog, None)

            # Verify progress dialog was destroyed
            mock_progress_dialog.Destroy.assert_called_once()

            # Verify "no update available" modal dialog was shown with settings dialog as parent
            mock_message_dialog.assert_called_once_with(
                mock_settings_dialog,  # Should use settings dialog as parent
                "You are running the latest version of AccessiWeather.",
                "No Updates Available",
                wx.OK | wx.ICON_INFORMATION,
            )
            mock_message_dialog_instance.ShowModal.assert_called_once()
            mock_message_dialog_instance.Destroy.assert_called_once()
            # Note: Modal dialogs handle focus automatically, no manual focus restoration needed

    def test_on_manual_check_error_with_settings_dialog(self):
        """Test _on_manual_check_error uses settings dialog as parent when available."""
        # Create mock dialogs
        mock_progress_dialog = MagicMock()
        mock_settings_dialog = MagicMock()
        mock_settings_dialog.IsShown.return_value = True
        error_message = "Test error message"

        # Set up the settings dialog reference
        self.mock_weather_app._last_settings_dialog = mock_settings_dialog

        with patch(
            "accessiweather.gui.handlers.update_handlers.SimpleMessageDialog"
        ) as mock_message_dialog:
            # Mock message dialog instance
            mock_message_dialog_instance = MagicMock()
            mock_message_dialog.return_value = mock_message_dialog_instance

            # Call _on_manual_check_error
            self.mock_weather_app._on_manual_check_error(mock_progress_dialog, error_message)

            # Verify progress dialog was destroyed
            mock_progress_dialog.Destroy.assert_called_once()

            # Verify error modal dialog was shown with settings dialog as parent
            mock_message_dialog.assert_called_once_with(
                mock_settings_dialog,  # Should use settings dialog as parent
                f"Failed to check for updates:\n\n{error_message}",
                "Update Check Failed",
                wx.OK | wx.ICON_ERROR,
            )
            mock_message_dialog_instance.ShowModal.assert_called_once()
            mock_message_dialog_instance.Destroy.assert_called_once()
            # Note: Modal dialogs handle focus automatically, no manual focus restoration needed

    def test_on_manual_check_complete_settings_dialog_hidden(self):
        """Test _on_manual_check_complete uses settings dialog as parent even when hidden."""
        # Create mock dialogs
        mock_progress_dialog = MagicMock()
        mock_settings_dialog = MagicMock()
        mock_settings_dialog.IsShown.return_value = False  # Dialog is hidden

        # Set up the settings dialog reference
        self.mock_weather_app._last_settings_dialog = mock_settings_dialog

        with patch(
            "accessiweather.gui.handlers.update_handlers.SimpleMessageDialog"
        ) as mock_message_dialog:
            # Mock message dialog instance
            mock_message_dialog_instance = MagicMock()
            mock_message_dialog.return_value = mock_message_dialog_instance

            # Call _on_manual_check_complete with None (no update)
            self.mock_weather_app._on_manual_check_complete(mock_progress_dialog, None)

            # Verify progress dialog was destroyed
            mock_progress_dialog.Destroy.assert_called_once()

            # Verify "no update available" modal dialog was shown with settings dialog as parent
            mock_message_dialog.assert_called_once_with(
                mock_settings_dialog,  # Should still use settings dialog as parent
                "You are running the latest version of AccessiWeather.",
                "No Updates Available",
                wx.OK | wx.ICON_INFORMATION,
            )
            mock_message_dialog_instance.ShowModal.assert_called_once()
            mock_message_dialog_instance.Destroy.assert_called_once()
            # Note: Modal dialogs handle focus automatically regardless of parent visibility

    def test_on_manual_check_complete_no_settings_dialog(self):
        """Test _on_manual_check_complete without settings dialog (uses main window as parent)."""
        # Create mock progress dialog
        mock_progress_dialog = MagicMock()

        # No settings dialog reference
        if hasattr(self.mock_weather_app, "_last_settings_dialog"):
            delattr(self.mock_weather_app, "_last_settings_dialog")

        with patch(
            "accessiweather.gui.handlers.update_handlers.SimpleMessageDialog"
        ) as mock_message_dialog:
            # Mock message dialog instance
            mock_message_dialog_instance = MagicMock()
            mock_message_dialog.return_value = mock_message_dialog_instance

            # Call _on_manual_check_complete with None (no update)
            self.mock_weather_app._on_manual_check_complete(mock_progress_dialog, None)

            # Verify progress dialog was destroyed
            mock_progress_dialog.Destroy.assert_called_once()

            # Verify "no update available" modal dialog was shown with main window as parent
            mock_message_dialog.assert_called_once_with(
                self.mock_weather_app,  # Should use main window as parent
                "You are running the latest version of AccessiWeather.",
                "No Updates Available",
                wx.OK | wx.ICON_INFORMATION,
            )
            mock_message_dialog_instance.ShowModal.assert_called_once()
            mock_message_dialog_instance.Destroy.assert_called_once()
            # Note: Modal dialogs handle focus automatically, no manual focus restoration needed

    def test_on_manual_check_error_no_settings_dialog(self):
        """Test _on_manual_check_error without settings dialog (uses main window as parent)."""
        # Create mock progress dialog
        mock_progress_dialog = MagicMock()
        error_message = "Network error"

        # No settings dialog reference
        if hasattr(self.mock_weather_app, "_last_settings_dialog"):
            delattr(self.mock_weather_app, "_last_settings_dialog")

        with patch(
            "accessiweather.gui.handlers.update_handlers.SimpleMessageDialog"
        ) as mock_message_dialog:
            # Mock message dialog instance
            mock_message_dialog_instance = MagicMock()
            mock_message_dialog.return_value = mock_message_dialog_instance

            # Call _on_manual_check_error
            self.mock_weather_app._on_manual_check_error(mock_progress_dialog, error_message)

            # Verify progress dialog was destroyed
            mock_progress_dialog.Destroy.assert_called_once()

            # Verify error modal dialog was shown with main window as parent
            mock_message_dialog.assert_called_once_with(
                self.mock_weather_app,  # Should use main window as parent
                f"Failed to check for updates:\n\n{error_message}",
                "Update Check Failed",
                wx.OK | wx.ICON_ERROR,
            )
            mock_message_dialog_instance.ShowModal.assert_called_once()
            mock_message_dialog_instance.Destroy.assert_called_once()
            # Note: Modal dialogs handle focus automatically, no manual focus restoration needed


if __name__ == "__main__":
    unittest.main()
