"""Tests for aviation-specific handlers and dialog triggers."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from accessiweather.handlers.aviation_handlers import on_view_aviation_pressed


@pytest.mark.asyncio
async def test_on_view_aviation_pressed_launches_dialog():
    app = SimpleNamespace(
        weather_client=object(),
        main_window=MagicMock(),
        aviation_dialog=None,
    )

    dialog_instance = MagicMock()
    dialog_instance.show_and_focus = AsyncMock()

    with patch(
        "accessiweather.handlers.aviation_handlers.AviationDialog",
        return_value=dialog_instance,
    ) as dialog_cls:
        await on_view_aviation_pressed(app, widget=object())

    dialog_cls.assert_called_once_with(app)
    dialog_instance.show_and_focus.assert_awaited_once()
    assert app.aviation_dialog is dialog_instance


@pytest.mark.asyncio
async def test_on_view_aviation_pressed_without_client_shows_message():
    info_dialog = AsyncMock()
    app = SimpleNamespace(
        weather_client=None,
        main_window=SimpleNamespace(info_dialog=info_dialog),
        aviation_dialog=None,
    )

    await on_view_aviation_pressed(app, widget=object())

    info_dialog.assert_awaited_once()


@pytest.mark.asyncio
async def test_aviation_dialog_registers_window_with_app():
    """Test that aviation dialog registers its window with app.windows before showing."""
    import os

    os.environ["TOGA_BACKEND"] = "toga_dummy"

    import toga

    # Create a proper app with window set support
    app = toga.App(
        formal_name="Test App",
        app_id="test.aviation.dialog",
    )
    app.main_window = toga.MainWindow(title="Test")
    app.main_window.content = toga.Box()

    # Simulate the app having a weather client
    app.weather_client = object()

    from accessiweather.dialogs.aviation_dialog import AviationDialog

    dialog = AviationDialog(app)

    # Show the dialog
    await dialog.show_and_focus()

    # Verify the window was registered with the app
    assert dialog.window is not None
    assert dialog.window in app.windows

    # Clean up
    dialog.window.close()
