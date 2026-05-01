"""Accessible alert notification message formatting helpers."""

from __future__ import annotations

import logging

from .constants import MAX_DISPLAYED_AREAS, MAX_NOTIFICATION_DESCRIPTION_LENGTH
from .display.presentation.formatters import format_display_datetime
from .models import AppSettings, WeatherAlert

logger = logging.getLogger(__name__)


def app_settings_debug_summary(settings: AppSettings | None) -> dict[str, object]:
    """Return a compact app-settings snapshot for debug logging."""
    if settings is None:
        return {"present": False}
    return {
        "present": True,
        "alert_notifications_enabled": getattr(settings, "alert_notifications_enabled", None),
        "sound_enabled": getattr(settings, "sound_enabled", None),
        "alert_global_cooldown_minutes": getattr(settings, "alert_global_cooldown_minutes", None),
        "alert_per_alert_cooldown_minutes": getattr(
            settings, "alert_per_alert_cooldown_minutes", None
        ),
        "alert_freshness_window_minutes": getattr(settings, "alert_freshness_window_minutes", None),
        "alert_max_notifications_per_hour": getattr(
            settings, "alert_max_notifications_per_hour", None
        ),
    }


def format_accessible_message(
    alert: WeatherAlert,
    reason: str,
    include_areas: bool = True,
    include_expiration: bool = True,
    settings: AppSettings | None = None,
) -> tuple[str, str]:
    """Format alert information for screen reader accessibility."""
    severity = (alert.severity or "Unknown").upper()
    event = alert.event or "Weather Alert"

    if reason == "escalation":
        title = f"ESCALATED {severity}: {event}"
    elif reason == "content_changed":
        title = f"UPDATED {severity}: {event}"
    elif reason == "reminder":
        title = f"ACTIVE {severity}: {event}"
    else:
        title = f"{severity} ALERT: {event}"

    message_parts = []
    urgency = (alert.urgency or "").lower()
    if urgency in ("immediate", "expected"):
        message_parts.append(f"{urgency.title()} action may be required.")

    headline = alert.headline or alert.title
    if headline:
        message_parts.append(headline)
    else:
        logger.warning(f"Alert {alert.get_unique_id()} missing headline")
        message_parts.append(f"A {severity.lower()} weather alert has been issued.")

    if alert.description:
        desc = alert.description[:MAX_NOTIFICATION_DESCRIPTION_LENGTH]
        if len(alert.description) > MAX_NOTIFICATION_DESCRIPTION_LENGTH:
            desc += "..."
        message_parts.append(desc)

    if include_areas and alert.areas:
        location_parts = alert.areas[:MAX_DISPLAYED_AREAS]
        location_text = ", ".join(location_parts)
        if len(alert.areas) > MAX_DISPLAYED_AREAS:
            location_text += f" and {len(alert.areas) - MAX_DISPLAYED_AREAS} more"
        message_parts.append(f"Areas: {location_text}")

    if include_expiration and alert.expires:
        if settings:
            time_display_mode = getattr(settings, "time_display_mode", "local")
            time_format_12hour = getattr(settings, "time_format_12hour", True)
            show_timezone_suffix = getattr(settings, "show_timezone_suffix", False)
        else:
            time_display_mode = "local"
            time_format_12hour = True
            show_timezone_suffix = False

        expires_str = format_display_datetime(
            alert.expires,
            time_display_mode=time_display_mode,
            use_12hour=time_format_12hour,
            show_timezone=show_timezone_suffix,
            date_format="%b %d",
        )
        message_parts.append(f"Expires: {expires_str}")

    return title, "\n\n".join(message_parts)
