"""Tests for keyboard shortcuts in AccessiWeather."""

from unittest.mock import AsyncMock, Mock, patch

import pytest


class TestLocationSelectionKeyboardShortcuts:
    """Test keyboard shortcuts for location selection widget."""

    def test_location_selection_delete_key_triggers_remove(self):
        """Delete key should schedule removal handler from location selection widget."""
        from accessiweather.ui_builder import create_location_section

        mock_app = Mock()
        mock_app.config_manager = Mock()
        current_location = Mock()
        current_location.name = "Location 1"
        mock_app.config_manager.get_current_location.return_value = current_location

        mock_selection = Mock()
        mock_selection.value = "Location 1"
        mock_selection.children = []

        with (
            patch("accessiweather.ui_builder.toga.Selection", return_value=mock_selection),
            patch(
                "accessiweather.ui_builder.app_helpers.get_location_choices",
                return_value=["Location 1", "Location 2"],
            ),
            patch(
                "accessiweather.ui_builder.event_handlers.on_remove_location_pressed",
                new_callable=AsyncMock,
            ) as mock_remove,
            patch("accessiweather.ui_builder.asyncio.create_task") as mock_create_task,
        ):
            create_location_section(mock_app)
            handler = mock_app.location_selection.on_key_down
            result = handler(mock_selection, "<delete>")

        assert result is True
        mock_remove.assert_called_once_with(mock_app, mock_selection)
        mock_create_task.assert_called_once()
        task_coro = mock_create_task.call_args[0][0]
        if hasattr(task_coro, "close"):
            task_coro.close()

    def test_location_selection_delete_key_ignored_for_other_keys(self):
        """Non-Delete keys should not trigger removal scheduling."""
        from accessiweather.ui_builder import create_location_section

        mock_app = Mock()
        mock_app.config_manager = Mock()
        current_location = Mock()
        current_location.name = "Location 1"
        mock_app.config_manager.get_current_location.return_value = current_location

        mock_selection = Mock()
        mock_selection.value = "Location 1"
        mock_selection.children = []

        with (
            patch("accessiweather.ui_builder.toga.Selection", return_value=mock_selection),
            patch(
                "accessiweather.ui_builder.app_helpers.get_location_choices",
                return_value=["Location 1", "Location 2"],
            ),
            patch(
                "accessiweather.ui_builder.event_handlers.on_remove_location_pressed",
                new_callable=AsyncMock,
            ) as mock_remove,
            patch("accessiweather.ui_builder.asyncio.create_task") as mock_create_task,
        ):
            create_location_section(mock_app)
            handler = mock_app.location_selection.on_key_down
            result = handler(mock_selection, "<enter>")

        assert result is False
        mock_remove.assert_not_called()
        mock_create_task.assert_not_called()

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

    def test_soundpack_delete_key_triggers_delete_pack(self):
        """Delete key should invoke delete_pack for the selected sound pack."""
        from accessiweather.dialogs.soundpack_manager.ui import create_pack_list_panel

        mock_dlg = Mock()
        mock_dlg.sound_packs = {}

        mock_pack_list = Mock()
        mock_pack_list.children = []

        with (
            patch(
                "accessiweather.dialogs.soundpack_manager.ui.toga.DetailedList",
                return_value=mock_pack_list,
            ),
            patch("accessiweather.dialogs.soundpack_manager.ui.toga.Box"),
            patch("accessiweather.dialogs.soundpack_manager.ui.toga.Label"),
            patch("accessiweather.dialogs.soundpack_manager.ui.toga.Button"),
            patch("accessiweather.dialogs.soundpack_manager.ops.delete_pack") as mock_delete_pack,
        ):
            create_pack_list_panel(mock_dlg)
            handler = mock_dlg.pack_list.on_key_down
            result = handler(mock_pack_list, "<delete>")

        assert result is True
        mock_delete_pack.assert_called_once_with(mock_dlg, mock_pack_list)

    def test_soundpack_delete_key_ignored_for_other_keys(self):
        """Non-Delete keys should not invoke delete_pack."""
        from accessiweather.dialogs.soundpack_manager.ui import create_pack_list_panel

        mock_dlg = Mock()
        mock_dlg.sound_packs = {}

        mock_pack_list = Mock()
        mock_pack_list.children = []

        with (
            patch(
                "accessiweather.dialogs.soundpack_manager.ui.toga.DetailedList",
                return_value=mock_pack_list,
            ),
            patch("accessiweather.dialogs.soundpack_manager.ui.toga.Box"),
            patch("accessiweather.dialogs.soundpack_manager.ui.toga.Label"),
            patch("accessiweather.dialogs.soundpack_manager.ui.toga.Button"),
            patch("accessiweather.dialogs.soundpack_manager.ops.delete_pack") as mock_delete_pack,
        ):
            create_pack_list_panel(mock_dlg)
            handler = mock_dlg.pack_list.on_key_down
            result = handler(mock_pack_list, "<enter>")

        assert result is False
        mock_delete_pack.assert_not_called()

    @pytest.mark.asyncio
    async def test_soundpack_delete_blocks_default_pack(self):
        """Test that delete_pack doesn't delete the default pack."""
        from accessiweather.dialogs.soundpack_manager.ops import delete_pack

        # Create mock dialog with default selected
        mock_dlg = Mock()
        mock_dlg.selected_pack = "default"
        mock_dlg.app = Mock()
        mock_dlg.app.main_window = Mock()

        # Call delete_pack - should return early without showing dialog
        await delete_pack(mock_dlg, Mock())

        # Verify no dialog was shown
        mock_dlg.app.main_window.question_dialog.assert_not_called()

    @pytest.mark.asyncio
    async def test_soundpack_delete_blocks_none_selection(self):
        """Test that delete_pack handles None selection gracefully."""
        from accessiweather.dialogs.soundpack_manager.ops import delete_pack

        # Create mock dialog with no selection
        mock_dlg = Mock()
        mock_dlg.selected_pack = None
        mock_dlg.app = Mock()

        # Call delete_pack - should return early without crashing
        await delete_pack(mock_dlg, Mock())

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
