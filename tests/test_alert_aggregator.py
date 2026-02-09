"""Tests for accessiweather.weather_client_alerts.AlertAggregator."""

from datetime import UTC, datetime, timedelta

from accessiweather.models.alerts import WeatherAlert, WeatherAlerts
from accessiweather.weather_client_alerts import AlertAggregator


def _make_alert(
    event="Winter Storm Warning",
    areas=None,
    onset=None,
    source=None,
    description="Test alert",
    severity="Severe",
    urgency="Immediate",
    certainty="Likely",
    headline=None,
    instruction=None,
):
    return WeatherAlert(
        title=f"Test: {event}",
        description=description,
        event=event,
        areas=areas or ["Test County"],
        onset=onset,
        source=source,
        severity=severity,
        urgency=urgency,
        certainty=certainty,
        headline=headline,
        instruction=instruction,
    )


class TestAlertAggregatorInit:
    def test_default_window(self):
        agg = AlertAggregator()
        assert agg.dedup_time_window == timedelta(minutes=60)

    def test_custom_window(self):
        agg = AlertAggregator(dedup_time_window_minutes=30)
        assert agg.dedup_time_window == timedelta(minutes=30)


class TestAggregateAlerts:
    def setup_method(self):
        self.agg = AlertAggregator()

    def test_both_none(self):
        result = self.agg.aggregate_alerts(None, None)
        assert result.alerts == []

    def test_nws_only(self):
        nws = WeatherAlerts(alerts=[_make_alert(source=None)])
        result = self.agg.aggregate_alerts(nws, None)
        assert len(result.alerts) == 1
        assert result.alerts[0].source == "nws"

    def test_vc_only(self):
        vc = WeatherAlerts(alerts=[_make_alert(source=None)])
        result = self.agg.aggregate_alerts(None, vc)
        assert len(result.alerts) == 1
        assert result.alerts[0].source == "visualcrossing"

    def test_both_sources_no_duplicates(self):
        nws = WeatherAlerts(alerts=[_make_alert(event="Tornado Warning")])
        vc = WeatherAlerts(alerts=[_make_alert(event="Flood Watch")])
        result = self.agg.aggregate_alerts(nws, vc)
        assert len(result.alerts) == 2

    def test_both_sources_with_duplicate(self):
        now = datetime.now(UTC)
        nws = WeatherAlerts(alerts=[_make_alert(onset=now, source="nws")])
        vc = WeatherAlerts(alerts=[_make_alert(onset=now, source="visualcrossing")])
        result = self.agg.aggregate_alerts(nws, vc)
        assert len(result.alerts) == 1  # deduplicated

    def test_empty_alert_lists(self):
        nws = WeatherAlerts(alerts=[])
        vc = WeatherAlerts(alerts=[])
        result = self.agg.aggregate_alerts(nws, vc)
        assert result.alerts == []

    def test_source_preserved_if_already_set(self):
        nws = WeatherAlerts(alerts=[_make_alert(source="custom-nws")])
        result = self.agg.aggregate_alerts(nws, None)
        assert result.alerts[0].source == "custom-nws"


class TestDeduplicateAlerts:
    def setup_method(self):
        self.agg = AlertAggregator()

    def test_empty_list(self):
        assert self.agg._deduplicate_alerts([]) == []

    def test_no_duplicates(self):
        alerts = [
            _make_alert(event="Tornado Warning"),
            _make_alert(event="Flood Watch"),
        ]
        result = self.agg._deduplicate_alerts(alerts)
        assert len(result) == 2

    def test_duplicates_merged(self):
        now = datetime.now(UTC)
        alerts = [
            _make_alert(onset=now, source="nws", description="short"),
            _make_alert(onset=now, source="vc", description="a much longer description here"),
        ]
        result = self.agg._deduplicate_alerts(alerts)
        assert len(result) == 1


class TestIsDuplicate:
    def setup_method(self):
        self.agg = AlertAggregator()

    def test_different_events(self):
        a1 = _make_alert(event="Tornado Warning")
        a2 = _make_alert(event="Flood Watch")
        assert not self.agg._is_duplicate(a1, a2)

    def test_same_event_same_area(self):
        a1 = _make_alert()
        a2 = _make_alert()
        assert self.agg._is_duplicate(a1, a2)

    def test_non_overlapping_areas(self):
        a1 = _make_alert(areas=["County A"])
        a2 = _make_alert(areas=["County B"])
        assert not self.agg._is_duplicate(a1, a2)

    def test_onset_within_window(self):
        now = datetime.now(UTC)
        a1 = _make_alert(onset=now)
        a2 = _make_alert(onset=now + timedelta(minutes=30))
        assert self.agg._is_duplicate(a1, a2)

    def test_onset_outside_window(self):
        now = datetime.now(UTC)
        a1 = _make_alert(onset=now)
        a2 = _make_alert(onset=now + timedelta(hours=2))
        assert not self.agg._is_duplicate(a1, a2)

    def test_none_onsets_still_match(self):
        a1 = _make_alert(onset=None)
        a2 = _make_alert(onset=None)
        assert self.agg._is_duplicate(a1, a2)

    def test_mixed_tz_aware_naive(self):
        aware = datetime(2025, 1, 1, 12, 0, tzinfo=UTC)
        naive = datetime(2025, 1, 1, 12, 0)
        a1 = _make_alert(onset=aware)
        a2 = _make_alert(onset=naive)
        # Should not crash; timezone normalization handles it
        result = self.agg._is_duplicate(a1, a2)
        assert isinstance(result, bool)

    def test_one_onset_none(self):
        a1 = _make_alert(onset=datetime.now(UTC))
        a2 = _make_alert(onset=None)
        # If one onset is None, time check is skipped, so they match on event+area
        assert self.agg._is_duplicate(a1, a2)


class TestAreasOverlap:
    def setup_method(self):
        self.agg = AlertAggregator()

    def test_empty_first(self):
        assert self.agg._areas_overlap([], ["County A"]) is True

    def test_empty_second(self):
        assert self.agg._areas_overlap(["County A"], []) is True

    def test_both_empty(self):
        assert self.agg._areas_overlap([], []) is True

    def test_overlap(self):
        assert self.agg._areas_overlap(["County A", "County B"], ["County B", "County C"]) is True

    def test_no_overlap(self):
        assert self.agg._areas_overlap(["County A"], ["County B"]) is False

    def test_case_insensitive(self):
        assert self.agg._areas_overlap(["county a"], ["COUNTY A"]) is True

    def test_whitespace_stripped(self):
        assert self.agg._areas_overlap(["  County A  "], ["county a"]) is True


class TestMergeDuplicateAlerts:
    def setup_method(self):
        self.agg = AlertAggregator()

    def test_single_alert(self):
        alert = _make_alert()
        result = self.agg._merge_duplicate_alerts([alert])
        assert result is alert

    def test_nws_preferred_as_base(self):
        nws = _make_alert(source="nws", severity="Severe")
        vc = _make_alert(source="visualcrossing", severity="Unknown")
        result = self.agg._merge_duplicate_alerts([vc, nws])
        # NWS should be base (sorted first)
        assert result.severity == "Severe"

    def test_longer_description_wins(self):
        nws = _make_alert(source="nws", description="short")
        vc = _make_alert(
            source="visualcrossing", description="a much longer and more detailed description"
        )
        result = self.agg._merge_duplicate_alerts([nws, vc])
        assert result.description == "a much longer and more detailed description"

    def test_longer_headline_wins(self):
        nws = _make_alert(source="nws", headline="brief")
        vc = _make_alert(source="visualcrossing", headline="a much longer headline text")
        result = self.agg._merge_duplicate_alerts([nws, vc])
        assert result.headline == "a much longer headline text"

    def test_longer_instruction_wins(self):
        nws = _make_alert(source="nws", instruction="go")
        vc = _make_alert(
            source="visualcrossing", instruction="take shelter immediately and seek cover"
        )
        result = self.agg._merge_duplicate_alerts([nws, vc])
        assert result.instruction == "take shelter immediately and seek cover"

    def test_unknown_metadata_replaced(self):
        nws = _make_alert(source="nws", severity="Unknown", urgency="Unknown", certainty="Unknown")
        vc = _make_alert(
            source="visualcrossing", severity="Moderate", urgency="Future", certainty="Possible"
        )
        result = self.agg._merge_duplicate_alerts([nws, vc])
        assert result.severity == "Moderate"
        assert result.urgency == "Future"
        assert result.certainty == "Possible"

    def test_source_merged(self):
        nws = _make_alert(source="nws")
        vc = _make_alert(source="visualcrossing")
        result = self.agg._merge_duplicate_alerts([nws, vc])
        assert "nws" in result.source
        assert "visualcrossing" in result.source

    def test_areas_unioned(self):
        nws = _make_alert(source="nws", areas=["County A"])
        vc = _make_alert(source="visualcrossing", areas=["County B"])
        result = self.agg._merge_duplicate_alerts([nws, vc])
        assert set(result.areas) == {"County A", "County B"}

    def test_non_unknown_severity_kept(self):
        # If base already has good severity, VC Unknown shouldn't replace it
        nws = _make_alert(source="nws", severity="Extreme")
        vc = _make_alert(source="visualcrossing", severity="Unknown")
        result = self.agg._merge_duplicate_alerts([nws, vc])
        assert result.severity == "Extreme"
