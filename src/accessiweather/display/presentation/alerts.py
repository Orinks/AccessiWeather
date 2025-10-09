"""Builders for weather alert presentations."""

from __future__ import annotations

from ...models import Location, WeatherAlert, WeatherAlerts
from ..weather_presenter import AlertPresentation, AlertsPresentation
from .formatters import truncate, wrap_text


def build_alerts(alerts: WeatherAlerts, location: Location) -> AlertsPresentation:
    """Create an alerts presentation for a given location."""
    title = f"Weather alerts for {location.name}"
    if not alerts.has_alerts():
        return AlertsPresentation(title=title, fallback_text=f"{title}:\nNo active weather alerts.")

    active = alerts.get_active_alerts()
    if not active:
        return AlertsPresentation(title=title, fallback_text=f"{title}:\nNo active weather alerts.")

    presentations: list[AlertPresentation] = []
    fallback_lines = [title + ":"]

    for idx, alert in enumerate(active, start=1):
        presentation = build_single_alert(alert, idx)
        presentations.append(presentation)
        fallback_lines.append(presentation.fallback_text)

    fallback_text = "\n\n".join(fallback_lines)
    return AlertsPresentation(title=title, alerts=presentations, fallback_text=fallback_text)


def build_single_alert(alert: WeatherAlert, index: int) -> AlertPresentation:
    """Create a single alert presentation with truncated text for readability."""
    severity = alert.severity if alert.severity != "Unknown" else None
    urgency = alert.urgency if alert.urgency != "Unknown" else None
    areas = alert.areas[:3] if alert.areas else []
    expires = alert.expires.strftime("%m/%d %I:%M %p") if alert.expires else None

    description = truncate(alert.description, 200) if alert.description else None
    instruction = truncate(alert.instruction, 150) if alert.instruction else None

    parts: list[str] = [f"Alert {index}: {alert.title}" if alert.title else f"Alert {index}"]
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
        parts.append(f"  Areas: {area_text}")
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
