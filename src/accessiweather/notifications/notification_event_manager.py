"""
Notification event manager for tracking weather data changes.

This module provides state tracking and change detection for:
- Area Forecast Discussion (AFD) updates (using NWS API issuanceTime)
- Severe weather risk level changes

Both notification types are opt-in (disabled by default) and can be
enabled in Settings > Notifications.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import AppSettings, CurrentConditions, WeatherData

logger = logging.getLogger(__name__)


def _extract_discussion_issued_time_label(discussion_text: str | None) -> str | None:
    """Extract the station-local issued time label from AFD text when present."""
    if not discussion_text:
        return None

    compact_match = re.search(
        r"\bISSUED\s+(\d{1,2})(\d{2})\s+([AP]M)\s+([A-Z]{2,4})\b",
        discussion_text,
        re.IGNORECASE,
    )
    if compact_match:
        hour, minute, meridiem, tz_name = compact_match.groups()
        return f"{int(hour)}:{minute} {meridiem.upper()} {tz_name.upper()}"

    colon_match = re.search(
        r"\bISSUED\s+(\d{1,2}):(\d{2})\s+([AP]M)\s+([A-Z]{2,4})\b",
        discussion_text,
        re.IGNORECASE,
    )
    if colon_match:
        hour, minute, meridiem, tz_name = colon_match.groups()
        return f"{int(hour)}:{minute} {meridiem.upper()} {tz_name.upper()}"

    return None


def _format_issuance_time_label(issuance_time: datetime) -> str:
    """Format issuance time using the datetime's own timezone context."""
    time_str = issuance_time.strftime("%I:%M %p").lstrip("0")
    tz_name = issuance_time.tzname() or ""
    return f"{time_str} {tz_name}".strip()


def get_risk_category(risk: int) -> str:
    """
    Categorize severe weather risk level.

    Uses the same thresholds as the UI display in current_conditions.py.

    Args:
        risk: Risk percentage (0-100)

    Returns:
        Category name: 'minimal', 'low', 'moderate', 'high', or 'extreme'

    """
    if risk >= 80:
        return "extreme"
    if risk >= 60:
        return "high"
    if risk >= 40:
        return "moderate"
    if risk >= 20:
        return "low"
    return "minimal"


def _extract_section(text: str, start_marker: str, end_markers: tuple[str, ...]) -> str | None:
    """
    Extract the content of a named section from AFD text.

    Args:
        text: The full AFD text to search.
        start_marker: The section header to look for (e.g. '.WHAT HAS CHANGED...').
        end_markers: Tuple of prefixes that indicate the end of the section
                     (e.g. lines starting with '.' or '&&').

    Returns:
        The extracted section body (stripped), or None if the section is not found.

    """
    lines = text.splitlines()
    in_section = False
    body_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not in_section:
            if stripped.upper().startswith(start_marker.upper()):
                in_section = True
            continue
        # We are inside the section — check for terminator
        if any(stripped.startswith(m) for m in end_markers) or any(
            stripped.upper().startswith(m.upper()) for m in end_markers
        ):
            break
        body_lines.append(stripped)
    if not in_section:
        return None
    content = " ".join(part for part in body_lines if part)
    return content if content else None


def summarize_discussion_change(previous_text: str | None, current_text: str | None) -> str | None:
    """
    Return a short human-friendly summary of what changed in the discussion text.

    Priority order:
    1. `.WHAT HAS CHANGED...` section — extract body up to the next section marker.
    2. `.KEY MESSAGES...` section — extract body up to ``&&``.
    3. First new line not present in the previous discussion text.

    The result is truncated to ~300 characters.
    """
    if not current_text:
        return None

    # 1. Try .WHAT HAS CHANGED... section
    section = _extract_section(
        current_text,
        start_marker=".WHAT HAS CHANGED",
        end_markers=(".", "&&"),
    )
    if section:
        return section[:300]

    # 2. Try .KEY MESSAGES... section
    section = _extract_section(
        current_text,
        start_marker=".KEY MESSAGES",
        end_markers=("&&",),
    )
    if section:
        return section[:300]

    # 3. Fall back to first new line not present in previous text
    previous_lines = {
        line.strip()
        for line in (previous_text or "").splitlines()
        if line.strip() and not line.strip().startswith("$")
    }
    for raw_line in current_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("$"):
            continue
        if line not in previous_lines:
            return line[:300]
    return None


@dataclass
class NotificationEvent:
    """Represents a notification event to be sent."""

    event_type: str  # 'discussion_update' or 'severe_risk'
    title: str
    message: str
    sound_event: str  # Sound event key for the soundpack


@dataclass
class NotificationState:
    """Tracks state for notification change detection."""

    last_discussion_issuance_time: datetime | None = None  # NWS API issuanceTime
    last_discussion_text: str | None = None
    last_severe_risk: int | None = None
    last_check_time: datetime | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for persistence."""
        return {
            "last_discussion_issuance_time": (
                self.last_discussion_issuance_time.isoformat()
                if self.last_discussion_issuance_time
                else None
            ),
            "last_discussion_text": self.last_discussion_text,
            "last_severe_risk": self.last_severe_risk,
            "last_check_time": self.last_check_time.isoformat() if self.last_check_time else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> NotificationState:
        """Create from dictionary."""
        last_check = data.get("last_check_time")
        last_issuance = data.get("last_discussion_issuance_time")
        return cls(
            last_discussion_issuance_time=(
                datetime.fromisoformat(last_issuance) if last_issuance else None
            ),
            last_discussion_text=data.get("last_discussion_text"),
            last_severe_risk=data.get("last_severe_risk"),
            last_check_time=datetime.fromisoformat(last_check) if last_check else None,
        )


class NotificationEventManager:
    """
    Manages notification events for weather data changes.

    Tracks changes in:
    - Area Forecast Discussion (AFD) updates using NWS API issuanceTime
    - Severe weather risk levels (from Visual Crossing)

    Both notifications are opt-in (disabled by default).
    """

    def __init__(self, state_file: Path | None = None):
        """
        Initialize the notification event manager.

        Args:
            state_file: Optional path to persist notification state

        """
        self.state_file = state_file
        self.state = NotificationState()
        self._load_state()
        logger.info("NotificationEventManager initialized")

    def _load_state(self) -> None:
        """Load state from file if available."""
        if not self.state_file or not self.state_file.exists():
            return

        try:
            with open(self.state_file, encoding="utf-8") as f:
                data = json.load(f)
            self.state = NotificationState.from_dict(data)
            logger.debug("Loaded notification state from %s", self.state_file)
        except Exception as e:
            logger.warning("Failed to load notification state: %s", e)

    def _save_state(self) -> None:
        """Save state to file if configured."""
        if not self.state_file:
            return

        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(self.state.to_dict(), f, indent=2)
            logger.debug("Saved notification state to %s", self.state_file)
        except Exception as e:
            logger.warning("Failed to save notification state: %s", e)

    def check_for_events(
        self,
        weather_data: WeatherData,
        settings: AppSettings,
        location_name: str,
    ) -> list[NotificationEvent]:
        """
        Check weather data for notification-worthy events.

        Args:
            weather_data: The current weather data
            settings: Application settings (to check which notifications are enabled)
            location_name: Name of the current location

        Returns:
            List of notification events to send

        """
        events: list[NotificationEvent] = []

        # Check for AFD/discussion update using NWS API issuanceTime
        if settings.notify_discussion_update:
            discussion_event = self._check_discussion_update(
                weather_data.discussion_issuance_time,
                weather_data.discussion,
                location_name,
            )
            if discussion_event:
                events.append(discussion_event)

        # Check for severe risk level change
        if settings.notify_severe_risk_change:
            current_conditions = weather_data.current
            if current_conditions:
                risk_event = self._check_severe_risk_change(current_conditions, location_name)
                if risk_event:
                    events.append(risk_event)

        # Update check time and save state
        self.state.last_check_time = datetime.now()
        self._save_state()

        return events

    def _check_discussion_update(
        self, issuance_time: datetime | None, discussion_text: str | None, location_name: str
    ) -> NotificationEvent | None:
        """
        Check if the forecast discussion has been updated using NWS API issuanceTime.

        Args:
            issuance_time: The issuanceTime from the NWS API for the current AFD
            discussion_text: The latest discussion text used to summarize what changed
            location_name: Name of the location

        Returns:
            NotificationEvent if discussion was updated, None otherwise

        """
        if not issuance_time:
            # No issuance time available (non-US location or API issue)
            logger.debug(
                "_check_discussion_update: no issuance_time (non-US location or fetch failed) "
                "— skipping"
            )
            return None

        # First time seeing discussion - store but don't notify
        if self.state.last_discussion_issuance_time is None:
            self.state.last_discussion_issuance_time = issuance_time
            self.state.last_discussion_text = discussion_text
            logger.debug(
                "_check_discussion_update: first-run — stored issuance_time=%s, no notification",
                issuance_time,
            )
            return None

        logger.debug(
            "_check_discussion_update: last=%s current=%s",
            self.state.last_discussion_issuance_time,
            issuance_time,
        )

        # Check if issuance time is newer (discussion was updated)
        if issuance_time > self.state.last_discussion_issuance_time:
            logger.info(
                "Discussion updated: %s -> %s",
                self.state.last_discussion_issuance_time,
                issuance_time,
            )
            change_summary = summarize_discussion_change(
                self.state.last_discussion_text,
                discussion_text,
            )
            self.state.last_discussion_issuance_time = issuance_time
            self.state.last_discussion_text = discussion_text

            issued_label = _extract_discussion_issued_time_label(discussion_text)
            if not issued_label:
                issued_label = (
                    _format_issuance_time_label(issuance_time)
                    if hasattr(issuance_time, "strftime")
                    else str(issuance_time)
                )
            message = f"The Area Forecast Discussion for {location_name} was updated by the National Weather Service at {issued_label}."
            if change_summary:
                message += f" {change_summary}"

            return NotificationEvent(
                event_type="discussion_update",
                title="Forecast Discussion Updated",
                message=message,
                sound_event="discussion_update",
            )

        self.state.last_discussion_text = discussion_text
        logger.debug(
            "_check_discussion_update: issuance_time unchanged (%s) — no notification",
            issuance_time,
        )
        return None

    def _check_severe_risk_change(
        self, current: CurrentConditions, location_name: str
    ) -> NotificationEvent | None:
        """
        Check if the severe weather risk level has changed significantly.

        Visual Crossing severerisk scale (aligned with UI display):
        - 0-19: Minimal risk
        - 20-39: Low risk
        - 40-59: Moderate risk
        - 60-79: High risk
        - 80+: Extreme risk

        Only notify when crossing thresholds (e.g., low->moderate, moderate->high, etc.)

        Args:
            current: Current weather conditions
            location_name: Name of the location

        Returns:
            NotificationEvent if risk level changed significantly, None otherwise

        """
        severe_risk = getattr(current, "severe_weather_risk", None)
        if severe_risk is None:
            return None

        current_category = get_risk_category(severe_risk)

        # First time seeing risk - store but don't notify
        if self.state.last_severe_risk is None:
            self.state.last_severe_risk = severe_risk
            logger.debug("First severe risk stored: %s (%s)", severe_risk, current_category)
            return None

        previous_category = get_risk_category(self.state.last_severe_risk)

        # Check if category changed
        if current_category != previous_category:
            logger.info(
                "Severe risk changed: %s (%s) -> %s (%s)",
                self.state.last_severe_risk,
                previous_category,
                severe_risk,
                current_category,
            )
            self.state.last_severe_risk = severe_risk

            # Determine if risk increased or decreased
            category_levels = {"minimal": 0, "low": 1, "moderate": 2, "high": 3, "extreme": 4}
            increased = category_levels[current_category] > category_levels[previous_category]

            if increased:
                title = f"Severe Weather Risk Increased to {current_category.title()}"
                message = (
                    f"Severe weather risk for {location_name} has increased from "
                    f"{previous_category} to {current_category} (risk index: {severe_risk})."
                )
            else:
                title = f"Severe Weather Risk Decreased to {current_category.title()}"
                message = (
                    f"Severe weather risk for {location_name} has decreased from "
                    f"{previous_category} to {current_category} (risk index: {severe_risk})."
                )

            return NotificationEvent(
                event_type="severe_risk",
                title=title,
                message=message,
                sound_event="severe_risk",
            )

        # Update stored value even if category didn't change
        self.state.last_severe_risk = severe_risk
        return None

    def reset_state(self) -> None:
        """Reset all tracked state."""
        self.state = NotificationState()
        self._save_state()
        logger.info("Notification event state reset")
