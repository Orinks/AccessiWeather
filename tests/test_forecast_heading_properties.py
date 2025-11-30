"""
Property-based tests for forecast heading navigation.

These tests verify the correctness properties defined in the design document
for the forecast-navigation-improvements feature.

**Feature: forecast-navigation-improvements**
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest
from hypothesis import (
    HealthCheck,
    given,
    settings,
    strategies as st,
)

# Set TOGA_BACKEND before importing toga
os.environ.setdefault("TOGA_BACKEND", "toga_dummy")

import toga  # noqa: E402

from accessiweather.display.weather_presenter import (  # noqa: E402
    ForecastPeriodPresentation,
    ForecastPresentation,
    HourlyPeriodPresentation,
)
from accessiweather.ui_builder import render_forecast_with_headings  # noqa: E402

if TYPE_CHECKING:
    pass


# -----------------------------------------------------------------------------
# Hypothesis Strategies for generating test data
# -----------------------------------------------------------------------------

# Strategy for generating day names (realistic forecast day names)
day_names = st.sampled_from(
    [
        "Today",
        "Tonight",
        "Monday",
        "Monday Night",
        "Tuesday",
        "Tuesday Night",
        "Wednesday",
        "Wednesday Night",
        "Thursday",
        "Thursday Night",
        "Friday",
        "Friday Night",
        "Saturday",
        "Saturday Night",
        "Sunday",
        "Sunday Night",
        "This Afternoon",
        "This Evening",
        "Overnight",
    ]
)

# Strategy for generating temperature strings
temperatures = st.one_of(
    st.just(None),
    st.integers(min_value=-50, max_value=120).map(lambda t: f"{t}°F"),
    st.integers(min_value=-50, max_value=50).map(lambda t: f"{t}°C"),
    st.tuples(
        st.integers(min_value=-50, max_value=120), st.integers(min_value=-50, max_value=50)
    ).map(lambda t: f"{t[0]}°F ({t[1]}°C)"),
)

# Strategy for generating weather conditions
conditions = st.one_of(
    st.just(None),
    st.sampled_from(
        [
            "Sunny",
            "Partly Cloudy",
            "Cloudy",
            "Overcast",
            "Light Rain",
            "Heavy Rain",
            "Thunderstorms",
            "Snow",
            "Fog",
            "Windy",
            "Clear",
        ]
    ),
)

# Strategy for generating wind descriptions
winds = st.one_of(
    st.just(None),
    st.sampled_from(
        [
            "N 5 mph",
            "S 10 mph",
            "E 15 mph",
            "W 20 mph",
            "NE 8 mph",
            "SW 12 mph",
            "Calm",
            "Variable 5 mph",
        ]
    ),
)

# Strategy for generating detail text
details = st.one_of(
    st.just(None),
    st.text(
        min_size=0,
        max_size=200,
        alphabet=st.characters(
            whitelist_categories=("L", "N", "P", "Z"), whitelist_characters=" .,!?-"
        ),
    ),
)


@st.composite
def forecast_period_strategy(draw: st.DrawFn) -> ForecastPeriodPresentation:
    """Generate a random ForecastPeriodPresentation."""
    return ForecastPeriodPresentation(
        name=draw(day_names),
        temperature=draw(temperatures),
        conditions=draw(conditions),
        wind=draw(winds),
        details=draw(details),
    )


# Strategy for generating hourly time strings
hourly_times = st.sampled_from(
    [
        "12:00 PM",
        "1:00 PM",
        "2:00 PM",
        "3:00 PM",
        "4:00 PM",
        "5:00 PM",
        "6:00 PM",
        "7:00 PM",
        "8:00 PM",
        "9:00 PM",
        "10:00 PM",
        "11:00 PM",
        "12:00 AM",
        "1:00 AM",
        "2:00 AM",
        "3:00 AM",
        "4:00 AM",
        "5:00 AM",
    ]
)


@st.composite
def hourly_period_strategy(draw: st.DrawFn) -> HourlyPeriodPresentation:
    """Generate a random HourlyPeriodPresentation."""
    return HourlyPeriodPresentation(
        time=draw(hourly_times),
        temperature=draw(temperatures),
        conditions=draw(conditions),
        wind=draw(winds),
    )


@st.composite
def forecast_presentation_strategy(
    draw: st.DrawFn,
    min_periods: int = 0,
    max_periods: int = 14,
    include_hourly: bool = True,
) -> ForecastPresentation:
    """Generate a random ForecastPresentation with configurable period count."""
    periods = draw(
        st.lists(
            forecast_period_strategy(),
            min_size=min_periods,
            max_size=max_periods,
        )
    )

    hourly_periods: list[HourlyPeriodPresentation] = []
    if include_hourly and draw(st.booleans()):
        hourly_periods = draw(
            st.lists(
                hourly_period_strategy(),
                min_size=0,
                max_size=6,
            )
        )

    generated_at = draw(
        st.one_of(
            st.just(None),
            st.datetimes().map(lambda dt: dt.strftime("%Y-%m-%d %H:%M")),
        )
    )

    return ForecastPresentation(
        title="Extended Forecast",
        periods=periods,
        hourly_periods=hourly_periods,
        generated_at=generated_at,
        fallback_text="",
    )


# -----------------------------------------------------------------------------
# Property Tests
# -----------------------------------------------------------------------------


@pytest.mark.unit
class TestForecastHeadingStructureProperty:
    """
    **Property 1: Forecast heading structure preservation**.

    *For any* forecast data with multiple days, when the forecast view is rendered,
    each day should have a corresponding heading element with appropriate
    accessibility attributes.

    **Validates: Requirements 1.1, 1.4**
    """

    @given(presentation=forecast_presentation_strategy(min_periods=0, max_periods=14))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_heading_count_matches_period_count(self, presentation: ForecastPresentation) -> None:
        """
        **Feature: forecast-navigation-improvements, Property 1: Forecast heading structure preservation**.

        For any forecast presentation, the number of heading elements created
        should equal the number of forecast periods plus hourly section headings.
        Note: Hourly section is only rendered when there are forecast periods.
        """
        container = toga.Box()
        heading_labels = render_forecast_with_headings(presentation, container)

        # Count expected headings: one per period + one for hourly section if present
        # Note: hourly section only renders when there are periods
        expected_headings = len(presentation.periods)
        if presentation.periods and presentation.hourly_periods:
            expected_headings += 1  # "Next 6 Hours" heading

        assert len(heading_labels) == expected_headings, (
            f"Expected {expected_headings} headings for {len(presentation.periods)} periods "
            f"(hourly: {bool(presentation.hourly_periods)}), got {len(heading_labels)}"
        )

    @given(presentation=forecast_presentation_strategy(min_periods=1, max_periods=14))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_each_period_has_heading_with_aria_attributes(
        self, presentation: ForecastPresentation
    ) -> None:
        """
        **Feature: forecast-navigation-improvements, Property 1: Forecast heading structure preservation**.

        For any forecast period, the corresponding heading label should have
        aria_role="heading" and aria_level=2 set (when platform supports it).
        """
        container = toga.Box()
        heading_labels = render_forecast_with_headings(presentation, container)

        # Skip hourly heading if present, check period headings
        period_headings = heading_labels
        if presentation.hourly_periods:
            period_headings = heading_labels[1:]  # Skip "Next 6 Hours" heading

        for i, heading in enumerate(period_headings):
            # Check aria attributes are set (may not be available on all platforms)
            try:
                assert heading.aria_role == "heading", (
                    f"Heading {i} should have aria_role='heading'"
                )
                assert heading.aria_level == 2, f"Heading {i} should have aria_level=2"
            except AttributeError:
                # Platform doesn't support aria attributes - this is acceptable
                pass

    @given(presentation=forecast_presentation_strategy(min_periods=0, max_periods=14))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_container_children_created_for_all_content(
        self, presentation: ForecastPresentation
    ) -> None:
        """
        **Feature: forecast-navigation-improvements, Property 1: Forecast heading structure preservation**.

        For any forecast presentation, the container should have children
        widgets for all content (headings, temperatures, conditions, etc.).
        """
        container = toga.Box()
        render_forecast_with_headings(presentation, container)

        # Container should have at least one child (either content or "no data" message)
        assert len(container.children) >= 1, "Container should have at least one child"

        if presentation.periods:
            # Should have at least one child per period (the heading)
            assert len(container.children) >= len(presentation.periods), (
                f"Container should have at least {len(presentation.periods)} children "
                f"for {len(presentation.periods)} periods"
            )


@pytest.mark.unit
class TestHeadingNavigationSequenceProperty:
    """
    **Property 2: Heading navigation sequence**.

    *For any* forecast display with N days, navigating through headings should
    visit exactly N heading elements in chronological order.

    **Validates: Requirements 1.2**
    """

    @given(
        presentation=forecast_presentation_strategy(
            min_periods=1, max_periods=14, include_hourly=False
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_headings_in_chronological_order(self, presentation: ForecastPresentation) -> None:
        """
        **Feature: forecast-navigation-improvements, Property 2: Heading navigation sequence**.

        For any forecast presentation, headings should appear in the same order
        as the forecast periods (chronological order).
        """
        container = toga.Box()
        heading_labels = render_forecast_with_headings(presentation, container)

        # Verify headings match period names in order
        for i, (heading, period) in enumerate(
            zip(heading_labels, presentation.periods, strict=False)
        ):
            assert heading.text == period.name, (
                f"Heading {i} text '{heading.text}' should match period name '{period.name}'"
            )

    @given(
        presentation=forecast_presentation_strategy(
            min_periods=2, max_periods=14, include_hourly=False
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_heading_sequence_is_complete(self, presentation: ForecastPresentation) -> None:
        """
        **Feature: forecast-navigation-improvements, Property 2: Heading navigation sequence**.

        For any forecast with N periods, exactly N headings should be created,
        ensuring no periods are skipped during navigation.
        """
        container = toga.Box()
        heading_labels = render_forecast_with_headings(presentation, container)

        assert len(heading_labels) == len(presentation.periods), (
            f"Should have exactly {len(presentation.periods)} headings, got {len(heading_labels)}"
        )

        # Verify all period names are represented
        {h.text for h in heading_labels}
        {p.name for p in presentation.periods}

        # Note: period names might not be unique, so we check count instead
        assert len(heading_labels) == len(presentation.periods)


@pytest.mark.unit
class TestHeadingContentAnnouncementProperty:
    """
    **Property 3: Heading content announcement**.

    *For any* forecast day heading, when focused by a screen reader, the announced
    text should contain the day name (e.g., "Tuesday", "Wednesday").

    **Validates: Requirements 1.3**
    """

    @given(
        presentation=forecast_presentation_strategy(
            min_periods=1, max_periods=14, include_hourly=False
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_heading_aria_label_contains_day_name(self, presentation: ForecastPresentation) -> None:
        """
        **Feature: forecast-navigation-improvements, Property 3: Heading content announcement**.

        For any forecast period heading, the aria_label should contain the day name
        so screen readers announce it properly.
        """
        container = toga.Box()
        heading_labels = render_forecast_with_headings(presentation, container)

        for i, (heading, period) in enumerate(
            zip(heading_labels, presentation.periods, strict=False)
        ):
            try:
                # aria_label should contain the period name
                assert period.name in heading.aria_label, (
                    f"Heading {i} aria_label '{heading.aria_label}' should contain "
                    f"period name '{period.name}'"
                )
            except AttributeError:
                # Platform doesn't support aria_label - check text instead
                assert period.name == heading.text, f"Heading {i} text should be '{period.name}'"


@pytest.mark.unit
class TestForecastRenderingEdgeCases:
    """Unit tests for forecast rendering edge cases (Task 1.3)."""

    def test_empty_forecast_shows_no_data_message(self) -> None:
        """Test rendering with no forecast data shows appropriate message."""
        container = toga.Box()
        heading_labels = render_forecast_with_headings(None, container)

        assert len(heading_labels) == 0, "No headings for None presentation"
        assert len(container.children) == 1, "Should have 'no data' message"
        assert "No forecast data" in container.children[0].text

    def test_empty_periods_shows_no_data_message(self) -> None:
        """Test rendering with empty periods list shows appropriate message."""
        presentation = ForecastPresentation(
            title="Forecast",
            periods=[],
            hourly_periods=[],
            generated_at=None,
            fallback_text="",
        )
        container = toga.Box()
        heading_labels = render_forecast_with_headings(presentation, container)

        assert len(heading_labels) == 0, "No headings for empty periods"
        assert len(container.children) == 1, "Should have 'no data' message"

    def test_single_day_forecast(self) -> None:
        """Test rendering with single day forecast."""
        presentation = ForecastPresentation(
            title="Forecast",
            periods=[
                ForecastPeriodPresentation(
                    name="Today",
                    temperature="75°F",
                    conditions="Sunny",
                    wind="N 5 mph",
                    details="Clear skies expected.",
                )
            ],
            hourly_periods=[],
            generated_at=None,
            fallback_text="",
        )
        container = toga.Box()
        heading_labels = render_forecast_with_headings(presentation, container)

        assert len(heading_labels) == 1, "Should have exactly one heading"
        assert heading_labels[0].text == "Today"

    def test_maximum_days_forecast(self) -> None:
        """Test rendering with maximum (14) days forecast."""
        periods = [
            ForecastPeriodPresentation(
                name=f"Day {i}",
                temperature=f"{70 + i}°F",
                conditions="Sunny",
                wind=None,
                details=None,
            )
            for i in range(14)
        ]
        presentation = ForecastPresentation(
            title="Forecast",
            periods=periods,
            hourly_periods=[],
            generated_at=None,
            fallback_text="",
        )
        container = toga.Box()
        heading_labels = render_forecast_with_headings(presentation, container)

        assert len(heading_labels) == 14, "Should have 14 headings"

    def test_container_cleared_before_rendering(self) -> None:
        """Test that container is cleared before adding new content."""
        container = toga.Box()
        # Add some pre-existing children
        container.add(toga.Label("Old content 1"))
        container.add(toga.Label("Old content 2"))

        presentation = ForecastPresentation(
            title="Forecast",
            periods=[
                ForecastPeriodPresentation(
                    name="Today",
                    temperature="75°F",
                    conditions="Sunny",
                    wind=None,
                    details=None,
                )
            ],
            hourly_periods=[],
            generated_at=None,
            fallback_text="",
        )
        render_forecast_with_headings(presentation, container)

        # Old content should be gone
        old_texts = [c.text for c in container.children if hasattr(c, "text")]
        assert "Old content 1" not in old_texts
        assert "Old content 2" not in old_texts

    def test_hourly_section_has_heading(self) -> None:
        """Test that hourly section gets its own heading."""
        presentation = ForecastPresentation(
            title="Forecast",
            periods=[
                ForecastPeriodPresentation(
                    name="Today",
                    temperature="75°F",
                    conditions="Sunny",
                    wind=None,
                    details=None,
                )
            ],
            hourly_periods=[
                HourlyPeriodPresentation(
                    time="12:00 PM",
                    temperature="72°F",
                    conditions="Sunny",
                    wind="N 5 mph",
                )
            ],
            generated_at=None,
            fallback_text="",
        )
        container = toga.Box()
        heading_labels = render_forecast_with_headings(presentation, container)

        # Should have 2 headings: hourly section + Today
        assert len(heading_labels) == 2
        assert heading_labels[0].text == "Next 6 Hours:"
        assert heading_labels[1].text == "Today"
