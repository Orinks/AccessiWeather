"""Tests for alert lifecycle diff surfacing in AlertsPresentation — US-002."""

from __future__ import annotations

import pytest

from accessiweather.alert_lifecycle import AlertChange, AlertChangeKind, AlertLifecycleDiff
from accessiweather.display.presentation.alerts import build_alerts
from accessiweather.display.weather_presenter import AlertsPresentation
from accessiweather.models.alerts import WeatherAlert, WeatherAlerts
from accessiweather.models.weather import Location


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _loc(name: str = "Test City") -> Location:
    return Location(name=name, latitude=40.0, longitude=-75.0)


def _make_alert(
    title: str = "Tornado Warning",
    severity: str = "Extreme",
    urgency: str = "Immediate",
) -> WeatherAlert:
    return WeatherAlert(
        title=title,
        description=f"{title} in effect.",
        severity=severity,
        urgency=urgency,
    )


def _make_alerts(alerts: list[WeatherAlert] | None = None) -> WeatherAlerts:
    return WeatherAlerts(alerts=alerts or [_make_alert()])


def _make_diff(
    new_count: int = 0,
    updated_count: int = 0,
    cancelled_count: int = 0,
    summary: str | None = None,
) -> AlertLifecycleDiff:
    new_changes = [
        AlertChange(kind=AlertChangeKind.NEW, alert_id=f"new-{i}", title=f"New Alert {i}")
        for i in range(new_count)
    ]
    updated_changes = [
        AlertChange(
            kind=AlertChangeKind.UPDATED, alert_id=f"upd-{i}", title=f"Updated Alert {i}"
        )
        for i in range(updated_count)
    ]
    cancelled_changes = [
        AlertChange(
            kind=AlertChangeKind.CANCELLED, alert_id=f"can-{i}", title=f"Cancelled Alert {i}"
        )
        for i in range(cancelled_count)
    ]
    if summary is None:
        parts = []
        if new_count:
            parts.append(f"{new_count} new {'alert' if new_count == 1 else 'alerts'}")
        if updated_count:
            parts.append(f"{updated_count} updated")
        if cancelled_count:
            parts.append(f"{cancelled_count} cancelled")
        summary = ", ".join(parts) if parts else "No changes"
    return AlertLifecycleDiff(
        new_alerts=new_changes,
        updated_alerts=updated_changes,
        cancelled_alerts=cancelled_changes,
        summary=summary,
    )


# ---------------------------------------------------------------------------
# AlertsPresentation dataclass: change_summary field
# ---------------------------------------------------------------------------


class TestAlertsPresentationField:
    def test_change_summary_field_exists_and_defaults_none(self):
        """AlertsPresentation must have change_summary defaulting to None."""
        ap = AlertsPresentation(title="Test")
        assert hasattr(ap, "change_summary")
        assert ap.change_summary is None

    def test_change_summary_can_be_set(self):
        """change_summary can be assigned a string."""
        ap = AlertsPresentation(title="Test", change_summary="2 new alerts")
        assert ap.change_summary == "2 new alerts"


# ---------------------------------------------------------------------------
# build_alerts: lifecycle_diff=None (backward compatibility)
# ---------------------------------------------------------------------------


class TestBuildAlertsNoLifecycleDiff:
    def test_no_diff_change_summary_is_none(self):
        """Without lifecycle_diff, change_summary stays None."""
        result = build_alerts(_make_alerts(), _loc())
        assert result.change_summary is None

    def test_no_diff_fallback_text_unchanged(self):
        """Without lifecycle_diff, fallback_text does NOT start with 'Alert changes:'."""
        result = build_alerts(_make_alerts(), _loc())
        assert not result.fallback_text.startswith("Alert changes:")

    def test_no_diff_explicit_none_change_summary_is_none(self):
        """Explicit lifecycle_diff=None → change_summary is None."""
        result = build_alerts(_make_alerts(), _loc(), lifecycle_diff=None)
        assert result.change_summary is None


# ---------------------------------------------------------------------------
# build_alerts: lifecycle_diff with has_changes=True
# ---------------------------------------------------------------------------


class TestBuildAlertsWithLifecycleDiff:
    def test_new_alert_sets_change_summary(self):
        """When diff has 1 new alert, change_summary equals diff.summary."""
        diff = _make_diff(new_count=1, summary="1 new alert")
        result = build_alerts(_make_alerts(), _loc(), lifecycle_diff=diff)
        assert result.change_summary == "1 new alert"

    def test_multiple_changes_change_summary(self):
        """When diff has new + cancelled, change_summary reflects both."""
        diff = _make_diff(new_count=2, cancelled_count=1, summary="2 new alerts, 1 cancelled")
        result = build_alerts(_make_alerts(), _loc(), lifecycle_diff=diff)
        assert result.change_summary == "2 new alerts, 1 cancelled"

    def test_fallback_text_starts_with_alert_changes(self):
        """When diff has changes, fallback_text starts with 'Alert changes:'."""
        diff = _make_diff(new_count=1, summary="1 new alert")
        result = build_alerts(_make_alerts(), _loc(), lifecycle_diff=diff)
        assert result.fallback_text.startswith("Alert changes:")

    def test_fallback_text_contains_summary(self):
        """The lifecycle summary appears at the start of fallback_text."""
        diff = _make_diff(updated_count=1, summary="1 updated")
        result = build_alerts(_make_alerts(), _loc(), lifecycle_diff=diff)
        assert "Alert changes: 1 updated" in result.fallback_text

    def test_fallback_text_still_includes_alert_content(self):
        """Alert content appears after the change summary prefix."""
        diff = _make_diff(new_count=1, summary="1 new alert")
        result = build_alerts(_make_alerts([_make_alert("Tornado Warning")]), _loc(), lifecycle_diff=diff)
        assert "Tornado Warning" in result.fallback_text

    def test_updated_alert_change_summary(self):
        """Updated alert diff is reflected in change_summary."""
        diff = _make_diff(updated_count=2, summary="2 updated")
        result = build_alerts(_make_alerts(), _loc(), lifecycle_diff=diff)
        assert result.change_summary == "2 updated"

    def test_cancelled_alert_change_summary(self):
        """Cancelled alert diff is reflected in change_summary."""
        diff = _make_diff(cancelled_count=3, summary="3 cancelled")
        result = build_alerts(_make_alerts(), _loc(), lifecycle_diff=diff)
        assert result.change_summary == "3 cancelled"


# ---------------------------------------------------------------------------
# build_alerts: lifecycle_diff with has_changes=False
# ---------------------------------------------------------------------------


class TestBuildAlertsWithNoChangeDiff:
    def test_no_changes_diff_change_summary_is_none(self):
        """When diff has no changes, change_summary is None."""
        diff = _make_diff()  # 0 new, 0 updated, 0 cancelled
        assert not diff.has_changes
        result = build_alerts(_make_alerts(), _loc(), lifecycle_diff=diff)
        assert result.change_summary is None

    def test_no_changes_diff_fallback_text_unchanged(self):
        """When diff has no changes, fallback_text does NOT start with 'Alert changes:'."""
        diff = _make_diff()
        result = build_alerts(_make_alerts(), _loc(), lifecycle_diff=diff)
        assert not result.fallback_text.startswith("Alert changes:")


# ---------------------------------------------------------------------------
# build_alerts: no active alerts (edge cases)
# ---------------------------------------------------------------------------


class TestBuildAlertsEdgeCases:
    def test_no_alerts_returns_no_active_message(self):
        """Empty alerts returns 'No active weather alerts.' regardless of diff."""
        empty = WeatherAlerts(alerts=[])
        diff = _make_diff(new_count=1, summary="1 new alert")
        result = build_alerts(empty, _loc(), lifecycle_diff=diff)
        assert "No active weather alerts" in result.fallback_text
        # change_summary not set on empty-alert path (no alerts to present)
        assert result.change_summary is None

    def test_no_alerts_change_summary_none(self):
        """Empty alerts: change_summary always None."""
        empty = WeatherAlerts(alerts=[])
        result = build_alerts(empty, _loc())
        assert result.change_summary is None
