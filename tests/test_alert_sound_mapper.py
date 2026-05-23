"""
Tests for alert_sound_mapper module.

Alert sounds are severity-first. Exact alert text, hazard names, and alert
types are intentionally not part of normal candidate generation.
"""

from __future__ import annotations

import pytest

from accessiweather.models.alerts import WeatherAlert
from accessiweather.notifications.alert_sound_mapper import (
    ALERT_UPDATED_EVENT,
    GENERIC_FALLBACKS,
    KNOWN_SEVERITY_KEYS,
    choose_sound_event,
    get_candidate_sound_events,
)


def _alert(severity: str | None, event: str = "Tornado Warning") -> WeatherAlert:
    return WeatherAlert(
        title=event,
        description="Test alert text.",
        severity=severity,
        event=event,
    )


class TestGetCandidateSoundEvents:
    """Tests for get_candidate_sound_events function."""

    @pytest.mark.parametrize(
        "severity,expected_key",
        [
            ("Extreme", "extreme"),
            ("Severe", "severe"),
            ("Moderate", "moderate"),
            ("Minor", "minor"),
            ("extreme", "extreme"),
            ("SEVERE", "severe"),
        ],
    )
    def test_severity_first_candidates(self, severity: str, expected_key: str):
        candidates = get_candidate_sound_events(_alert(severity))

        assert candidates == [expected_key, "alert", "notify"]

    @pytest.mark.parametrize(
        "severity,expected_key",
        [
            ("critical", "extreme"),
            ("high", "severe"),
            ("medium", "moderate"),
            ("low", "minor"),
        ],
    )
    def test_provider_severity_aliases(self, severity: str, expected_key: str):
        candidates = get_candidate_sound_events(_alert(severity))

        assert candidates == [expected_key, "alert", "notify"]

    def test_unknown_severity_uses_generic_fallbacks(self):
        candidates = get_candidate_sound_events(_alert("Unknown", event="Excessive Heat Watch"))

        assert candidates == ["alert", "notify"]

    def test_missing_severity_uses_generic_fallbacks(self):
        candidates = get_candidate_sound_events(_alert(None))

        assert candidates == ["alert", "notify"]

    def test_alert_text_does_not_generate_specific_candidates(self):
        candidates = get_candidate_sound_events(_alert("Extreme", event="Tornado Warning"))

        assert candidates == ["extreme", "alert", "notify"]
        assert "tornado_warning" not in candidates
        assert "tornado" not in candidates
        assert "warning" not in candidates

    def test_specific_alert_sounds_try_exact_event_before_severity(self):
        candidates = get_candidate_sound_events(
            _alert("Extreme", event="Tornado Warning"), include_specific_events=True
        )

        assert candidates == [
            "tornado_warning",
            "tornado_extreme",
            "tornado",
            "warning",
            "extreme",
            "alert",
            "notify",
        ]

    def test_specific_alert_sounds_distinguish_watch_from_warning(self):
        watch_candidates = get_candidate_sound_events(
            _alert("Moderate", event="Tornado Watch"), include_specific_events=True
        )
        warning_candidates = get_candidate_sound_events(
            _alert("Extreme", event="Tornado Warning"), include_specific_events=True
        )

        assert watch_candidates[0] == "tornado_watch"
        assert warning_candidates[0] == "tornado_warning"

    def test_specific_alert_sounds_include_hazard_type_fallback(self):
        candidates = get_candidate_sound_events(
            _alert("Severe", event="Severe Thunderstorm Warning"),
            include_specific_events=True,
        )

        assert candidates[:3] == [
            "severe_thunderstorm_warning",
            "thunderstorm_warning",
            "thunderstorm_severe",
        ]
        assert candidates[-3:] == ["severe", "alert", "notify"]

    def test_primary_alert_event_takes_priority_over_description_hazard_terms(self):
        alert = WeatherAlert(
            title="Severe Thunderstorm Watch",
            event="Severe Thunderstorm Watch",
            headline="Severe Thunderstorm Watch",
            description="Severe thunderstorms with damaging wind possible.",
            severity="Severe",
        )

        candidates = get_candidate_sound_events(alert, include_specific_events=True)

        assert candidates[:3] == [
            "severe_thunderstorm_watch",
            "thunderstorm_watch",
            "thunderstorm_severe",
        ]
        assert "wind_watch" not in candidates

    def test_generic_fallbacks_always_present_at_end(self):
        candidates = get_candidate_sound_events(_alert("Moderate"))

        assert candidates[-2:] == GENERIC_FALLBACKS

    def test_alert_update_reason_uses_update_event_before_severity_fallback(self):
        candidates = get_candidate_sound_events(
            _alert("Moderate"),
            notification_reason="content_changed",
        )

        assert candidates == [ALERT_UPDATED_EVENT, "moderate", "alert", "notify"]

    def test_alert_update_reason_keeps_specific_alert_fallbacks(self):
        candidates = get_candidate_sound_events(
            _alert("Severe", event="Severe Thunderstorm Warning"),
            include_specific_events=True,
            notification_reason="content_changed",
        )

        assert candidates[:4] == [
            ALERT_UPDATED_EVENT,
            "severe_thunderstorm_warning",
            "thunderstorm_warning",
            "thunderstorm_severe",
        ]
        assert candidates[-3:] == ["severe", "alert", "notify"]


class TestChooseSoundEvent:
    """Tests for choose_sound_event function."""

    def test_choose_returns_first_candidate(self):
        alert = _alert("Extreme")
        chosen = choose_sound_event(alert)

        assert chosen == get_candidate_sound_events(alert)[0]
        assert chosen == "extreme"

    def test_choose_with_unknown_severity_returns_alert(self):
        assert choose_sound_event(_alert("Unknown")) == "alert"

    def test_choose_with_specific_alert_sounds_returns_exact_event(self):
        assert (
            choose_sound_event(_alert("Extreme"), include_specific_events=True) == "tornado_warning"
        )


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_no_duplicates(self):
        candidates = get_candidate_sound_events(_alert("Severe"))

        assert len(candidates) == len(set(candidates))

    def test_very_long_event_name_does_not_affect_mapping(self):
        long_event = "Very Long Weather Event Name That Goes On And On Warning"
        candidates = get_candidate_sound_events(_alert("Moderate", event=long_event))

        assert candidates == ["moderate", "alert", "notify"]


class TestKnownConstants:
    """Tests to verify the constants are properly defined."""

    def test_known_severity_keys(self):
        assert KNOWN_SEVERITY_KEYS == ["extreme", "severe", "moderate", "minor"]

    def test_generic_fallbacks(self):
        assert GENERIC_FALLBACKS == ["alert", "notify"]
