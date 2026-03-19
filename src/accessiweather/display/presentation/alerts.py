"""Builders for weather alert presentations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...models import AppSettings, Location, WeatherAlert, WeatherAlerts
from ..weather_presenter import AlertPresentation, AlertsPresentation
from .formatters import format_display_datetime, truncate, wrap_text

if TYPE_CHECKING:
    from accessiweather.alert_lifecycle import AlertLifecycleDiff


def _is_pirate_weather_alert(alert: WeatherAlert) -> bool:
    """Return True when the alert originated from Pirate Weather / WMO."""
    return "pirateweather" in (alert.source or "").strip().lower()


def build_alerts(
    alerts: WeatherAlerts,
    location: Location,
    settings: AppSettings | None = None,
    *,
    lifecycle_diff: AlertLifecycleDiff | None = None,
    lifecycle_states: dict[str, str] | None = None,
) -> AlertsPresentation:
    """
    Create an alerts presentation for a given location.

    Args:
        alerts: Current weather alerts snapshot.
        location: Location being presented.
        settings: Optional app settings for time formatting.
        lifecycle_diff: Optional diff from the previous alert snapshot.
            When provided and has changes, a concise change summary is
            prepended to the fallback text and stored on the presentation.
        lifecycle_states: Optional mapping of alert_id to label (e.g.
            {"alert-1": "New", "alert-2": "Extended"}).  When provided,
            labels are appended to each alert's header line in the
            presentation (e.g. "Alert 1: Dense Fog Advisory (Extended)").

    """
    title = f"Weather alerts for {location.name}"
    if not alerts.has_alerts():
        return AlertsPresentation(title=title, fallback_text=f"{title}:\nNo active weather alerts.")

    active = alerts.get_active_alerts()
    if not active:
        return AlertsPresentation(title=title, fallback_text=f"{title}:\nNo active weather alerts.")

    presentations: list[AlertPresentation] = []
    fallback_lines = [title + ":"]

    for idx, alert in enumerate(active, start=1):
        lifecycle_label: str | None = None
        if lifecycle_states:
            alert_id = alert.get_unique_id()
            lifecycle_label = lifecycle_states.get(alert_id)
        presentation = build_single_alert(alert, idx, settings, lifecycle_label=lifecycle_label)
        presentations.append(presentation)
        fallback_lines.append(presentation.fallback_text)

    fallback_text = "\n\n".join(fallback_lines)

    change_summary: str | None = None
    if lifecycle_diff is not None and lifecycle_diff.has_changes:
        change_summary = lifecycle_diff.summary
        fallback_text = f"Alert changes: {lifecycle_diff.summary}\n{fallback_text}"

    return AlertsPresentation(
        title=title,
        alerts=presentations,
        fallback_text=fallback_text,
        change_summary=change_summary,
    )


def build_single_alert(
    alert: WeatherAlert,
    index: int,
    settings: AppSettings | None = None,
    *,
    lifecycle_label: str | None = None,
) -> AlertPresentation:
    """
    Create a single alert presentation with truncated text for readability.

    Args:
        alert: The weather alert to present.
        index: 1-based display index.
        settings: Optional app settings for time formatting.
        lifecycle_label: Optional lifecycle status label (e.g. "New", "Updated",
            "Escalated", "Extended").  When provided it is appended to the header
            line: "Alert 1: Dense Fog Advisory (Extended)".

    """
    severity = alert.severity if alert.severity != "Unknown" else None
    urgency = alert.urgency if alert.urgency != "Unknown" else None
    areas = alert.areas[:3] if alert.areas else []
    is_regional_pw_alert = _is_pirate_weather_alert(alert)

    # Extract time preferences
    if settings:
        time_display_mode = getattr(settings, "time_display_mode", "local")
        time_format_12hour = getattr(settings, "time_format_12hour", True)
        show_timezone_suffix = getattr(settings, "show_timezone_suffix", False)
    else:
        time_display_mode = "local"
        time_format_12hour = True
        show_timezone_suffix = False

    expires = None
    if alert.expires:
        expires = format_display_datetime(
            alert.expires,
            time_display_mode=time_display_mode,
            use_12hour=time_format_12hour,
            show_timezone=show_timezone_suffix,
            date_format="%m/%d",
        )

    description = truncate(alert.description, 200) if alert.description else None
    instruction = truncate(alert.instruction, 150) if alert.instruction else None

    alert_header = f"Alert {index}: {alert.title}" if alert.title else f"Alert {index}"
    if lifecycle_label:
        alert_header = f"{alert_header} ({lifecycle_label})"
    parts: list[str] = [alert_header]
    if severity or urgency:
        sev_bits = []
        if severity:
            sev_bits.append(f"Severity: {severity}")
        if urgency:
            sev_bits.append(f"Urgency: {urgency}")
        parts.append("  " + ", ".join(sev_bits))
    if alert.event:
        parts.append(f"  Event: {alert.event}")
    if areas:
        remaining = len(alert.areas) - len(areas)
        area_text = ", ".join(areas)
        if remaining > 0:
            area_text += f" and {remaining} more"
        area_label = "Regions" if is_regional_pw_alert else "Areas"
        parts.append(f"  {area_label}: {area_text}")
    if is_regional_pw_alert:
        parts.append(
            "  Coverage: Regional alert from Pirate Weather/WMO; may not match your exact county or zone."
        )
    if expires:
        parts.append(f"  Expires: {expires}")
    if description:
        parts.append(f"  Description: {wrap_text(description, 80)}")
    if instruction:
        parts.append(f"  Instructions: {wrap_text(instruction, 80)}")

    fallback_text = "\n".join(parts)
    return AlertPresentation(
        title=alert.title or alert.event or f"Alert {index}",
        severity=severity,
        urgency=urgency,
        event=alert.event,
        areas=alert.areas or [],
        expires=expires,
        description=description,
        instructions=instruction,
        fallback_text=fallback_text,
    )
