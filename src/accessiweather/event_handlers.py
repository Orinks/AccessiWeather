"""
Event handler implementations for AccessiWeather.

This module re-exports handlers from the handlers package for backward
compatibility.
"""

from __future__ import annotations

from .handlers import (
    convert_alerts_to_table_data,
    download_update,
    notify_new_alerts,
    on_about_pressed,
    on_add_location_pressed,
    on_alert_details_pressed,
    on_alert_selected,
    on_check_updates_pressed,
    on_discussion_pressed,
    on_location_changed,
    on_refresh_pressed,
    on_remove_location_pressed,
    on_settings_pressed,
    on_show_hide_window,
    on_test_notification_pressed,
    on_tray_exit,
    on_tray_refresh,
    on_tray_settings,
    on_view_air_quality,
    on_view_alert_details,
    on_view_aviation_pressed,
    on_view_weather_history,
    on_window_show,
    refresh_weather_data,
    show_remove_confirmation_dialog,
    show_settings_dialog,
    test_alert_notification,
    update_weather_displays,
)

__all__ = [
    "on_location_changed",
    "on_add_location_pressed",
    "on_remove_location_pressed",
    "show_remove_confirmation_dialog",
    "on_refresh_pressed",
    "refresh_weather_data",
    "update_weather_displays",
    "convert_alerts_to_table_data",
    "notify_new_alerts",
    "on_view_weather_history",
    "on_view_air_quality",
    "on_settings_pressed",
    "show_settings_dialog",
    "on_discussion_pressed",
    "on_alert_details_pressed",
    "on_alert_selected",
    "on_view_alert_details",
    "on_view_aviation_pressed",
    "on_about_pressed",
    "on_check_updates_pressed",
    "download_update",
    "on_show_hide_window",
    "on_window_show",
    "on_tray_refresh",
    "on_tray_settings",
    "on_tray_exit",
    "test_alert_notification",
    "on_test_notification_pressed",
]
