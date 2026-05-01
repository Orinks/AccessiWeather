"""Tests for alert_lifecycle module: AlertLifecycleDiff and diff_alerts()."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from accessiweather.alert_lifecycle import (
    AlertChange,
    AlertChangeKind,
    AlertLifecycleDiff,
    _alert_is_recently_issued,
    compute_lifecycle_labels,
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
    def test_has_five_members(self):
        members = list(AlertChangeKind)
        assert len(members) == 5

    def test_has_new(self):
        assert AlertChangeKind.NEW.value == "new"

    def test_has_updated(self):
        assert AlertChangeKind.UPDATED.value == "updated"

    def test_has_escalated(self):
        assert AlertChangeKind.ESCALATED.value == "escalated"

    def test_has_extended(self):
        assert AlertChangeKind.EXTENDED.value == "extended"

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

    def test_escalated_alerts_has_changes(self):
        change = AlertChange(kind=AlertChangeKind.ESCALATED)
        diff = AlertLifecycleDiff(escalated_alerts=[change])
        assert diff.has_changes is True

    def test_extended_alerts_has_changes(self):
        change = AlertChange(kind=AlertChangeKind.EXTENDED)
        diff = AlertLifecycleDiff(extended_alerts=[change])
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

    def test_severity_downgrade_goes_to_updated(self):
        """Severity downgrade (not an escalation) should appear in updated_alerts."""
        a_prev = make_alert("Ice Storm Warning", severity="Extreme", alert_id="is1")
        a_curr = make_alert("Ice Storm Warning", severity="Minor", alert_id="is1")
        diff = diff_alerts(alerts(a_prev), alerts(a_curr))
        assert len(diff.updated_alerts) == 1
        assert diff.updated_alerts[0].kind == AlertChangeKind.UPDATED
        assert len(diff.escalated_alerts) == 0

    def test_urgency_change_detected(self):
        """Alert with changed urgency should appear in updated_alerts."""
        a_prev = make_alert("Flood Watch", urgency="Expected", alert_id="fw1")
        a_curr = make_alert("Flood Watch", urgency="Immediate", alert_id="fw1")
        diff = diff_alerts(alerts(a_prev), alerts(a_curr))
        assert len(diff.updated_alerts) == 1

    def test_identical_alert_no_update(self):
        """Identical alerts should not appear in any change list."""
        a = make_alert("Dense Fog Advisory", alert_id="df1")
        diff = diff_alerts(alerts(a), alerts(a))
        assert diff.has_changes is False
        assert diff.summary == "No changes"


class TestDiffAlertsEscalated:
    def test_severity_escalation_goes_to_escalated_alerts(self):
        """Severity upgrade should go to escalated_alerts, not updated_alerts."""
        a_prev = make_alert("Storm Warning", severity="Minor", alert_id="sw1")
        a_curr = make_alert("Storm Warning", severity="Extreme", alert_id="sw1")
        diff = diff_alerts(alerts(a_prev), alerts(a_curr))
        assert len(diff.escalated_alerts) == 1
        assert diff.escalated_alerts[0].kind == AlertChangeKind.ESCALATED
        assert len(diff.updated_alerts) == 0

    def test_escalated_is_severity_upgrade_true(self):
        """is_severity_upgrade should be True on ESCALATED changes."""
        a_prev = make_alert("Storm Warning", severity="Minor", alert_id="sw1")
        a_curr = make_alert("Storm Warning", severity="Extreme", alert_id="sw1")
        diff = diff_alerts(alerts(a_prev), alerts(a_curr))
        assert diff.escalated_alerts[0].is_severity_upgrade is True

    def test_escalated_has_old_and_new_severity(self):
        """Escalated change should record old and new severity."""
        a_prev = make_alert("Ice Storm", severity="Moderate", alert_id="is1")
        a_curr = make_alert("Ice Storm", severity="Extreme", alert_id="is1")
        diff = diff_alerts(alerts(a_prev), alerts(a_curr))
        change = diff.escalated_alerts[0]
        assert change.old_severity == "Moderate"
        assert change.new_severity == "Extreme"

    def test_same_severity_not_escalated(self):
        """Same severity level (no change) should not go to escalated_alerts."""
        a_prev = make_alert("Storm", severity="Moderate", alert_id="s1")
        a_curr = make_alert("Storm", severity="Moderate", alert_id="s1")
        diff = diff_alerts(alerts(a_prev), alerts(a_curr))
        assert len(diff.escalated_alerts) == 0


class TestDiffAlertsExtended:
    def _make_alert_with_expires(
        self,
        alert_id: str = "ext1",
        expires_offset_hours: float = 12.0,
        **kwargs,
    ) -> WeatherAlert:
        return WeatherAlert(
            title=kwargs.get("title", "Fog Advisory"),
            description=kwargs.get("description", "Fog in the area."),
            severity=kwargs.get("severity", "Moderate"),
            urgency=kwargs.get("urgency", "Expected"),
            id=alert_id,
            expires=datetime.now(UTC) + timedelta(hours=expires_offset_hours),
        )

    def test_expiry_pushed_later_goes_to_extended_alerts(self):
        """Alert with same content but later expires goes to extended_alerts."""
        a_prev = self._make_alert_with_expires("fog1", expires_offset_hours=6.0)
        a_curr = self._make_alert_with_expires("fog1", expires_offset_hours=24.0)
        diff = diff_alerts(alerts(a_prev), alerts(a_curr))
        assert len(diff.extended_alerts) == 1
        assert diff.extended_alerts[0].kind == AlertChangeKind.EXTENDED
        assert len(diff.updated_alerts) == 0
        assert len(diff.escalated_alerts) == 0

    def test_expiry_not_changed_not_extended(self):
        """Identical alert (same expires) produces no extended entry."""
        a = self._make_alert_with_expires("fog1", expires_offset_hours=12.0)
        diff = diff_alerts(alerts(a), alerts(a))
        assert len(diff.extended_alerts) == 0
        assert diff.has_changes is False

    def test_expiry_moved_earlier_not_extended(self):
        """Alert with expires moved to a sooner time is NOT extended."""
        a_prev = self._make_alert_with_expires("fog1", expires_offset_hours=24.0)
        a_curr = self._make_alert_with_expires("fog1", expires_offset_hours=6.0)
        diff = diff_alerts(alerts(a_prev), alerts(a_curr))
        assert len(diff.extended_alerts) == 0

    def test_no_expires_not_extended(self):
        """Alert without an expires field is not classified as extended."""
        a_prev = make_alert("Dense Fog Advisory", alert_id="df1")
        a_curr = make_alert("Dense Fog Advisory", alert_id="df1")
        diff = diff_alerts(alerts(a_prev), alerts(a_curr))
        assert len(diff.extended_alerts) == 0


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

    def test_summary_escalated_mentioned(self):
        """Escalated alerts appear as 'escalated' in the summary."""
        a_prev = make_alert("Storm", severity="Minor", alert_id="s1")
        a_curr = make_alert("Storm", severity="Extreme", alert_id="s1")
        diff = diff_alerts(alerts(a_prev), alerts(a_curr))
        assert "escalated" in diff.summary.lower()

    def test_summary_extended_mentioned(self):
        """Extended alert appears as 'extended' in the summary."""
        expires_prev = datetime.now(UTC) + timedelta(hours=6)
        expires_later = datetime.now(UTC) + timedelta(hours=24)
        a_prev = WeatherAlert(
            title="Fog Advisory",
            description="Fog.",
            severity="Moderate",
            urgency="Expected",
            id="fog1",
            expires=expires_prev,
        )
        a_curr = WeatherAlert(
            title="Fog Advisory",
            description="Fog.",
            severity="Moderate",
            urgency="Expected",
            id="fog1",
            expires=expires_later,
        )
        diff = diff_alerts(alerts(a_prev), alerts(a_curr))
        assert "extended" in diff.summary.lower()


# ---------------------------------------------------------------------------
# compute_lifecycle_labels
# ---------------------------------------------------------------------------


class TestComputeLifecycleLabels:
    def _make_nws_alert(
        self,
        alert_id: str = "nws-1",
        message_type: str | None = "Alert",
    ) -> WeatherAlert:
        return WeatherAlert(
            title="Test Alert",
            description="A description.",
            severity="Moderate",
            urgency="Expected",
            id=alert_id,
            source="NWS",
            message_type=message_type,
        )

    def _make_openmeteo_alert(self, alert_id: str = "om-1") -> WeatherAlert:
        return WeatherAlert(
            title="Open-Meteo Alert",
            description="An Open-Meteo description.",
            severity="Moderate",
            urgency="Expected",
            id=alert_id,
            source="Open-Meteo",
        )

    def test_empty_list_returns_empty_dict(self):
        assert compute_lifecycle_labels([]) == {}

    def test_nws_alert_type_labeled_new(self):
        alert = self._make_nws_alert(alert_id="nws-new", message_type="Alert")
        labels = compute_lifecycle_labels([alert])
        assert labels == {"nws-new": "New"}

    def test_nws_update_type_labeled_updated(self):
        alert = self._make_nws_alert(alert_id="nws-upd", message_type="Update")
        labels = compute_lifecycle_labels([alert])
        assert labels == {"nws-upd": "Updated"}

    def test_nws_alert_type_case_insensitive(self):
        alert = self._make_nws_alert(alert_id="nws-ci", message_type="ALERT")
        labels = compute_lifecycle_labels([alert])
        assert labels == {"nws-ci": "New"}

    def test_nws_cancel_type_omitted(self):
        """Cancel messageType means the alert is no longer active — omit from labels."""
        alert = self._make_nws_alert(alert_id="nws-can", message_type="Cancel")
        labels = compute_lifecycle_labels([alert])
        assert labels == {}

    def test_nws_no_message_type_omitted(self):
        alert = self._make_nws_alert(alert_id="nws-none", message_type=None)
        labels = compute_lifecycle_labels([alert])
        assert labels == {}

    def test_non_nws_alert_gets_no_label(self):
        """Open-Meteo alerts have no NWS messageType equivalent."""
        alert = self._make_openmeteo_alert(alert_id="om-1")
        labels = compute_lifecycle_labels([alert])
        assert labels == {}

    def test_mixed_alerts_returns_nws_labels_only(self):
        alerts = [
            self._make_nws_alert(alert_id="nws-a", message_type="Alert"),
            self._make_nws_alert(alert_id="nws-u", message_type="Update"),
            self._make_nws_alert(alert_id="nws-c", message_type="Cancel"),
            self._make_openmeteo_alert(alert_id="om-1"),
        ]
        labels = compute_lifecycle_labels(alerts)
        assert labels == {
            "nws-a": "New",
            "nws-u": "Updated",
        }
        assert "nws-c" not in labels
        assert "om-1" not in labels


# ---------------------------------------------------------------------------
# Bug fix: first-load stale alerts should not fire "New" notifications
# ---------------------------------------------------------------------------


class TestDiffAlertsFirstLoadStaleFilter:
    def test_first_load_old_alerts_not_new(self):
        """Alerts active for hours should not appear as NEW on first load."""
        old_alert = WeatherAlert(
            title="Heat Advisory",
            description="Excessive heat.",
            severity="Moderate",
            urgency="Expected",
            id="ha1",
            effective=datetime.now(UTC) - timedelta(hours=2),
        )
        diff = diff_alerts(None, alerts(old_alert))
        assert len(diff.new_alerts) == 0

    def test_first_load_recent_alerts_are_new(self):
        """Alerts issued within 10 minutes should appear as NEW on first load."""
        recent_alert = WeatherAlert(
            title="Tornado Warning",
            description="Take shelter.",
            severity="Extreme",
            urgency="Immediate",
            id="tw1",
            effective=datetime.now(UTC) - timedelta(minutes=3),
        )
        diff = diff_alerts(None, alerts(recent_alert))
        assert len(diff.new_alerts) == 1
        assert diff.new_alerts[0].alert_id == "tw1"

    def test_first_load_no_effective_assumes_new(self):
        """Alert without effective/onset timestamps should be treated as new."""
        alert = make_alert("Unknown Alert", alert_id="ua1")
        diff = diff_alerts(None, alerts(alert))
        assert len(diff.new_alerts) == 1

    def test_second_load_old_alert_still_detected(self):
        """With a real previous snapshot (empty), old alerts should be detected as NEW."""
        old_alert = WeatherAlert(
            title="Heat Advisory",
            description="Excessive heat.",
            severity="Moderate",
            urgency="Expected",
            id="ha1",
            effective=datetime.now(UTC) - timedelta(hours=2),
        )
        # previous is an empty WeatherAlerts, NOT None — the filter doesn't apply
        diff = diff_alerts(alerts(), alerts(old_alert))
        assert len(diff.new_alerts) == 1

    def test_first_load_mixed_old_and_new(self):
        """Only recent alerts fire notifications; old ones silently enter known-set."""
        old_alert = WeatherAlert(
            title="Heat Advisory",
            description="Excessive heat.",
            severity="Moderate",
            urgency="Expected",
            id="ha1",
            effective=datetime.now(UTC) - timedelta(hours=5),
        )
        recent_alert = WeatherAlert(
            title="Tornado Warning",
            description="Take shelter.",
            severity="Extreme",
            urgency="Immediate",
            id="tw1",
            effective=datetime.now(UTC) - timedelta(minutes=2),
        )
        diff = diff_alerts(None, alerts(old_alert, recent_alert))
        assert len(diff.new_alerts) == 1
        assert diff.new_alerts[0].alert_id == "tw1"


# ---------------------------------------------------------------------------
# Cancellation verification via NWS cancel endpoint
# ---------------------------------------------------------------------------


def make_nws_alert(
    alert_id: str,
    title: str = "Test NWS Alert",
    event: str = "Tornado Warning",
) -> WeatherAlert:
    return WeatherAlert(
        title=title,
        description="desc",
        event=event,
        areas=["County A"],
        id=alert_id,
        source="NWS",
        expires=datetime.now(UTC) + timedelta(hours=1),
    )


class TestCancellationVerification:
    def test_genuine_cancel_fires_notification(self):
        """NWS alert in confirmed_cancel_ids → cancel notification fires."""
        prev_snap = alerts(make_nws_alert("NWS-1"))
        curr_snap = alerts()
        diff = diff_alerts(prev_snap, curr_snap, confirmed_cancel_ids={"NWS-1"})
        assert len(diff.cancelled_alerts) == 1
        assert diff.cancelled_alerts[0].alert_id == "NWS-1"

    def test_alert_disappears_not_in_cancel_list_suppressed(self):
        """NWS alert disappears but not in confirmed_cancel_ids → suppressed."""
        prev_snap = alerts(make_nws_alert("NWS-1"))
        curr_snap = alerts()
        diff = diff_alerts(prev_snap, curr_snap, confirmed_cancel_ids=set())
        assert len(diff.cancelled_alerts) == 0

    def test_confirmed_cancel_ids_none_suppresses_nws(self):
        """confirmed_cancel_ids=None → NWS cancels suppressed (safe default)."""
        prev_snap = alerts(make_nws_alert("NWS-1"))
        curr_snap = alerts()
        diff = diff_alerts(prev_snap, curr_snap, confirmed_cancel_ids=None)
        assert len(diff.cancelled_alerts) == 0

    def test_openmeteo_alert_cancel_fires_without_confirmation(self):
        """Open-Meteo alerts: disappear = cancelled regardless of confirmed_cancel_ids."""
        om = WeatherAlert(title="OM", description="d", id="OM-1", source="Open-Meteo")
        prev_snap = alerts(om)
        curr_snap = alerts()
        diff = diff_alerts(prev_snap, curr_snap, confirmed_cancel_ids=None)
        assert len(diff.cancelled_alerts) == 1
        assert diff.cancelled_alerts[0].alert_id == "OM-1"

    def test_pirate_weather_alert_cancel_is_suppressed_without_confirmation(self):
        """Pirate Weather / WMO disappearance should not emit a cancellation by default."""
        pw = WeatherAlert(title="PW", description="d", id="PW-1", source="PirateWeather")
        prev_snap = alerts(pw)
        curr_snap = alerts()
        diff = diff_alerts(prev_snap, curr_snap, confirmed_cancel_ids=None)
        assert len(diff.cancelled_alerts) == 0

    def test_stale_cache_flicker_no_notification(self):
        """Alert disappears then reappears → no cancel notification."""
        a = make_nws_alert("NWS-1")
        prev_snap = alerts(a)
        curr_snap = alerts(a)
        diff = diff_alerts(prev_snap, curr_snap, confirmed_cancel_ids=set())
        assert len(diff.cancelled_alerts) == 0

    def test_update_supersession_no_cancel(self):
        """Alert replaced by new ID (NWS Update pattern) → old ID suppressed."""
        old = make_nws_alert("NWS-OLD")
        new = make_nws_alert("NWS-NEW")
        prev_snap = alerts(old)
        curr_snap = alerts(new)
        diff = diff_alerts(prev_snap, curr_snap, confirmed_cancel_ids={"NWS-UNRELATED"})
        assert len(diff.cancelled_alerts) == 0
        assert len(diff.new_alerts) == 1


# ---------------------------------------------------------------------------
# _alert_is_recently_issued helper
# ---------------------------------------------------------------------------


class TestAlertIsRecentlyIssued:
    def test_recent_alert_returns_true(self):
        alert = WeatherAlert(
            title="Test",
            description="Test",
            effective=datetime.now(UTC) - timedelta(minutes=5),
        )
        assert _alert_is_recently_issued(alert) is True

    def test_old_alert_returns_false(self):
        alert = WeatherAlert(
            title="Test",
            description="Test",
            effective=datetime.now(UTC) - timedelta(hours=1),
        )
        assert _alert_is_recently_issued(alert) is False

    def test_no_timestamps_returns_true(self):
        alert = WeatherAlert(title="Test", description="Test")
        assert _alert_is_recently_issued(alert) is True

    def test_none_alert_returns_true(self):
        assert _alert_is_recently_issued(None) is True

    def test_onset_used_when_no_effective(self):
        alert = WeatherAlert(
            title="Test",
            description="Test",
            onset=datetime.now(UTC) - timedelta(hours=2),
        )
        assert _alert_is_recently_issued(alert) is False

    def test_naive_datetime_treated_as_utc(self):
        alert = WeatherAlert(
            title="Test",
            description="Test",
            effective=datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=2),
        )
        assert _alert_is_recently_issued(alert) is False
