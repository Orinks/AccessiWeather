"""Alert lifecycle intelligence: diff two alert snapshots to detect changes."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from accessiweather.constants import SEVERITY_PRIORITY_MAP
from accessiweather.models.alerts import WeatherAlert, WeatherAlerts


class AlertChangeKind(Enum):
    NEW = "new"
    UPDATED = "updated"
    CANCELLED = "cancelled"


@dataclass
class AlertChange:
    """Represents a single alert change (new, updated, or cancelled)."""

    kind: AlertChangeKind
    alert: WeatherAlert | None = None
    alert_id: str = ""
    title: str = ""
    old_severity: str | None = None
    new_severity: str | None = None

    @property
    def is_severity_upgrade(self) -> bool:
        """Return True when the alert severity increased to a higher priority."""
        if self.old_severity is None or self.new_severity is None:
            return False
        old_priority: int = SEVERITY_PRIORITY_MAP.get(self.old_severity.lower(), 0)
        new_priority: int = SEVERITY_PRIORITY_MAP.get(self.new_severity.lower(), 0)
        return bool(new_priority > old_priority)


@dataclass
class AlertLifecycleDiff:
    """Structured diff between two alert snapshots."""

    new_alerts: list[AlertChange] = field(default_factory=list)
    updated_alerts: list[AlertChange] = field(default_factory=list)
    cancelled_alerts: list[AlertChange] = field(default_factory=list)
    summary: str = "No changes"

    @property
    def has_changes(self) -> bool:
        """Return True if any alerts changed."""
        return bool(self.new_alerts or self.updated_alerts or self.cancelled_alerts)


def _alert_label(count: int, singular: str, plural: str | None = None) -> str:
    if plural is None:
        plural = singular + "s"
    return f"{count} {singular if count == 1 else plural}"


def _build_summary(
    new: list[AlertChange],
    updated: list[AlertChange],
    cancelled: list[AlertChange],
) -> str:
    parts: list[str] = []

    if new:
        parts.append(_alert_label(len(new), "new alert"))

    if updated:
        # Check if any are severity upgrades
        upgrades = [c for c in updated if c.is_severity_upgrade]
        if upgrades:
            # Include the worst new severity in the label
            highest = max(
                upgrades,
                key=lambda c: SEVERITY_PRIORITY_MAP.get((c.new_severity or "").lower(), 0),
            )
            severity_note = (highest.new_severity or "higher").capitalize()
            label = _alert_label(len(updated), "updated")
            parts.append(f"{label} (severity upgraded to {severity_note})")
        else:
            parts.append(_alert_label(len(updated), "updated"))

    if cancelled:
        parts.append(_alert_label(len(cancelled), "cancelled"))

    return ", ".join(parts) if parts else "No changes"


def diff_alerts(
    previous: WeatherAlerts | None,
    current: WeatherAlerts | None,
) -> AlertLifecycleDiff:
    """
    Compare two alert snapshots and return a structured diff.

    Args:
        previous: The earlier snapshot (or None if no history).
        current:  The latest snapshot (or None if alerts are unavailable).

    Returns:
        An :class:`AlertLifecycleDiff` describing what changed.

    """
    prev_active = previous.get_active_alerts() if previous is not None else []
    curr_active = current.get_active_alerts() if current is not None else []

    prev_map: dict[str, WeatherAlert] = {a.get_unique_id(): a for a in prev_active}
    curr_map: dict[str, WeatherAlert] = {a.get_unique_id(): a for a in curr_active}

    new_changes: list[AlertChange] = []
    updated_changes: list[AlertChange] = []
    cancelled_changes: list[AlertChange] = []

    # New: in current but not previous
    for alert_id, alert in curr_map.items():
        if alert_id not in prev_map:
            new_changes.append(
                AlertChange(
                    kind=AlertChangeKind.NEW,
                    alert=alert,
                    alert_id=alert_id,
                    title=alert.title or "",
                )
            )

    # Cancelled: in previous but not current
    for alert_id, prev_alert in prev_map.items():
        if alert_id not in curr_map:
            cancelled_changes.append(
                AlertChange(
                    kind=AlertChangeKind.CANCELLED,
                    alert_id=alert_id,
                    title=prev_alert.title or "",
                )
            )

    # Updated: in both maps but content or severity/urgency changed
    for alert_id, alert in curr_map.items():
        if alert_id in prev_map:
            prev_alert = prev_map[alert_id]
            content_changed = alert.get_content_hash() != prev_alert.get_content_hash()
            severity_changed = alert.severity != prev_alert.severity
            urgency_changed = alert.urgency != prev_alert.urgency
            if content_changed or severity_changed or urgency_changed:
                updated_changes.append(
                    AlertChange(
                        kind=AlertChangeKind.UPDATED,
                        alert=alert,
                        alert_id=alert_id,
                        title=alert.title or "",
                        old_severity=prev_alert.severity,
                        new_severity=alert.severity,
                    )
                )

    summary = _build_summary(new_changes, updated_changes, cancelled_changes)

    return AlertLifecycleDiff(
        new_alerts=new_changes,
        updated_alerts=updated_changes,
        cancelled_alerts=cancelled_changes,
        summary=summary,
    )
