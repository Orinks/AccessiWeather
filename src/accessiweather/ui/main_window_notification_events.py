"""Notification event fetch helpers for :mod:`accessiweather.ui.main_window`."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import wx

if TYPE_CHECKING:
    from .main_window import MainWindow

logger = logging.getLogger(__name__)


def refresh_notification_events_async(window: MainWindow) -> None:
    """Run a lightweight event check without refreshing the full weather UI."""
    if window.app.is_updating:
        logger.debug("Skipping event check while full weather refresh is in progress")
        return
    window.app.run_async(fetch_notification_event_data(window))


async def fetch_notification_event_data(window: MainWindow) -> None:
    """Fetch only the lightweight data needed for notifications."""
    try:
        location = window.app.config_manager.get_current_location()
        if not location or location.name == "Nationwide":
            return

        weather_data = await window.app.weather_client.get_notification_event_data(location)
        wx.CallAfter(window._on_notification_event_data_received, weather_data)
    except Exception as e:
        logger.debug(f"Failed to fetch lightweight notification data: {e}")
