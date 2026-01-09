"""Unit tests for settings dialog export/import UI handlers."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Set up toga-dummy backend for testing
os.environ["TOGA_BACKEND"] = "toga_dummy"

from accessiweather.dialogs import settings_operations


class FakeDialog:
    """Fake dialog for testing UI handlers."""

    def __init__(self, config_manager=None):
        """Set up minimal fake dialog state for handler tests."""
        self.config_manager = config_manager or MagicMock()
        self.current_settings = MagicMock()
        self.window = MagicMock()
        self.app = MagicMock()
        self.app.main_window = MagicMock()

        # Track errors and dialog calls
        self.errors: list[tuple[str, str]] = []
        self.dialog_calls: list[tuple[str, tuple]] = []
        self.focus_calls = 0

        # Mock status label
        self.update_status_label = MagicMock()
        self.update_status_label.text = ""

    def _ensure_dialog_focus(self) -> None:
        """Track focus restoration calls."""
        self.focus_calls += 1

    async def _show_dialog_error(self, title: str, message: str) -> None:
        """Track error dialogs."""
        self.errors.append((title, message))


async def _fake_call_dialog_method(dialog, method_name, *args, **kwargs):
    """Mock _call_dialog_method to track dialog calls."""
    dialog.dialog_calls.append((method_name, args, kwargs))
    # Return value based on method type
    if method_name == "save_file_dialog" or method_name == "open_file_dialog":
        return kwargs.get("return_value")
    if method_name == "confirm_dialog":
        return kwargs.get("return_value", True)
    if method_name == "info_dialog":
        return None
    return None


class TestExportSettingsHandler:
    """Test export settings UI handler."""

    @pytest.mark.asyncio
    async def test_export_opens_save_dialog(self, monkeypatch):
        """Test export handler opens save dialog with correct parameters."""
        dialog = FakeDialog()

        # Mock _call_dialog_method to track save dialog call
        async def mock_call_dialog(dlg, method_name, *args, **kwargs):
            dlg.dialog_calls.append((method_name, args, kwargs))
            return  # User cancelled

        monkeypatch.setattr(settings_operations, "_call_dialog_method", mock_call_dialog)

        await settings_operations.export_settings(dialog)

        # Verify save_file_dialog was called
        assert len(dialog.dialog_calls) > 0
        method_name, args, kwargs = dialog.dialog_calls[0]
        assert method_name == "save_file_dialog"
        assert "suggested_filename" in kwargs
        assert "accessiweather_settings" in kwargs["suggested_filename"]
        assert ".json" in kwargs["suggested_filename"]
        assert kwargs.get("file_types") == ["json"]

    @pytest.mark.asyncio
    async def test_export_calls_export_settings_with_correct_path(self, monkeypatch, tmp_path):
        """Test export handler calls config_manager.export_settings() with correct path."""
        mock_config_manager = MagicMock()
        mock_config_manager.export_settings.return_value = True
        dialog = FakeDialog(config_manager=mock_config_manager)

        export_path = tmp_path / "test_settings.json"

        # Mock _call_dialog_method to return path
        async def mock_call_dialog(dlg, method_name, *args, **kwargs):
            if method_name == "save_file_dialog":
                return str(export_path)
            dlg.dialog_calls.append((method_name, args, kwargs))
            return None

        monkeypatch.setattr(settings_operations, "_call_dialog_method", mock_call_dialog)

        await settings_operations.export_settings(dialog)

        # Verify export_settings was called with correct path
        mock_config_manager.export_settings.assert_called_once()
        call_args = mock_config_manager.export_settings.call_args[0]
        assert Path(call_args[0]) == export_path

    @pytest.mark.asyncio
    async def test_export_ensures_json_extension(self, monkeypatch, tmp_path):
        """Test export handler ensures .json extension on path."""
        mock_config_manager = MagicMock()
        mock_config_manager.export_settings.return_value = True
        dialog = FakeDialog(config_manager=mock_config_manager)

        # Path without .json extension
        export_path = tmp_path / "test_settings"

        async def mock_call_dialog(dlg, method_name, *args, **kwargs):
            if method_name == "save_file_dialog":
                return str(export_path)
            dlg.dialog_calls.append((method_name, args, kwargs))
            return None

        monkeypatch.setattr(settings_operations, "_call_dialog_method", mock_call_dialog)

        await settings_operations.export_settings(dialog)

        # Verify export_settings was called with .json extension
        mock_config_manager.export_settings.assert_called_once()
        call_args = mock_config_manager.export_settings.call_args[0]
        assert Path(call_args[0]).suffix == ".json"

    @pytest.mark.asyncio
    async def test_export_shows_success_message(self, monkeypatch, tmp_path):
        """Test export handler shows success message on successful export."""
        mock_config_manager = MagicMock()
        mock_config_manager.export_settings.return_value = True
        dialog = FakeDialog(config_manager=mock_config_manager)

        export_path = tmp_path / "test_settings.json"

        async def mock_call_dialog(dlg, method_name, *args, **kwargs):
            if method_name == "save_file_dialog":
                return str(export_path)
            dlg.dialog_calls.append((method_name, args, kwargs))
            return None

        monkeypatch.setattr(settings_operations, "_call_dialog_method", mock_call_dialog)

        await settings_operations.export_settings(dialog)

        # Verify success message was shown
        assert len(dialog.dialog_calls) > 0
        # Find info_dialog call
        info_dialogs = [call for call in dialog.dialog_calls if call[0] == "info_dialog"]
        assert len(info_dialogs) == 1
        method_name, args, kwargs = info_dialogs[0]
        assert "Export Successful" in args
        # Check path is in message (normalize for Windows path separators)
        path_str = str(export_path)
        args_str = str(args)
        assert path_str in args_str or path_str.replace("\\", "\\\\") in args_str
        assert "API keys" in str(args)  # Should mention API keys exclusion

    @pytest.mark.asyncio
    async def test_export_shows_error_message_on_failure(self, monkeypatch, tmp_path):
        """Test export handler shows error message on export failure."""
        mock_config_manager = MagicMock()
        mock_config_manager.export_settings.return_value = False
        dialog = FakeDialog(config_manager=mock_config_manager)

        export_path = tmp_path / "test_settings.json"

        async def mock_call_dialog(dlg, method_name, *args, **kwargs):
            if method_name == "save_file_dialog":
                return str(export_path)
            return None

        monkeypatch.setattr(settings_operations, "_call_dialog_method", mock_call_dialog)

        await settings_operations.export_settings(dialog)

        # Verify error dialog was shown
        assert len(dialog.errors) == 1
        title, message = dialog.errors[0]
        assert title == "Export Failed"
        assert str(export_path) in message

    @pytest.mark.asyncio
    async def test_export_handles_cancelled_dialog(self, monkeypatch):
        """Test export handler handles cancelled save dialog gracefully."""
        dialog = FakeDialog()

        # Mock _call_dialog_method to return None (cancelled)
        async def mock_call_dialog(dlg, method_name, *args, **kwargs):
            if method_name == "save_file_dialog":
                return
            return

        monkeypatch.setattr(settings_operations, "_call_dialog_method", mock_call_dialog)

        await settings_operations.export_settings(dialog)

        # Verify no errors were raised and no config methods were called
        assert len(dialog.errors) == 0
        dialog.config_manager.export_settings.assert_not_called()

    @pytest.mark.asyncio
    async def test_export_handles_exception(self, monkeypatch, tmp_path):
        """Test export handler handles exceptions gracefully."""
        mock_config_manager = MagicMock()
        mock_config_manager.export_settings.side_effect = Exception("Unexpected error")
        dialog = FakeDialog(config_manager=mock_config_manager)

        export_path = tmp_path / "test_settings.json"

        async def mock_call_dialog(dlg, method_name, *args, **kwargs):
            if method_name == "save_file_dialog":
                return str(export_path)
            return None

        monkeypatch.setattr(settings_operations, "_call_dialog_method", mock_call_dialog)

        await settings_operations.export_settings(dialog)

        # Verify error dialog was shown
        assert len(dialog.errors) == 1
        title, message = dialog.errors[0]
        assert "Export Error" in title or "Export Failed" in title

    @pytest.mark.asyncio
    async def test_export_restores_focus(self, monkeypatch, tmp_path):
        """Test export handler restores dialog focus."""
        mock_config_manager = MagicMock()
        mock_config_manager.export_settings.return_value = True
        dialog = FakeDialog(config_manager=mock_config_manager)

        export_path = tmp_path / "test_settings.json"

        async def mock_call_dialog(dlg, method_name, *args, **kwargs):
            if method_name == "save_file_dialog":
                return str(export_path)
            dlg.dialog_calls.append((method_name, args, kwargs))
            return None

        monkeypatch.setattr(settings_operations, "_call_dialog_method", mock_call_dialog)

        await settings_operations.export_settings(dialog)

        # Verify focus was restored at least once
        assert dialog.focus_calls > 0


class TestImportSettingsHandler:
    """Test import settings UI handler."""

    @pytest.mark.asyncio
    async def test_import_shows_confirmation_dialog(self, monkeypatch):
        """Test import handler shows confirmation dialog before importing."""
        dialog = FakeDialog()

        # Mock _call_dialog_method to track confirm dialog call
        async def mock_call_dialog(dlg, method_name, *args, **kwargs):
            dlg.dialog_calls.append((method_name, args, kwargs))
            if method_name == "confirm_dialog":
                return False  # User declined
            return None

        monkeypatch.setattr(settings_operations, "_call_dialog_method", mock_call_dialog)

        await settings_operations.import_settings(dialog)

        # Verify confirm_dialog was called
        confirm_dialogs = [call for call in dialog.dialog_calls if call[0] == "confirm_dialog"]
        assert len(confirm_dialogs) == 1
        method_name, args, kwargs = confirm_dialogs[0]
        assert "Import Settings" in args
        assert "overwrite" in str(args).lower()
        assert "locations" in str(args).lower()

    @pytest.mark.asyncio
    async def test_import_opens_file_dialog(self, monkeypatch, tmp_path):
        """Test import handler opens file open dialog with correct parameters."""
        dialog = FakeDialog()

        # Mock _call_dialog_method to track open dialog call
        async def mock_call_dialog(dlg, method_name, *args, **kwargs):
            dlg.dialog_calls.append((method_name, args, kwargs))
            if method_name == "confirm_dialog":
                return True  # User confirmed
            if method_name == "open_file_dialog":
                return None  # User cancelled
            return None

        monkeypatch.setattr(settings_operations, "_call_dialog_method", mock_call_dialog)

        await settings_operations.import_settings(dialog)

        # Verify open_file_dialog was called
        open_dialogs = [call for call in dialog.dialog_calls if call[0] == "open_file_dialog"]
        assert len(open_dialogs) == 1
        method_name, args, kwargs = open_dialogs[0]
        assert "Import Settings" in args
        assert kwargs.get("file_types") == ["json"]

    @pytest.mark.asyncio
    async def test_import_calls_import_settings_with_correct_path(self, monkeypatch, tmp_path):
        """Test import handler calls config_manager.import_settings() with correct path."""
        mock_config_manager = MagicMock()
        mock_config_manager.import_settings.return_value = True
        mock_config_manager.get_settings.return_value = MagicMock()
        dialog = FakeDialog(config_manager=mock_config_manager)

        import_path = tmp_path / "test_settings.json"
        import_path.write_text('{"settings": {}}')

        # Mock _call_dialog_method
        async def mock_call_dialog(dlg, method_name, *args, **kwargs):
            if method_name == "confirm_dialog":
                return True
            if method_name == "open_file_dialog":
                return str(import_path)
            dlg.dialog_calls.append((method_name, args, kwargs))
            return None

        monkeypatch.setattr(settings_operations, "_call_dialog_method", mock_call_dialog)
        monkeypatch.setattr(
            "accessiweather.dialogs.settings_handlers.apply_settings_to_ui", MagicMock()
        )

        await settings_operations.import_settings(dialog)

        # Verify import_settings was called with correct path
        mock_config_manager.import_settings.assert_called_once()
        call_args = mock_config_manager.import_settings.call_args[0]
        assert Path(call_args[0]) == import_path

    @pytest.mark.asyncio
    async def test_import_reloads_ui_after_success(self, monkeypatch, tmp_path):
        """Test import handler reloads UI after successful import."""
        mock_config_manager = MagicMock()
        mock_config_manager.import_settings.return_value = True
        mock_settings = MagicMock()
        mock_config_manager.get_settings.return_value = mock_settings
        dialog = FakeDialog(config_manager=mock_config_manager)

        import_path = tmp_path / "test_settings.json"
        import_path.write_text('{"settings": {}}')

        async def mock_call_dialog(dlg, method_name, *args, **kwargs):
            if method_name == "confirm_dialog":
                return True
            if method_name == "open_file_dialog":
                return str(import_path)
            dlg.dialog_calls.append((method_name, args, kwargs))
            return None

        mock_apply_settings = MagicMock()
        monkeypatch.setattr(settings_operations, "_call_dialog_method", mock_call_dialog)
        monkeypatch.setattr(
            "accessiweather.dialogs.settings_handlers.apply_settings_to_ui", mock_apply_settings
        )

        await settings_operations.import_settings(dialog)

        # Verify settings were reloaded
        assert dialog.current_settings == mock_settings
        # Verify apply_settings_to_ui was called
        mock_apply_settings.assert_called_once_with(dialog)

    @pytest.mark.asyncio
    async def test_import_shows_success_message(self, monkeypatch, tmp_path):
        """Test import handler shows success message on successful import."""
        mock_config_manager = MagicMock()
        mock_config_manager.import_settings.return_value = True
        mock_config_manager.get_settings.return_value = MagicMock()
        dialog = FakeDialog(config_manager=mock_config_manager)

        import_path = tmp_path / "test_settings.json"
        import_path.write_text('{"settings": {}}')

        async def mock_call_dialog(dlg, method_name, *args, **kwargs):
            if method_name == "confirm_dialog":
                return True
            if method_name == "open_file_dialog":
                return str(import_path)
            dlg.dialog_calls.append((method_name, args, kwargs))
            return None

        monkeypatch.setattr(settings_operations, "_call_dialog_method", mock_call_dialog)
        monkeypatch.setattr(
            "accessiweather.dialogs.settings_handlers.apply_settings_to_ui", MagicMock()
        )

        await settings_operations.import_settings(dialog)

        # Verify success message was shown
        info_dialogs = [call for call in dialog.dialog_calls if call[0] == "info_dialog"]
        assert len(info_dialogs) == 1
        method_name, args, kwargs = info_dialogs[0]
        assert "Import Successful" in args
        # Check path is in message (normalize for Windows path separators)
        path_str = str(import_path)
        args_str = str(args)
        assert path_str in args_str or path_str.replace("\\", "\\\\") in args_str
        assert "API keys" in str(args)  # Should mention API keys exclusion

    @pytest.mark.asyncio
    async def test_import_shows_error_message_on_failure(self, monkeypatch, tmp_path):
        """Test import handler shows error message on import failure."""
        mock_config_manager = MagicMock()
        mock_config_manager.import_settings.return_value = False
        dialog = FakeDialog(config_manager=mock_config_manager)

        import_path = tmp_path / "test_settings.json"
        import_path.write_text('{"settings": {}}')

        async def mock_call_dialog(dlg, method_name, *args, **kwargs):
            if method_name == "confirm_dialog":
                return True
            if method_name == "open_file_dialog":
                return str(import_path)
            return None

        monkeypatch.setattr(settings_operations, "_call_dialog_method", mock_call_dialog)

        await settings_operations.import_settings(dialog)

        # Verify error dialog was shown
        assert len(dialog.errors) == 1
        title, message = dialog.errors[0]
        assert title == "Import Failed"
        assert str(import_path) in message

    @pytest.mark.asyncio
    async def test_import_validates_file_exists(self, monkeypatch, tmp_path):
        """Test import handler validates that selected file exists."""
        dialog = FakeDialog()

        import_path = tmp_path / "nonexistent.json"

        async def mock_call_dialog(dlg, method_name, *args, **kwargs):
            if method_name == "confirm_dialog":
                return True
            if method_name == "open_file_dialog":
                return str(import_path)
            return None

        monkeypatch.setattr(settings_operations, "_call_dialog_method", mock_call_dialog)

        await settings_operations.import_settings(dialog)

        # Verify error was shown for non-existent file
        assert len(dialog.errors) == 1
        title, message = dialog.errors[0]
        assert title == "Import Failed"
        assert "does not exist" in message

    @pytest.mark.asyncio
    async def test_import_validates_json_extension(self, monkeypatch, tmp_path):
        """Test import handler validates file has .json extension."""
        dialog = FakeDialog()

        import_path = tmp_path / "test_settings.txt"
        import_path.write_text("not json")

        async def mock_call_dialog(dlg, method_name, *args, **kwargs):
            if method_name == "confirm_dialog":
                return True
            if method_name == "open_file_dialog":
                return str(import_path)
            return None

        monkeypatch.setattr(settings_operations, "_call_dialog_method", mock_call_dialog)

        await settings_operations.import_settings(dialog)

        # Verify error was shown for wrong extension
        assert len(dialog.errors) == 1
        title, message = dialog.errors[0]
        assert title == "Import Failed"
        assert ".json" in message

    @pytest.mark.asyncio
    async def test_import_handles_cancelled_confirmation(self, monkeypatch):
        """Test import handler handles cancelled confirmation dialog."""
        dialog = FakeDialog()

        async def mock_call_dialog(dlg, method_name, *args, **kwargs):
            if method_name == "confirm_dialog":
                return False  # User cancelled
            return None

        monkeypatch.setattr(settings_operations, "_call_dialog_method", mock_call_dialog)

        await settings_operations.import_settings(dialog)

        # Verify no file dialog was opened and no import was attempted
        dialog.config_manager.import_settings.assert_not_called()

    @pytest.mark.asyncio
    async def test_import_handles_cancelled_file_dialog(self, monkeypatch):
        """Test import handler handles cancelled file dialog."""
        dialog = FakeDialog()

        async def mock_call_dialog(dlg, method_name, *args, **kwargs):
            if method_name == "confirm_dialog":
                return True
            if method_name == "open_file_dialog":
                return None  # User cancelled
            return None

        monkeypatch.setattr(settings_operations, "_call_dialog_method", mock_call_dialog)

        await settings_operations.import_settings(dialog)

        # Verify no import was attempted
        dialog.config_manager.import_settings.assert_not_called()

    @pytest.mark.asyncio
    async def test_import_handles_exception(self, monkeypatch, tmp_path):
        """Test import handler handles exceptions gracefully."""
        mock_config_manager = MagicMock()
        mock_config_manager.import_settings.side_effect = Exception("Unexpected error")
        dialog = FakeDialog(config_manager=mock_config_manager)

        import_path = tmp_path / "test_settings.json"
        import_path.write_text('{"settings": {}}')

        async def mock_call_dialog(dlg, method_name, *args, **kwargs):
            if method_name == "confirm_dialog":
                return True
            if method_name == "open_file_dialog":
                return str(import_path)
            return None

        monkeypatch.setattr(settings_operations, "_call_dialog_method", mock_call_dialog)

        await settings_operations.import_settings(dialog)

        # Verify error dialog was shown
        assert len(dialog.errors) == 1
        title, message = dialog.errors[0]
        assert "Import Error" in title or "Import Failed" in title

    @pytest.mark.asyncio
    async def test_import_updates_status_label(self, monkeypatch, tmp_path):
        """Test import handler updates status label on success."""
        mock_config_manager = MagicMock()
        mock_config_manager.import_settings.return_value = True
        mock_config_manager.get_settings.return_value = MagicMock()
        dialog = FakeDialog(config_manager=mock_config_manager)

        import_path = tmp_path / "test_settings.json"
        import_path.write_text('{"settings": {}}')

        async def mock_call_dialog(dlg, method_name, *args, **kwargs):
            if method_name == "confirm_dialog":
                return True
            if method_name == "open_file_dialog":
                return str(import_path)
            dlg.dialog_calls.append((method_name, args, kwargs))
            return None

        monkeypatch.setattr(settings_operations, "_call_dialog_method", mock_call_dialog)
        monkeypatch.setattr(
            "accessiweather.dialogs.settings_handlers.apply_settings_to_ui", MagicMock()
        )

        await settings_operations.import_settings(dialog)

        # Verify status label was updated
        assert dialog.update_status_label.text == "Settings were imported successfully"

    @pytest.mark.asyncio
    async def test_import_restores_focus(self, monkeypatch, tmp_path):
        """Test import handler restores dialog focus."""
        mock_config_manager = MagicMock()
        mock_config_manager.import_settings.return_value = True
        mock_config_manager.get_settings.return_value = MagicMock()
        dialog = FakeDialog(config_manager=mock_config_manager)

        import_path = tmp_path / "test_settings.json"
        import_path.write_text('{"settings": {}}')

        async def mock_call_dialog(dlg, method_name, *args, **kwargs):
            if method_name == "confirm_dialog":
                return True
            if method_name == "open_file_dialog":
                return str(import_path)
            dlg.dialog_calls.append((method_name, args, kwargs))
            return None

        monkeypatch.setattr(settings_operations, "_call_dialog_method", mock_call_dialog)
        monkeypatch.setattr(
            "accessiweather.dialogs.settings_handlers.apply_settings_to_ui", MagicMock()
        )

        await settings_operations.import_settings(dialog)

        # Verify focus was restored at least once
        assert dialog.focus_calls > 0
