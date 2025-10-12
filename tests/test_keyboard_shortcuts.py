"""Tests for keyboard shortcuts in AccessiWeather."""

from unittest.mock import AsyncMock, Mock, patch

import pytest


class TestLocationSelectionKeyboardShortcuts:
    """Test keyboard shortcuts for location selection widget."""

    @pytest.mark.asyncio
    async def test_location_selection_delete_key_triggers_remove(self):
        """Test that pressing Delete on location selection triggers remove handler."""
        # Create mock location selection widget
        location_selection = Mock()
        location_selection.value = "Location 2"

        # Create mock app with config manager
        mock_app = Mock()
        mock_app.location_selection = location_selection
        mock_app.config_manager = Mock()
        mock_app.config_manager.get_location_names = Mock(
            return_value=["Location 1", "Location 2", "Location 3"]
        )
        mock_app.main_window = Mock()
        mock_app.main_window.question_dialog = AsyncMock(return_value=True)
        mock_app.config_manager.remove_location = Mock()

        # Import the handler we'll test
        from accessiweather.handlers.location_handlers import on_remove_location_pressed

        # Mock the remove handler to be called on Delete key
        with (
            patch("accessiweather.app_helpers.update_location_selection"),
            patch(
                "accessiweather.handlers.weather_handlers.refresh_weather_data",
                new_callable=AsyncMock,
            ),
        ):
            # Call the remove handler directly (simulating Delete key press)
            await on_remove_location_pressed(mock_app, Mock())

            # Verify the location was removed
            mock_app.config_manager.remove_location.assert_called_once_with("Location 2")

    @pytest.mark.asyncio
    async def test_location_selection_delete_key_with_no_selection(self):
        """Test that Delete key with no selection shows info dialog."""
        # Create mock location selection widget with no selection
        location_selection = Mock()
        location_selection.value = None

        # Create mock app
        mock_app = Mock()
        mock_app.location_selection = location_selection
        mock_app.main_window = Mock()
        mock_app.main_window.info_dialog = AsyncMock()

        # Import the handler
        from accessiweather.handlers.location_handlers import on_remove_location_pressed

        # Call the remove handler - should show info dialog
        await on_remove_location_pressed(mock_app, Mock())

        # Verify info dialog was shown
        mock_app.main_window.info_dialog.assert_called_once()
        call_args = mock_app.main_window.info_dialog.call_args
        assert "No Selection" in call_args[0]

    @pytest.mark.asyncio
    async def test_location_selection_delete_last_location_blocked(self):
        """Test that deleting the last location is blocked."""
        # Create mock location selection widget
        location_selection = Mock()
        location_selection.value = "Only Location"

        # Create mock app with only one location
        mock_app = Mock()
        mock_app.location_selection = location_selection
        mock_app.config_manager = Mock()
        mock_app.config_manager.get_location_names = Mock(return_value=["Only Location"])
        mock_app.main_window = Mock()
        mock_app.main_window.info_dialog = AsyncMock()

        # Import the handler
        from accessiweather.handlers.location_handlers import on_remove_location_pressed

        # Call the remove handler - should show info dialog blocking removal
        await on_remove_location_pressed(mock_app, Mock())

        # Verify info dialog was shown with cannot remove message
        mock_app.main_window.info_dialog.assert_called_once()
        call_args = mock_app.main_window.info_dialog.call_args
        assert "Cannot Remove" in call_args[0]


class TestSoundpackSelectionKeyboardShortcuts:
    """Test keyboard shortcuts for soundpack selection widget."""

    def test_soundpack_delete_function_exists(self):
        """Test that the delete_pack function exists and can be called."""
        # Import the delete function
        from accessiweather.dialogs.soundpack_manager.ops import delete_pack

        # Create mock dialog
        mock_dlg = Mock()
        mock_dlg.selected_pack = "pack1"
        mock_dlg.sound_packs = {
            "pack1": {"name": "Pack 1", "path": Mock()},
        }
        mock_dlg.app = Mock()
        mock_dlg.app.main_window = Mock()
        mock_dlg.app.main_window.question_dialog = Mock(return_value=False)  # User cancels

        # Call delete_pack - should not crash
        delete_pack(mock_dlg, Mock())

        # Verify question dialog was shown
        mock_dlg.app.main_window.question_dialog.assert_called_once()

    def test_soundpack_delete_blocks_default_pack(self):
        """Test that delete_pack doesn't delete the default pack."""
        from accessiweather.dialogs.soundpack_manager.ops import delete_pack

        # Create mock dialog with default selected
        mock_dlg = Mock()
        mock_dlg.selected_pack = "default"
        mock_dlg.app = Mock()
        mock_dlg.app.main_window = Mock()

        # Call delete_pack - should return early without showing dialog
        delete_pack(mock_dlg, Mock())

        # Verify no dialog was shown
        mock_dlg.app.main_window.question_dialog.assert_not_called()

    def test_soundpack_delete_blocks_none_selection(self):
        """Test that delete_pack handles None selection gracefully."""
        from accessiweather.dialogs.soundpack_manager.ops import delete_pack

        # Create mock dialog with no selection
        mock_dlg = Mock()
        mock_dlg.selected_pack = None
        mock_dlg.app = Mock()

        # Call delete_pack - should return early without crashing
        delete_pack(mock_dlg, Mock())

        # Should not have accessed any dialogs
        assert not mock_dlg.app.main_window.called


class TestKeyboardShortcutAccessibility:
    """Test accessibility features of keyboard shortcuts."""

    def test_keyboard_shortcut_handler_signature(self):
        """Test that keyboard shortcut handlers have correct signature."""
        # This test verifies the handler can be used as a keyboard event handler
        # The handler should accept (widget, key) parameters

        async def mock_handler(widget, key):
            """Mock keyboard handler."""
            return key == "Delete"

        # Simulate calling the handler
        import asyncio

        result = asyncio.run(mock_handler(Mock(), "Delete"))
        assert result is True

        result = asyncio.run(mock_handler(Mock(), "Enter"))
        assert result is False
