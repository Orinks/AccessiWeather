"""
Regression / property tests for unit-preference bugs:

Bug 1  – Temperature trend shows °F even when user prefers °C.
Bug 2  – Hourly precip always renders "0.00 in" (ignores mm preference).
Bug 3  – Hourly wind/gust use different unit systems.
Bug 4  – Daily forecast is capped at 7 days even when 15-day is configured.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from accessiweather.display.presentation.current_conditions import (
    _adapt_temperature_trend_summary,
    _build_basic_metrics,
    _build_trend_metrics,
    build_current_conditions,
    format_trend_lines,
)
from accessiweather.display.presentation.forecast import build_hourly_summary
from accessiweather.models import (
    AppSettings,
    CurrentConditions,
    Forecast,
    ForecastPeriod,
    HourlyForecast,
    HourlyForecastPeriod,
    Location,
    TrendInsight,
)
from accessiweather.pirate_weather_client import PirateWeatherClient
from accessiweather.utils import TemperatureUnit

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2025, 3, 1, 12, 0, tzinfo=UTC)


def _make_hourly_period(
    offset_hours: int = 1,
    temp_f: float = 70.0,
    wind_speed: str | None = "10 km/h",
    wind_direction: str | None = "N",
    wind_gust_mph: float | None = 12.0,
    precip_amount: float | None = 0.5,  # inches
    precip_prob: float | None = 80,
) -> HourlyForecastPeriod:
    return HourlyForecastPeriod(
        start_time=_NOW + timedelta(hours=offset_hours),
        temperature=temp_f,
        temperature_unit="F",
        short_forecast="Rain",
        wind_speed=wind_speed,
        wind_direction=wind_direction,
        wind_gust_mph=wind_gust_mph,
        precipitation_amount=precip_amount,
        precipitation_probability=precip_prob,
    )


def _make_settings(**kwargs) -> AppSettings:
    s = AppSettings()
    for k, v in kwargs.items():
        setattr(s, k, v)
    return s


# ---------------------------------------------------------------------------
# Bug 1 – Temperature trend unit conversion
# ---------------------------------------------------------------------------


class TestTemperatureTrendUnitBug:
    """Temperature trend summary must use the user's preferred unit."""

    def _trend_f(self, change: float = 3.0) -> TrendInsight:
        return TrendInsight(
            metric="temperature",
            direction="rising",
            change=change,
            unit="°F",
            timeframe_hours=24,
            summary=f"Temperature rising {change:+.1f}°F over 24h",
        )

    def test_fahrenheit_pref_keeps_f(self):
        trend = self._trend_f(3.0)
        result = _adapt_temperature_trend_summary(trend, TemperatureUnit.FAHRENHEIT)
        assert "°F" in result
        assert "°C" not in result

    def test_celsius_pref_converts_to_c(self):
        trend = self._trend_f(9.0)  # 9°F = 5°C delta
        result = _adapt_temperature_trend_summary(trend, TemperatureUnit.CELSIUS)
        assert "°C" in result
        assert "°F" not in result
        assert "+5.0°C" in result

    def test_both_pref_shows_both(self):
        trend = self._trend_f(9.0)
        result = _adapt_temperature_trend_summary(trend, TemperatureUnit.BOTH)
        assert "°F" in result
        assert "°C" in result

    def test_celsius_source_to_fahrenheit_pref(self):
        trend = TrendInsight(
            metric="temperature",
            direction="falling",
            change=-5.0,  # -5°C delta = -9°F delta
            unit="°C",
            timeframe_hours=24,
            summary="Temperature falling -5.0°C over 24h",
        )
        result = _adapt_temperature_trend_summary(trend, TemperatureUnit.FAHRENHEIT)
        assert "°F" in result
        assert "°C" not in result
        assert "-9.0°F" in result

    def test_non_temp_trend_unchanged(self):
        trend = TrendInsight(
            metric="pressure",
            direction="rising",
            change=0.03,
            unit="inHg",
            timeframe_hours=6,
            summary="Pressure rising +0.03inHg over 6h",
        )
        result = _adapt_temperature_trend_summary(trend, TemperatureUnit.CELSIUS)
        # Non-temperature trends are returned as-is
        assert result == trend.summary

    def test_build_trend_metrics_celsius_pref_shows_celsius(self):
        """_build_trend_metrics must honour unit_pref for temperature trends."""
        current = CurrentConditions(temperature_f=72.0, temperature_c=22.2, condition="Sunny")
        trend = self._trend_f(9.0)
        metrics = _build_trend_metrics(
            [trend],
            current,
            hourly_forecast=None,
            show_pressure_trend=False,
            unit_pref=TemperatureUnit.CELSIUS,
        )
        assert len(metrics) == 1
        assert "°C" in metrics[0].value
        assert "°F" not in metrics[0].value

    def test_format_trend_lines_celsius_pref(self):
        trend = self._trend_f(9.0)
        lines = format_trend_lines([trend], unit_pref=TemperatureUnit.CELSIUS)
        assert len(lines) == 1
        assert "°C" in lines[0]
        assert "°F" not in lines[0]


@given(
    change_f=st.floats(min_value=-20.0, max_value=20.0, allow_nan=False, allow_infinity=False),
    unit_pref=st.sampled_from(list(TemperatureUnit)),
)
@settings(max_examples=50)
def test_temperature_trend_always_uses_preferred_unit(change_f, unit_pref):
    """Property: temperature trend summary always contains the preferred unit symbol."""
    trend = TrendInsight(
        metric="temperature",
        direction="rising",
        change=change_f,
        unit="°F",
        timeframe_hours=24,
        summary=f"Temperature rising {change_f:+.1f}°F over 24h",
    )
    result = _adapt_temperature_trend_summary(trend, unit_pref)
    if unit_pref == TemperatureUnit.FAHRENHEIT:
        assert "°F" in result
    elif unit_pref == TemperatureUnit.CELSIUS:
        assert "°C" in result
        assert "°F" not in result
    else:  # BOTH
        assert "°F" in result
        assert "°C" in result


# ---------------------------------------------------------------------------
# Bug 2 – Hourly precipitation unit
# ---------------------------------------------------------------------------


class TestHourlyPrecipUnitBug:
    """Hourly precipitation amount must honour the user's unit preference."""

    def _make_hourly(self, precip_in: float = 0.5) -> HourlyForecast:
        period = _make_hourly_period(precip_amount=precip_in)
        return HourlyForecast(periods=[period], generated_at=_NOW)

    def _settings(self, unit: str = "both") -> AppSettings:
        s = _make_settings(verbosity_level="detailed", hourly_forecast_hours=1)
        s.temperature_unit = unit
        return s

    def test_fahrenheit_pref_shows_in(self):
        hourly = self._make_hourly(0.5)
        unit_pref = TemperatureUnit.FAHRENHEIT
        results = build_hourly_summary(hourly, unit_pref, settings=self._settings("fahrenheit"))
        found = [p for p in results if p.precipitation_amount]
        assert found, "precipitation_amount should be present"
        assert "in" in found[0].precipitation_amount
        assert "mm" not in found[0].precipitation_amount

    def test_celsius_pref_shows_mm(self):
        hourly = self._make_hourly(0.5)
        unit_pref = TemperatureUnit.CELSIUS
        results = build_hourly_summary(hourly, unit_pref, settings=self._settings("celsius"))
        found = [p for p in results if p.precipitation_amount]
        assert found, "precipitation_amount should be present"
        assert "mm" in found[0].precipitation_amount
        assert " in" not in found[0].precipitation_amount

    def test_both_pref_shows_both(self):
        hourly = self._make_hourly(0.5)
        unit_pref = TemperatureUnit.BOTH
        results = build_hourly_summary(hourly, unit_pref, settings=self._settings("both"))
        found = [p for p in results if p.precipitation_amount]
        assert found, "precipitation_amount should be present"
        assert "in" in found[0].precipitation_amount
        assert "mm" in found[0].precipitation_amount

    def test_zero_precip_not_shown(self):
        period = _make_hourly_period(precip_amount=0.0)
        hourly = HourlyForecast(periods=[period], generated_at=_NOW)
        results = build_hourly_summary(
            hourly,
            TemperatureUnit.FAHRENHEIT,
            settings=self._settings("fahrenheit"),
        )
        assert not any(p.precipitation_amount for p in results)


@given(
    precip_in=st.floats(min_value=0.01, max_value=5.0, allow_nan=False),
    unit_pref=st.sampled_from(list(TemperatureUnit)),
)
@settings(max_examples=50)
def test_hourly_precip_always_uses_preferred_unit(precip_in, unit_pref):
    """Property: hourly precip amount always contains the preferred unit."""
    period = _make_hourly_period(precip_amount=precip_in)
    hourly = HourlyForecast(periods=[period], generated_at=_NOW)
    s = AppSettings()
    s.verbosity_level = "detailed"
    s.hourly_forecast_hours = 1
    results = build_hourly_summary(hourly, unit_pref, settings=s)
    found = [p for p in results if p.precipitation_amount]
    assert found, f"precipitation should be present for {precip_in} in"
    amt_str = found[0].precipitation_amount
    if unit_pref == TemperatureUnit.FAHRENHEIT:
        assert " in" in amt_str, f"Expected 'in' in {amt_str!r}"
    elif unit_pref == TemperatureUnit.CELSIUS:
        assert "mm" in amt_str, f"Expected 'mm' in {amt_str!r}"
    else:
        assert " in" in amt_str and "mm" in amt_str, f"Expected both in {amt_str!r}"


# ---------------------------------------------------------------------------
# Bug 3 – Hourly wind/gust same unit
# ---------------------------------------------------------------------------


class TestHourlyWindGustUnitBug:
    """Wind speed and wind gust must use the same preferred unit."""

    def _run(
        self,
        unit_pref: TemperatureUnit,
        wind_speed: str = "10 km/h",
        wind_gust_mph: float = 15.0,
    ) -> list:
        period = _make_hourly_period(
            wind_speed=wind_speed,
            wind_gust_mph=wind_gust_mph,
        )
        hourly = HourlyForecast(periods=[period], generated_at=_NOW)
        s = AppSettings()
        s.verbosity_level = "detailed"
        s.hourly_forecast_hours = 1
        return build_hourly_summary(hourly, unit_pref, settings=s)

    def test_celsius_pref_gust_in_kmh(self):
        results = self._run(TemperatureUnit.CELSIUS)
        found = [p for p in results if p.wind_gust]
        assert found, "wind_gust should be present"
        gust_str = found[0].wind_gust
        assert "km/h" in gust_str, f"Expected km/h in gust, got {gust_str!r}"
        assert "mph" not in gust_str

    def test_fahrenheit_pref_gust_in_mph(self):
        results = self._run(TemperatureUnit.FAHRENHEIT, wind_speed="10 mph")
        found = [p for p in results if p.wind_gust]
        assert found, "wind_gust should be present"
        gust_str = found[0].wind_gust
        assert "mph" in gust_str, f"Expected mph in gust, got {gust_str!r}"
        assert "km/h" not in gust_str

    def test_both_pref_gust_shows_both(self):
        results = self._run(TemperatureUnit.BOTH)
        found = [p for p in results if p.wind_gust]
        assert found
        gust_str = found[0].wind_gust
        assert "mph" in gust_str and "km/h" in gust_str


@given(
    wind_gust_mph=st.floats(min_value=1.0, max_value=100.0, allow_nan=False),
    unit_pref=st.sampled_from(list(TemperatureUnit)),
)
@settings(max_examples=50)
def test_hourly_wind_gust_always_uses_preferred_unit(wind_gust_mph, unit_pref):
    """Property: hourly wind gust always uses the same unit as the user preference."""
    period = _make_hourly_period(wind_gust_mph=wind_gust_mph)
    hourly = HourlyForecast(periods=[period], generated_at=_NOW)
    s = AppSettings()
    s.verbosity_level = "detailed"
    s.hourly_forecast_hours = 1
    results = build_hourly_summary(hourly, unit_pref, settings=s)
    found = [p for p in results if p.wind_gust]
    assert found, f"wind_gust should be present for {wind_gust_mph} mph"
    gust_str = found[0].wind_gust
    if unit_pref == TemperatureUnit.FAHRENHEIT:
        assert "mph" in gust_str, f"Expected mph in {gust_str!r}"
        assert "km/h" not in gust_str
    elif unit_pref == TemperatureUnit.CELSIUS:
        assert "km/h" in gust_str, f"Expected km/h in {gust_str!r}"
        assert "mph" not in gust_str
    else:  # BOTH
        assert "mph" in gust_str and "km/h" in gust_str, f"Expected both in {gust_str!r}"


# ---------------------------------------------------------------------------
# Bug 4 – Daily forecast days limit
# ---------------------------------------------------------------------------


class TestDailyForecastDaysRegressionPirateWeather:
    """PirateWeatherClient._parse_forecast must return ALL available days."""

    def _build_pw_payload(self, num_days: int) -> dict:
        """Build a synthetic Pirate Weather response with num_days daily entries."""
        base_ts = int(datetime(2025, 3, 2, 0, 0, 0, tzinfo=UTC).timestamp())
        day_secs = 86400
        daily_data = []
        for i in range(num_days):
            daily_data.append(
                {
                    "time": base_ts + i * day_secs,
                    "temperatureHigh": 70.0 + i,
                    "temperatureLow": 50.0 + i,
                    "summary": "Sunny",
                    "icon": "clear-day",
                    "precipProbability": 0.1,
                    "precipIntensity": 0.0,
                    "windSpeed": 10.0,
                    "windBearing": 180,
                    "cloudCover": 0.2,
                    "uvIndex": 5,
                    "windGust": 15.0,
                }
            )
        return {
            "currently": {"temperature": 72.0, "summary": "Clear"},
            "daily": {"summary": "Sunny week", "data": daily_data},
            "hourly": {"data": []},
            "offset": -5,
        }

    def test_all_days_returned_when_pw_has_8(self):
        client = PirateWeatherClient(api_key="test", units="us")
        payload = self._build_pw_payload(8)
        forecast = client._parse_forecast(payload)
        assert len(forecast.periods) == 8

    def test_all_days_returned_when_pw_has_16(self):
        client = PirateWeatherClient(api_key="test", units="us")
        payload = self._build_pw_payload(16)
        forecast = client._parse_forecast(payload)
        assert len(forecast.periods) == 16

    def test_backward_compat_days_param_ignored(self):
        """The legacy ``days`` parameter must not restrict the output."""
        client = PirateWeatherClient(api_key="test", units="us")
        payload = self._build_pw_payload(10)
        # Old callers may pass days=7; result must still include all 10 periods.
        forecast = client._parse_forecast(payload, days=7)
        assert len(forecast.periods) == 10

    def test_no_duplicate_days(self):
        """Each calendar date must appear at most once in the parsed periods."""
        client = PirateWeatherClient(api_key="test", units="us")
        payload = self._build_pw_payload(8)
        forecast = client._parse_forecast(payload)
        dates = [p.start_time.date() for p in forecast.periods if p.start_time]
        assert len(dates) == len(set(dates)), "Duplicate dates found in forecast"

    def test_15_day_setting_shows_15_days(self):
        """With forecast_duration_days=15 the display layer selects up to 15 days."""
        from accessiweather.display.presentation.forecast import build_forecast

        client = PirateWeatherClient(api_key="test", units="us")
        payload = self._build_pw_payload(16)
        raw_forecast = client._parse_forecast(payload)
        location = Location(name="Test City", latitude=40.0, longitude=-74.0, country_code="US")
        settings = _make_settings(forecast_duration_days=15)
        presentation = build_forecast(raw_forecast, None, location, TemperatureUnit.FAHRENHEIT, settings)
        assert len(presentation.periods) == 15

    def test_7_day_setting_shows_7_days(self):
        """With forecast_duration_days=7 (default) exactly 7 days are shown."""
        from accessiweather.display.presentation.forecast import build_forecast

        client = PirateWeatherClient(api_key="test", units="us")
        payload = self._build_pw_payload(16)
        raw_forecast = client._parse_forecast(payload)
        location = Location(name="Test City", latitude=40.0, longitude=-74.0, country_code="US")
        settings = _make_settings(forecast_duration_days=7)
        presentation = build_forecast(raw_forecast, None, location, TemperatureUnit.FAHRENHEIT, settings)
        assert len(presentation.periods) == 7
