"""Event handler modules for AccessiWeather."""

from __future__ import annotations

from .alert_handlers import (
    on_alert_details_pressed,
    on_alert_selected,
    on_view_alert_details,
)
from .aviation_handlers import on_view_aviation_pressed
from .location_handlers import (
    on_add_location_pressed,
    on_location_changed,
    on_remove_location_pressed,
    show_remove_confirmation_dialog,
)
from .settings_handlers import (
    on_discussion_pressed,
    on_settings_pressed,
    show_settings_dialog,
)
from .update_handlers import (
    download_update,
    on_about_pressed,
    on_check_updates_pressed,
    on_show_hide_window,
    on_test_notification_pressed,
    on_tray_exit,
    on_tray_refresh,
    on_tray_settings,
    test_alert_notification,
)
from .weather_handlers import (
    convert_alerts_to_table_data,
    notify_new_alerts,
    on_refresh_pressed,
    on_view_weather_history,
    refresh_weather_data,
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
    "on_tray_refresh",
    "on_tray_settings",
    "on_tray_exit",
    "test_alert_notification",
    "on_test_notification_pressed",
]
