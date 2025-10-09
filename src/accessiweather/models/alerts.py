"""Weather alert models for AccessiWeather."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class WeatherAlert:
    """Weather alert/warning."""

    title: str
    description: str
    severity: str = "Unknown"
    urgency: str = "Unknown"
    certainty: str = "Unknown"
    event: str | None = None
    headline: str | None = None
    instruction: str | None = None
    onset: datetime | None = None
    expires: datetime | None = None
    areas: list[str] = field(default_factory=list)
    id: str | None = None
    source: str | None = None

    def __post_init__(self):
        if self.areas is None:
            self.areas = []

    def get_unique_id(self) -> str:
        """Get a unique identifier for this alert."""
        if self.id:
            return self.id

        key_parts = [
            self.event or "unknown",
            self.severity or "unknown",
            self.headline or self.title or "unknown",
        ]
        if self.source:
            key_parts.append(self.source)
        return "-".join(part.lower().replace(" ", "_") for part in key_parts)

    def get_content_hash(self) -> str:
        """Generate a hash of key content fields for change detection."""
        import hashlib

        content_parts = [
            self.title or "",
            self.description or "",
            self.severity or "",
            self.urgency or "",
            self.headline or "",
            self.instruction or "",
        ]

        content_string = "|".join(content_parts)
        return hashlib.md5(content_string.encode(), usedforsecurity=False).hexdigest()

    def is_expired(self) -> bool:
        """Check if this alert has expired."""
        if self.expires is None:
            return False

        now = datetime.now(UTC)
        alert_expires = self.expires

        if alert_expires.tzinfo is None:
            alert_expires = alert_expires.replace(tzinfo=UTC)

        return now > alert_expires

    def get_severity_priority(self) -> int:
        """Get numeric priority for severity level (higher = more severe)."""
        severity_map = {"extreme": 5, "severe": 4, "moderate": 3, "minor": 2, "unknown": 1}
        return severity_map.get(self.severity.lower(), 1)


@dataclass
class WeatherAlerts:
    """Collection of weather alerts."""

    alerts: list[WeatherAlert]

    def has_alerts(self) -> bool:
        """Check if we have any active alerts."""
        return len(self.alerts) > 0

    def get_active_alerts(self) -> list[WeatherAlert]:
        """Get alerts that haven't expired."""
        now = datetime.now(UTC)
        active = []

        for alert in self.alerts:
            if alert.expires is None:
                active.append(alert)
            else:
                alert_expires = alert.expires
                if alert_expires.tzinfo is None:
                    alert_expires = alert_expires.replace(tzinfo=UTC)

                if alert_expires > now:
                    active.append(alert)

        return active
