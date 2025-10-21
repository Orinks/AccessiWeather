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
