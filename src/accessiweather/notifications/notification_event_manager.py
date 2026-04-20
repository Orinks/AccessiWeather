"""
Notification event manager for tracking weather data changes.

This module provides state tracking and change detection for:
- Area Forecast Discussion (AFD) updates (using NWS API issuanceTime)
- Severe weather risk level changes
- Pirate Weather minutely precipitation start/stop transitions

All notification types are opt-in (disabled by default) and can be
enabled in Settings > Notifications.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from ..runtime_state import RuntimeStateManager
from .minutely_precipitation import (
    SENSITIVITY_THRESHOLDS,
    build_minutely_likelihood_signature,
    build_minutely_transition_signature,
    detect_minutely_precipitation_likelihood,
    detect_minutely_precipitation_transition,
)

if TYPE_CHECKING:
    from ..models import AppSettings, CurrentConditions, Location, TextProduct, WeatherData


# Rate-limit window for per-(product, location) notifications. The HWO check
# suppresses re-dispatch within this window while still advancing stored state
# so we don't re-trigger on the next cycle forever.
_HWO_RATE_LIMIT_WINDOW = timedelta(minutes=30)
# Summaries shorter than this (after stripping) fall back to the generic body.
_HWO_SUMMARY_MIN_CHARS = 20

logger = logging.getLogger(__name__)


def _extract_discussion_issued_time_label(discussion_text: str | None) -> str | None:
    """Extract the station-local issued time label from AFD text when present."""
    if not discussion_text:
        return None

    patterns = (
        r"\bISSUED\s+(\d{1,2})(\d{2})\s+([AP]M)\s+([A-Z]{2,4})\b",
        r"\bISSUED\s+(\d{1,2}):(\d{2})\s+([AP]M)\s+([A-Z]{2,4})\b",
        r"(?:^|\n)\s*(\d{1,2})(\d{2})\s+([AP]M)\s+([A-Z]{2,4})\s+(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\b",
        r"(?:^|\n)\s*(\d{1,2}):(\d{2})\s+([AP]M)\s+([A-Z]{2,4})\s+(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\b",
    )

    for pattern in patterns:
        match = re.search(pattern, discussion_text, re.IGNORECASE)
        if match:
            hour, minute, meridiem, tz_name = match.groups()
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

    event_type: str
    title: str
    message: str
    sound_event: str  # Sound event key for the soundpack


@dataclass
class NotificationState:
    """Tracks state for notification change detection."""

    last_discussion_issuance_time: datetime | None = None  # NWS API issuanceTime
    last_discussion_text: str | None = None
    last_severe_risk: int | None = None
    last_minutely_transition_signature: str | None = None
    last_minutely_likelihood_signature: str | None = None
    last_check_time: datetime | None = None
    # HWO (Hazardous Weather Outlook) tracking — Unit 10 populates these.
    last_hwo_issuance_time: datetime | None = None
    last_hwo_text: str | None = None
    last_hwo_summary_signature: str | None = None
    # SPS (Special Weather Statement) tracking — Unit 11 populates these.
    # Stored as a set for O(1) dedupe; round-trips through JSON as sorted list.
    last_sps_product_ids: set[str] = field(default_factory=set)

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
            "last_minutely_transition_signature": self.last_minutely_transition_signature,
            "last_minutely_likelihood_signature": self.last_minutely_likelihood_signature,
            "last_check_time": self.last_check_time.isoformat() if self.last_check_time else None,
            "last_hwo_issuance_time": (
                self.last_hwo_issuance_time.isoformat() if self.last_hwo_issuance_time else None
            ),
            "last_hwo_text": self.last_hwo_text,
            "last_hwo_summary_signature": self.last_hwo_summary_signature,
            # Sort for deterministic output (JSON diffs, snapshot tests).
            "last_sps_product_ids": sorted(self.last_sps_product_ids),
        }

    @classmethod
    def from_dict(cls, data: dict) -> NotificationState:
        """Create from dictionary."""
        last_check = data.get("last_check_time")
        last_issuance = data.get("last_discussion_issuance_time")
        last_hwo_issuance = data.get("last_hwo_issuance_time")
        sps_ids = data.get("last_sps_product_ids") or []
        return cls(
            last_discussion_issuance_time=(
                datetime.fromisoformat(last_issuance) if last_issuance else None
            ),
            last_discussion_text=data.get("last_discussion_text"),
            last_severe_risk=data.get("last_severe_risk"),
            last_minutely_transition_signature=data.get("last_minutely_transition_signature"),
            last_minutely_likelihood_signature=data.get("last_minutely_likelihood_signature"),
            last_check_time=datetime.fromisoformat(last_check) if last_check else None,
            last_hwo_issuance_time=(
                datetime.fromisoformat(last_hwo_issuance) if last_hwo_issuance else None
            ),
            last_hwo_text=data.get("last_hwo_text"),
            last_hwo_summary_signature=data.get("last_hwo_summary_signature"),
            last_sps_product_ids=set(sps_ids),
        )


class NotificationEventManager:
    """
    Manages notification events for weather data changes.

    Tracks changes in:
    - Area Forecast Discussion (AFD) updates using NWS API issuanceTime
    - Severe weather risk levels (from Visual Crossing)
    - Minutely precipitation start/stop transitions (from Pirate Weather)

    All notifications are opt-in (disabled by default).
    """

    def __init__(
        self,
        state_file: Path | None = None,
        runtime_state_manager: RuntimeStateManager | None = None,
    ):
        """
        Initialize the notification event manager.

        Args:
            state_file: Optional path to persist notification state
            runtime_state_manager: Optional unified runtime-state manager

        """
        self.state_file = state_file
        self.runtime_state_manager = runtime_state_manager
        self.state = NotificationState()
        # Ephemeral per-(product, location) rate-limit bookkeeping. Intentionally
        # in-memory only — see Unit 10 plan: we want cold-starts to re-evaluate
        # against stored content, not silently gag notifications across restarts.
        self._last_product_notified_at: dict[tuple[str, str], datetime] = {}
        self._load_state()
        logger.info("NotificationEventManager initialized")

    def _load_state(self) -> None:
        """Load state from file if available."""
        try:
            if self.runtime_state_manager is not None:
                data = self._runtime_section_to_legacy_shape(
                    self.runtime_state_manager.load_section("notification_events")
                )
            elif self.state_file and self.state_file.exists():
                with open(self.state_file, encoding="utf-8") as f:
                    data = json.load(f)
            else:
                return
            self.state = NotificationState.from_dict(data)
            logger.debug(
                "Loaded notification state from %s",
                self.runtime_state_manager.state_file
                if self.runtime_state_manager
                else self.state_file,
            )
        except Exception as e:
            logger.warning("Failed to load notification state: %s", e)

    def _save_state(self) -> None:
        """Save state to file if configured."""
        try:
            if self.runtime_state_manager is not None:
                self.runtime_state_manager.save_section(
                    "notification_events",
                    self._legacy_shape_to_runtime_section(self.state.to_dict()),
                )
                logger.debug(
                    "Saved notification state to %s", self.runtime_state_manager.state_file
                )
            elif self.state_file:
                self.state_file.parent.mkdir(parents=True, exist_ok=True)
                with open(self.state_file, "w", encoding="utf-8") as f:
                    json.dump(self.state.to_dict(), f, indent=2)
                logger.debug("Saved notification state to %s", self.state_file)
        except Exception as e:
            logger.warning("Failed to save notification state: %s", e)

    @staticmethod
    def _runtime_section_to_legacy_shape(section: dict) -> dict:
        """Convert unified runtime state to the legacy notification-state shape."""
        discussion = section.get("discussion", {})
        severe_risk = section.get("severe_risk", {})
        minutely_precipitation = section.get("minutely_precipitation", {})
        hwo = section.get("hwo", {})
        sps = section.get("sps", {})
        return {
            "last_discussion_issuance_time": discussion.get("last_issuance_time"),
            "last_discussion_text": discussion.get("last_text"),
            "last_severe_risk": severe_risk.get("last_value"),
            "last_minutely_transition_signature": minutely_precipitation.get(
                "last_transition_signature"
            ),
            "last_minutely_likelihood_signature": minutely_precipitation.get(
                "last_likelihood_signature"
            ),
            "last_check_time": discussion.get("last_check_time")
            or severe_risk.get("last_check_time")
            or minutely_precipitation.get("last_check_time"),
            "last_hwo_issuance_time": hwo.get("last_issuance_time"),
            "last_hwo_text": hwo.get("last_text"),
            "last_hwo_summary_signature": hwo.get("last_summary_signature"),
            "last_sps_product_ids": list(sps.get("last_product_ids") or []),
        }

    @staticmethod
    def _legacy_shape_to_runtime_section(data: dict) -> dict:
        """Convert legacy notification-state payloads to the unified section shape."""
        last_check_time = data.get("last_check_time")
        sps_ids = data.get("last_sps_product_ids") or []
        return {
            "discussion": {
                "last_issuance_time": data.get("last_discussion_issuance_time"),
                "last_text": data.get("last_discussion_text"),
                "last_check_time": last_check_time,
            },
            "severe_risk": {
                "last_value": data.get("last_severe_risk"),
                "last_check_time": last_check_time,
            },
            "minutely_precipitation": {
                "last_transition_signature": data.get("last_minutely_transition_signature"),
                "last_likelihood_signature": data.get("last_minutely_likelihood_signature"),
                "last_check_time": last_check_time,
            },
            "hwo": {
                "last_issuance_time": data.get("last_hwo_issuance_time"),
                "last_text": data.get("last_hwo_text"),
                "last_summary_signature": data.get("last_hwo_summary_signature"),
                "last_check_time": last_check_time,
            },
            "sps": {
                # Sorted so round-trips are stable; NotificationState's
                # ``set`` field re-materializes order-independence.
                "last_product_ids": sorted(sps_ids),
                "last_check_time": last_check_time,
            },
        }

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

        if (
            settings.notify_minutely_precipitation_start
            or settings.notify_minutely_precipitation_stop
        ):
            minutely_event = self._check_minutely_precipitation_transition(
                weather_data.minutely_precipitation,
                settings,
                location_name,
            )
            if minutely_event:
                events.append(minutely_event)

        if getattr(settings, "notify_precipitation_likelihood", False):
            likelihood_event = self._check_minutely_precipitation_likelihood(
                weather_data.minutely_precipitation,
                settings,
                location_name,
            )
            if likelihood_event:
                events.append(likelihood_event)

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

    def _check_hwo_update(
        self,
        location: Location,
        hwo_product: TextProduct | None,
        settings: AppSettings,
    ) -> None:
        """
        Inspect a freshly-fetched HWO product and notify on material updates.

        Unit 10 — Hazardous Weather Outlook change detection. The event loop
        feeds us the pre-warmed HWO for ``location``; we:

        1. Seed baseline state on the first fetch (no notification).
        2. Compare ``issuance_time`` + content-signature against stored values;
           short-circuit when both are unchanged.
        3. On change, persist the new baseline, then — subject to the
           ``notify_hwo_update`` setting (default True when absent) and a
           sliding 30-minute rate-limit bucket keyed by ``("HWO", location)`` —
           dispatch a desktop notification.

        ``None`` products and locations without a ``cwa_office`` are no-ops.
        """
        if hwo_product is None:
            return
        if not getattr(location, "cwa_office", None):
            return

        new_issuance = hwo_product.issuance_time
        new_text = hwo_product.product_text or ""
        signature = self._hash_product_text(new_text)

        stored_issuance = self.state.last_hwo_issuance_time
        stored_signature = self.state.last_hwo_summary_signature
        stored_text = self.state.last_hwo_text

        # Cold-start: no stored baseline → record silently, never dispatch.
        if stored_issuance is None and stored_signature is None:
            self.state.last_hwo_issuance_time = new_issuance
            self.state.last_hwo_text = new_text
            self.state.last_hwo_summary_signature = signature
            self._save_state()
            logger.debug(
                "_check_hwo_update: first-run baseline for %s (%s) — no notification",
                location.name,
                location.cwa_office,
            )
            return

        # Unchanged → true no-op: no state churn, no dispatch.
        if stored_issuance == new_issuance and stored_signature == signature:
            return

        # Changed: persist new baseline before deciding whether to notify so we
        # never re-fire against the old state if dispatch is suppressed below.
        self.state.last_hwo_issuance_time = new_issuance
        self.state.last_hwo_text = new_text
        self.state.last_hwo_summary_signature = signature
        self._save_state()

        if not getattr(settings, "notify_hwo_update", True):
            logger.debug(
                "_check_hwo_update: notify_hwo_update disabled — suppressing dispatch for %s",
                location.name,
            )
            return

        bucket = ("HWO", location.name)
        now = datetime.now(timezone.utc)
        last_sent = self._last_product_notified_at.get(bucket)
        if last_sent is not None and now - last_sent < _HWO_RATE_LIMIT_WINDOW:
            logger.debug(
                "_check_hwo_update: rate-limited for %s (last=%s) — state updated, no dispatch",
                location.name,
                last_sent,
            )
            return
        self._last_product_notified_at[bucket] = now

        message = self._format_hwo_body(stored_text, hwo_product)
        logger.info(
            "HWO updated for %s (%s): %s -> %s",
            location.name,
            location.cwa_office,
            stored_issuance,
            new_issuance,
        )
        self._dispatch_hwo_notification(
            location=location,
            product=hwo_product,
            message=message,
        )

    @staticmethod
    def _hash_product_text(text: str) -> str:
        """Return a stable signature for an HWO product text."""
        normalized = (text or "").strip()
        return hashlib.sha256(normalized.encode("utf-8", errors="replace")).hexdigest()

    @staticmethod
    def _format_hwo_body(stored_text: str | None, new_product: TextProduct) -> str:
        """Produce the notification body — prefer summarizer output, fall back to generic."""
        summary = summarize_discussion_change(stored_text, new_product.product_text)
        if summary and len(summary.strip()) > _HWO_SUMMARY_MIN_CHARS:
            return summary.strip()
        return f"Hazardous Weather Outlook updated for {new_product.cwa_office} — tap to view."

    def _dispatch_hwo_notification(
        self,
        *,
        location: Location,
        product: TextProduct,
        message: str,
    ) -> None:
        """
        Emit the HWO notification event.

        The default implementation builds a :class:`NotificationEvent` and logs
        it; the UI-layer caller is responsible for wiring it into the actual
        notifier. Tests monkey-patch this method to capture dispatches.
        """
        event = NotificationEvent(
            event_type="hwo_update",
            title="Hazardous Weather Outlook Updated",
            message=message,
            sound_event="notify",
        )
        logger.debug(
            "[events] HWO dispatch (default no-op): location=%s product=%s title=%r",
            location.name,
            product.product_id,
            event.title,
        )

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

    def _check_minutely_precipitation_transition(
        self,
        minutely_precipitation,
        settings: AppSettings,
        location_name: str,
    ) -> NotificationEvent | None:
        """Check for a new dry/wet transition in Pirate Weather minutely guidance."""
        sensitivity = getattr(settings, "precipitation_sensitivity", "light")
        threshold = SENSITIVITY_THRESHOLDS.get(sensitivity, SENSITIVITY_THRESHOLDS["light"])

        signature = build_minutely_transition_signature(minutely_precipitation, threshold=threshold)
        if signature is None:
            return None

        if self.state.last_minutely_transition_signature is None:
            self.state.last_minutely_transition_signature = signature
            logger.debug("First minutely precipitation state stored: %s", signature)
            return None

        if signature == self.state.last_minutely_transition_signature:
            return None

        self.state.last_minutely_transition_signature = signature
        transition = detect_minutely_precipitation_transition(
            minutely_precipitation, threshold=threshold
        )
        if transition is None:
            return None

        if (
            transition.transition_type == "starting"
            and not settings.notify_minutely_precipitation_start
        ):
            return None
        if (
            transition.transition_type == "stopping"
            and not settings.notify_minutely_precipitation_stop
        ):
            return None

        return NotificationEvent(
            event_type=transition.event_type,
            title=transition.title,
            message=f"{transition.title} for {location_name}.",
            sound_event="notify",
        )

    def _check_minutely_precipitation_likelihood(
        self,
        minutely_precipitation,
        settings: AppSettings,
        location_name: str,
    ) -> NotificationEvent | None:
        """Check for probability-based precipitation likelihood in minutely data."""
        threshold = getattr(settings, "precipitation_likelihood_threshold", 0.5)
        signature = build_minutely_likelihood_signature(minutely_precipitation, threshold)
        if signature is None:
            return None

        if self.state.last_minutely_likelihood_signature is None:
            self.state.last_minutely_likelihood_signature = signature
            logger.debug("First minutely likelihood state stored: %s", signature)
            return None

        if signature == self.state.last_minutely_likelihood_signature:
            return None

        self.state.last_minutely_likelihood_signature = signature
        likelihood = detect_minutely_precipitation_likelihood(minutely_precipitation, threshold)
        if likelihood is None:
            return None

        return NotificationEvent(
            event_type=likelihood.event_type,
            title=likelihood.title,
            message=f"{likelihood.title} for {location_name}.",
            sound_event="notify",
        )

    def reset_state(self) -> None:
        """Reset all tracked state."""
        self.state = NotificationState()
        self._save_state()
        logger.info("Notification event state reset")
