"""
Timer management functions for AccessiWeatherApp.

Extracted from app.py to reduce module size. All functions take the app
instance as their first argument and operate on its timer attributes.
"""

from __future__ import annotations

import contextlib
import logging
from typing import TYPE_CHECKING

import wx

if TYPE_CHECKING:
    from .app import AccessiWeatherApp

logger = logging.getLogger(__name__)


def stop_auto_update_checks(app: AccessiWeatherApp) -> None:
    """Stop and detach the automatic update-check timer, if present."""
    timer = getattr(app, "_auto_update_check_timer", None)
    if not timer:
        return

    try:
        timer.Stop()
    except Exception as e:
        logger.debug(f"Failed to stop auto-update timer cleanly: {e}")

    # Unbind the old timer source so reconfiguration cannot stack handlers.
    with contextlib.suppress(Exception):
        app.Unbind(wx.EVT_TIMER, source=timer)

    app._auto_update_check_timer = None


def start_auto_update_checks(app: AccessiWeatherApp) -> None:
    """Start periodic automatic update checks based on user settings."""
    try:
        settings = app.config_manager.get_settings()
        auto_enabled = bool(getattr(settings, "auto_update_enabled", True))

        # Stop existing timer before reconfiguring
        stop_auto_update_checks(app)

        if not auto_enabled:
            logger.debug("Automatic update checks disabled")
            return

        interval_hours = max(1, int(getattr(settings, "update_check_interval_hours", 24)))
        interval_ms = interval_hours * 60 * 60 * 1000

        timer = wx.Timer(app)
        app.Bind(wx.EVT_TIMER, app._on_auto_update_check_timer, timer)
        timer.Start(interval_ms)
        app._auto_update_check_timer = timer

        logger.info(
            "Automatic update checks scheduled every %s hour(s)",
            interval_hours,
        )
    except Exception as e:
        logger.warning(f"Failed to start automatic update checks: {e}")


def on_auto_update_check_timer(app: AccessiWeatherApp, event) -> None:
    """Run an automatic update check on timer ticks."""
    app._check_for_updates_on_startup()


def stop_background_updates(app: AccessiWeatherApp) -> None:
    """Stop any running background timers."""
    weather_timer = getattr(app, "_update_timer", None)
    if weather_timer:
        weather_timer.Stop()

    event_timer = getattr(app, "_event_check_timer", None)
    if event_timer:
        event_timer.Stop()


def start_background_updates(app: AccessiWeatherApp) -> None:
    """Start split background timers for full refreshes and lightweight event checks."""
    try:
        from .constants import ALERT_POLL_INTERVAL_SECONDS

        stop_background_updates(app)
        settings = app.config_manager.get_settings()
        interval_minutes = getattr(settings, "update_interval_minutes", 10)
        interval_ms = interval_minutes * 60 * 1000
        event_interval_ms = ALERT_POLL_INTERVAL_SECONDS * 1000

        app._update_timer = wx.Timer()
        app._update_timer.Bind(wx.EVT_TIMER, app._on_background_update)
        app._update_timer.Start(interval_ms)

        app._event_check_timer = wx.Timer()
        app._event_check_timer.Bind(wx.EVT_TIMER, app._on_event_check_update)
        app._event_check_timer.Start(event_interval_ms)

        logger.info(
            "Background updates started (weather every %s minutes, events every %ss)",
            interval_minutes,
            ALERT_POLL_INTERVAL_SECONDS,
        )
    except Exception as e:
        logger.error(f"Failed to start background updates: {e}")


def on_background_update(app: AccessiWeatherApp, event) -> None:
    """Handle slower full weather refresh timer event."""
    if app.main_window and not app.is_updating:
        app.main_window.refresh_weather_async()


def on_event_check_update(app: AccessiWeatherApp, event) -> None:
    """Handle fast lightweight event-check timer event."""
    if app.main_window:
        app.main_window.refresh_notification_events_async()
