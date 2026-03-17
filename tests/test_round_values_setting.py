"""Tests for the round_values / whole-number display setting."""

from __future__ import annotations

from accessiweather.display.presentation.current_conditions import (
    _build_basic_metrics,
    _build_seasonal_metrics,
    build_current_conditions,
)
from accessiweather.display.presentation.formatters import (
    format_pressure_value,
    format_visibility_value,
    format_wind,
)
from accessiweather.models import (
    AppSettings,
    CurrentConditions,
    Location,
)
from accessiweather.taskbar_icon_updater import TaskbarIconUpdater
from accessiweather.utils import TemperatureUnit

# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_current(
    temp_f: float = 72.4,
    wind_mph: float = 8.7,
    pressure_in: float = 29.92,
    visibility_miles: float = 9.5,
    precip_in: float = 0.15,
    snow_in: float = 3.7,
    humidity: float = 55.0,
) -> CurrentConditions:
    return CurrentConditions(
        temperature_f=temp_f,
        temperature_c=(temp_f - 32) * 5 / 9,
        humidity=humidity,
        condition="Partly Cloudy",
        wind_speed_mph=wind_mph,
        wind_speed_kph=wind_mph * 1.60934,
        wind_direction="NW",
        pressure_in=pressure_in,
        pressure_mb=pressure_in * 33.8639,
        visibility_miles=visibility_miles,
        visibility_km=visibility_miles * 1.60934,
        precipitation_in=precip_in,
        precipitation_mm=precip_in * 25.4,
        snow_depth_in=snow_in,
        snow_depth_cm=snow_in * 2.54,
    )


def _make_settings(round_values: bool) -> AppSettings:
    return AppSettings(temperature_unit="fahrenheit", round_values=round_values)


def _make_location() -> Location:
    return Location(name="Test City", latitude=40.0, longitude=-75.0)


# ── AppSettings round_values field ───────────────────────────────────────────


class TestAppSettingsRoundValues:
    def test_default_is_false(self):
        s = AppSettings()
        assert s.round_values is False

    def test_round_true_roundtrips(self):
        s = AppSettings(round_values=True)
        d = s.to_dict()
        assert d["round_values"] is True
        restored = AppSettings.from_dict(d)
        assert restored.round_values is True

    def test_round_false_roundtrips(self):
        s = AppSettings(round_values=False)
        d = s.to_dict()
        assert d["round_values"] is False
        restored = AppSettings.from_dict(d)
        assert restored.round_values is False

    def test_from_dict_missing_key_defaults_false(self):
        s = AppSettings.from_dict({})
        assert s.round_values is False

    def test_from_dict_truthy_string(self):
        s = AppSettings.from_dict({"round_values": "true"})
        assert s.round_values is True


# ── format_wind precision ─────────────────────────────────────────────────────


class TestFormatWindPrecision:
    def setup_method(self):
        self.current = _make_current(wind_mph=8.7)

    def test_default_has_decimal(self):
        result = format_wind(self.current, TemperatureUnit.FAHRENHEIT)
        assert "8.7" in result

    def test_precision_zero_rounds(self):
        result = format_wind(self.current, TemperatureUnit.FAHRENHEIT, precision=0)
        assert "9" in result
        assert "8.7" not in result


# ── format_pressure_value precision ──────────────────────────────────────────


class TestFormatPressurePrecision:
    def setup_method(self):
        self.current = _make_current(pressure_in=29.92)

    def test_default_has_decimal(self):
        result = format_pressure_value(self.current, TemperatureUnit.FAHRENHEIT)
        assert "." in result

    def test_precision_zero_no_decimal(self):
        result = format_pressure_value(self.current, TemperatureUnit.FAHRENHEIT, precision=0)
        assert "." not in result
        assert "30" in result


# ── format_visibility_value precision ────────────────────────────────────────


class TestFormatVisibilityPrecision:
    def setup_method(self):
        self.current = _make_current(visibility_miles=9.5)

    def test_default_has_decimal(self):
        result = format_visibility_value(self.current, TemperatureUnit.FAHRENHEIT)
        assert "9.5" in result

    def test_precision_zero_rounds(self):
        result = format_visibility_value(self.current, TemperatureUnit.FAHRENHEIT, precision=0)
        assert "10" in result
        assert "9.5" not in result


# ── build_current_conditions with round_values ───────────────────────────────


class TestBuildCurrentConditionsRoundValues:
    def setup_method(self):
        self.current = _make_current(
            temp_f=72.4,
            wind_mph=8.7,
            pressure_in=29.92,
            visibility_miles=9.5,
            precip_in=0.15,
        )
        self.location = _make_location()

    def _get_metric(self, presentation, label):
        for m in presentation.metrics:
            if m.label == label:
                return m.value
        return None

    def test_round_values_false_keeps_decimals(self):
        settings = _make_settings(round_values=False)
        pres = build_current_conditions(
            self.current,
            self.location,
            TemperatureUnit.FAHRENHEIT,
            settings=settings,
        )
        temp = self._get_metric(pres, "Temperature")
        assert temp is not None
        # With smart_precision in format_temperature, 72.4°F stays as 72.4
        # Wind: 8.7 mph should show decimal
        wind = self._get_metric(pres, "Wind")
        assert wind is not None
        assert "8.7" in wind

    def test_round_values_true_removes_decimals_from_wind(self):
        settings = _make_settings(round_values=True)
        pres = build_current_conditions(
            self.current,
            self.location,
            TemperatureUnit.FAHRENHEIT,
            settings=settings,
        )
        wind = self._get_metric(pres, "Wind")
        assert wind is not None
        assert "8.7" not in wind
        assert "9" in wind

    def test_round_values_true_removes_decimals_from_pressure(self):
        settings = _make_settings(round_values=True)
        pres = build_current_conditions(
            self.current,
            self.location,
            TemperatureUnit.FAHRENHEIT,
            settings=settings,
        )
        pressure = self._get_metric(pres, "Pressure")
        assert pressure is not None
        assert "." not in pressure

    def test_round_values_true_removes_decimals_from_visibility(self):
        settings = _make_settings(round_values=True)
        pres = build_current_conditions(
            self.current,
            self.location,
            TemperatureUnit.FAHRENHEIT,
            settings=settings,
        )
        visibility = self._get_metric(pres, "Visibility")
        assert visibility is not None
        assert "9.5" not in visibility

    def test_round_values_true_removes_decimals_from_precipitation(self):
        settings = _make_settings(round_values=True)
        pres = build_current_conditions(
            self.current,
            self.location,
            TemperatureUnit.FAHRENHEIT,
            settings=settings,
        )
        precip = self._get_metric(pres, "Precipitation")
        assert precip is not None
        assert "0.15" not in precip


# ── _build_basic_metrics precipitation ───────────────────────────────────────


class TestBuildBasicMetricsPrecipitation:
    def test_precision_1_formats_correctly(self):
        current = _make_current(precip_in=0.17)
        metrics = _build_basic_metrics(current, TemperatureUnit.FAHRENHEIT, 1, True, True, True)
        precip = next((m for m in metrics if m.label == "Precipitation"), None)
        assert precip is not None
        assert "0.2" in precip.value  # rounds 0.17 to 0.2 at precision=1

    def test_precision_0_rounds_to_whole(self):
        current = _make_current(precip_in=0.15)
        metrics = _build_basic_metrics(current, TemperatureUnit.FAHRENHEIT, 0, True, True, True)
        precip = next((m for m in metrics if m.label == "Precipitation"), None)
        assert precip is not None
        assert "0.15" not in precip.value
        assert "." not in precip.value.split(" ")[0]


# ── _build_seasonal_metrics snow depth ───────────────────────────────────────


class TestBuildSeasonalMetricsSnowDepth:
    def test_default_precision_has_decimal(self):
        current = _make_current(snow_in=3.7)
        metrics = _build_seasonal_metrics(current, TemperatureUnit.FAHRENHEIT, 1)
        snow = next((m for m in metrics if m.label == "Snow on ground"), None)
        assert snow is not None
        assert "3.7" in snow.value

    def test_precision_0_rounds(self):
        current = _make_current(snow_in=3.7)
        metrics = _build_seasonal_metrics(current, TemperatureUnit.FAHRENHEIT, 0)
        snow = next((m for m in metrics if m.label == "Snow on ground"), None)
        assert snow is not None
        assert "3.7" not in snow.value
        assert "4" in snow.value


# ── TaskbarIconUpdater round_values ──────────────────────────────────────────


class TestTaskbarIconUpdaterRoundValues:
    def _make_current_ns(self, wind_mph=8.7, pressure_in=29.92, visibility_miles=9.5):
        from types import SimpleNamespace

        return SimpleNamespace(
            temperature_f=72.0,
            temperature_c=22.2,
            condition="Cloudy",
            humidity=55,
            wind_speed=wind_mph,
            wind_speed_mph=wind_mph,
            wind_speed_kph=wind_mph * 1.60934,
            wind_direction="NW",
            pressure=pressure_in,
            pressure_in=pressure_in,
            pressure_mb=pressure_in * 33.8639,
            feels_like_f=72.0,
            feels_like_c=22.2,
            uv_index=5,
            visibility_miles=visibility_miles,
            visibility_km=visibility_miles * 1.60934,
            precipitation=0.0,
            precipitation_mm=0.0,
            precipitation_probability=20,
            has_data=lambda: True,
        )

    def test_round_values_false_wind_has_decimal(self):
        updater = TaskbarIconUpdater(
            text_enabled=True,
            temperature_unit="fahrenheit",
            round_values=False,
        )
        current = self._make_current_ns(wind_mph=8.7)
        result = updater._format_wind_speed(current)
        assert "8.7" in result

    def test_round_values_true_wind_no_decimal(self):
        updater = TaskbarIconUpdater(
            text_enabled=True,
            temperature_unit="fahrenheit",
            round_values=True,
        )
        current = self._make_current_ns(wind_mph=8.7)
        result = updater._format_wind_speed(current)
        assert "8.7" not in result
        assert "9" in result

    def test_round_values_true_pressure_no_decimal(self):
        updater = TaskbarIconUpdater(
            text_enabled=True,
            temperature_unit="fahrenheit",
            round_values=True,
        )
        current = self._make_current_ns(pressure_in=29.92)
        result = updater._format_pressure(current)
        assert "." not in result

    def test_round_values_true_visibility_no_decimal(self):
        updater = TaskbarIconUpdater(
            text_enabled=True,
            temperature_unit="fahrenheit",
            round_values=True,
        )
        current = self._make_current_ns(visibility_miles=9.5)
        result = updater._format_visibility(current)
        assert "9.5" not in result

    def test_update_settings_round_values(self):
        updater = TaskbarIconUpdater(text_enabled=True, round_values=False)
        assert updater.round_values is False
        updater.update_settings(round_values=True)
        assert updater.round_values is True
