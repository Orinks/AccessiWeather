"""Tests for alert_lifecycle module: AlertLifecycleDiff and diff_alerts()."""

from __future__ import annotations

import pytest

from accessiweather.alert_lifecycle import (
    AlertChange,
    AlertChangeKind,
    AlertLifecycleDiff,
    diff_alerts,
)
from accessiweather.models.alerts import WeatherAlert, WeatherAlerts


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_alert(
    title: str = "Test Alert",
    description: str = "A description.",
    severity: str = "Moderate",
    urgency: str = "Expected",
    alert_id: str | None = None,
) -> WeatherAlert:
    return WeatherAlert(
        title=title,
        description=description,
        severity=severity,
        urgency=urgency,
        id=alert_id,
    )


def alerts(*alert_list: WeatherAlert) -> WeatherAlerts:
    return WeatherAlerts(alerts=list(alert_list))


# ---------------------------------------------------------------------------
# AlertChangeKind
# ---------------------------------------------------------------------------

class TestAlertChangeKind:
    def test_has_three_members(self):
        members = list(AlertChangeKind)
        assert len(members) == 3

    def test_has_new(self):
        assert AlertChangeKind.NEW.value == "new"

    def test_has_updated(self):
        assert AlertChangeKind.UPDATED.value == "updated"

    def test_has_cancelled(self):
        assert AlertChangeKind.CANCELLED.value == "cancelled"


# ---------------------------------------------------------------------------
# AlertChange.is_severity_upgrade
# ---------------------------------------------------------------------------

class TestAlertChangeIsSeverityUpgrade:
    def test_upgrade_moderate_to_extreme(self):
        change = AlertChange(
            kind=AlertChangeKind.UPDATED,
            old_severity="Moderate",
            new_severity="Extreme",
        )
        assert change.is_severity_upgrade is True

    def test_downgrade_extreme_to_minor(self):
        change = AlertChange(
            kind=AlertChangeKind.UPDATED,
            old_severity="Extreme",
            new_severity="Minor",
        )
        assert change.is_severity_upgrade is False

    def test_same_severity_not_upgrade(self):
        change = AlertChange(
            kind=AlertChangeKind.UPDATED,
            old_severity="Severe",
            new_severity="Severe",
        )
        assert change.is_severity_upgrade is False

    def test_none_old_severity(self):
        change = AlertChange(
            kind=AlertChangeKind.UPDATED,
            old_severity=None,
            new_severity="Extreme",
        )
        assert change.is_severity_upgrade is False

    def test_none_new_severity(self):
        change = AlertChange(
            kind=AlertChangeKind.UPDATED,
            old_severity="Minor",
            new_severity=None,
        )
        assert change.is_severity_upgrade is False


# ---------------------------------------------------------------------------
# AlertLifecycleDiff.has_changes
# ---------------------------------------------------------------------------

class TestAlertLifecycleDiffHasChanges:
    def test_empty_has_no_changes(self):
        diff = AlertLifecycleDiff()
        assert diff.has_changes is False

    def test_new_alerts_has_changes(self):
        change = AlertChange(kind=AlertChangeKind.NEW)
        diff = AlertLifecycleDiff(new_alerts=[change])
        assert diff.has_changes is True

    def test_updated_alerts_has_changes(self):
        change = AlertChange(kind=AlertChangeKind.UPDATED)
        diff = AlertLifecycleDiff(updated_alerts=[change])
        assert diff.has_changes is True

    def test_cancelled_alerts_has_changes(self):
        change = AlertChange(kind=AlertChangeKind.CANCELLED)
        diff = AlertLifecycleDiff(cancelled_alerts=[change])
        assert diff.has_changes is True


# ---------------------------------------------------------------------------
# diff_alerts
# ---------------------------------------------------------------------------

class TestDiffAlertsNewAlert:
    def test_new_alert_detected(self):
        """Alert in current but not previous should appear in new_alerts."""
        a = make_alert("Tornado Warning", alert_id="a1")
        diff = diff_alerts(alerts(), alerts(a))
        assert len(diff.new_alerts) == 1
        assert diff.new_alerts[0].kind == AlertChangeKind.NEW
        assert diff.new_alerts[0].alert_id == "a1"
        assert diff.new_alerts[0].title == "Tornado Warning"

    def test_previous_none_all_new(self):
        """diff_alerts(None, current) should return all current alerts as NEW."""
        a = make_alert("Flash Flood Watch", alert_id="ff1")
        b = make_alert("Winter Storm Warning", alert_id="ws1")
        diff = diff_alerts(None, alerts(a, b))
        assert len(diff.new_alerts) == 2
        kinds = {c.kind for c in diff.new_alerts}
        assert kinds == {AlertChangeKind.NEW}

    def test_both_none_returns_empty_diff(self):
        """diff_alerts(None, None) should return an empty diff."""
        diff = diff_alerts(None, None)
        assert diff.has_changes is False
        assert diff.summary == "No changes"


class TestDiffAlertsCancelled:
    def test_cancelled_alert_detected(self):
        """Alert in previous but not current should appear in cancelled_alerts."""
        a = make_alert("Severe Thunderstorm Warning", alert_id="st1")
        diff = diff_alerts(alerts(a), alerts())
        assert len(diff.cancelled_alerts) == 1
        assert diff.cancelled_alerts[0].kind == AlertChangeKind.CANCELLED
        assert diff.cancelled_alerts[0].alert_id == "st1"

    def test_current_none_all_cancelled(self):
        """diff_alerts(previous, None) should return all previous alerts as CANCELLED."""
        a = make_alert("Blizzard Warning", alert_id="bz1")
        diff = diff_alerts(alerts(a), None)
        assert len(diff.cancelled_alerts) == 1
        assert diff.cancelled_alerts[0].kind == AlertChangeKind.CANCELLED


class TestDiffAlertsUpdated:
    def test_content_change_detected(self):
        """Alert with changed description should appear in updated_alerts."""
        a_prev = make_alert("Wind Advisory", description="Winds 20 mph.", alert_id="wa1")
        a_curr = make_alert("Wind Advisory", description="Winds 40 mph.", alert_id="wa1")
        diff = diff_alerts(alerts(a_prev), alerts(a_curr))
        assert len(diff.updated_alerts) == 1
        assert diff.updated_alerts[0].kind == AlertChangeKind.UPDATED

    def test_severity_change_detected(self):
        """Alert with changed severity should appear in updated_alerts."""
        a_prev = make_alert("Ice Storm Warning", severity="Moderate", alert_id="is1")
        a_curr = make_alert("Ice Storm Warning", severity="Extreme", alert_id="is1")
        diff = diff_alerts(alerts(a_prev), alerts(a_curr))
        assert len(diff.updated_alerts) == 1
        assert diff.updated_alerts[0].kind == AlertChangeKind.UPDATED

    def test_urgency_change_detected(self):
        """Alert with changed urgency should appear in updated_alerts."""
        a_prev = make_alert("Flood Watch", urgency="Expected", alert_id="fw1")
        a_curr = make_alert("Flood Watch", urgency="Immediate", alert_id="fw1")
        diff = diff_alerts(alerts(a_prev), alerts(a_curr))
        assert len(diff.updated_alerts) == 1

    def test_severity_upgrade_flag(self):
        """is_severity_upgrade should be True when severity went up."""
        a_prev = make_alert("Storm Warning", severity="Minor", alert_id="sw1")
        a_curr = make_alert("Storm Warning", severity="Extreme", alert_id="sw1")
        diff = diff_alerts(alerts(a_prev), alerts(a_curr))
        assert len(diff.updated_alerts) == 1
        assert diff.updated_alerts[0].is_severity_upgrade is True

    def test_severity_downgrade_flag(self):
        """is_severity_upgrade should be False when severity went down."""
        a_prev = make_alert("Storm Warning", severity="Extreme", alert_id="sw2")
        a_curr = make_alert("Storm Warning", severity="Minor", alert_id="sw2")
        diff = diff_alerts(alerts(a_prev), alerts(a_curr))
        assert len(diff.updated_alerts) == 1
        assert diff.updated_alerts[0].is_severity_upgrade is False

    def test_identical_alert_no_update(self):
        """Identical alerts should not appear in any change list."""
        a = make_alert("Dense Fog Advisory", alert_id="df1")
        diff = diff_alerts(alerts(a), alerts(a))
        assert diff.has_changes is False
        assert diff.summary == "No changes"


class TestDiffAlertsSummary:
    def test_summary_one_new_alert(self):
        a = make_alert("Tornado Watch", alert_id="tw1")
        diff = diff_alerts(None, alerts(a))
        assert "1 new alert" in diff.summary

    def test_summary_multiple_new_alerts(self):
        a = make_alert("Alert A", alert_id="a1")
        b = make_alert("Alert B", alert_id="a2")
        diff = diff_alerts(None, alerts(a, b))
        assert "2 new alerts" in diff.summary

    def test_summary_one_cancelled(self):
        a = make_alert("Alert A", alert_id="a1")
        diff = diff_alerts(alerts(a), None)
        assert "1 cancelled" in diff.summary

    def test_summary_combined(self):
        a_old = make_alert("Old Alert", alert_id="old1")
        b_new = make_alert("New Alert", alert_id="new1")
        diff = diff_alerts(alerts(a_old), alerts(b_new))
        assert "new" in diff.summary
        assert "cancelled" in diff.summary

    def test_summary_no_changes(self):
        diff = AlertLifecycleDiff()
        assert diff.summary == "No changes"

    def test_summary_severity_upgrade_mentioned(self):
        a_prev = make_alert("Storm", severity="Minor", alert_id="s1")
        a_curr = make_alert("Storm", severity="Extreme", alert_id="s1")
        diff = diff_alerts(alerts(a_prev), alerts(a_curr))
        assert "severity upgraded" in diff.summary.lower()
