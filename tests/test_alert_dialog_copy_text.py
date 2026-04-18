"""Tests for AlertDialog._copy_payload (clipboard text source)."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from accessiweather.models.config import AppSettings
from accessiweather.ui.dialogs.alert_dialog import AlertDialog


def _alert():
    return SimpleNamespace(
        title="t",
        description="WHAT...Frost.\nWHERE...Michigan.",
        severity="Moderate",
        urgency="Expected",
        certainty="Likely",
        event="Frost Advisory",
        headline="FROST ADVISORY IN EFFECT 2 AM TO 10 AM",
        instruction="Protect tender plants.",
        areas=[],
        references=[],
        sent=datetime(2026, 4, 18, 14, 10),
        expires=datetime(2026, 4, 18, 22, 15),
    )


class TestCopyPayload:
    def test_matches_build_combined_text(self) -> None:
        alert = _alert()
        settings = AppSettings()
        assert AlertDialog._copy_payload(alert, settings) == AlertDialog._build_combined_text(
            alert, settings
        )

    def test_contains_expected_sections(self) -> None:
        alert = _alert()
        payload = AlertDialog._copy_payload(alert, AppSettings())
        assert "FROST ADVISORY" in payload
        assert "WHAT...Frost" in payload
        assert "Protect tender plants" in payload
        assert "Issued:" in payload
        assert "Expires:" in payload

    def test_identical_regardless_of_display_style(self) -> None:
        alert = _alert()
        separate = AlertDialog._copy_payload(alert, AppSettings(alert_display_style="separate"))
        combined = AlertDialog._copy_payload(alert, AppSettings(alert_display_style="combined"))
        assert separate == combined

    def test_settings_none_does_not_crash(self) -> None:
        alert = _alert()
        payload = AlertDialog._copy_payload(alert, None)
        assert "FROST ADVISORY" in payload
