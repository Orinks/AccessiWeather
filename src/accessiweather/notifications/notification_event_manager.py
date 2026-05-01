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

import json
import logging
from datetime import datetime
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
from .notification_event_products import check_hwo_update, check_sps_new
from .notification_event_state import (
    NotificationEvent,
    NotificationState,
    legacy_shape_to_runtime_section,
    runtime_section_to_legacy_shape,
)
from .notification_event_text import (
    extract_discussion_issued_time_label as _extract_discussion_issued_time_label,
    extract_section as _extract_section,
    format_issuance_time_label as _format_issuance_time_label,
    get_risk_category,
    hash_product_text,
    is_no_change_summary as _is_no_change_summary,
    summarize_discussion_change,
)
from .notification_sps_helpers import (
    format_sps_body,
    sps_alert_signatures,
    sps_is_case_a,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ..models import (
        AppSettings,
        CurrentConditions,
        Location,
        TextProduct,
        WeatherAlert,
        WeatherData,
    )


logger = logging.getLogger(__name__)


class NotificationEventManager:
    """
    Manages notification events for weather data changes.

    Tracks changes in:
    - Area Forecast Discussion (AFD) updates using NWS API issuanceTime
    - Severe weather risk levels
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
        return runtime_section_to_legacy_shape(section)

    @staticmethod
    def _legacy_shape_to_runtime_section(data: dict) -> dict:
        """Convert legacy notification-state payloads to the unified section shape."""
        return legacy_shape_to_runtime_section(data)

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

            if change_summary is None and _is_no_change_summary(
                _extract_section(
                    discussion_text or "",
                    start_marker=".WHAT HAS CHANGED",
                    end_markers=(".", "&&"),
                )
            ):
                logger.info(
                    "Discussion issuance advanced for %s, but AFD says no changes; "
                    "state updated without notification",
                    location_name,
                )
                return None

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
        """Inspect a freshly fetched HWO product and notify on material updates."""
        check_hwo_update(self, location, hwo_product, settings)

    @staticmethod
    def _hash_product_text(text: str) -> str:
        """Return a stable signature for an HWO product text."""
        return hash_product_text(text)

    @staticmethod
    def _format_hwo_body(stored_text: str | None, new_product: TextProduct) -> str:
        """Produce the notification body — prefer summarizer output, fall back to generic."""
        summary = summarize_discussion_change(stored_text, new_product.product_text)
        if summary and len(summary.strip()) > 20:
            return summary.strip()
        return f"Hazardous Weather Outlook updated for {new_product.cwa_office} - tap to view."

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

    # ------------------------------------------------------------------
    # Unit 11 — Special Weather Statement (SPS) informational notifications
    # ------------------------------------------------------------------

    def _check_sps_new(
        self,
        location: Location,
        sps_products: Sequence[TextProduct] | None,
        cached_alerts: Sequence[WeatherAlert] | None,
        settings: AppSettings,
    ) -> None:
        """Dispatch notifications for informational SPS products only."""
        check_sps_new(self, location, sps_products, cached_alerts, settings)

    @classmethod
    def _sps_alert_signatures(cls, alerts: Sequence[WeatherAlert]) -> list[str]:
        """Collect normalized signatures for active SPS alerts."""
        return sps_alert_signatures(alerts)

    @classmethod
    def _sps_is_case_a(cls, product: TextProduct, alert_signatures: Sequence[str]) -> bool:
        """Return True when ``product`` looks like the event-style SPS an alert covers."""
        return sps_is_case_a(product, alert_signatures)

    @classmethod
    def _format_sps_body(cls, product: TextProduct) -> str:
        """Build the toast body — headline + CWA office, with text fallback."""
        return format_sps_body(product)

    def _dispatch_sps_notification(
        self,
        *,
        location: Location,
        product: TextProduct,
        message: str,
    ) -> None:
        """
        Emit the SPS notification event.

        Default is a no-op logger call mirroring
        :meth:`_dispatch_hwo_notification`; the UI layer monkey-patches it to
        fire a real desktop notification. Tests capture dispatches by
        replacing this method.
        """
        event = NotificationEvent(
            event_type="sps_issued",
            title="Special Weather Statement",
            message=message,
            sound_event="notify",
        )
        logger.debug(
            "[events] SPS dispatch (default no-op): location=%s product=%s title=%r",
            location.name,
            product.product_id,
            event.title,
        )

    def _check_severe_risk_change(
        self, current: CurrentConditions, location_name: str
    ) -> NotificationEvent | None:
        """
        Check if the severe weather risk level has changed significantly.

        Severe weather risk scale (aligned with UI display):
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
