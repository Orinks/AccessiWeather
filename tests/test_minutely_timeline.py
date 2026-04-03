"""Tests for accessiweather.display.presentation.minutely_timeline module."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from accessiweather.display.presentation.minutely_timeline import (
    build_minutely_timeline,
    generate_minutely_summary,
)
from accessiweather.models import (
    MinutelyPrecipitationForecast,
    MinutelyPrecipitationPoint,
)


def _make_point(
    offset_minutes: int = 0,
    intensity: float | None = None,
    probability: float | None = None,
    precip_type: str | None = None,
) -> MinutelyPrecipitationPoint:
    return MinutelyPrecipitationPoint(
        time=datetime(2025, 6, 1, 12, 0, tzinfo=UTC) + timedelta(minutes=offset_minutes),
        precipitation_intensity=intensity,
        precipitation_probability=probability,
        precipitation_type=precip_type,
    )


def _make_forecast(
    points: list[MinutelyPrecipitationPoint],
    summary: str | None = None,
) -> MinutelyPrecipitationForecast:
    return MinutelyPrecipitationForecast(summary=summary, points=points)


# ── generate_minutely_summary ──


class TestGenerateMinutelySummary:
    def test_none_forecast(self):
        assert generate_minutely_summary(None) is None

    def test_empty_points(self):
        forecast = _make_forecast([])
        assert generate_minutely_summary(forecast) is None

    def test_all_dry(self):
        points = [_make_point(i, intensity=0.0) for i in range(60)]
        result = generate_minutely_summary(_make_forecast(points))
        assert result == "No precipitation expected"

    def test_all_wet_light_rain(self):
        points = [_make_point(i, intensity=0.05, precip_type="rain") for i in range(60)]
        result = generate_minutely_summary(_make_forecast(points))
        assert result is not None
        assert "rain" in result.lower()
        assert "next hour" in result.lower()

    def test_all_wet_heavy_snow(self):
        points = [_make_point(i, intensity=2.0, precip_type="snow") for i in range(60)]
        result = generate_minutely_summary(_make_forecast(points))
        assert result is not None
        assert "snow" in result.lower()
        assert "heavy" in result.lower()

    def test_dry_to_wet_transition(self):
        points = [_make_point(i, intensity=0.0) for i in range(12)]
        points += [_make_point(i, intensity=0.5, precip_type="rain") for i in range(12, 60)]
        result = generate_minutely_summary(_make_forecast(points))
        assert result is not None
        assert "starting" in result.lower()
        assert "12" in result

    def test_wet_to_dry_transition(self):
        points = [_make_point(i, intensity=0.5, precip_type="rain") for i in range(20)]
        points += [_make_point(i, intensity=0.0) for i in range(20, 60)]
        result = generate_minutely_summary(_make_forecast(points))
        assert result is not None
        assert "stopping" in result.lower()
        assert "20" in result

    def test_uses_precipitation_type_label(self):
        points = [_make_point(i, intensity=0.0) for i in range(5)]
        points += [_make_point(i, intensity=0.3, precip_type="snow") for i in range(5, 60)]
        result = generate_minutely_summary(_make_forecast(points))
        assert result is not None
        assert "Snow" in result

    def test_all_wet_no_type(self):
        """When no precipitation_type is set, falls back to 'precipitation'."""
        points = [_make_point(i, intensity=0.05) for i in range(60)]
        result = generate_minutely_summary(_make_forecast(points))
        assert result is not None
        assert "precipitation" in result.lower()


# ── build_minutely_timeline ──


class TestBuildMinutelyTimeline:
    def test_none_forecast(self):
        assert build_minutely_timeline(None) is None

    def test_empty_points(self):
        forecast = _make_forecast([])
        assert build_minutely_timeline(forecast) is None

    def test_samples_at_5_min_intervals(self):
        # 61 points (0..60), all dry
        points = [_make_point(i, intensity=0.0) for i in range(61)]
        result = build_minutely_timeline(_make_forecast(points))
        assert result is not None
        parts = [p.strip() for p in result.split(",")]
        assert parts[0].startswith("Now:")
        assert parts[1].startswith("+5m:")
        assert len(parts) == 13  # 0, 5, 10, ..., 60

    def test_intensity_classification(self):
        points = [_make_point(0, intensity=0.0)]  # None
        points += [_make_point(i, intensity=0.0) for i in range(1, 5)]
        points += [_make_point(5, intensity=0.05)]  # Light
        points += [_make_point(i, intensity=0.0) for i in range(6, 10)]
        points += [_make_point(10, intensity=0.5)]  # Moderate
        points += [_make_point(i, intensity=0.0) for i in range(11, 15)]
        points += [_make_point(15, intensity=2.0)]  # Heavy
        result = build_minutely_timeline(_make_forecast(points))
        assert result is not None
        assert "Now: None" in result
        assert "+5m: Light" in result
        assert "+10m: Moderate" in result
        assert "+15m: Heavy" in result

    def test_fewer_than_5_points(self):
        points = [_make_point(0, intensity=0.0), _make_point(1, intensity=0.05)]
        result = build_minutely_timeline(_make_forecast(points))
        assert result is not None
        # Only index 0 is sampled (next would be index 5 which doesn't exist)
        assert result == "Now: None"

    def test_screen_reader_friendly(self):
        """Output uses commas, no pipes or box-drawing chars."""
        points = [_make_point(i, intensity=0.0) for i in range(61)]
        result = build_minutely_timeline(_make_forecast(points))
        assert result is not None
        assert "|" not in result
        assert "─" not in result
        assert "," in result

    def test_max_60_minutes(self):
        # 120 points - should only go up to index 60
        points = [_make_point(i, intensity=0.0) for i in range(120)]
        result = build_minutely_timeline(_make_forecast(points))
        parts = [p.strip() for p in result.split(",")]
        last_part = parts[-1]
        assert last_part.startswith("+60m:")


# ── Integration with build_current_conditions ──


class TestCurrentConditionsIntegration:
    """Test that build_current_conditions uses generated summary when PW summary is None."""

    def test_generated_summary_when_pw_summary_none(self):
        from accessiweather.display.presentation.current_conditions import (
            build_current_conditions,
        )
        from accessiweather.models import CurrentConditions, Location
        from accessiweather.utils import TemperatureUnit

        current = CurrentConditions(
            temperature=72.0,
            condition="Clear",
        )
        location = Location(name="Test City", latitude=40.0, longitude=-74.0)

        # Minutely forecast with points but no summary
        points = [_make_point(i, intensity=0.0) for i in range(60)]
        minutely = _make_forecast(points, summary=None)

        result = build_current_conditions(
            current,
            location,
            TemperatureUnit.FAHRENHEIT,
            minutely_precipitation=minutely,
        )

        metric_labels = [m.label for m in result.metrics]
        assert "Precipitation outlook" in metric_labels
        assert "Next hour precipitation" in metric_labels

        # Find the summary metric
        outlook = next(m for m in result.metrics if m.label == "Precipitation outlook")
        assert outlook.value == "No precipitation expected"

    def test_pw_summary_preferred_over_generated(self):
        from accessiweather.display.presentation.current_conditions import (
            build_current_conditions,
        )
        from accessiweather.models import CurrentConditions, Location
        from accessiweather.utils import TemperatureUnit

        current = CurrentConditions(
            temperature=72.0,
            condition="Clear",
        )
        location = Location(name="Test City", latitude=40.0, longitude=-74.0)

        points = [_make_point(i, intensity=0.0) for i in range(60)]
        minutely = _make_forecast(points, summary="PW provided summary")

        result = build_current_conditions(
            current,
            location,
            TemperatureUnit.FAHRENHEIT,
            minutely_precipitation=minutely,
        )

        outlook = next(m for m in result.metrics if m.label == "Precipitation outlook")
        assert outlook.value == "PW provided summary"
