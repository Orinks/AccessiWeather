"""Tests for accessiweather.display.presentation.current_conditions module."""

from __future__ import annotations

from datetime import datetime, timezone

from accessiweather.display.presentation.current_conditions import (
    _build_astronomical_metrics,
    _build_basic_metrics,
    _build_environmental_metrics,
    _build_seasonal_metrics,
    _build_trend_metrics,
    _categorize_metric,
    _get_severe_risk_description,
    _order_metrics_by_priority,
    build_current_conditions,
    compute_pressure_trend_from_hourly,
    describe_trend,
    direction_descriptor,
    format_temperature_value,
    format_trend_lines,
    split_direction_descriptor,
)
from accessiweather.display.priority_engine import WeatherCategory
from accessiweather.display.weather_presenter import Metric
from accessiweather.models import (
    CurrentConditions,
    EnvironmentalConditions,
    HourlyForecast,
    HourlyForecastPeriod,
    Location,
    TrendInsight,
)
from accessiweather.utils import TemperatureUnit

# ── format_temperature_value ──


class TestFormatTemperatureValue:
    def test_fahrenheit(self):
        assert format_temperature_value(72.0, 22.2, TemperatureUnit.FAHRENHEIT, 0) == "72°F"

    def test_celsius_with_c_value(self):
        assert format_temperature_value(72.0, 22.2, TemperatureUnit.CELSIUS, 1) == "22.2°C"

    def test_celsius_converts_from_f(self):
        result = format_temperature_value(32.0, None, TemperatureUnit.CELSIUS, 0)
        assert result == "0°C"

    def test_both_units(self):
        result = format_temperature_value(32.0, 0.0, TemperatureUnit.BOTH, 0)
        assert "32°F" in result
        assert "0°C" in result

    def test_both_converts_c(self):
        result = format_temperature_value(212.0, None, TemperatureUnit.BOTH, 0)
        assert "212°F" in result
        assert "100°C" in result

    def test_none_both(self):
        assert format_temperature_value(None, None, TemperatureUnit.FAHRENHEIT, 0) is None

    def test_fahrenheit_none_f(self):
        assert format_temperature_value(None, 20.0, TemperatureUnit.FAHRENHEIT, 0) is None

    def test_celsius_none_both(self):
        assert format_temperature_value(None, None, TemperatureUnit.CELSIUS, 0) is None

    def test_both_none_f(self):
        assert format_temperature_value(None, 20.0, TemperatureUnit.BOTH, 0) is None


# ── _get_severe_risk_description ──


class TestSevereRiskDescription:
    def test_extreme(self):
        assert _get_severe_risk_description(80) == "Extreme"
        assert _get_severe_risk_description(100) == "Extreme"

    def test_high(self):
        assert _get_severe_risk_description(60) == "High"
        assert _get_severe_risk_description(79) == "High"

    def test_moderate(self):
        assert _get_severe_risk_description(40) == "Moderate"

    def test_low(self):
        assert _get_severe_risk_description(20) == "Low"

    def test_minimal(self):
        assert _get_severe_risk_description(19) == "Minimal"
        assert _get_severe_risk_description(0) == "Minimal"


# ── direction_descriptor ──


class TestDirectionDescriptor:
    def test_rising_strong(self):
        assert "rising" in direction_descriptor(0.06, minor=0.02, strong=0.05)
        assert "⬆⬆" in direction_descriptor(0.06, minor=0.02, strong=0.05)

    def test_rising_minor(self):
        result = direction_descriptor(0.03, minor=0.02, strong=0.05)
        assert "rising" in result
        assert "⬆⬆" not in result

    def test_falling_strong(self):
        result = direction_descriptor(-0.06, minor=0.02, strong=0.05)
        assert "falling" in result
        assert "⬇⬇" in result

    def test_falling_minor(self):
        result = direction_descriptor(-0.03, minor=0.02, strong=0.05)
        assert "falling" in result
        assert "⬇⬇" not in result

    def test_steady(self):
        assert "steady" in direction_descriptor(0.01, minor=0.02, strong=0.05)


# ── split_direction_descriptor ──


class TestSplitDirectionDescriptor:
    def test_with_arrow(self):
        assert split_direction_descriptor("rising ⬆") == ("rising", "⬆")

    def test_no_arrow(self):
        assert split_direction_descriptor("steady") == ("steady", "")

    def test_empty(self):
        assert split_direction_descriptor("") == ("steady", "")

    def test_double_arrow(self):
        direction, arrow = split_direction_descriptor("falling ⬇⬇")
        assert direction == "falling"
        assert "⬇⬇" in arrow


# ── describe_trend ──


class TestDescribeTrend:
    def test_basic(self):
        trend = TrendInsight(metric="temperature", direction="rising", change=2.5, unit="°F")
        result = describe_trend(trend)
        assert "Rising" in result
        assert "+2.5°F" in result
        assert "24h" in result

    def test_no_change(self):
        trend = TrendInsight(metric="pressure", direction="steady")
        result = describe_trend(trend)
        assert "Steady" in result

    def test_custom_timeframe(self):
        trend = TrendInsight(
            metric="humidity", direction="falling", change=-5.0, unit="%", timeframe_hours=6
        )
        result = describe_trend(trend)
        assert "6h" in result

    def test_no_unit(self):
        trend = TrendInsight(metric="something", direction="rising", change=1.5)
        result = describe_trend(trend)
        assert "+1.5" in result

    def test_none_direction(self):
        trend = TrendInsight(metric="x", direction=None)
        result = describe_trend(trend)
        assert "Steady" in result


# ── _categorize_metric ──


class TestCategorizeMetric:
    def test_temperature(self):
        assert _categorize_metric("Temperature") == WeatherCategory.TEMPERATURE

    def test_feels_like(self):
        assert _categorize_metric("Feels different") == WeatherCategory.TEMPERATURE

    def test_wind(self):
        assert _categorize_metric("Wind") == WeatherCategory.WIND

    def test_wind_chill_is_temperature(self):
        assert _categorize_metric("Wind chill") == WeatherCategory.TEMPERATURE

    def test_precipitation(self):
        assert _categorize_metric("Precipitation type") == WeatherCategory.PRECIPITATION

    def test_humidity(self):
        assert _categorize_metric("Humidity") == WeatherCategory.HUMIDITY_PRESSURE

    def test_pressure(self):
        assert _categorize_metric("Pressure") == WeatherCategory.HUMIDITY_PRESSURE

    def test_visibility(self):
        assert _categorize_metric("Visibility") == WeatherCategory.VISIBILITY_CLOUDS

    def test_uv(self):
        assert _categorize_metric("UV Index") == WeatherCategory.UV_INDEX

    def test_unknown_defaults_temperature(self):
        assert _categorize_metric("Something random") == WeatherCategory.TEMPERATURE


# ── _order_metrics_by_priority ──


class TestOrderMetricsByPriority:
    def test_reorders(self):
        metrics = [
            Metric("Wind", "10 mph"),
            Metric("Temperature", "72°F"),
        ]
        ordered = _order_metrics_by_priority(
            metrics, [WeatherCategory.TEMPERATURE, WeatherCategory.WIND]
        )
        assert ordered[0].label == "Temperature"
        assert ordered[1].label == "Wind"

    def test_empty(self):
        assert _order_metrics_by_priority([], [WeatherCategory.TEMPERATURE]) == []


# ── _build_basic_metrics ──


class TestBuildBasicMetrics:
    def test_full_data(self):
        current = CurrentConditions(
            temperature_f=72.0,
            temperature_c=22.2,
            humidity=55,
            wind_speed_mph=10.0,
            wind_direction="NW",
            dewpoint_f=50.0,
            dewpoint_c=10.0,
            pressure_in=30.01,
            visibility_miles=10.0,
            uv_index=5.0,
        )
        metrics = _build_basic_metrics(
            current,
            TemperatureUnit.FAHRENHEIT,
            0,
            show_dewpoint=True,
            show_visibility=True,
            show_uv_index=True,
        )
        labels = [m.label for m in metrics]
        assert "Temperature" in labels
        assert "Humidity" in labels
        assert "Wind" in labels
        assert "Dewpoint" in labels
        assert "Pressure" in labels
        assert "Visibility" in labels
        assert "UV Index" in labels

    def test_minimal_data(self):
        current = CurrentConditions(temperature_f=72.0)
        metrics = _build_basic_metrics(
            current,
            TemperatureUnit.FAHRENHEIT,
            0,
            show_dewpoint=True,
            show_visibility=True,
            show_uv_index=True,
        )
        labels = [m.label for m in metrics]
        assert "Temperature" in labels
        assert "Humidity" not in labels

    def test_dewpoint_hidden(self):
        current = CurrentConditions(temperature_f=72.0, dewpoint_f=50.0)
        metrics = _build_basic_metrics(
            current,
            TemperatureUnit.FAHRENHEIT,
            0,
            show_dewpoint=False,
            show_visibility=True,
            show_uv_index=True,
        )
        labels = [m.label for m in metrics]
        assert "Dewpoint" not in labels

    def test_visibility_hidden(self):
        current = CurrentConditions(temperature_f=72.0, visibility_miles=10.0)
        metrics = _build_basic_metrics(
            current,
            TemperatureUnit.FAHRENHEIT,
            0,
            show_dewpoint=True,
            show_visibility=False,
            show_uv_index=True,
        )
        labels = [m.label for m in metrics]
        assert "Visibility" not in labels

    def test_uv_hidden(self):
        current = CurrentConditions(temperature_f=72.0, uv_index=5.0)
        metrics = _build_basic_metrics(
            current,
            TemperatureUnit.FAHRENHEIT,
            0,
            show_dewpoint=True,
            show_visibility=True,
            show_uv_index=False,
        )
        labels = [m.label for m in metrics]
        assert "UV Index" not in labels


# ── _build_astronomical_metrics ──


class TestBuildAstronomicalMetrics:
    def test_with_times(self):
        dt = datetime(2026, 2, 7, 12, 0, tzinfo=timezone.utc)
        current = CurrentConditions(
            sunrise_time=dt,
            sunset_time=dt,
            moon_phase="Full",
            moonrise_time=dt,
            moonset_time=dt,
        )
        metrics = _build_astronomical_metrics(current)
        labels = [m.label for m in metrics]
        assert "Sunrise" in labels
        assert "Sunset" in labels
        assert "Moon phase" in labels
        assert "Moonrise" in labels
        assert "Moonset" in labels

    def test_no_times(self):
        current = CurrentConditions()
        metrics = _build_astronomical_metrics(current)
        assert len(metrics) == 0

    def test_moon_phase_only(self):
        current = CurrentConditions(moon_phase="Waning Crescent")
        metrics = _build_astronomical_metrics(current)
        assert len(metrics) == 1
        assert metrics[0].label == "Moon phase"


# ── _build_environmental_metrics ──


class TestBuildEnvironmentalMetrics:
    def test_none_environmental(self):
        assert _build_environmental_metrics(None, None) == []

    def test_air_quality_index(self):
        env = EnvironmentalConditions(
            air_quality_index=42.0,
            air_quality_category="Good",
            air_quality_pollutant="PM2.5",
        )
        metrics = _build_environmental_metrics(env, None)
        assert len(metrics) == 1
        assert "42" in metrics[0].value
        assert "Good" in metrics[0].value
        assert "PM2.5" in metrics[0].value

    def test_pollen(self):
        env = EnvironmentalConditions(
            pollen_index=3.0,
            pollen_category="Moderate",
            pollen_primary_allergen="Grass",
        )
        metrics = _build_environmental_metrics(env, None)
        labels = [m.label for m in metrics]
        assert "Pollen" in labels
        pollen = next(m for m in metrics if m.label == "Pollen")
        assert "3" in pollen.value
        assert "Moderate" in pollen.value
        assert "Grass" in pollen.value

    def test_pollen_allergen_only(self):
        env = EnvironmentalConditions(pollen_primary_allergen="Tree")
        metrics = _build_environmental_metrics(env, None)
        assert len(metrics) == 1
        assert "Tree" in metrics[0].value

    def test_pollen_category_no_index(self):
        env = EnvironmentalConditions(
            pollen_category="Low", pollen_index=None, pollen_primary_allergen=None
        )
        # pollen_index is None and pollen_primary_allergen is None, so no pollen metric
        metrics = _build_environmental_metrics(env, None)
        assert len(metrics) == 0


# ── _build_seasonal_metrics ──


class TestBuildSeasonalMetrics:
    def test_snow_depth_fahrenheit(self):
        current = CurrentConditions(snow_depth_in=6.0)
        metrics = _build_seasonal_metrics(current, TemperatureUnit.FAHRENHEIT, 0)
        assert any("6.0 in" in m.value for m in metrics)

    def test_snow_depth_celsius(self):
        current = CurrentConditions(snow_depth_in=6.0)
        metrics = _build_seasonal_metrics(current, TemperatureUnit.CELSIUS, 0)
        assert any("cm" in m.value for m in metrics)

    def test_snow_depth_both(self):
        current = CurrentConditions(snow_depth_in=6.0)
        metrics = _build_seasonal_metrics(current, TemperatureUnit.BOTH, 0)
        snow = [m for m in metrics if m.label == "Snow on ground"]
        assert len(snow) == 1
        assert "in" in snow[0].value and "cm" in snow[0].value

    def test_zero_snow(self):
        current = CurrentConditions(snow_depth_in=0.0)
        metrics = _build_seasonal_metrics(current, TemperatureUnit.FAHRENHEIT, 0)
        assert not any(m.label == "Snow on ground" for m in metrics)

    def test_wind_chill(self):
        current = CurrentConditions(temperature_f=20.0, wind_chill_f=5.0)
        metrics = _build_seasonal_metrics(current, TemperatureUnit.FAHRENHEIT, 0)
        assert any(m.label == "Wind chill" for m in metrics)

    def test_wind_chill_close_to_temp(self):
        current = CurrentConditions(temperature_f=20.0, wind_chill_f=19.0)
        metrics = _build_seasonal_metrics(current, TemperatureUnit.FAHRENHEIT, 0)
        assert not any(m.label == "Wind chill" for m in metrics)

    def test_wind_chill_no_temp(self):
        current = CurrentConditions(wind_chill_f=5.0)
        metrics = _build_seasonal_metrics(current, TemperatureUnit.FAHRENHEIT, 0)
        assert any(m.label == "Wind chill" for m in metrics)

    def test_heat_index(self):
        current = CurrentConditions(temperature_f=95.0, heat_index_f=110.0)
        metrics = _build_seasonal_metrics(current, TemperatureUnit.FAHRENHEIT, 0)
        assert any(m.label == "Heat index" for m in metrics)

    def test_heat_index_close_to_temp(self):
        current = CurrentConditions(temperature_f=95.0, heat_index_f=96.0)
        metrics = _build_seasonal_metrics(current, TemperatureUnit.FAHRENHEIT, 0)
        assert not any(m.label == "Heat index" for m in metrics)

    def test_frost_risk(self):
        current = CurrentConditions(frost_risk="High")
        metrics = _build_seasonal_metrics(current, TemperatureUnit.FAHRENHEIT, 0)
        assert any(m.label == "Frost risk" for m in metrics)

    def test_frost_risk_none(self):
        current = CurrentConditions(frost_risk="None")
        metrics = _build_seasonal_metrics(current, TemperatureUnit.FAHRENHEIT, 0)
        assert not any(m.label == "Frost risk" for m in metrics)

    def test_precipitation_type_with_active_precip(self):
        current = CurrentConditions(
            condition="Heavy Rain",
            precipitation_type=["rain"],
        )
        metrics = _build_seasonal_metrics(current, TemperatureUnit.FAHRENHEIT, 0)
        assert any(m.label == "Precipitation type" for m in metrics)

    def test_precipitation_type_no_active_precip(self):
        current = CurrentConditions(
            condition="Clear",
            precipitation_type=["rain"],
        )
        metrics = _build_seasonal_metrics(current, TemperatureUnit.FAHRENHEIT, 0)
        assert not any(m.label == "Precipitation type" for m in metrics)

    def test_severe_weather_risk(self):
        current = CurrentConditions(severe_weather_risk=60)
        metrics = _build_seasonal_metrics(current, TemperatureUnit.FAHRENHEIT, 0)
        risk = [m for m in metrics if m.label == "Severe weather risk"]
        assert len(risk) == 1
        assert "High" in risk[0].value

    def test_severe_weather_risk_zero(self):
        current = CurrentConditions(severe_weather_risk=0)
        metrics = _build_seasonal_metrics(current, TemperatureUnit.FAHRENHEIT, 0)
        assert not any(m.label == "Severe weather risk" for m in metrics)

    def test_freezing_level_fahrenheit(self):
        current = CurrentConditions(freezing_level_ft=5000.0)
        metrics = _build_seasonal_metrics(current, TemperatureUnit.FAHRENHEIT, 0)
        assert any("5000 ft" in m.value for m in metrics)

    def test_freezing_level_celsius(self):
        current = CurrentConditions(freezing_level_ft=5000.0)
        metrics = _build_seasonal_metrics(current, TemperatureUnit.CELSIUS, 0)
        assert any("m" in m.value for m in metrics)

    def test_freezing_level_both(self):
        current = CurrentConditions(freezing_level_ft=5000.0)
        metrics = _build_seasonal_metrics(current, TemperatureUnit.BOTH, 0)
        fl = [m for m in metrics if m.label == "Freezing level"]
        assert len(fl) == 1
        assert "ft" in fl[0].value and "m" in fl[0].value


# ── _build_trend_metrics ──


class TestBuildTrendMetrics:
    def test_with_trends(self):
        trends = [
            TrendInsight(metric="temperature", direction="rising", summary="Getting warmer"),
        ]
        current = CurrentConditions()
        metrics = _build_trend_metrics(trends, current, None, show_pressure_trend=True)
        assert len(metrics) == 1
        assert "warmer" in metrics[0].value

    def test_pressure_trend_hidden(self):
        trends = [
            TrendInsight(metric="pressure", direction="rising", summary="Pressure rising"),
        ]
        current = CurrentConditions()
        metrics = _build_trend_metrics(trends, current, None, show_pressure_trend=False)
        assert len(metrics) == 0

    def test_no_trends(self):
        metrics = _build_trend_metrics(None, CurrentConditions(), None, show_pressure_trend=True)
        assert len(metrics) == 0

    def test_sparkline_appended(self):
        trends = [
            TrendInsight(
                metric="temperature",
                direction="rising",
                summary="Rising",
                sparkline="▁▃▅▇",
            ),
        ]
        metrics = _build_trend_metrics(trends, CurrentConditions(), None, show_pressure_trend=True)
        assert "▁▃▅▇" in metrics[0].value


# ── compute_pressure_trend_from_hourly ──


class TestComputePressureTrend:
    def test_no_hourly(self):
        current = CurrentConditions(pressure_in=30.0)
        assert compute_pressure_trend_from_hourly(current, None) is None

    def test_with_pressure_data_in(self):
        current = CurrentConditions(pressure_in=30.0)
        dt = datetime(2026, 2, 7, 12, 0, tzinfo=timezone.utc)
        periods = [
            HourlyForecastPeriod(start_time=dt, pressure_in=30.0),
            HourlyForecastPeriod(start_time=dt, pressure_in=30.05),
            HourlyForecastPeriod(start_time=dt, pressure_in=30.10),
        ]
        hourly = HourlyForecast(periods=periods)
        result = compute_pressure_trend_from_hourly(current, hourly)
        assert result is not None
        assert "rising" in result["summary"].lower() or "Rising" in result["value"]

    def test_with_pressure_data_mb(self):
        current = CurrentConditions(pressure_mb=1013.0)
        dt = datetime(2026, 2, 7, 12, 0, tzinfo=timezone.utc)
        periods = [
            HourlyForecastPeriod(start_time=dt, pressure_mb=1013.0),
            HourlyForecastPeriod(start_time=dt, pressure_mb=1011.0),
        ]
        hourly = HourlyForecast(periods=periods)
        result = compute_pressure_trend_from_hourly(current, hourly)
        assert result is not None
        assert "mb" in result["value"]

    def test_no_pressure_in_periods(self):
        current = CurrentConditions(pressure_in=30.0)
        dt = datetime(2026, 2, 7, 12, 0, tzinfo=timezone.utc)
        periods = [HourlyForecastPeriod(start_time=dt)]
        hourly = HourlyForecast(periods=periods)
        result = compute_pressure_trend_from_hourly(current, hourly)
        assert result is None


# ── format_trend_lines ──


class TestFormatTrendLines:
    def test_basic(self):
        trends = [
            TrendInsight(metric="temperature", direction="rising", summary="Warming up"),
        ]
        lines = format_trend_lines(trends)
        assert "Warming up" in lines

    def test_no_trends(self):
        assert format_trend_lines(None) == []

    def test_pressure_excluded(self):
        trends = [
            TrendInsight(metric="pressure", direction="rising", summary="Pressure up"),
        ]
        lines = format_trend_lines(trends, include_pressure=False)
        assert len(lines) == 0


# ── build_current_conditions (integration) ──


class TestBuildCurrentConditions:
    def test_basic(self):
        current = CurrentConditions(
            temperature_f=72.0,
            temperature_c=22.2,
            condition="Partly Cloudy",
            humidity=55,
        )
        location = Location(name="Test City", latitude=40.0, longitude=-74.0)
        result = build_current_conditions(current, location, TemperatureUnit.FAHRENHEIT)
        assert "Test City" in result.title
        assert result.description == "Partly Cloudy"
        assert len(result.metrics) > 0
        assert "72" in result.fallback_text

    def test_unknown_condition(self):
        current = CurrentConditions(temperature_f=72.0)
        location = Location(name="Nowhere", latitude=0, longitude=0)
        result = build_current_conditions(current, location, TemperatureUnit.FAHRENHEIT)
        assert result.description == "Unknown"

    def test_with_environmental(self):
        current = CurrentConditions(temperature_f=72.0)
        location = Location(name="City", latitude=0, longitude=0)
        env = EnvironmentalConditions(air_quality_index=50.0, air_quality_category="Good")
        result = build_current_conditions(
            current, location, TemperatureUnit.FAHRENHEIT, environmental=env
        )
        labels = [m.label for m in result.metrics]
        assert "Air Quality" in labels

    def test_with_trends(self):
        current = CurrentConditions(temperature_f=72.0)
        location = Location(name="City", latitude=0, longitude=0)
        trends = [TrendInsight(metric="temperature", direction="rising", summary="Getting hot")]
        result = build_current_conditions(
            current, location, TemperatureUnit.FAHRENHEIT, trends=trends
        )
        assert len(result.trends) > 0
