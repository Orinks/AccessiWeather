"""Tests for AlertDialog._build_combined_text (pure string assembly)."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from accessiweather.models.config import AppSettings
from accessiweather.ui.dialogs.alert_dialog import AlertDialog


def _alert(**kwargs):
    defaults = {
        "headline": None,
        "event": None,
        "description": None,
        "instruction": None,
        "sent": None,
        "expires": None,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _settings(**kwargs):
    return AppSettings(**kwargs)


class TestBuildCombinedText:
    def test_all_fields_present_in_order(self) -> None:
        alert = _alert(
            headline="FROST ADVISORY IN EFFECT FROM 2 AM TO 10 AM",
            description="WHAT...Frost.\nWHERE...Michigan.",
            instruction="Protect tender plants.",
            sent=datetime(2026, 4, 18, 14, 10),
            expires=datetime(2026, 4, 18, 22, 15),
        )
        text = AlertDialog._build_combined_text(alert, _settings())
        headline_i = text.index("FROST ADVISORY")
        desc_i = text.index("WHAT...Frost")
        instr_i = text.index("Protect tender plants")
        issued_i = text.index("Issued:")
        expires_i = text.index("Expires:")
        assert headline_i < desc_i < instr_i < issued_i < expires_i

    def test_falls_back_to_event_when_no_headline(self) -> None:
        alert = _alert(event="Frost Advisory")
        text = AlertDialog._build_combined_text(alert, _settings())
        assert text.startswith("Frost Advisory")

    def test_missing_instruction_omitted(self) -> None:
        alert = _alert(
            headline="H",
            description="D",
            sent=datetime(2026, 4, 18, 14, 10),
            expires=datetime(2026, 4, 18, 22, 15),
        )
        text = AlertDialog._build_combined_text(alert, _settings())
        assert "Issued:" in text
        assert "None" not in text

    def test_missing_expires_line_absent(self) -> None:
        alert = _alert(
            headline="H",
            sent=datetime(2026, 4, 18, 14, 10),
        )
        text = AlertDialog._build_combined_text(alert, _settings())
        assert "Issued:" in text
        assert "Expires:" not in text

    def test_missing_sent_line_absent(self) -> None:
        alert = _alert(headline="H", expires=datetime(2026, 4, 18, 22, 15))
        text = AlertDialog._build_combined_text(alert, _settings())
        assert "Issued:" not in text
        assert "Expires:" in text

    def test_date_format_and_12hour_applied(self) -> None:
        alert = _alert(
            headline="H",
            sent=datetime(2026, 4, 18, 14, 5),
        )
        settings = _settings(date_format="us_long", time_format_12hour=True)
        text = AlertDialog._build_combined_text(alert, settings)
        assert "Issued: April 18, 2026 2:05 PM" in text

    def test_empty_description_does_not_add_blank_block(self) -> None:
        alert = _alert(headline="H")
        text = AlertDialog._build_combined_text(alert, _settings())
        assert "\n\n\n" not in text

    def test_fallback_headline_when_nothing_given(self) -> None:
        alert = _alert()
        text = AlertDialog._build_combined_text(alert, _settings())
        assert text.startswith("Weather Alert")
