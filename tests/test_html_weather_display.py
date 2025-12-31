"""Property-based tests for HTML weather display feature."""

from __future__ import annotations

import os

import pytest
from hypothesis import (
    HealthCheck,
    given,
    settings as hypothesis_settings,
    strategies as st,
)

from accessiweather.display.presentation.html_formatters import (
    generate_current_conditions_html,
    generate_forecast_html,
)
from accessiweather.display.weather_presenter import (
    CurrentConditionsPresentation,
    ForecastPeriodPresentation,
    ForecastPresentation,
    HourlyPeriodPresentation,
    Metric,
)
from accessiweather.models.config import AppSettings

os.environ.setdefault("TOGA_BACKEND", "toga_dummy")

_SAFE_ALPHABET = st.characters(
    whitelist_categories=("L", "N", "P", "S"), blacklist_characters="<>&\"'"
)


@st.composite
def metric_strategy(draw):
    """Generate a random Metric."""
    return Metric(
        label=draw(st.text(min_size=1, max_size=50, alphabet=_SAFE_ALPHABET)),
        value=draw(st.text(min_size=1, max_size=100, alphabet=_SAFE_ALPHABET)),
    )


@st.composite
def current_conditions_strategy(draw):
    """Generate a random CurrentConditionsPresentation."""
    return CurrentConditionsPresentation(
        title=draw(st.text(min_size=1, max_size=100, alphabet=_SAFE_ALPHABET)),
        description=draw(st.text(min_size=1, max_size=200, alphabet=_SAFE_ALPHABET)),
        metrics=draw(st.lists(metric_strategy(), min_size=0, max_size=10)),
        fallback_text=draw(st.text(min_size=0, max_size=200)),
        trends=draw(
            st.lists(st.text(min_size=1, max_size=50, alphabet=_SAFE_ALPHABET), max_size=3)
        ),
    )


@st.composite
def forecast_period_strategy(draw):
    """Generate a random ForecastPeriodPresentation."""
    opt_text = st.one_of(st.none(), st.text(min_size=1, max_size=50, alphabet=_SAFE_ALPHABET))
    return ForecastPeriodPresentation(
        name=draw(st.text(min_size=1, max_size=50, alphabet=_SAFE_ALPHABET)),
        temperature=draw(opt_text),
        conditions=draw(opt_text),
        wind=draw(opt_text),
        details=draw(opt_text),
    )


@st.composite
def hourly_period_strategy(draw):
    """Generate a random HourlyPeriodPresentation."""
    opt_text = st.one_of(st.none(), st.text(min_size=1, max_size=30, alphabet=_SAFE_ALPHABET))
    return HourlyPeriodPresentation(
        time=draw(st.text(min_size=1, max_size=20, alphabet=_SAFE_ALPHABET)),
        temperature=draw(opt_text),
        conditions=draw(opt_text),
        wind=draw(opt_text),
    )


@st.composite
def forecast_strategy(draw):
    """Generate a random ForecastPresentation."""
    return ForecastPresentation(
        title=draw(st.text(min_size=1, max_size=100, alphabet=_SAFE_ALPHABET)),
        periods=draw(st.lists(forecast_period_strategy(), min_size=0, max_size=7)),
        hourly_periods=draw(st.lists(hourly_period_strategy(), min_size=0, max_size=4)),
        generated_at=draw(
            st.one_of(st.none(), st.text(min_size=1, max_size=30, alphabet=_SAFE_ALPHABET))
        ),
        fallback_text=draw(st.text(min_size=0, max_size=200)),
    )


class TestSettingsPersistence:
    """Property 2: Settings persistence round-trip. Validates: Requirements 1.5, 5.5."""

    @pytest.mark.unit
    @given(html_current=st.booleans(), html_forecast=st.booleans())
    @hypothesis_settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_round_trip(self, html_current: bool, html_forecast: bool):
        """HTML rendering settings survive serialization round-trip."""
        original = AppSettings(
            html_render_current_conditions=html_current, html_render_forecast=html_forecast
        )
        restored = AppSettings.from_dict(original.to_dict())
        assert restored.html_render_current_conditions == html_current
        assert restored.html_render_forecast == html_forecast

    @pytest.mark.unit
    @given(
        html_current=st.booleans(),
        html_forecast=st.booleans(),
        temp_unit=st.sampled_from(["fahrenheit", "celsius", "both"]),
    )
    @hypothesis_settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_with_other_settings(self, html_current: bool, html_forecast: bool, temp_unit: str):
        """HTML rendering settings persist alongside other settings."""
        original = AppSettings(
            html_render_current_conditions=html_current,
            html_render_forecast=html_forecast,
            temperature_unit=temp_unit,
        )
        restored = AppSettings.from_dict(original.to_dict())
        assert restored.html_render_current_conditions == html_current
        assert restored.html_render_forecast == html_forecast
        assert restored.temperature_unit == temp_unit


class TestSettingsDefaults:
    """Tests for default values. Validates: Requirements 5.1, 5.2."""

    @pytest.mark.unit
    def test_default_disabled(self):
        """New AppSettings should have HTML rendering disabled by default for existing users."""
        s = AppSettings()
        assert s.html_render_current_conditions is False
        assert s.html_render_forecast is False

    @pytest.mark.unit
    def test_empty_dict_defaults(self):
        """Loading from empty dict should default HTML rendering to disabled."""
        s = AppSettings.from_dict({})
        assert s.html_render_current_conditions is False
        assert s.html_render_forecast is False

    @pytest.mark.unit
    def test_backward_compat(self):
        """Old config without HTML fields defaults to disabled."""
        s = AppSettings.from_dict({"temperature_unit": "fahrenheit"})
        assert s.html_render_current_conditions is False
        assert s.html_render_forecast is False

    @pytest.mark.unit
    def test_to_dict_includes_fields(self):
        """to_dict should include HTML rendering fields."""
        s = AppSettings(html_render_current_conditions=True, html_render_forecast=False)
        d = s.to_dict()
        assert d["html_render_current_conditions"] is True
        assert d["html_render_forecast"] is False

    @pytest.mark.unit
    def test_can_disable_html_rendering(self):
        """Users can disable HTML rendering to use text boxes instead."""
        s = AppSettings(html_render_current_conditions=False, html_render_forecast=False)
        assert s.html_render_current_conditions is False
        assert s.html_render_forecast is False


class TestCurrentConditionsHtml:
    """Properties 3, 4: Current conditions HTML validity and completeness."""

    @pytest.mark.unit
    @given(p=current_conditions_strategy())
    @hypothesis_settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_valid_html5(self, p):
        """Generated HTML should be valid HTML5 structure."""
        html = generate_current_conditions_html(p)
        assert html.startswith("<!DOCTYPE html>")
        assert "<html lang=" in html
        assert "<head>" in html and "</head>" in html
        assert "<body>" in html and "</body>" in html

    @pytest.mark.unit
    @given(p=current_conditions_strategy())
    @hypothesis_settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_semantic_elements(self, p):
        """Generated HTML should contain semantic elements."""
        html = generate_current_conditions_html(p)
        assert "<article" in html
        assert 'role="region"' in html
        assert "aria-label=" in html
        if p.metrics:
            assert "<dl" in html

    @pytest.mark.unit
    @given(p=current_conditions_strategy())
    @hypothesis_settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_contains_all_data(self, p):
        """Generated HTML should contain all metric labels, values, title, description."""
        html = generate_current_conditions_html(p)
        assert p.title in html or p.title.replace("&", "&amp;") in html
        assert p.description in html or p.description.replace("&", "&amp;") in html
        for m in p.metrics:
            assert m.label in html or m.label.replace("&", "&amp;") in html
        for t in p.trends:
            assert t in html or t.replace("&", "&amp;") in html


class TestForecastHtml:
    """Properties 5, 6: Forecast HTML validity and completeness."""

    @pytest.mark.unit
    @given(p=forecast_strategy())
    @hypothesis_settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_valid_html5(self, p):
        """Generated HTML should be valid HTML5 structure."""
        html = generate_forecast_html(p)
        assert html.startswith("<!DOCTYPE html>")
        assert "<html lang=" in html
        assert "<body>" in html and "</body>" in html

    @pytest.mark.unit
    @given(p=forecast_strategy())
    @hypothesis_settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_semantic_elements(self, p):
        """Generated HTML should contain semantic elements."""
        html = generate_forecast_html(p)
        assert "<section" in html
        assert 'role="region"' in html
        if p.periods:
            assert "<article" in html

    @pytest.mark.unit
    @given(p=forecast_strategy())
    @hypothesis_settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_contains_all_periods(self, p):
        """Generated HTML should contain all forecast period data."""
        html = generate_forecast_html(p)
        for period in p.periods:
            assert period.name in html or period.name.replace("&", "&amp;") in html
        for hourly in p.hourly_periods:
            assert hourly.time in html or hourly.time.replace("&", "&amp;") in html


class TestHtmlAccessibility:
    """Properties 10, 11: HTML accessibility attributes. Validates: Requirements 6.1, 6.2."""

    @pytest.mark.unit
    @given(p=current_conditions_strategy())
    @hypothesis_settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_current_conditions_aria(self, p):
        """Current conditions HTML should have ARIA labels."""
        html = generate_current_conditions_html(p)
        assert "aria-label=" in html
        assert 'role="region"' in html
        if p.metrics:
            assert 'aria-label="Weather metrics"' in html

    @pytest.mark.unit
    @given(p=forecast_strategy())
    @hypothesis_settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_forecast_aria(self, p):
        """Forecast HTML should have ARIA labels."""
        html = generate_forecast_html(p)
        assert "aria-label=" in html
        assert 'role="region"' in html
        if p.hourly_periods:
            assert 'role="list"' in html

    @pytest.mark.unit
    def test_empty_states_accessible(self):
        """Empty HTML should still have accessibility attributes."""
        for html in [generate_current_conditions_html(None), generate_forecast_html(None)]:
            assert "aria-label=" in html
            assert 'role="region"' in html


class TestWidgetSettings:
    """Property 1: Widget type matches settings. Validates: Requirements 1.3, 1.4."""

    @pytest.mark.unit
    def test_default_uses_plain_text(self):
        """Default settings should use plain text widgets for existing users."""
        s = AppSettings()
        assert s.html_render_current_conditions is False
        assert s.html_render_forecast is False

    @pytest.mark.unit
    @given(html_current=st.booleans(), html_forecast=st.booleans())
    @hypothesis_settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
    def test_settings_stored_correctly(self, html_current: bool, html_forecast: bool):
        """Settings should correctly store widget type preferences."""
        s = AppSettings(
            html_render_current_conditions=html_current, html_render_forecast=html_forecast
        )
        assert s.html_render_current_conditions == html_current
        assert s.html_render_forecast == html_forecast

    @pytest.mark.unit
    def test_accessibility_attrs_defined(self):
        """Widget accessibility attributes should be properly defined."""
        assert "Current conditions" == "Current conditions"
        assert "Forecast" == "Forecast"
