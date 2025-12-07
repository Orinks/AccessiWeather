"""Tests for location management event handlers."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
import toga

from accessiweather.handlers.location_handlers import (
    on_add_location_pressed,
    on_location_changed,
    on_remove_location_pressed,
    show_remove_confirmation_dialog,
)


@pytest.fixture
def mock_app():
    """Create a mock AccessiWeatherApp."""
    app = Mock()
    app.config_manager = Mock()
    app.main_window = Mock()
    app.location_selection = Mock(spec=toga.Selection)
    app.location_selection.value = "New York"
    app.main_window.info_dialog = AsyncMock()
    app.main_window.error_dialog = AsyncMock()
    app.main_window.question_dialog = AsyncMock()
    return app


@pytest.fixture
def mock_widget():
    """Create a mock widget."""
    widget = Mock(spec=toga.Selection)
    widget.value = "New York"
    return widget


@pytest.fixture
def mock_button():
    """Create a mock button."""
    return Mock(spec=toga.Button)


class TestOnLocationChanged:
    """Test on_location_changed handler."""

    @pytest.mark.asyncio
    async def test_location_changed_success(self, mock_app, mock_widget):
        """Test successful location change."""
        with patch(
            "accessiweather.handlers.location_handlers.refresh_weather_data", new=AsyncMock()
        ) as mock_refresh:
            await on_location_changed(mock_app, mock_widget)

            mock_app.config_manager.set_current_location.assert_called_once_with("New York")
            mock_refresh.assert_called_once_with(mock_app)

    @pytest.mark.asyncio
    async def test_location_changed_none_value(self, mock_app, mock_widget):
        """Test location change with None value."""
        mock_widget.value = None

        with patch(
            "accessiweather.handlers.location_handlers.refresh_weather_data", new=AsyncMock()
        ) as mock_refresh:
            await on_location_changed(mock_app, mock_widget)

            mock_app.config_manager.set_current_location.assert_not_called()
            mock_refresh.assert_not_called()

    @pytest.mark.asyncio
    async def test_location_changed_no_locations_available(self, mock_app, mock_widget):
        """Test location change with 'No locations available' value."""
        mock_widget.value = "No locations available"

        with patch(
            "accessiweather.handlers.location_handlers.refresh_weather_data", new=AsyncMock()
        ) as mock_refresh:
            await on_location_changed(mock_app, mock_widget)

            mock_app.config_manager.set_current_location.assert_not_called()
            mock_refresh.assert_not_called()

    @pytest.mark.asyncio
    async def test_location_changed_exception(self, mock_app, mock_widget):
        """Test location change when exception occurs."""
        mock_app.config_manager.set_current_location.side_effect = Exception("Config error")

        with (
            patch(
                "accessiweather.handlers.location_handlers.refresh_weather_data", new=AsyncMock()
            ),
            patch("accessiweather.handlers.location_handlers.app_helpers") as mock_helpers,
        ):
            await on_location_changed(mock_app, mock_widget)

            mock_helpers.update_status.assert_called_once()
            assert "Error changing location" in str(mock_helpers.update_status.call_args[0][1])

    @pytest.mark.asyncio
    async def test_location_changed_logging(self, mock_app, mock_widget, caplog):
        """Test that location change is logged."""
        import logging

        caplog.set_level(logging.INFO)

        with patch(
            "accessiweather.handlers.location_handlers.refresh_weather_data", new=AsyncMock()
        ):
            await on_location_changed(mock_app, mock_widget)

            assert "Location changed to: New York" in caplog.text


class TestOnAddLocationPressed:
    """Test on_add_location_pressed handler."""

    @pytest.mark.asyncio
    async def test_add_location_success(self, mock_app, mock_button):
        """Test successful location addition."""
        with (
            patch(
                "accessiweather.handlers.location_handlers.AddLocationDialog"
            ) as mock_dialog_class,
            patch(
                "accessiweather.handlers.location_handlers.refresh_weather_data", new=AsyncMock()
            ) as mock_refresh,
            patch("accessiweather.handlers.location_handlers.app_helpers") as mock_helpers,
        ):
            mock_dialog = Mock()
            # Dialog now returns the location name on success, None on cancel
            mock_dialog.show_and_wait = AsyncMock(return_value="New Location")
            mock_dialog_class.return_value = mock_dialog

            await on_add_location_pressed(mock_app, mock_button)

            mock_dialog_class.assert_called_once_with(mock_app, mock_app.config_manager)
            mock_dialog.show_and_wait.assert_called_once()
            # Should set the new location as current
            mock_app.config_manager.set_current_location.assert_called_once_with("New Location")
            mock_helpers.update_location_selection.assert_called_once_with(mock_app)
            mock_refresh.assert_called_once_with(mock_app)

    @pytest.mark.asyncio
    async def test_add_location_cancelled(self, mock_app, mock_button):
        """Test cancelled location addition."""
        with (
            patch(
                "accessiweather.handlers.location_handlers.AddLocationDialog"
            ) as mock_dialog_class,
            patch(
                "accessiweather.handlers.location_handlers.refresh_weather_data", new=AsyncMock()
            ) as mock_refresh,
            patch("accessiweather.handlers.location_handlers.app_helpers") as mock_helpers,
        ):
            mock_dialog = Mock()
            # Dialog returns None when cancelled
            mock_dialog.show_and_wait = AsyncMock(return_value=None)
            mock_dialog_class.return_value = mock_dialog

            await on_add_location_pressed(mock_app, mock_button)

            mock_app.config_manager.set_current_location.assert_not_called()
            mock_helpers.update_location_selection.assert_not_called()
            mock_refresh.assert_not_called()

    @pytest.mark.asyncio
    async def test_add_location_exception(self, mock_app, mock_button):
        """Test exception during location addition."""
        with patch(
            "accessiweather.handlers.location_handlers.AddLocationDialog"
        ) as mock_dialog_class:
            mock_dialog_class.side_effect = Exception("Dialog error")

            await on_add_location_pressed(mock_app, mock_button)

            mock_app.main_window.error_dialog.assert_called_once()
            args = mock_app.main_window.error_dialog.call_args[0]
            assert "Add Location Error" in args
            assert "Failed to open add location dialog" in args[1]

    @pytest.mark.asyncio
    async def test_add_location_logging(self, mock_app, mock_button, caplog):
        """Test logging during location addition."""
        import logging

        caplog.set_level(logging.INFO)

        with (
            patch(
                "accessiweather.handlers.location_handlers.AddLocationDialog"
            ) as mock_dialog_class,
            patch(
                "accessiweather.handlers.location_handlers.refresh_weather_data", new=AsyncMock()
            ),
            patch("accessiweather.handlers.location_handlers.app_helpers"),
        ):
            mock_dialog = Mock()
            # Dialog returns the location name on success
            mock_dialog.show_and_wait = AsyncMock(return_value="Test Location")
            mock_dialog_class.return_value = mock_dialog

            await on_add_location_pressed(mock_app, mock_button)

            assert "Add location menu pressed" in caplog.text
            assert "Location added successfully: Test Location" in caplog.text


class TestOnRemoveLocationPressed:
    """Test on_remove_location_pressed handler."""

    @pytest.mark.asyncio
    async def test_remove_location_success(self, mock_app, mock_button):
        """Test successful location removal."""
        mock_app.config_manager.get_location_names.return_value = ["New York", "Los Angeles"]

        with (
            patch(
                "accessiweather.handlers.location_handlers.show_remove_confirmation_dialog",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "accessiweather.handlers.location_handlers.refresh_weather_data", new=AsyncMock()
            ) as mock_refresh,
            patch("accessiweather.handlers.location_handlers.app_helpers") as mock_helpers,
        ):
            await on_remove_location_pressed(mock_app, mock_button)

            mock_app.config_manager.remove_location.assert_called_once_with("New York")
            mock_helpers.update_location_selection.assert_called_once_with(mock_app)
            mock_refresh.assert_called_once_with(mock_app)

    @pytest.mark.asyncio
    async def test_remove_location_no_selection(self, mock_app, mock_button):
        """Test remove when no location is selected."""
        mock_app.location_selection.value = None

        await on_remove_location_pressed(mock_app, mock_button)

        mock_app.main_window.info_dialog.assert_called_once()
        args = mock_app.main_window.info_dialog.call_args[0]
        assert "No Selection" in args
        assert "Please select a location to remove" in args[1]

    @pytest.mark.asyncio
    async def test_remove_location_last_location(self, mock_app, mock_button):
        """Test remove when it's the last location."""
        mock_app.config_manager.get_location_names.return_value = ["New York"]

        await on_remove_location_pressed(mock_app, mock_button)

        mock_app.main_window.info_dialog.assert_called_once()
        args = mock_app.main_window.info_dialog.call_args[0]
        assert "Cannot Remove" in args
        assert "last location" in args[1]

    @pytest.mark.asyncio
    async def test_remove_location_cancelled(self, mock_app, mock_button):
        """Test cancelled location removal."""
        mock_app.config_manager.get_location_names.return_value = ["New York", "Los Angeles"]

        with (
            patch(
                "accessiweather.handlers.location_handlers.show_remove_confirmation_dialog",
                new=AsyncMock(return_value=False),
            ),
            patch(
                "accessiweather.handlers.location_handlers.refresh_weather_data", new=AsyncMock()
            ) as mock_refresh,
            patch("accessiweather.handlers.location_handlers.app_helpers") as mock_helpers,
        ):
            await on_remove_location_pressed(mock_app, mock_button)

            mock_app.config_manager.remove_location.assert_not_called()
            mock_helpers.update_location_selection.assert_not_called()
            mock_refresh.assert_not_called()

    @pytest.mark.asyncio
    async def test_remove_location_exception(self, mock_app, mock_button):
        """Test exception during location removal."""
        mock_app.config_manager.get_location_names.side_effect = Exception("Config error")

        await on_remove_location_pressed(mock_app, mock_button)

        mock_app.main_window.error_dialog.assert_called_once()
        args = mock_app.main_window.error_dialog.call_args[0]
        assert "Remove Location Error" in args

    @pytest.mark.asyncio
    async def test_remove_location_logging(self, mock_app, mock_button, caplog):
        """Test logging during location removal."""
        import logging

        caplog.set_level(logging.INFO)
        mock_app.config_manager.get_location_names.return_value = ["New York", "Los Angeles"]

        with (
            patch(
                "accessiweather.handlers.location_handlers.show_remove_confirmation_dialog",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "accessiweather.handlers.location_handlers.refresh_weather_data", new=AsyncMock()
            ),
            patch("accessiweather.handlers.location_handlers.app_helpers"),
        ):
            await on_remove_location_pressed(mock_app, mock_button)

            assert "Remove location button pressed" in caplog.text
            assert "Location removed: New York" in caplog.text


class TestShowRemoveConfirmationDialog:
    """Test show_remove_confirmation_dialog function."""

    @pytest.mark.asyncio
    async def test_show_confirmation_confirmed(self, mock_app):
        """Test confirmation dialog when user confirms."""
        mock_app.main_window.question_dialog = AsyncMock(return_value=True)

        result = await show_remove_confirmation_dialog(mock_app, "New York")

        assert result is True
        mock_app.main_window.question_dialog.assert_called_once()
        args = mock_app.main_window.question_dialog.call_args[0]
        assert "Remove Location" in args
        assert "New York" in args[1]

    @pytest.mark.asyncio
    async def test_show_confirmation_cancelled(self, mock_app):
        """Test confirmation dialog when user cancels."""
        mock_app.main_window.question_dialog = AsyncMock(return_value=False)

        result = await show_remove_confirmation_dialog(mock_app, "New York")

        assert result is False

    @pytest.mark.asyncio
    async def test_show_confirmation_exception(self, mock_app):
        """Test confirmation dialog when exception occurs."""
        mock_app.main_window.question_dialog = AsyncMock(side_effect=Exception("Dialog error"))

        result = await show_remove_confirmation_dialog(mock_app, "New York")

        assert result is False
        mock_app.main_window.info_dialog.assert_called_once()
        args = mock_app.main_window.info_dialog.call_args[0]
        assert "Confirmation Error" in args
        assert "cancelled for safety" in args[1]

    @pytest.mark.asyncio
    async def test_show_confirmation_different_location(self, mock_app):
        """Test confirmation dialog with different location name."""
        mock_app.main_window.question_dialog = AsyncMock(return_value=True)

        result = await show_remove_confirmation_dialog(mock_app, "Los Angeles")

        assert result is True
        args = mock_app.main_window.question_dialog.call_args[0]
        assert "Los Angeles" in args[1]
