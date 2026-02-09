"""Tests for weather_client_trends module."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from accessiweather.models.weather import (
    CurrentConditions,
    Forecast,
    ForecastPeriod,
    HourlyForecast,
    HourlyForecastPeriod,
    Location,
    TrendInsight,
    WeatherData,
)
from accessiweather.weather_client_trends import (
    apply_trend_insights,
    compute_daily_trend,
    compute_pressure_trend,
    compute_temperature_trend,
    normalize_datetime,
    period_for_hours_ahead,
    trend_descriptor,
)


def _make_location() -> Location:
    return Location(name="Test", latitude=40.0, longitude=-74.0)


def _make_hourly_periods(
    base_temp: float = 70.0,
    temp_change: float = 5.0,
    hours: int = 12,
    pressure_mb: float | None = None,
    pressure_in: float | None = None,
    pressure_change_mb: float | None = None,
    pressure_change_in: float | None = None,
) -> list[HourlyForecastPeriod]:
    now = datetime.now()
    periods = []
    for i in range(hours):
        t = base_temp + (temp_change * i / max(hours - 1, 1))
        p_mb = None
        p_in = None
        if pressure_mb is not None and pressure_change_mb is not None:
            p_mb = pressure_mb + (pressure_change_mb * i / max(hours - 1, 1))
        if pressure_in is not None and pressure_change_in is not None:
            p_in = pressure_in + (pressure_change_in * i / max(hours - 1, 1))
        periods.append(
            HourlyForecastPeriod(
                start_time=now + timedelta(hours=i),
                temperature=round(t, 1),
                pressure_mb=round(p_mb, 2) if p_mb is not None else None,
                pressure_in=round(p_in, 4) if p_in is not None else None,
            )
        )
    return periods


def _make_weather_data(
    temp_f: float | None = 70.0,
    temp_c: float | None = None,
    hourly_periods: list[HourlyForecastPeriod] | None = None,
    forecast_periods: list[ForecastPeriod] | None = None,
    daily_history: list[ForecastPeriod] | None = None,
    pressure_mb: float | None = None,
    pressure_in: float | None = None,
) -> WeatherData:
    current = CurrentConditions(
        temperature_f=temp_f,
        temperature_c=temp_c,
        pressure_mb=pressure_mb,
        pressure_in=pressure_in,
    )
    hourly = HourlyForecast(periods=hourly_periods or []) if hourly_periods else None
    forecast = Forecast(periods=forecast_periods or []) if forecast_periods else None
    return WeatherData(
        location=_make_location(),
        current=current,
        hourly_forecast=hourly,
        forecast=forecast,
        daily_history=daily_history or [],
    )


# --- trend_descriptor ---


class TestTrendDescriptor:
    def test_strong_rising(self):
        direction, sparkline = trend_descriptor(4.0, minor=1.0, strong=3.0)
        assert direction == "rising"
        assert sparkline == "↑↑"

    def test_minor_rising(self):
        direction, sparkline = trend_descriptor(1.5, minor=1.0, strong=3.0)
        assert direction == "rising"
        assert sparkline == "↑"

    def test_strong_falling(self):
        direction, sparkline = trend_descriptor(-4.0, minor=1.0, strong=3.0)
        assert direction == "falling"
        assert sparkline == "↓↓"

    def test_minor_falling(self):
        direction, sparkline = trend_descriptor(-1.5, minor=1.0, strong=3.0)
        assert direction == "falling"
        assert sparkline == "↓"

    def test_steady(self):
        direction, sparkline = trend_descriptor(0.3, minor=1.0, strong=3.0)
        assert direction == "steady"
        assert sparkline == "→"

    def test_exact_boundary_minor(self):
        direction, sparkline = trend_descriptor(1.0, minor=1.0, strong=3.0)
        assert direction == "rising"

    def test_exact_boundary_strong(self):
        direction, sparkline = trend_descriptor(3.0, minor=1.0, strong=3.0)
        assert direction == "rising"
        assert sparkline == "↑↑"

    def test_exact_negative_boundary(self):
        direction, sparkline = trend_descriptor(-3.0, minor=1.0, strong=3.0)
        assert direction == "falling"
        assert sparkline == "↓↓"


# --- normalize_datetime ---


class TestNormalizeDatetime:
    def test_none_input(self):
        assert normalize_datetime(None) is None

    def test_naive_datetime(self):
        dt = datetime(2025, 1, 1, 12, 0)
        result = normalize_datetime(dt)
        assert result == dt
        assert result.tzinfo is None

    def test_aware_datetime(self):
        dt = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
        result = normalize_datetime(dt)
        assert result is not None
        assert result.tzinfo is None


# --- period_for_hours_ahead ---


class TestPeriodForHoursAhead:
    def test_empty_periods(self):
        assert period_for_hours_ahead([], 6) is None

    def test_finds_closest_period(self):
        periods = _make_hourly_periods(hours=12)
        result = period_for_hours_ahead(periods, 6)
        assert result is not None
        assert result.temperature is not None

    def test_single_period(self):
        period = HourlyForecastPeriod(
            start_time=datetime.now() + timedelta(hours=3),
            temperature=75.0,
        )
        result = period_for_hours_ahead([period], 6)
        assert result == period

    def test_skips_none_start_time_periods(self):
        # All periods have start_time (required field), but test mixed aware/naive
        now = datetime.now()
        periods = [
            HourlyForecastPeriod(start_time=now + timedelta(hours=6), temperature=80.0),
        ]
        result = period_for_hours_ahead(periods, 6)
        assert result is not None


# --- compute_temperature_trend ---


class TestComputeTemperatureTrend:
    def test_basic_rising_trend_fahrenheit(self):
        wd = _make_weather_data(
            temp_f=70.0,
            hourly_periods=_make_hourly_periods(base_temp=70.0, temp_change=5.0, hours=12),
        )
        result = compute_temperature_trend(wd, 6)
        assert result is not None
        assert result.metric == "temperature"
        assert result.unit == "°F"
        assert result.timeframe_hours == 6
        assert "Temperature" in result.summary

    def test_falling_trend(self):
        wd = _make_weather_data(
            temp_f=80.0,
            hourly_periods=_make_hourly_periods(base_temp=80.0, temp_change=-10.0, hours=12),
        )
        result = compute_temperature_trend(wd, 6)
        assert result is not None
        assert result.direction == "falling"

    def test_celsius_fallback(self):
        wd = _make_weather_data(
            temp_f=None,
            temp_c=21.0,
            hourly_periods=_make_hourly_periods(base_temp=21.0, temp_change=3.0, hours=12),
        )
        result = compute_temperature_trend(wd, 6)
        assert result is not None
        assert result.unit == "°C"

    def test_no_current(self):
        wd = WeatherData(location=_make_location(), current=None)
        assert compute_temperature_trend(wd, 6) is None

    def test_no_hourly(self):
        wd = _make_weather_data(temp_f=70.0, hourly_periods=None)
        assert compute_temperature_trend(wd, 6) is None

    def test_no_temperature_in_current(self):
        wd = _make_weather_data(temp_f=None, temp_c=None)
        wd.hourly_forecast = HourlyForecast(periods=_make_hourly_periods(hours=6))
        assert compute_temperature_trend(wd, 6) is None

    def test_target_period_missing_temperature(self):
        now = datetime.now()
        periods = [
            HourlyForecastPeriod(start_time=now + timedelta(hours=6), temperature=None),
        ]
        wd = _make_weather_data(temp_f=70.0, hourly_periods=periods)
        assert compute_temperature_trend(wd, 6) is None


# --- compute_pressure_trend ---


class TestComputePressureTrend:
    def test_rising_pressure_mb(self):
        periods = _make_hourly_periods(
            hours=12,
            pressure_mb=1013.0,
            pressure_change_mb=2.0,
        )
        wd = _make_weather_data(
            temp_f=70.0,
            pressure_mb=1013.0,
            hourly_periods=periods,
        )
        result = compute_pressure_trend(wd, 6)
        assert result is not None
        assert result.metric == "pressure"
        assert result.unit == "mb"
        assert "Pressure" in result.summary

    def test_pressure_in_unit(self):
        periods = _make_hourly_periods(
            hours=12,
            pressure_in=29.92,
            pressure_change_in=0.1,
        )
        wd = _make_weather_data(
            temp_f=70.0,
            pressure_in=29.92,
            hourly_periods=periods,
        )
        result = compute_pressure_trend(wd, 6)
        assert result is not None
        assert result.unit == "inHg"

    def test_no_current(self):
        wd = WeatherData(location=_make_location(), current=None)
        assert compute_pressure_trend(wd, 6) is None

    def test_no_pressure_data(self):
        periods = _make_hourly_periods(hours=12)  # no pressure
        wd = _make_weather_data(temp_f=70.0, hourly_periods=periods)
        assert compute_pressure_trend(wd, 6) is None

    def test_no_hourly(self):
        wd = _make_weather_data(temp_f=70.0, pressure_mb=1013.0)
        assert compute_pressure_trend(wd, 6) is None

    def test_falling_pressure(self):
        periods = _make_hourly_periods(
            hours=12,
            pressure_mb=1013.0,
            pressure_change_mb=-3.0,
        )
        wd = _make_weather_data(
            temp_f=70.0,
            pressure_mb=1013.0,
            hourly_periods=periods,
        )
        result = compute_pressure_trend(wd, 6)
        assert result is not None
        assert result.direction == "falling"


# --- compute_daily_trend ---


class TestComputeDailyTrend:
    def test_warmer_than_yesterday(self):
        today_period = ForecastPeriod(name="Today", temperature=85.0, temperature_unit="F")
        yesterday_period = ForecastPeriod(name="Yesterday", temperature=75.0, temperature_unit="F")
        wd = _make_weather_data(
            forecast_periods=[today_period],
            daily_history=[yesterday_period],
        )
        result = compute_daily_trend(wd)
        assert result is not None
        assert result.direction == "warmer"
        assert result.metric == "daily_trend"
        assert "warmer" in result.summary

    def test_cooler_than_yesterday(self):
        today_period = ForecastPeriod(name="Today", temperature=65.0, temperature_unit="F")
        yesterday_period = ForecastPeriod(name="Yesterday", temperature=80.0, temperature_unit="F")
        wd = _make_weather_data(
            forecast_periods=[today_period],
            daily_history=[yesterday_period],
        )
        result = compute_daily_trend(wd)
        assert result is not None
        assert result.direction == "cooler"
        assert "cooler" in result.summary

    def test_similar_temperatures(self):
        today_period = ForecastPeriod(name="Today", temperature=75.0, temperature_unit="F")
        yesterday_period = ForecastPeriod(name="Yesterday", temperature=74.5, temperature_unit="F")
        wd = _make_weather_data(
            forecast_periods=[today_period],
            daily_history=[yesterday_period],
        )
        result = compute_daily_trend(wd)
        assert result is not None
        assert result.direction == "similar"
        assert "similar" in result.summary.lower()

    def test_no_forecast(self):
        wd = _make_weather_data()
        wd.forecast = None
        assert compute_daily_trend(wd) is None

    def test_empty_forecast_periods(self):
        wd = _make_weather_data(forecast_periods=[])
        # Forecast with empty periods
        assert compute_daily_trend(wd) is None

    def test_no_daily_history(self):
        today_period = ForecastPeriod(name="Today", temperature=75.0)
        wd = _make_weather_data(forecast_periods=[today_period])
        wd.daily_history = []
        assert compute_daily_trend(wd) is None

    def test_missing_today_temperature(self):
        today_period = ForecastPeriod(name="Today", temperature=None)
        yesterday_period = ForecastPeriod(name="Yesterday", temperature=75.0)
        wd = _make_weather_data(
            forecast_periods=[today_period],
            daily_history=[yesterday_period],
        )
        assert compute_daily_trend(wd) is None

    def test_missing_yesterday_temperature(self):
        today_period = ForecastPeriod(name="Today", temperature=75.0)
        yesterday_period = ForecastPeriod(name="Yesterday", temperature=None)
        wd = _make_weather_data(
            forecast_periods=[today_period],
            daily_history=[yesterday_period],
        )
        assert compute_daily_trend(wd) is None

    def test_celsius_unit(self):
        today_period = ForecastPeriod(name="Today", temperature=30.0, temperature_unit="C")
        yesterday_period = ForecastPeriod(name="Yesterday", temperature=25.0, temperature_unit="C")
        wd = _make_weather_data(
            forecast_periods=[today_period],
            daily_history=[yesterday_period],
        )
        result = compute_daily_trend(wd)
        assert result is not None
        assert result.unit == "C"

    def test_sparkline_directions(self):
        # Positive change
        today = ForecastPeriod(name="Today", temperature=80.0, temperature_unit="F")
        yesterday = ForecastPeriod(name="Yesterday", temperature=70.0, temperature_unit="F")
        wd = _make_weather_data(forecast_periods=[today], daily_history=[yesterday])
        result = compute_daily_trend(wd)
        assert result.sparkline == "↑"

        # Negative change
        today2 = ForecastPeriod(name="Today", temperature=60.0, temperature_unit="F")
        wd2 = _make_weather_data(forecast_periods=[today2], daily_history=[yesterday])
        result2 = compute_daily_trend(wd2)
        assert result2.sparkline == "↓"

        # Zero change
        today3 = ForecastPeriod(name="Today", temperature=70.0, temperature_unit="F")
        wd3 = _make_weather_data(forecast_periods=[today3], daily_history=[yesterday])
        result3 = compute_daily_trend(wd3)
        assert result3.sparkline == "→"


# --- apply_trend_insights ---


class TestApplyTrendInsights:
    def test_disabled_clears_insights(self):
        wd = _make_weather_data()
        wd.trend_insights = [TrendInsight(metric="test", direction="up")]
        apply_trend_insights(wd, trend_insights_enabled=False, trend_hours=6)
        assert wd.trend_insights == []

    def test_enabled_populates_insights(self):
        periods = _make_hourly_periods(
            base_temp=70.0,
            temp_change=5.0,
            hours=12,
            pressure_mb=1013.0,
            pressure_change_mb=2.0,
        )
        today_period = ForecastPeriod(name="Today", temperature=80.0, temperature_unit="F")
        yesterday_period = ForecastPeriod(name="Yesterday", temperature=70.0, temperature_unit="F")
        wd = _make_weather_data(
            temp_f=70.0,
            pressure_mb=1013.0,
            hourly_periods=periods,
            forecast_periods=[today_period],
            daily_history=[yesterday_period],
        )
        apply_trend_insights(wd, trend_insights_enabled=True, trend_hours=6)
        assert len(wd.trend_insights) >= 1
        metrics = [i.metric for i in wd.trend_insights]
        assert "temperature" in metrics

    def test_exclude_pressure(self):
        periods = _make_hourly_periods(
            base_temp=70.0,
            temp_change=5.0,
            hours=12,
            pressure_mb=1013.0,
            pressure_change_mb=2.0,
        )
        wd = _make_weather_data(
            temp_f=70.0,
            pressure_mb=1013.0,
            hourly_periods=periods,
        )
        apply_trend_insights(
            wd,
            trend_insights_enabled=True,
            trend_hours=6,
            include_pressure=False,
        )
        metrics = [i.metric for i in wd.trend_insights]
        assert "pressure" not in metrics

    def test_no_data_yields_empty(self):
        wd = WeatherData(location=_make_location(), current=None)
        apply_trend_insights(wd, trend_insights_enabled=True, trend_hours=6)
        assert wd.trend_insights == []
