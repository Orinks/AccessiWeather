"""Tests verifying the three-source weather model defaults."""

from __future__ import annotations

from datetime import UTC, datetime

from accessiweather.config.source_priority import SourcePriorityConfig
from accessiweather.models.config import AppSettings
from accessiweather.models.weather import (
    CurrentConditions,
    Forecast,
    ForecastPeriod,
    HourlyForecast,
    HourlyForecastPeriod,
    Location,
    SourceData,
)
from accessiweather.weather_client_fusion import DataFusionEngine

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_source(name, current=None, forecast=None, hourly=None, alerts=None, success=True):
    return SourceData(
        source=name,
        current=current,
        forecast=forecast,
        hourly_forecast=hourly,
        alerts=alerts,
        fetch_time=datetime.now(UTC),
        success=success,
    )


def _make_forecast(name="Day 1"):
    dt = datetime.now(UTC).replace(microsecond=0)
    period = ForecastPeriod(
        name=name,
        start_time=dt,
        end_time=dt,
        temperature=70,
        wind_speed="10 mph",
        wind_direction="N",
        short_forecast="Sunny",
        detailed_forecast="Sunny skies.",
    )
    return Forecast(periods=[period])


def _make_hourly(hours=24):
    dt = datetime.now(UTC).replace(microsecond=0)
    periods = [
        HourlyForecastPeriod(
            start_time=dt, temperature=70, wind_speed="10 mph", short_forecast="Clear"
        )
        for _ in range(hours)
    ]
    return HourlyForecast(periods=periods)


US_LOCATION = Location(name="New York", latitude=40.7, longitude=-74.0, country_code="US")
INTL_LOCATION = Location(name="London", latitude=51.5, longitude=-0.1, country_code="GB")


# ---------------------------------------------------------------------------
# SourcePriorityConfig defaults
# ---------------------------------------------------------------------------


class TestSourcePriorityConfigDefaults:
    def test_us_default_includes_pirateweather(self):
        config = SourcePriorityConfig()
        assert "pirateweather" in config.us_default

    def test_us_default_order(self):
        config = SourcePriorityConfig()
        assert config.us_default == ["nws", "openmeteo", "pirateweather"]

    def test_international_default_includes_pirateweather(self):
        config = SourcePriorityConfig()
        assert "pirateweather" in config.international_default

    def test_international_default_order(self):
        config = SourcePriorityConfig()
        assert config.international_default == ["openmeteo", "pirateweather"]

    def test_from_dict_us_default_fallback_includes_pirateweather(self):
        config = SourcePriorityConfig.from_dict({})
        assert "pirateweather" in config.us_default

    def test_from_dict_international_default_fallback_includes_pirateweather(self):
        config = SourcePriorityConfig.from_dict({})
        assert "pirateweather" in config.international_default

    def test_from_dict_preserves_explicit_list(self):
        custom_us = ["pirateweather", "nws", "openmeteo"]
        config = SourcePriorityConfig.from_dict({"us_default": custom_us})
        assert config.us_default == custom_us

    def test_roundtrip_json_preserves_pirateweather(self):
        config = SourcePriorityConfig()
        restored = SourcePriorityConfig.from_json(config.to_json())
        assert "pirateweather" in restored.us_default
        assert "pirateweather" in restored.international_default

    def test_roundtrip_dict_preserves_pirateweather(self):
        config = SourcePriorityConfig()
        restored = SourcePriorityConfig.from_dict(config.to_dict())
        assert restored.us_default == config.us_default
        assert restored.international_default == config.international_default


# ---------------------------------------------------------------------------
# AppSettings source priority defaults
# ---------------------------------------------------------------------------


class TestAppSettingsSourcePriorityDefaults:
    def test_us_priority_default_includes_pirateweather(self):
        settings = AppSettings()
        assert "pirateweather" in settings.source_priority_us

    def test_us_priority_default_order(self):
        settings = AppSettings()
        assert settings.source_priority_us == [
            "nws",
            "openmeteo",
            "pirateweather",
        ]

    def test_international_priority_default_includes_pirateweather(self):
        settings = AppSettings()
        assert "pirateweather" in settings.source_priority_international

    def test_international_priority_default_order(self):
        settings = AppSettings()
        assert settings.source_priority_international == [
            "openmeteo",
            "pirateweather",
        ]

    def test_from_dict_us_fallback_includes_pirateweather(self):
        settings = AppSettings.from_dict({})
        assert "pirateweather" in settings.source_priority_us

    def test_from_dict_international_fallback_includes_pirateweather(self):
        settings = AppSettings.from_dict({})
        assert "pirateweather" in settings.source_priority_international

    def test_from_dict_explicit_list_preserved(self):
        custom = ["pirateweather", "openmeteo"]
        data = {"source_priority_international": custom}
        settings = AppSettings.from_dict(data)
        assert settings.source_priority_international == custom

    def test_from_dict_filters_legacy_visual_crossing_sources(self):
        settings = AppSettings.from_dict(
            {
                "source_priority_us": ["nws", "visualcrossing", "pirateweather"],
                "source_priority_international": ["visualcrossing", "openmeteo"],
                "auto_sources_us": ["visualcrossing", "openmeteo"],
                "auto_sources_international": ["visualcrossing"],
            }
        )

        assert settings.source_priority_us == ["nws", "pirateweather"]
        assert settings.source_priority_international == ["openmeteo"]
        assert settings.auto_sources_us == ["openmeteo"]
        assert settings.auto_sources_international == ["openmeteo", "pirateweather"]


# ---------------------------------------------------------------------------
# DataFusionEngine forecast preferred_order
# ---------------------------------------------------------------------------


class TestFusionEnginePirateWeatherOrder:
    def test_merge_forecasts_us_falls_back_to_pirateweather(self):
        """When NWS and OM are absent, PW forecast is selected for US."""
        pw_forecast = _make_forecast("PW Day 1")
        sources = [_make_source("pirateweather", forecast=pw_forecast)]
        engine = DataFusionEngine()
        result, attribution = engine.merge_forecasts(sources, US_LOCATION)
        assert result is pw_forecast
        assert attribution.get("forecast_source") == "pirateweather"

    def test_merge_forecasts_intl_uses_pw_when_openmeteo_absent(self):
        """For international, PW should be selected when OM is absent."""
        pw_forecast = _make_forecast("PW Day 1")
        sources = [_make_source("pirateweather", forecast=pw_forecast)]
        engine = DataFusionEngine()
        result, attribution = engine.merge_forecasts(sources, INTL_LOCATION)
        assert result is pw_forecast
        assert attribution.get("forecast_source") == "pirateweather"

    def test_merge_forecasts_intl_prefers_openmeteo_over_pw(self):
        """For international, OM should be selected over PW."""
        om_forecast = _make_forecast("OM Day 1")
        pw_forecast = _make_forecast("PW Day 1")
        sources = [
            _make_source("openmeteo", forecast=om_forecast),
            _make_source("pirateweather", forecast=pw_forecast),
        ]
        engine = DataFusionEngine()
        result, attribution = engine.merge_forecasts(sources, INTL_LOCATION)
        assert result is om_forecast
        assert attribution.get("forecast_source") == "openmeteo"

    def test_merge_hourly_us_falls_back_to_pirateweather(self):
        """When NWS and OM are absent, PW hourly is selected for US."""
        pw_hourly = _make_hourly()
        sources = [_make_source("pirateweather", hourly=pw_hourly)]
        engine = DataFusionEngine()
        result, attribution = engine.merge_hourly_forecasts(sources, US_LOCATION)
        assert result is pw_hourly
        assert attribution.get("hourly_source") == "pirateweather"

    def test_merge_hourly_intl_uses_pw_when_openmeteo_absent(self):
        """For international, PW hourly should be selected when OM is absent."""
        pw_hourly = _make_hourly()
        sources = [_make_source("pirateweather", hourly=pw_hourly)]
        engine = DataFusionEngine()
        result, attribution = engine.merge_hourly_forecasts(sources, INTL_LOCATION)
        assert result is pw_hourly
        assert attribution.get("hourly_source") == "pirateweather"

    def test_merge_current_conditions_includes_pirateweather(self):
        """PW current conditions are included in merge when present."""
        pw_current = CurrentConditions(temperature_f=68.0)
        sources = [_make_source("pirateweather", current=pw_current)]
        engine = DataFusionEngine()
        result, attribution = engine.merge_current_conditions(sources, INTL_LOCATION)
        assert result is not None
        assert "pirateweather" in attribution.contributing_sources

    def test_merge_current_conditions_us_nws_takes_priority_over_pw(self):
        """For US, NWS current conditions take priority over PW."""
        nws_current = CurrentConditions(temperature_f=72.0)
        pw_current = CurrentConditions(temperature_f=65.0)
        sources = [
            _make_source("nws", current=nws_current),
            _make_source("pirateweather", current=pw_current),
        ]
        engine = DataFusionEngine()
        result, attribution = engine.merge_current_conditions(sources, US_LOCATION)
        assert result is not None
        # NWS temperature should win for US
        assert attribution.field_sources.get("temperature_f") == "nws"
