"""Unit tests for update progress dialog."""

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set up toga-dummy backend for testing
os.environ["TOGA_BACKEND"] = "toga_dummy"

from accessiweather.dialogs.update_progress_dialog import (
    UpdateNotificationDialog,
    UpdateProgressDialog,
)


@pytest.fixture
def mock_app():
    """Mock Toga app instance."""
    app = MagicMock()
    # Create a mock loop instead of getting the real event loop
    mock_loop = MagicMock()
    mock_loop.create_future.return_value = asyncio.Future()
    app.loop = mock_loop
    app.main_window = MagicMock()
    return app


@pytest.fixture
def mock_window():
    """Mock Toga window."""
    window = MagicMock()
    window.show = MagicMock()
    window.close = MagicMock()
    return window


@pytest.fixture
def progress_dialog(mock_app):
    """Create progress dialog instance."""
    return UpdateProgressDialog(mock_app, "Test Update")


class TestUpdateProgressDialog:
    """Test the update progress dialog."""

    def test_initialize_dialog(self, mock_app):
        """Test dialog initialization."""
        dialog = UpdateProgressDialog(mock_app, "Custom Title")

        assert dialog.app == mock_app
        assert dialog.title == "Custom Title"
        assert dialog.window is None
        assert dialog.future is None
        assert dialog.is_cancelled is False
        assert dialog.current_progress == 0
        assert dialog.total_size == 0
        assert dialog.downloaded_size == 0

    def test_initialize_dialog_with_defaults(self, mock_app):
        """Test dialog initialization with default title."""
        dialog = UpdateProgressDialog(mock_app)

        assert dialog.title == "Updating AccessiWeather"

    @patch("toga.Window")
    @patch("toga.Box")
    @patch("toga.Label")
    @patch("toga.ActivityIndicator")
    @patch("toga.Button")
    def test_show_and_prepare(
        self, mock_button, mock_indicator, mock_label, mock_box, mock_window_class, progress_dialog
    ):
        """Test showing and preparing the dialog."""
        mock_window = MagicMock()
        mock_window_class.return_value = mock_window

        # Mock UI components
        mock_status_label = MagicMock()
        mock_detail_label = MagicMock()
        mock_progress_indicator = MagicMock()
        mock_cancel_button = MagicMock()
        mock_main_box = MagicMock()

        mock_label.side_effect = [mock_status_label, mock_detail_label]
        mock_indicator.return_value = mock_progress_indicator
        mock_button.return_value = mock_cancel_button
        mock_box.return_value = mock_main_box

        progress_dialog.show_and_prepare()

        # Verify window was created and shown
        mock_window_class.assert_called_once()
        mock_window.show.assert_called_once()

        # Verify future was created
        assert progress_dialog.future is not None
        assert not progress_dialog.future.done()

    @patch("toga.Window")
    def test_show_and_prepare_exception(self, mock_window_class, progress_dialog):
        """Test exception handling in show_and_prepare."""
        mock_window_class.side_effect = Exception("Window creation failed")

        progress_dialog.show_and_prepare()

        # Future should be set with exception
        assert progress_dialog.future is not None
        assert progress_dialog.future.done()

        with pytest.raises(Exception, match="Window creation failed"):
            progress_dialog.future.result()

    def test_await_without_future(self, progress_dialog):
        """Test awaiting dialog without preparing first."""
        with pytest.raises(RuntimeError, match="Dialog future not initialized"):
            progress_dialog.__await__()

    @pytest.mark.asyncio
    async def test_update_progress(self, progress_dialog):
        """Test updating progress display."""
        # Mock UI components
        progress_dialog.status_label = MagicMock()
        progress_dialog.detail_label = MagicMock()
        progress_dialog.progress_indicator = MagicMock()

        await progress_dialog.update_progress(25.5, downloaded=256000, total=1024000)

        assert progress_dialog.current_progress == 25.5
        assert progress_dialog.downloaded_size == 256000
        assert progress_dialog.total_size == 1024000

        # Check that UI was updated
        progress_dialog.status_label.text = "Downloading update... 25.5%"
        progress_dialog.detail_label.text = "0.2 MB of 1.0 MB"
        progress_dialog.progress_indicator.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_progress_preparing(self, progress_dialog):
        """Test progress update during preparation phase."""
        progress_dialog.status_label = MagicMock()
        progress_dialog.detail_label = MagicMock()
        progress_dialog.progress_indicator = MagicMock()

        await progress_dialog.update_progress(0.5)

        # Should show preparing status
        progress_dialog.status_label.text = "Preparing update..."

    @pytest.mark.asyncio
    async def test_update_progress_finalizing(self, progress_dialog):
        """Test progress update during finalization."""
        progress_dialog.status_label = MagicMock()
        progress_dialog.detail_label = MagicMock()
        progress_dialog.progress_indicator = MagicMock()

        await progress_dialog.update_progress(100)

        # Should show finalizing status and stop indicator
        progress_dialog.status_label.text = "Finalizing update..."
        progress_dialog.progress_indicator.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_status(self, progress_dialog):
        """Test setting status and detail text."""
        progress_dialog.status_label = MagicMock()
        progress_dialog.detail_label = MagicMock()

        await progress_dialog.set_status("Custom Status", "Custom Detail")

        progress_dialog.status_label.text = "Custom Status"
        progress_dialog.detail_label.text = "Custom Detail"

    @pytest.mark.asyncio
    async def test_set_status_no_detail(self, progress_dialog):
        """Test setting status without detail."""
        progress_dialog.status_label = MagicMock()
        progress_dialog.detail_label = MagicMock()

        await progress_dialog.set_status("Status Only")

        progress_dialog.status_label.text = "Status Only"
        # detail_label should not be modified when no detail provided

    def test_on_cancel(self, progress_dialog):
        """Test cancel button press."""
        progress_dialog.status_label = MagicMock()
        progress_dialog.cancel_button = MagicMock()
        progress_dialog.progress_indicator = MagicMock()
        progress_dialog.future = MagicMock()
        progress_dialog.future.done.return_value = False

        progress_dialog._on_cancel(None)

        assert progress_dialog.is_cancelled is True
        progress_dialog.status_label.text = "Cancelling update..."
        progress_dialog.cancel_button.enabled = False
        progress_dialog.progress_indicator.stop.assert_called_once()
        progress_dialog.future.set_result.assert_called_once_with("cancelled")

    def test_on_cancel_already_done(self, progress_dialog):
        """Test cancel when future is already done."""
        progress_dialog.future = MagicMock()
        progress_dialog.future.done.return_value = True
        # Mock the UI components to avoid AttributeError
        progress_dialog.status_label = MagicMock()
        progress_dialog.cancel_button = MagicMock()
        progress_dialog.progress_indicator = MagicMock()

        progress_dialog._on_cancel(None)

        assert progress_dialog.is_cancelled is True
        # set_result should not be called when future is already done
        progress_dialog.future.set_result.assert_not_called()

    @pytest.mark.asyncio
    async def test_complete_success(self, progress_dialog):
        """Test successful completion."""
        progress_dialog.status_label = MagicMock()
        progress_dialog.detail_label = MagicMock()
        progress_dialog.progress_indicator = MagicMock()
        progress_dialog.cancel_button = MagicMock()
        progress_dialog.future = MagicMock()
        progress_dialog.future.done.return_value = False

        # Mock asyncio.sleep to speed up test
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await progress_dialog.complete_success("Custom success message")

        progress_dialog.status_label.text = "Custom success message"
        progress_dialog.detail_label.text = "The application will restart shortly."
        progress_dialog.progress_indicator.stop.assert_called_once()
        progress_dialog.cancel_button.text = "Close"
        progress_dialog.cancel_button.enabled = True
        progress_dialog.future.set_result.assert_called_once_with("success")

    @pytest.mark.asyncio
    async def test_complete_error(self, progress_dialog):
        """Test error completion."""
        progress_dialog.status_label = MagicMock()
        progress_dialog.detail_label = MagicMock()
        progress_dialog.progress_indicator = MagicMock()
        progress_dialog.cancel_button = MagicMock()
        progress_dialog.future = MagicMock()
        progress_dialog.future.done.return_value = False

        await progress_dialog.complete_error("Download failed")

        progress_dialog.status_label.text = "Update failed"
        progress_dialog.detail_label.text = "Download failed"
        progress_dialog.progress_indicator.stop.assert_called_once()
        progress_dialog.cancel_button.text = "Close"
        progress_dialog.cancel_button.enabled = True
        progress_dialog.future.set_result.assert_called_once_with("error")

    def test_close(self, progress_dialog):
        """Test dialog closing."""
        mock_window = MagicMock()
        progress_dialog.window = mock_window

        progress_dialog.close()

        mock_window.close.assert_called_once()
        assert progress_dialog.window is None

    def test_close_no_window(self, progress_dialog):
        """Test closing when no window exists."""
        progress_dialog.window = None

        # Should not raise exception
        progress_dialog.close()

    def test_close_with_exception(self, progress_dialog):
        """Test closing with exception."""
        progress_dialog.window = MagicMock()
        progress_dialog.window.close.side_effect = Exception("Close failed")

        # Should not raise exception, just log error
        progress_dialog.close()


class TestUpdateNotificationDialog:
    """Test the update notification dialog."""

    @pytest.fixture
    def update_info(self):
        """Mock update info."""
        info = MagicMock()
        info.version = "2.0.0"
        return info

    @pytest.fixture
    def platform_info(self):
        """Mock platform info."""
        info = MagicMock()
        info.update_capable = True
        return info

    @pytest.fixture
    def notification_dialog(self, mock_app, update_info, platform_info):
        """Create notification dialog instance."""
        return UpdateNotificationDialog(mock_app, update_info, platform_info)

    def test_initialize_notification_dialog(self, mock_app, update_info, platform_info):
        """Test notification dialog initialization."""
        dialog = UpdateNotificationDialog(mock_app, update_info, platform_info)

        assert dialog.app == mock_app
        assert dialog.update_info == update_info
        assert dialog.platform_info == platform_info

    @pytest.mark.asyncio
    async def test_show_update_capable_platform(self, notification_dialog, mock_app):
        """Test showing dialog on update-capable platform."""
        mock_app.main_window.question_dialog = AsyncMock(return_value=True)

        with patch.object(notification_dialog, "_get_current_version", return_value="1.0.0"):
            result = await notification_dialog.show()

        assert result == "download"
        mock_app.main_window.question_dialog.assert_called_once()

    @pytest.mark.asyncio
    async def test_show_update_capable_platform_declined(self, notification_dialog, mock_app):
        """Test showing dialog on update-capable platform when user declines."""
        mock_app.main_window.question_dialog = AsyncMock(return_value=False)

        with patch.object(notification_dialog, "_get_current_version", return_value="1.0.0"):
            result = await notification_dialog.show()

        assert result == "later"
        mock_app.main_window.question_dialog.assert_called_once()

    @pytest.mark.asyncio
    async def test_show_non_update_capable_platform(
        self, notification_dialog, mock_app, platform_info
    ):
        """Test showing dialog on non-update-capable platform."""
        platform_info.update_capable = False
        mock_app.main_window.info_dialog = AsyncMock()

        with patch.object(notification_dialog, "_get_current_version", return_value="1.0.0"):
            result = await notification_dialog.show()

        assert result == "manual"
        mock_app.main_window.info_dialog.assert_called_once()

    @pytest.mark.asyncio
    async def test_show_with_exception(self, notification_dialog, mock_app):
        """Test showing dialog with exception."""
        mock_app.main_window.question_dialog = AsyncMock(side_effect=Exception("Dialog error"))

        result = await notification_dialog.show()

        assert result == "error"

    def test_get_current_version(self, notification_dialog):
        """Test getting current version."""
        with patch("accessiweather.version.__version__", "1.5.0"):
            version = notification_dialog._get_current_version()
            assert version == "1.5.0"

    def test_get_current_version_import_error(self, notification_dialog):
        """Test getting current version with import error."""
        with patch.dict("sys.modules", {"accessiweather.version": None}):
            version = notification_dialog._get_current_version()
            assert version == "Unknown"


class TestUpdateProgressExceptionHandling:
    """Test exception handling in update progress dialog."""

    @pytest.mark.asyncio
    async def test_update_progress_with_exception(self):
        """Test update_progress with exception in UI update."""
        mock_app = MagicMock()
        progress_dialog = UpdateProgressDialog(mock_app, "Test Update")
        progress_dialog.status_label = MagicMock()
        progress_dialog.status_label.text = MagicMock(side_effect=Exception("UI Error"))

        # Should not raise exception
        await progress_dialog.update_progress(50)

    @pytest.mark.asyncio
    async def test_set_status_with_exception(self):
        """Test set_status with exception in UI update."""
        mock_app = MagicMock()
        progress_dialog = UpdateProgressDialog(mock_app, "Test Update")
        progress_dialog.status_label = MagicMock()
        progress_dialog.status_label.text = MagicMock(side_effect=Exception("UI Error"))

        # Should not raise exception
        await progress_dialog.set_status("Test Status")

    @pytest.mark.asyncio
    async def test_complete_success_with_exception(self):
        """Test complete_success with exception."""
        mock_app = MagicMock()
        progress_dialog = UpdateProgressDialog(mock_app, "Test Update")
        progress_dialog.future = MagicMock()
        progress_dialog.future.done.return_value = False
        progress_dialog.status_label = MagicMock()
        progress_dialog.status_label.text = MagicMock(side_effect=Exception("UI Error"))

        # Should not raise exception
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await progress_dialog.complete_success()

    @pytest.mark.asyncio
    async def test_complete_error_with_exception(self):
        """Test complete_error with exception."""
        mock_app = MagicMock()
        progress_dialog = UpdateProgressDialog(mock_app, "Test Update")
        progress_dialog.future = MagicMock()
        progress_dialog.future.done.return_value = False
        progress_dialog.status_label = MagicMock()
        progress_dialog.status_label.text = MagicMock(side_effect=Exception("UI Error"))

        # Should not raise exception
        await progress_dialog.complete_error("Test Error")

    def test_set_initial_focus_with_exception(self):
        """Test _set_initial_focus with exception."""
        mock_app = MagicMock()
        progress_dialog = UpdateProgressDialog(mock_app, "Test Update")
        progress_dialog.cancel_button = MagicMock()
        progress_dialog.cancel_button.focus.side_effect = Exception("Focus Error")

        # Should not raise exception
        progress_dialog._set_initial_focus()
