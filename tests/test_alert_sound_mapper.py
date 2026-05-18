"""
Tests for alert_sound_mapper module.

Alert sounds are severity-first. Exact alert text, hazard names, and alert
types are intentionally not part of normal candidate generation.
"""

from __future__ import annotations

import pytest

from accessiweather.models.alerts import WeatherAlert
from accessiweather.notifications.alert_sound_mapper import (
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

    def test_generic_fallbacks_always_present_at_end(self):
        candidates = get_candidate_sound_events(_alert("Moderate"))

        assert candidates[-2:] == GENERIC_FALLBACKS


class TestChooseSoundEvent:
    """Tests for choose_sound_event function."""

    def test_choose_returns_first_candidate(self):
        alert = _alert("Extreme")
        chosen = choose_sound_event(alert)

        assert chosen == get_candidate_sound_events(alert)[0]
        assert chosen == "extreme"

    def test_choose_with_unknown_severity_returns_alert(self):
        assert choose_sound_event(_alert("Unknown")) == "alert"


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
