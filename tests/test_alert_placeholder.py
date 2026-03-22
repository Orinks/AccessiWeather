"""Tests for the {alert} tray text placeholder."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from accessiweather.format_string_parser import FormatStringParser
from accessiweather.models import WeatherAlert, WeatherAlerts
from accessiweather.taskbar_icon_updater import TaskbarIconUpdater

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_alert(event: str, severity: str, expires_in_hours: float = 8.0) -> WeatherAlert:
    return WeatherAlert(
        title=event,
        description=f"{event} in effect.",
        severity=severity,
        event=event,
        expires=datetime.now(UTC) + timedelta(hours=expires_in_hours),
    )


def _make_current() -> SimpleNamespace:
    return SimpleNamespace(
        temperature_f=72.0,
        temperature_c=22.2,
        condition="Partly Cloudy",
        humidity=60,
        wind_speed=8.0,
        wind_speed_mph=8.0,
        wind_speed_kph=12.9,
        wind_direction="NW",
        pressure_in=30.0,
        pressure_mb=1015.9,
        feels_like_f=74.0,
        feels_like_c=23.3,
        uv_index=5,
        visibility_miles=10.0,
        visibility_km=16.1,
        precipitation=0.0,
        precipitation_mm=0.0,
        precipitation_probability=20,
        has_data=lambda: True,
    )


def _make_weather_data(alerts: list[WeatherAlert] | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        current_conditions=_make_current(),
        forecast=None,
        alerts=WeatherAlerts(alerts=alerts or []),
    )


def _make_updater(format_string: str = "{alert}") -> TaskbarIconUpdater:
    return TaskbarIconUpdater(
        text_enabled=True,
        format_string=format_string,
        temperature_unit="fahrenheit",
    )


# ---------------------------------------------------------------------------
# FormatStringParser: 'alert' is a supported placeholder
# ---------------------------------------------------------------------------


class TestAlertPlaceholderRegistered:
    def test_alert_in_supported_placeholders(self):
        assert "alert" in FormatStringParser.SUPPORTED_PLACEHOLDERS

    def test_alert_validates_ok(self):
        parser = FormatStringParser()
        valid, err = parser.validate_format_string("{alert}")
        assert valid is True
        assert err is None

    def test_alert_help_text_mentions_alert(self):
        help_text = FormatStringParser.get_supported_placeholders_help()
        assert "{alert}" in help_text


# ---------------------------------------------------------------------------
# _extract_alert_event: unit tests on the helper method
# ---------------------------------------------------------------------------


class TestExtractAlertEvent:
    def setup_method(self):
        self.updater = _make_updater()

    def test_no_alerts_returns_empty(self):
        wd = _make_weather_data(alerts=[])
        assert self.updater._extract_alert_event(wd) == ""

    def test_none_alerts_container_returns_empty(self):
        wd = SimpleNamespace(alerts=None)
        assert self.updater._extract_alert_event(wd) == ""

    def test_no_alerts_attribute_returns_empty(self):
        assert self.updater._extract_alert_event(SimpleNamespace()) == ""

    def test_single_alert_returns_event(self):
        wd = _make_weather_data(alerts=[_make_alert("Heat Advisory", "Moderate")])
        assert self.updater._extract_alert_event(wd) == "Heat Advisory"

    def test_picks_most_severe(self):
        alerts = [
            _make_alert("Heat Advisory", "Moderate"),
            _make_alert("Tornado Warning", "Extreme"),
            _make_alert("Wind Advisory", "Minor"),
        ]
        wd = _make_weather_data(alerts=alerts)
        assert self.updater._extract_alert_event(wd) == "Tornado Warning"

    def test_severity_order_extreme_beats_severe(self):
        alerts = [
            _make_alert("Severe Thunderstorm Warning", "Severe"),
            _make_alert("Tornado Emergency", "Extreme"),
        ]
        wd = _make_weather_data(alerts=alerts)
        assert self.updater._extract_alert_event(wd) == "Tornado Emergency"

    def test_severity_order_severe_beats_moderate(self):
        alerts = [
            _make_alert("Heat Advisory", "Moderate"),
            _make_alert("Flash Flood Warning", "Severe"),
        ]
        wd = _make_weather_data(alerts=alerts)
        assert self.updater._extract_alert_event(wd) == "Flash Flood Warning"

    def test_severity_order_moderate_beats_minor(self):
        alerts = [
            _make_alert("Wind Advisory", "Minor"),
            _make_alert("Frost Advisory", "Moderate"),
        ]
        wd = _make_weather_data(alerts=alerts)
        assert self.updater._extract_alert_event(wd) == "Frost Advisory"

    def test_ties_pick_first(self):
        alerts = [
            _make_alert("Red Flag Warning", "Moderate"),
            _make_alert("Dense Fog Advisory", "Moderate"),
        ]
        wd = _make_weather_data(alerts=alerts)
        # max() is stable on ties — first element with highest priority wins
        assert self.updater._extract_alert_event(wd) == "Red Flag Warning"

    def test_unknown_severity_treated_as_lowest(self):
        alerts = [
            _make_alert("Special Statement", "Unknown"),
            _make_alert("Wind Advisory", "Minor"),
        ]
        wd = _make_weather_data(alerts=alerts)
        assert self.updater._extract_alert_event(wd) == "Wind Advisory"

    def test_falls_back_to_title_when_event_is_none(self):
        alert = WeatherAlert(
            title="Custom Alert Title",
            description="desc",
            severity="Moderate",
            event=None,
        )
        wd = _make_weather_data(alerts=[alert])
        assert self.updater._extract_alert_event(wd) == "Custom Alert Title"


# ---------------------------------------------------------------------------
# format_tooltip: end-to-end via public API
# ---------------------------------------------------------------------------


class TestAlertPlaceholderFormatTooltip:
    def test_alert_populated_in_tooltip(self):
        updater = _make_updater("{alert}")
        wd = _make_weather_data(alerts=[_make_alert("Tornado Watch", "Severe")])
        result = updater.format_tooltip(wd, location_name="Test City")
        assert result == "Tornado Watch"

    def test_alert_empty_when_no_alerts(self):
        updater = _make_updater("Weather: {alert}")
        wd = _make_weather_data(alerts=[])
        result = updater.format_tooltip(wd, location_name="Test City")
        # Trailing space is stripped by format_with_fallback
        assert result == "Weather:"

    def test_alert_combined_with_other_placeholders(self):
        updater = _make_updater("{temp} | {alert}")
        wd = _make_weather_data(alerts=[_make_alert("Red Flag Warning", "Moderate")])
        result = updater.format_tooltip(wd, location_name="Test City")
        assert "Red Flag Warning" in result
        assert "72F" in result

    def test_most_severe_shown_when_multiple_alerts(self):
        updater = _make_updater("{alert}")
        alerts = [
            _make_alert("Wind Advisory", "Minor"),
            _make_alert("Flash Flood Warning", "Extreme"),
            _make_alert("Heat Advisory", "Moderate"),
        ]
        wd = _make_weather_data(alerts=alerts)
        result = updater.format_tooltip(wd, location_name="Test City")
        assert result == "Flash Flood Warning"
