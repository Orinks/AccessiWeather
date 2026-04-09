"""Tests for the show_impact_summaries opt-in setting."""

from __future__ import annotations

from accessiweather.display.presentation.current_conditions import build_current_conditions
from accessiweather.display.presentation.forecast import build_forecast
from accessiweather.models import AppSettings, CurrentConditions, Location
from accessiweather.models.weather import Forecast, ForecastPeriod
from accessiweather.utils import TemperatureUnit

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_location() -> Location:
    return Location(name="Test City", latitude=40.0, longitude=-75.0)


def _make_current() -> CurrentConditions:
    return CurrentConditions(
        temperature_f=72.0,
        temperature_c=22.2,
        condition="Partly Cloudy",
        humidity=60,
        wind_speed_mph=10.0,
        wind_speed_kph=16.1,
        wind_direction="N",
        pressure_in=30.0,
        pressure_mb=1016.0,
        feels_like_f=74.0,
        feels_like_c=23.3,
    )


def _make_forecast() -> Forecast:
    from datetime import UTC, datetime

    period = ForecastPeriod(
        name="Today",
        temperature=75,
        temperature_unit="F",
        short_forecast="Sunny",
        detailed_forecast="Sunny with highs near 75.",
        wind_speed="10 mph",
        wind_direction="NW",
    )
    return Forecast(periods=[period], generated_at=datetime.now(UTC))


def _settings(*, show_impact: bool) -> AppSettings:
    return AppSettings(temperature_unit="fahrenheit", show_impact_summaries=show_impact)


def _impact_labels(presentation) -> list[str]:
    """Return metric labels that start with 'Impact:'."""
    return [m.label for m in presentation.metrics if m.label.startswith("Impact:")]


# ── AppSettings.show_impact_summaries field ───────────────────────────────────


class TestAppSettingsShowImpactSummaries:
    def test_default_is_false(self):
        """Default value must be False so impact summaries are opt-in."""
        assert AppSettings().show_impact_summaries is False

    def test_enabled_roundtrips(self):
        """Enabled flag survives to_dict / from_dict."""
        s = AppSettings(show_impact_summaries=True)
        d = s.to_dict()
        assert d["show_impact_summaries"] is True
        assert AppSettings.from_dict(d).show_impact_summaries is True

    def test_disabled_roundtrips(self):
        """Disabled flag survives to_dict / from_dict."""
        s = AppSettings(show_impact_summaries=False)
        d = s.to_dict()
        assert d["show_impact_summaries"] is False
        assert AppSettings.from_dict(d).show_impact_summaries is False

    def test_missing_key_defaults_false(self):
        """Absent key in stored config resolves to False."""
        assert AppSettings.from_dict({}).show_impact_summaries is False

    def test_truthy_string_accepted(self):
        """String 'true' is accepted via _as_bool."""
        assert (
            AppSettings.from_dict({"show_impact_summaries": "true"}).show_impact_summaries is True
        )


# ── build_current_conditions impact gating ───────────────────────────────────


class TestCurrentConditionsImpactGating:
    def setup_method(self):
        self.current = _make_current()
        self.location = _make_location()

    def test_impact_metrics_absent_when_disabled(self):
        """No Impact: metrics when show_impact_summaries is False."""
        pres = build_current_conditions(
            self.current,
            self.location,
            TemperatureUnit.FAHRENHEIT,
            settings=_settings(show_impact=False),
        )
        assert _impact_labels(pres) == []

    def test_impact_metrics_present_when_enabled(self):
        """Impact: Outdoor and Impact: Driving appear when show_impact_summaries is True."""
        pres = build_current_conditions(
            self.current,
            self.location,
            TemperatureUnit.FAHRENHEIT,
            settings=_settings(show_impact=True),
        )
        labels = _impact_labels(pres)
        assert "Impact: Outdoor" in labels
        assert "Impact: Driving" in labels

    def test_impact_absent_with_no_settings(self):
        """Passing settings=None defaults to no impact metrics."""
        pres = build_current_conditions(
            self.current,
            self.location,
            TemperatureUnit.FAHRENHEIT,
            settings=None,
        )
        assert _impact_labels(pres) == []

    def test_impact_absent_in_fallback_text_when_disabled(self):
        """Fallback text contains no Impact lines when disabled."""
        pres = build_current_conditions(
            self.current,
            self.location,
            TemperatureUnit.FAHRENHEIT,
            settings=_settings(show_impact=False),
        )
        assert "Impact:" not in pres.fallback_text

    def test_impact_present_in_fallback_text_when_enabled(self):
        """Fallback text includes Impact lines when enabled."""
        pres = build_current_conditions(
            self.current,
            self.location,
            TemperatureUnit.FAHRENHEIT,
            settings=_settings(show_impact=True),
        )
        assert "Impact:" in pres.fallback_text

    def test_impact_summary_field_none_when_disabled(self):
        """impact_summary on the presentation has no content when disabled."""
        pres = build_current_conditions(
            self.current,
            self.location,
            TemperatureUnit.FAHRENHEIT,
            settings=_settings(show_impact=False),
        )
        assert not pres.impact_summary.has_content()


# ── build_forecast impact gating ─────────────────────────────────────────────


class TestForecastImpactGating:
    def setup_method(self):
        self.forecast = _make_forecast()
        self.location = _make_location()

    def test_impact_summary_none_when_disabled(self):
        """forecast_impact is None when show_impact_summaries is False."""
        pres = build_forecast(
            self.forecast,
            None,
            self.location,
            TemperatureUnit.FAHRENHEIT,
            settings=_settings(show_impact=False),
        )
        assert pres.impact_summary is None

    def test_impact_summary_populated_when_enabled(self):
        """forecast_impact is an ImpactSummary with content when enabled."""
        pres = build_forecast(
            self.forecast,
            None,
            self.location,
            TemperatureUnit.FAHRENHEIT,
            settings=_settings(show_impact=True),
        )
        assert pres.impact_summary is not None

    def test_impact_summary_none_with_no_settings(self):
        """Passing settings=None defaults to no forecast impact summary."""
        pres = build_forecast(
            self.forecast,
            None,
            self.location,
            TemperatureUnit.FAHRENHEIT,
            settings=None,
        )
        assert pres.impact_summary is None
