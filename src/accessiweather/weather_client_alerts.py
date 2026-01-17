"""Alert aggregation for merging alerts from multiple sources."""

from __future__ import annotations

import logging
from datetime import timedelta

from accessiweather.models.alerts import WeatherAlert, WeatherAlerts

logger = logging.getLogger(__name__)


class AlertAggregator:
    """
    Aggregates and deduplicates alerts from multiple sources.

    Collects alerts from NWS and Visual Crossing (Open-Meteo does not provide alerts),
    deduplicates based on event type, area, and time window, and preserves the most
    detailed description when merging duplicates.
    """

    def __init__(self, dedup_time_window_minutes: int = 60):
        """
        Initialize the alert aggregator.

        Args:
            dedup_time_window_minutes: Time window in minutes for considering
                alerts as duplicates (default: 60 minutes)

        """
        self.dedup_time_window = timedelta(minutes=dedup_time_window_minutes)

    def aggregate_alerts(
        self,
        nws_alerts: WeatherAlerts | None,
        vc_alerts: WeatherAlerts | None,
    ) -> WeatherAlerts:
        """
        Combine alerts from NWS and Visual Crossing.

        Deduplicates based on event type, area, and time window.
        Preserves most detailed description when merging duplicates.

        Args:
            nws_alerts: Alerts from NWS (may be None)
            vc_alerts: Alerts from Visual Crossing (may be None)

        Returns:
            Merged WeatherAlerts with duplicates removed

        """
        all_alerts: list[WeatherAlert] = []

        # Collect alerts from NWS
        if nws_alerts and nws_alerts.alerts:
            for alert in nws_alerts.alerts:
                # Ensure source is set
                if not alert.source:
                    alert.source = "nws"
                all_alerts.append(alert)

        # Collect alerts from Visual Crossing
        if vc_alerts and vc_alerts.alerts:
            for alert in vc_alerts.alerts:
                # Ensure source is set
                if not alert.source:
                    alert.source = "visualcrossing"
                all_alerts.append(alert)

        if not all_alerts:
            return WeatherAlerts(alerts=[])

        # Group potential duplicates
        deduplicated = self._deduplicate_alerts(all_alerts)

        return WeatherAlerts(alerts=deduplicated)

    def _deduplicate_alerts(self, alerts: list[WeatherAlert]) -> list[WeatherAlert]:
        """
        Remove duplicate alerts, keeping the most detailed version.

        Args:
            alerts: List of all alerts from all sources

        Returns:
            Deduplicated list of alerts

        """
        if not alerts:
            return []

        # Group alerts that might be duplicates
        groups: list[list[WeatherAlert]] = []

        for alert in alerts:
            # Try to find an existing group this alert belongs to
            found_group = False
            for group in groups:
                if self._is_duplicate(alert, group[0]):
                    group.append(alert)
                    found_group = True
                    break

            if not found_group:
                groups.append([alert])

        # Merge each group into a single alert
        result: list[WeatherAlert] = []
        for group in groups:
            if len(group) == 1:
                result.append(group[0])
            else:
                merged = self._merge_duplicate_alerts(group)
                result.append(merged)

        return result

    def _is_duplicate(
        self,
        alert1: WeatherAlert,
        alert2: WeatherAlert,
    ) -> bool:
        """
        Check if two alerts describe the same event.

        Alerts are considered duplicates if they have:
        - Same event type
        - Overlapping areas
        - Onset times within the deduplication time window

        Args:
            alert1: First alert to compare
            alert2: Second alert to compare

        Returns:
            True if alerts are duplicates

        """
        # Must have same event type
        if alert1.event != alert2.event:
            return False

        # Check for area overlap
        if not self._areas_overlap(alert1.areas, alert2.areas):
            return False

        # Check onset time proximity
        if alert1.onset and alert2.onset:
            try:
                # Normalize both datetimes to avoid naive/aware comparison errors
                onset1 = alert1.onset
                onset2 = alert2.onset
                # If one is aware and one is naive, convert both to naive local time
                if (onset1.tzinfo is None) != (onset2.tzinfo is None):
                    if onset1.tzinfo is not None:
                        onset1 = onset1.astimezone().replace(tzinfo=None)
                    if onset2.tzinfo is not None:
                        onset2 = onset2.astimezone().replace(tzinfo=None)
                time_diff = abs((onset1 - onset2).total_seconds())
                if time_diff > self.dedup_time_window.total_seconds():
                    return False
            except (TypeError, ValueError):
                # If datetime comparison fails, skip this check
                pass

        return True

    def _areas_overlap(self, areas1: list[str], areas2: list[str]) -> bool:
        """
        Check if two area lists have any overlap.

        Args:
            areas1: First list of area names
            areas2: Second list of area names

        Returns:
            True if there's any overlap (or if either list is empty)

        """
        # If either list is empty, consider it a potential match
        if not areas1 or not areas2:
            return True

        # Normalize area names for comparison
        normalized1 = {a.lower().strip() for a in areas1}
        normalized2 = {a.lower().strip() for a in areas2}

        return bool(normalized1 & normalized2)

    def _merge_duplicate_alerts(
        self,
        alerts: list[WeatherAlert],
    ) -> WeatherAlert:
        """
        Merge duplicate alerts, keeping most detailed info.

        NWS alerts are preferred as the base because they provide better metadata
        (severity, urgency, certainty) compared to Visual Crossing which often
        returns "Unknown" for these fields.

        Args:
            alerts: List of duplicate alerts to merge

        Returns:
            Single merged alert with most detailed information

        """
        if len(alerts) == 1:
            return alerts[0]

        def source_priority(alert: WeatherAlert) -> int:
            source = (alert.source or "").lower()
            if "nws" in source:
                return 0
            return 1

        sorted_alerts = sorted(alerts, key=source_priority)
        base = sorted_alerts[0]

        # Find the most detailed description
        best_description = base.description
        best_instruction = base.instruction
        best_headline = base.headline

        # Track all sources
        sources: set[str] = set()
        if base.source:
            sources.add(base.source)

        # Combine all areas
        all_areas: set[str] = set(base.areas) if base.areas else set()

        # For metadata, prefer non-Unknown values (NWS provides better metadata)
        best_severity = base.severity
        best_urgency = base.urgency
        best_certainty = base.certainty

        for alert in sorted_alerts[1:]:
            # Keep longer description
            if alert.description and len(alert.description) > len(best_description or ""):
                best_description = alert.description

            # Keep longer instruction
            if alert.instruction and len(alert.instruction) > len(best_instruction or ""):
                best_instruction = alert.instruction

            # Keep longer headline
            if alert.headline and len(alert.headline) > len(best_headline or ""):
                best_headline = alert.headline

            # Add source
            if alert.source:
                sources.add(alert.source)

            # Add areas
            if alert.areas:
                all_areas.update(alert.areas)

            # Prefer non-Unknown severity/urgency/certainty
            if best_severity == "Unknown" and alert.severity and alert.severity != "Unknown":
                best_severity = alert.severity
            if best_urgency == "Unknown" and alert.urgency and alert.urgency != "Unknown":
                best_urgency = alert.urgency
            if best_certainty == "Unknown" and alert.certainty and alert.certainty != "Unknown":
                best_certainty = alert.certainty

        # Create merged source string
        merged_source = ", ".join(sorted(sources)) if sources else None

        return WeatherAlert(
            title=base.title,
            description=best_description or base.description,
            severity=best_severity,
            urgency=best_urgency,
            certainty=best_certainty,
            event=base.event,
            headline=best_headline,
            instruction=best_instruction,
            onset=base.onset,
            expires=base.expires,
            sent=base.sent,
            effective=base.effective,
            areas=list(all_areas),
            id=base.id,
            source=merged_source,
        )
