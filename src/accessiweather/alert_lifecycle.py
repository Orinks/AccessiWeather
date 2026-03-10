"""Alert lifecycle intelligence: diff two alert snapshots to detect changes."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

from accessiweather.constants import SEVERITY_PRIORITY_MAP
from accessiweather.models.alerts import WeatherAlert, WeatherAlerts


class AlertChangeKind(Enum):
    NEW = "new"
    UPDATED = "updated"
    ESCALATED = "escalated"
    EXTENDED = "extended"
    CANCELLED = "cancelled"


@dataclass
class AlertChange:
    """Represents a single alert change (new, updated, escalated, extended, or cancelled)."""

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
    escalated_alerts: list[AlertChange] = field(default_factory=list)
    extended_alerts: list[AlertChange] = field(default_factory=list)
    cancelled_alerts: list[AlertChange] = field(default_factory=list)
    summary: str = "No changes"

    @property
    def has_changes(self) -> bool:
        """Return True if any alerts changed."""
        return bool(
            self.new_alerts
            or self.updated_alerts
            or self.escalated_alerts
            or self.extended_alerts
            or self.cancelled_alerts
        )


def compute_lifecycle_labels(alerts: list[WeatherAlert]) -> dict[str, str]:
    """
    Build alert_id → label mapping using messageType for NWS alerts.

    VisualCrossing alerts have no messageType equivalent — no label returned for them.

    Args:
        alerts: List of current active WeatherAlert objects.

    Returns:
        A dict mapping alert IDs to their display label strings.

    """
    labels: dict[str, str] = {}
    for alert in alerts:
        alert_id = alert.get_unique_id()
        if alert.source != "NWS" or not alert.message_type:
            continue  # VC and unknown sources: no label
        mt = alert.message_type.lower()
        if mt == "alert":
            labels[alert_id] = "New"
        elif mt == "update":
            labels[alert_id] = "Updated"
        # Cancel: alert is no longer active, omit
    return labels


def _alert_label(count: int, singular: str, plural: str | None = None) -> str:
    if plural is None:
        plural = singular + "s"
    return f"{count} {singular if count == 1 else plural}"


def _expires_extended(prev: WeatherAlert, curr: WeatherAlert) -> bool:
    """Return True when the expiry timestamp was pushed to a later time."""
    if prev.expires is None or curr.expires is None:
        return False
    prev_exp: datetime = prev.expires if prev.expires.tzinfo else prev.expires.replace(tzinfo=UTC)
    curr_exp: datetime = curr.expires if curr.expires.tzinfo else curr.expires.replace(tzinfo=UTC)
    return curr_exp > prev_exp


def _build_summary(
    new: list[AlertChange],
    updated: list[AlertChange],
    escalated: list[AlertChange],
    extended: list[AlertChange],
    cancelled: list[AlertChange],
) -> str:
    parts: list[str] = []

    if new:
        parts.append(_alert_label(len(new), "new alert"))

    if updated:
        # Check for legacy severity-upgrade entries in updated (kept for safety)
        upgrades = [c for c in updated if c.is_severity_upgrade]
        if upgrades:
            highest = max(
                upgrades,
                key=lambda c: SEVERITY_PRIORITY_MAP.get((c.new_severity or "").lower(), 0),
            )
            severity_note = (highest.new_severity or "higher").capitalize()
            label = _alert_label(len(updated), "updated")
            parts.append(f"{label} (severity upgraded to {severity_note})")
        else:
            parts.append(_alert_label(len(updated), "updated"))

    if escalated:
        highest = max(
            escalated,
            key=lambda c: SEVERITY_PRIORITY_MAP.get((c.new_severity or "").lower(), 0),
        )
        severity_note = (highest.new_severity or "higher").capitalize()
        label = _alert_label(len(escalated), "escalated")
        parts.append(f"{label} (to {severity_note})")

    if extended:
        parts.append(_alert_label(len(extended), "extended"))

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
        An AlertLifecycleDiff describing what changed.

    Change classification for alerts present in both snapshots:
    - ESCALATED: severity moved to a higher priority tier.
    - UPDATED: content hash, severity (downgrade), or urgency changed; not escalated.
    - EXTENDED: expiry timestamp pushed later with no other changes.
    - No-op: everything identical -- alert is omitted from all change lists.

    """
    prev_active = previous.get_active_alerts() if previous is not None else []
    curr_active = current.get_active_alerts() if current is not None else []

    prev_map: dict[str, WeatherAlert] = {a.get_unique_id(): a for a in prev_active}
    curr_map: dict[str, WeatherAlert] = {a.get_unique_id(): a for a in curr_active}

    new_changes: list[AlertChange] = []
    updated_changes: list[AlertChange] = []
    escalated_changes: list[AlertChange] = []
    extended_changes: list[AlertChange] = []
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

    # Changed: in both maps -- classify into escalated / updated / extended
    for alert_id, alert in curr_map.items():
        if alert_id not in prev_map:
            continue  # already handled as NEW

        prev_alert = prev_map[alert_id]
        content_changed = alert.get_content_hash() != prev_alert.get_content_hash()
        severity_changed = alert.severity != prev_alert.severity
        urgency_changed = alert.urgency != prev_alert.urgency

        old_priority: int = SEVERITY_PRIORITY_MAP.get((prev_alert.severity or "").lower(), 0)
        new_priority: int = SEVERITY_PRIORITY_MAP.get((alert.severity or "").lower(), 0)
        severity_escalated = severity_changed and new_priority > old_priority

        if severity_escalated:
            escalated_changes.append(
                AlertChange(
                    kind=AlertChangeKind.ESCALATED,
                    alert=alert,
                    alert_id=alert_id,
                    title=alert.title or "",
                    old_severity=prev_alert.severity,
                    new_severity=alert.severity,
                )
            )
        elif content_changed or severity_changed or urgency_changed:
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
        elif _expires_extended(prev_alert, alert):
            extended_changes.append(
                AlertChange(
                    kind=AlertChangeKind.EXTENDED,
                    alert=alert,
                    alert_id=alert_id,
                    title=alert.title or "",
                )
            )

    summary = _build_summary(
        new_changes, updated_changes, escalated_changes, extended_changes, cancelled_changes
    )

    return AlertLifecycleDiff(
        new_alerts=new_changes,
        updated_alerts=updated_changes,
        escalated_alerts=escalated_changes,
        extended_alerts=extended_changes,
        cancelled_alerts=cancelled_changes,
        summary=summary,
    )
