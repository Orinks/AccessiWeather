"""Tests for alert display + date format settings round-trip."""

from __future__ import annotations

from accessiweather.models.config import AppSettings


class TestDefaults:
    def test_alert_display_style_defaults_to_separate(self) -> None:
        assert AppSettings().alert_display_style == "separate"

    def test_date_format_defaults_to_iso(self) -> None:
        assert AppSettings().date_format == "iso"


class TestRoundTrip:
    def test_to_dict_includes_new_fields(self) -> None:
        data = AppSettings().to_dict()
        assert data["alert_display_style"] == "separate"
        assert data["date_format"] == "iso"

    def test_from_dict_preserves_valid_values(self) -> None:
        settings = AppSettings.from_dict(
            {"alert_display_style": "combined", "date_format": "us_long"}
        )
        assert settings.alert_display_style == "combined"
        assert settings.date_format == "us_long"

    def test_from_dict_falls_back_on_bogus_alert_display_style(self) -> None:
        settings = AppSettings.from_dict({"alert_display_style": "bogus"})
        assert settings.alert_display_style == "separate"

    def test_from_dict_falls_back_on_bogus_date_format(self) -> None:
        settings = AppSettings.from_dict({"date_format": "not-a-format"})
        assert settings.date_format == "iso"

    def test_from_dict_empty_dict_uses_defaults(self) -> None:
        settings = AppSettings.from_dict({})
        assert settings.alert_display_style == "separate"
        assert settings.date_format == "iso"

    def test_from_dict_non_string_values_fall_back(self) -> None:
        settings = AppSettings.from_dict({"alert_display_style": None, "date_format": 42})
        assert settings.alert_display_style == "separate"
        assert settings.date_format == "iso"

    def test_full_round_trip_preserves_combined_and_us_long(self) -> None:
        original = AppSettings(alert_display_style="combined", date_format="us_long")
        restored = AppSettings.from_dict(original.to_dict())
        assert restored.alert_display_style == "combined"
        assert restored.date_format == "us_long"
