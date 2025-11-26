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


class TestCurrentConditionsHtml:
    """Properties 3, 4: Current conditions HTML validity and completeness."""

    @pytest.mark.unit
    @given(p=current_conditions_strategy())
    @hypothesis_settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_valid_html5(self, p):
        """Generated HTML should be valid HTML5 structure."""
        html = generate_current_conditions_html(p)
        assert html.startswith("<!DOCTYPE html>")
        assert "<html lang=" in html
        assert "<head>" in html and "</head>" in html
        assert "<body>" in html and "</body>" in html

    @pytest.mark.unit
    @given(p=current_conditions_strategy())
    @hypothesis_settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
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
    @hypothesis_settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
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
    @hypothesis_settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_valid_html5(self, p):
        """Generated HTML should be valid HTML5 structure."""
        html = generate_forecast_html(p)
        assert html.startswith("<!DOCTYPE html>")
        assert "<html lang=" in html
        assert "<body>" in html and "</body>" in html

    @pytest.mark.unit
    @given(p=forecast_strategy())
    @hypothesis_settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_semantic_elements(self, p):
        """Generated HTML should contain semantic elements."""
        html = generate_forecast_html(p)
        assert "<section" in html
        assert 'role="region"' in html
        if p.periods:
            assert "<article" in html

    @pytest.mark.unit
    @given(p=forecast_strategy())
    @hypothesis_settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
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
    @hypothesis_settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_current_conditions_aria(self, p):
        """Current conditions HTML should have ARIA labels."""
        html = generate_current_conditions_html(p)
        assert "aria-label=" in html
        assert 'role="region"' in html
        if p.metrics:
            assert 'aria-label="Weather metrics"' in html

    @pytest.mark.unit
    @given(p=forecast_strategy())
    @hypothesis_settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
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
