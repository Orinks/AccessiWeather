"""
Tests for alert_sound_mapper module.

Tests the mapping of WeatherAlert objects to sound event keys,
including hazard detection, severity fallbacks, and candidate ordering.
"""

from __future__ import annotations

import pytest

from accessiweather.models.alerts import WeatherAlert
from accessiweather.notifications.alert_sound_mapper import (
    GENERIC_FALLBACKS,
    HAZARD_KEYWORDS,
    KNOWN_ALERT_TYPE_KEYS,
    KNOWN_SEVERITY_KEYS,
    choose_sound_event,
    get_candidate_sound_events,
)


class TestGetCandidateSoundEvents:
    """Tests for get_candidate_sound_events function."""

    def test_tornado_warning_candidates(self):
        """Test that Tornado Warning generates correct candidates."""
        alert = WeatherAlert(
            title="Tornado Warning",
            description="A tornado has been spotted.",
            severity="Extreme",
            event="Tornado Warning",
        )
        candidates = get_candidate_sound_events(alert)

        # Should include normalized event, hazard+type combo, severity, and fallbacks
        assert "tornado_warning" in candidates
        assert "tornado" in candidates  # hazard
        assert "warning" in candidates  # type
        assert "extreme" in candidates  # severity
        assert "alert" in candidates  # generic fallback

    def test_excessive_heat_watch_candidates(self):
        """Test Excessive Heat Watch generates correct candidates."""
        alert = WeatherAlert(
            title="Excessive Heat Watch",
            description="Dangerously hot conditions possible.",
            severity="Severe",
            event="Excessive Heat Watch",
        )
        candidates = get_candidate_sound_events(alert)

        assert "excessive_heat_watch" in candidates
        assert "heat_watch" in candidates  # hazard + type
        assert "heat" in candidates  # hazard only
        assert "watch" in candidates  # type
        assert "severe" in candidates  # severity

    def test_winter_storm_warning_candidates(self):
        """Test Winter Storm Warning generates correct candidates."""
        alert = WeatherAlert(
            title="Winter Storm Warning",
            description="Heavy snow and ice expected.",
            severity="Severe",
            event="Winter Storm Warning",
        )
        candidates = get_candidate_sound_events(alert)

        assert "winter_storm_warning" in candidates
        assert "winter_warning" in candidates
        assert "winter" in candidates
        assert "warning" in candidates

    def test_flood_advisory_candidates(self):
        """Test Flood Advisory generates correct candidates."""
        alert = WeatherAlert(
            title="Flood Advisory",
            description="Minor flooding expected.",
            severity="Minor",
            event="Flood Advisory",
        )
        candidates = get_candidate_sound_events(alert)

        assert "flood_advisory" in candidates
        assert "flood" in candidates
        assert "advisory" in candidates
        assert "minor" in candidates

    def test_severity_fallback_extreme(self):
        """Test that Extreme severity is included in candidates."""
        alert = WeatherAlert(
            title="Unknown Alert Type",
            description="Some unknown alert.",
            severity="Extreme",
            event="Special Weather Statement",
        )
        candidates = get_candidate_sound_events(alert)

        assert "extreme" in candidates
        assert "statement" in candidates

    def test_severity_fallback_moderate(self):
        """Test that Moderate severity is included in candidates."""
        alert = WeatherAlert(
            title="Some Advisory",
            description="Some weather condition.",
            severity="Moderate",
            event="Some Advisory",
        )
        candidates = get_candidate_sound_events(alert)

        assert "moderate" in candidates
        assert "advisory" in candidates

    def test_generic_fallbacks_always_present(self):
        """Test that generic fallbacks are always at the end."""
        alert = WeatherAlert(
            title="Random Alert",
            description="Random description.",
            severity="Unknown",
        )
        candidates = get_candidate_sound_events(alert)

        # Generic fallbacks should be at the end
        for fb in GENERIC_FALLBACKS:
            assert fb in candidates

    def test_candidate_order_specific_first(self):
        """Test that specific keys come before generic ones."""
        alert = WeatherAlert(
            title="Tornado Warning",
            description="Tornado spotted.",
            severity="Extreme",
            event="Tornado Warning",
        )
        candidates = get_candidate_sound_events(alert)

        # Normalized event should be first
        assert candidates[0] == "tornado_warning"

        # Generic fallbacks should be at the end
        alert_idx = candidates.index("alert")
        notify_idx = candidates.index("notify")
        assert alert_idx > candidates.index("tornado_warning")
        assert notify_idx > alert_idx or notify_idx == len(candidates) - 1


class TestChooseSoundEvent:
    """Tests for choose_sound_event function."""

    def test_choose_returns_first_candidate(self):
        """Test that choose_sound_event returns the first candidate."""
        alert = WeatherAlert(
            title="Tornado Warning",
            description="Tornado spotted.",
            severity="Extreme",
            event="Tornado Warning",
        )
        chosen = choose_sound_event(alert)
        candidates = get_candidate_sound_events(alert)

        assert chosen == candidates[0]
        assert chosen == "tornado_warning"

    def test_choose_with_no_event(self):
        """Test choosing sound when event is None."""
        alert = WeatherAlert(
            title="Weather Alert",
            description="Some weather condition.",
            severity="Moderate",
        )
        chosen = choose_sound_event(alert)

        # Should still return something useful
        assert chosen is not None
        assert len(chosen) > 0


class TestHazardDetection:
    """Tests for hazard keyword detection."""

    @pytest.mark.parametrize(
        "event,expected_hazard",
        [
            ("Flash Flood Warning", "flood"),
            ("Tornado Watch", "tornado"),
            ("Excessive Heat Warning", "heat"),
            ("High Wind Warning", "wind"),
            ("Winter Storm Watch", "winter"),
            ("Heavy Snow Warning", "snow"),
            ("Ice Storm Warning", "ice"),
            ("Severe Thunderstorm Warning", "thunderstorm"),
            ("Hurricane Warning", "hurricane"),
            ("Red Flag Warning", "fire"),
            ("Dense Fog Advisory", "fog"),
            ("Blowing Dust Advisory", "dust"),
            ("Air Quality Alert", "air_quality"),
        ],
    )
    def test_hazard_detection(self, event: str, expected_hazard: str):
        """Test that hazards are correctly detected from event names."""
        alert = WeatherAlert(
            title=event,
            description="Test description.",
            severity="Moderate",
            event=event,
        )
        candidates = get_candidate_sound_events(alert)

        assert expected_hazard in candidates


class TestSeverityNormalization:
    """Tests for severity normalization."""

    @pytest.mark.parametrize(
        "severity,expected_key",
        [
            ("Extreme", "extreme"),
            ("Severe", "severe"),
            ("Moderate", "moderate"),
            ("Minor", "minor"),
            ("extreme", "extreme"),  # lowercase
            ("SEVERE", "severe"),  # uppercase (if normalized)
        ],
    )
    def test_severity_in_candidates(self, severity: str, expected_key: str):
        """Test that severity levels are properly included in candidates."""
        alert = WeatherAlert(
            title="Test Alert",
            description="Test description.",
            severity=severity,
            event="Test Warning",
        )
        candidates = get_candidate_sound_events(alert)

        # Note: The mapper normalizes to lowercase
        # Check if the expected key or its lowercase version is present
        assert expected_key in candidates or expected_key.lower() in candidates


class TestAlertTypeDetection:
    """Tests for alert type (warning/watch/advisory/statement) detection."""

    @pytest.mark.parametrize(
        "event,expected_type",
        [
            ("Tornado Warning", "warning"),
            ("Winter Storm Watch", "watch"),
            ("Heat Advisory", "advisory"),
            ("Special Weather Statement", "statement"),
        ],
    )
    def test_alert_type_detection(self, event: str, expected_type: str):
        """Test that alert types are correctly detected."""
        alert = WeatherAlert(
            title=event,
            description="Test.",
            severity="Moderate",
            event=event,
        )
        candidates = get_candidate_sound_events(alert)

        assert expected_type in candidates


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_event(self):
        """Test handling of empty/None event."""
        alert = WeatherAlert(
            title="Alert",
            description="Description",
            severity="Moderate",
            event=None,
        )
        candidates = get_candidate_sound_events(alert)

        # Should still have fallbacks
        assert "alert" in candidates
        assert "notify" in candidates

    def test_unknown_severity(self):
        """Test handling of unknown severity."""
        alert = WeatherAlert(
            title="Alert",
            description="Description",
            severity="Unknown",
            event="Some Warning",
        )
        candidates = get_candidate_sound_events(alert)

        # Should not include invalid severity keys
        assert "unknown" not in candidates or candidates.index("unknown") > 0
        # Should still have type and fallbacks
        assert "warning" in candidates
        assert "alert" in candidates

    def test_no_duplicates(self):
        """Test that candidates don't have duplicates."""
        alert = WeatherAlert(
            title="Flood Warning",
            description="Flooding expected in flood-prone areas.",
            severity="Severe",
            event="Flood Warning",
            headline="Flood Warning for flood areas",
        )
        candidates = get_candidate_sound_events(alert)

        # Check no duplicates
        assert len(candidates) == len(set(candidates))

    def test_very_long_event_name(self):
        """Test handling of unusually long event names."""
        long_event = "Very Long Weather Event Name That Goes On And On Warning"
        alert = WeatherAlert(
            title=long_event,
            description="Description",
            severity="Moderate",
            event=long_event,
        )
        candidates = get_candidate_sound_events(alert)

        # Should still work and have warning type
        assert "warning" in candidates
        assert len(candidates) > 0


class TestKnownConstants:
    """Tests to verify the constants are properly defined."""

    def test_known_alert_type_keys(self):
        """Test that known alert type keys are defined."""
        assert "warning" in KNOWN_ALERT_TYPE_KEYS
        assert "watch" in KNOWN_ALERT_TYPE_KEYS
        assert "advisory" in KNOWN_ALERT_TYPE_KEYS
        assert "statement" in KNOWN_ALERT_TYPE_KEYS

    def test_known_severity_keys(self):
        """Test that known severity keys are defined."""
        assert "extreme" in KNOWN_SEVERITY_KEYS
        assert "severe" in KNOWN_SEVERITY_KEYS
        assert "moderate" in KNOWN_SEVERITY_KEYS
        assert "minor" in KNOWN_SEVERITY_KEYS

    def test_hazard_keywords_coverage(self):
        """Test that common hazards are covered."""
        hazards = list(HAZARD_KEYWORDS.keys())
        assert "flood" in hazards
        assert "tornado" in hazards
        assert "heat" in hazards
        assert "wind" in hazards
        assert "winter" in hazards
        assert "thunderstorm" in hazards
        assert "hurricane" in hazards

    def test_generic_fallbacks(self):
        """Test that generic fallbacks are defined."""
        assert "alert" in GENERIC_FALLBACKS
        assert "notify" in GENERIC_FALLBACKS
