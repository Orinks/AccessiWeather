"""
Unit tests for accessiweather.impact_summary.

Covers:
- Outdoor guidance temperature bands
- Outdoor UV index modifiers
- Outdoor active precipitation modifier
- Driving: visibility thresholds
- Driving: precipitation-type detection (ice, snow, thunder, rain)
- Driving: near-freezing black-ice warning
- Driving: wind thresholds
- Driving: normal conditions baseline
- Allergy: pollen category bands
- Allergy: wind dispersion modifier
- Allergy: air quality modifier
- Allergy: pollen index fallback
- build_impact_summary: wires all three areas
- build_forecast_impact_summary: derives from ForecastPeriod
- ImpactSummary.has_content
"""

from __future__ import annotations

import pytest

from accessiweather.impact_summary import (
    ImpactSummary,
    _allergy_from_conditions,
    _driving_from_conditions,
    _outdoor_from_conditions,
    build_forecast_impact_summary,
    build_impact_summary,
)
from accessiweather.models.weather import (
    CurrentConditions,
    EnvironmentalConditions,
    ForecastPeriod,
)

# ── ImpactSummary helpers ──────────────────────────────────────────────────────


class TestImpactSummaryHasContent:
    def test_empty(self):
        assert ImpactSummary().has_content() is False

    def test_outdoor_only(self):
        assert ImpactSummary(outdoor="Hot").has_content() is True

    def test_driving_only(self):
        assert ImpactSummary(driving="Caution").has_content() is True

    def test_allergy_only(self):
        assert ImpactSummary(allergy="High pollen").has_content() is True

    def test_all_fields(self):
        assert ImpactSummary(outdoor="A", driving="B", allergy="C").has_content() is True


# ── Outdoor guidance ──────────────────────────────────────────────────────────


class TestOutdoorTemperatureBands:
    @pytest.mark.parametrize(
        "temp_f, expected_fragment",
        [
            (-5, "Dangerous cold"),
            (10, "Extreme cold"),
            (20, "Very cold"),
            (28, "Cold"),
            (45, "Cool"),
            (55, "Mild"),
            (70, "Comfortable"),
            (80, "Warm"),
            (90, "Hot"),
            (100, "Very hot"),
            (110, "Extreme heat"),
        ],
    )
    def test_temperature_bands(self, temp_f, expected_fragment):
        result = _outdoor_from_conditions(
            feels_like_f=temp_f, temp_f=temp_f, uv_index=None, condition=None
        )
        assert result is not None
        assert expected_fragment.lower() in result.lower()

    def test_feels_like_takes_priority_over_temp(self):
        # feels_like much colder than actual temp
        result = _outdoor_from_conditions(feels_like_f=5, temp_f=40, uv_index=None, condition=None)
        assert result is not None
        assert "extreme cold" in result.lower()

    def test_no_temp_returns_none(self):
        result = _outdoor_from_conditions(
            feels_like_f=None, temp_f=None, uv_index=None, condition=None
        )
        assert result is None

    def test_boundary_exact_zero(self):
        # Exactly 0°F → Extreme cold band (upper_exclusive=0 means < 0 is Dangerous cold)
        result = _outdoor_from_conditions(feels_like_f=0, temp_f=0, uv_index=None, condition=None)
        assert result is not None
        assert "extreme cold" in result.lower()

    def test_boundary_at_freezing(self):
        # Exactly 32°F → Cool band (upper_exclusive=32 means < 32 is Cold)
        result = _outdoor_from_conditions(feels_like_f=32, temp_f=32, uv_index=None, condition=None)
        assert result is not None
        assert "cool" in result.lower()

    def test_actual_temp_fallback_when_no_feels_like(self):
        result = _outdoor_from_conditions(
            feels_like_f=None, temp_f=70, uv_index=None, condition=None
        )
        assert result is not None
        assert "comfortable" in result.lower()


class TestOutdoorUVModifier:
    def test_uv_very_high(self):
        result = _outdoor_from_conditions(feels_like_f=72, temp_f=72, uv_index=9, condition=None)
        assert result is not None
        assert "uv very high" in result.lower()

    def test_uv_high(self):
        result = _outdoor_from_conditions(feels_like_f=72, temp_f=72, uv_index=7, condition=None)
        assert result is not None
        assert "sunscreen" in result.lower()

    def test_uv_low_no_modifier(self):
        result = _outdoor_from_conditions(feels_like_f=72, temp_f=72, uv_index=3, condition=None)
        assert result is not None
        assert "sunscreen" not in result.lower()
        assert "uv" not in result.lower()

    def test_uv_exactly_8_triggers_very_high(self):
        result = _outdoor_from_conditions(feels_like_f=72, temp_f=72, uv_index=8, condition=None)
        assert result is not None
        assert "uv very high" in result.lower()

    def test_uv_exactly_6_triggers_sunscreen(self):
        result = _outdoor_from_conditions(feels_like_f=72, temp_f=72, uv_index=6, condition=None)
        assert result is not None
        assert "sunscreen" in result.lower()

    def test_uv_none_no_modifier(self):
        result = _outdoor_from_conditions(feels_like_f=72, temp_f=72, uv_index=None, condition=None)
        assert result is not None
        assert "uv" not in result.lower()


class TestOutdoorPrecipitationModifier:
    @pytest.mark.parametrize(
        "condition",
        ["Light Rain", "Heavy Snow", "Thunderstorm", "Drizzle", "Sleet", "Hail", "Snow Flurries"],
    )
    def test_active_precip_adds_modifier(self, condition):
        result = _outdoor_from_conditions(
            feels_like_f=65, temp_f=65, uv_index=None, condition=condition
        )
        assert result is not None
        assert "precipitation" in result.lower()

    def test_clear_condition_no_precip_modifier(self):
        result = _outdoor_from_conditions(
            feels_like_f=72, temp_f=72, uv_index=None, condition="Mostly Sunny"
        )
        assert result is not None
        assert "precipitation" not in result.lower()

    def test_none_condition_no_precip_modifier(self):
        result = _outdoor_from_conditions(feels_like_f=72, temp_f=72, uv_index=None, condition=None)
        assert result is not None
        assert "precipitation" not in result.lower()

    def test_multiple_modifiers_joined_by_semicolon(self):
        result = _outdoor_from_conditions(feels_like_f=72, temp_f=72, uv_index=9, condition="Rain")
        assert result is not None
        assert ";" in result
        assert "uv very high" in result.lower()
        assert "precipitation" in result.lower()


# ── Driving guidance ──────────────────────────────────────────────────────────


class TestDrivingVisibility:
    def test_near_zero(self):
        result = _driving_from_conditions(0.1, None, None, 50, None, None)
        assert result is not None
        assert "near-zero visibility" in result.lower()

    def test_very_low(self):
        result = _driving_from_conditions(0.5, None, None, 50, None, None)
        assert result is not None
        assert "very low visibility" in result.lower()

    def test_reduced(self):
        result = _driving_from_conditions(2.0, None, None, 50, None, None)
        assert result is not None
        assert "reduced visibility" in result.lower()

    def test_good_visibility_no_mention(self):
        result = _driving_from_conditions(10.0, None, None, 50, None, None)
        assert result is not None
        assert "visibility" not in result.lower()

    def test_boundary_exactly_025(self):
        # 0.25 is not < 0.25, so should be "very low" (< 1.0)
        result = _driving_from_conditions(0.25, None, None, 50, None, None)
        assert result is not None
        assert "very low visibility" in result.lower()

    def test_boundary_exactly_1(self):
        # 1.0 is not < 1.0, so should be "reduced" (< 3.0)
        result = _driving_from_conditions(1.0, None, None, 50, None, None)
        assert result is not None
        assert "reduced visibility" in result.lower()

    def test_boundary_exactly_3(self):
        # 3.0 is not < 3.0, so no visibility warning
        result = _driving_from_conditions(3.0, None, None, 50, None, None)
        assert result is not None
        assert "visibility" not in result.lower()


class TestDrivingPrecipitationType:
    def test_ice_from_precip_list(self):
        result = _driving_from_conditions(None, None, None, 30, None, ["ice"])
        assert result is not None
        assert "ice" in result.lower()

    def test_freezing_rain_from_condition(self):
        result = _driving_from_conditions(None, None, None, 30, "Freezing Rain", None)
        assert result is not None
        assert "ice" in result.lower()

    def test_sleet_from_condition(self):
        result = _driving_from_conditions(None, None, None, 30, "Sleet", None)
        assert result is not None
        assert "ice" in result.lower()

    def test_snow_from_precip_list(self):
        result = _driving_from_conditions(None, None, None, 28, None, ["snow"])
        assert result is not None
        assert "snow" in result.lower()

    def test_blizzard_from_condition(self):
        result = _driving_from_conditions(None, None, None, 20, "Blizzard", None)
        assert result is not None
        assert "snow" in result.lower()

    def test_thunderstorm_from_condition(self):
        result = _driving_from_conditions(None, None, None, 65, "Thunderstorm", None)
        assert result is not None
        assert "thunderstorm" in result.lower()

    def test_rain_from_condition(self):
        result = _driving_from_conditions(None, None, None, 55, "Light Rain", None)
        assert result is not None
        assert "wet roads" in result.lower()

    def test_drizzle_from_condition(self):
        result = _driving_from_conditions(None, None, None, 55, "Drizzle", None)
        assert result is not None
        assert "wet roads" in result.lower()

    def test_ice_takes_priority_over_snow(self):
        # Both ice and snow keywords: ice should win
        result = _driving_from_conditions(None, None, None, 28, "Freezing Snow", None)
        assert result is not None
        assert "ice" in result.lower()

    def test_snow_takes_priority_over_thunder(self):
        result = _driving_from_conditions(None, None, None, 28, "Snow Storm", None)
        assert result is not None
        assert "snow" in result.lower()


class TestDrivingBlackIce:
    def test_near_freezing_with_cloudy_triggers_warning(self):
        result = _driving_from_conditions(None, None, None, 32, "Overcast", None)
        assert result is not None
        assert "black ice" in result.lower()

    def test_near_freezing_with_fog_triggers_warning(self):
        result = _driving_from_conditions(None, None, None, 30, "Foggy", None)
        assert result is not None
        assert "black ice" in result.lower()

    def test_near_freezing_clear_no_warning(self):
        result = _driving_from_conditions(None, None, None, 32, "Sunny", None)
        # Clear/sunny has no moisture keywords, should not trigger black ice
        assert result is not None
        assert "black ice" not in result.lower()

    def test_warm_temp_no_ice_warning(self):
        result = _driving_from_conditions(None, None, None, 60, "Rain", None)
        assert result is not None
        assert "black ice" not in result.lower()

    def test_too_cold_no_black_ice_warning(self):
        # Below 25°F → outside the near-freezing band
        result = _driving_from_conditions(None, None, None, 10, "Cloudy", None)
        assert result is not None
        assert "black ice" not in result.lower()

    def test_ice_already_present_no_duplicate(self):
        # Freezing rain already triggers ice warning; black ice should not be duplicated
        result = _driving_from_conditions(None, None, None, 32, "Freezing Rain Overcast", None)
        assert result is not None
        assert result.count("ice") == 1 or "near-freezing" not in result.lower()


class TestDrivingWind:
    def test_dangerous_wind(self):
        result = _driving_from_conditions(None, 50, None, 60, None, None)
        assert result is not None
        assert "dangerous winds" in result.lower()

    def test_high_wind(self):
        result = _driving_from_conditions(None, 35, None, 60, None, None)
        assert result is not None
        assert "high winds" in result.lower()

    def test_gusty_wind(self):
        result = _driving_from_conditions(None, 22, None, 60, None, None)
        assert result is not None
        assert "gusty winds" in result.lower()

    def test_calm_wind_no_mention(self):
        result = _driving_from_conditions(None, 10, None, 60, None, None)
        assert result is not None
        assert "wind" not in result.lower()

    def test_gust_used_when_higher_than_sustained(self):
        # sustained = 10 mph, gust = 50 mph → should trigger dangerous
        result = _driving_from_conditions(None, 10, 50, 60, None, None)
        assert result is not None
        assert "dangerous winds" in result.lower()

    def test_boundary_exactly_45(self):
        result = _driving_from_conditions(None, 45, None, 60, None, None)
        assert result is not None
        assert "dangerous winds" in result.lower()

    def test_boundary_exactly_30(self):
        result = _driving_from_conditions(None, 30, None, 60, None, None)
        assert result is not None
        assert "high winds" in result.lower()

    def test_boundary_exactly_20(self):
        result = _driving_from_conditions(None, 20, None, 60, None, None)
        assert result is not None
        assert "gusty winds" in result.lower()

    def test_none_wind_no_mention(self):
        result = _driving_from_conditions(None, None, None, 60, None, None)
        assert result is not None
        assert "wind" not in result.lower()


class TestDrivingNormalConditions:
    def test_no_hazards_returns_normal(self):
        result = _driving_from_conditions(10.0, 5.0, None, 65, "Sunny", None)
        assert result == "Normal driving conditions"

    def test_all_none_returns_normal(self):
        result = _driving_from_conditions(None, None, None, None, None, None)
        assert result == "Normal driving conditions"

    def test_caution_prefix_when_issues(self):
        result = _driving_from_conditions(0.1, None, None, 50, None, None)
        assert result is not None
        assert result.startswith("Caution:")


class TestDrivingMultipleIssues:
    def test_visibility_and_wind_combined(self):
        result = _driving_from_conditions(0.5, 50, None, 65, None, None)
        assert result is not None
        assert "very low visibility" in result.lower()
        assert "dangerous winds" in result.lower()

    def test_ice_and_wind_combined(self):
        result = _driving_from_conditions(None, 35, None, 30, "Freezing Rain", None)
        assert result is not None
        assert "ice" in result.lower()
        assert "high winds" in result.lower()


# ── Allergy guidance ──────────────────────────────────────────────────────────


class TestAllergyPollenCategory:
    @pytest.mark.parametrize(
        "category, fragment",
        [
            ("Extreme", "very high pollen"),
            ("Very High", "very high pollen"),
            ("High", "high pollen"),
            ("Moderate", "moderate pollen"),
            ("Low", "low pollen"),
            ("Very Low", "low pollen"),
        ],
    )
    def test_pollen_categories(self, category, fragment):
        result = _allergy_from_conditions(None, category, None, None, None)
        assert result is not None
        assert fragment in result.lower()

    def test_none_category_returns_none_when_no_index(self):
        result = _allergy_from_conditions(None, None, None, None, None)
        assert result is None

    def test_allergen_name_appended(self):
        result = _allergy_from_conditions(None, "High", "Oak", None, None)
        assert result is not None
        assert "oak" in result.lower()

    def test_allergen_appended_to_very_high(self):
        result = _allergy_from_conditions(None, "Very High", "Grass", None, None)
        assert result is not None
        assert "grass" in result.lower()

    def test_allergen_appended_to_moderate(self):
        result = _allergy_from_conditions(None, "Moderate", "Ragweed", None, None)
        assert result is not None
        assert "ragweed" in result.lower()

    def test_none_pollen_category_no_allergen_note(self):
        # No pollen data at all → returns None
        result = _allergy_from_conditions(None, None, "Oak", None, None)
        assert result is None


class TestAllergyWindDispersion:
    def test_moderate_pollen_with_wind_adds_note(self):
        result = _allergy_from_conditions(None, "Moderate", None, 20, None)
        assert result is not None
        assert "wind" in result.lower()

    def test_high_pollen_with_wind_adds_note(self):
        result = _allergy_from_conditions(None, "High", None, 20, None)
        assert result is not None
        assert "wind" in result.lower()

    def test_low_pollen_wind_no_dispersion_note(self):
        result = _allergy_from_conditions(None, "Low", None, 25, None)
        assert result is not None
        assert "wind" not in result.lower()

    def test_calm_wind_no_dispersion_note(self):
        result = _allergy_from_conditions(None, "High", None, 10, None)
        assert result is not None
        assert "wind" not in result.lower()

    def test_boundary_exactly_15mph_triggers_note(self):
        result = _allergy_from_conditions(None, "High", None, 15, None)
        assert result is not None
        assert "wind" in result.lower()

    def test_wind_14mph_no_dispersion(self):
        result = _allergy_from_conditions(None, "High", None, 14, None)
        assert result is not None
        assert "wind" not in result.lower()


class TestAllergyAirQuality:
    def test_unhealthy_aq_adds_note(self):
        result = _allergy_from_conditions(None, None, None, None, "Unhealthy")
        assert result is not None
        assert "limit outdoor exposure" in result.lower()

    def test_very_unhealthy_aq_adds_note(self):
        result = _allergy_from_conditions(None, None, None, None, "Very Unhealthy")
        assert result is not None
        assert "limit outdoor exposure" in result.lower()

    def test_hazardous_aq_adds_note(self):
        result = _allergy_from_conditions(None, None, None, None, "Hazardous")
        assert result is not None
        assert "limit outdoor exposure" in result.lower()

    def test_sensitive_groups_aq_adds_note(self):
        result = _allergy_from_conditions(None, None, None, None, "Unhealthy for Sensitive Groups")
        assert result is not None
        assert "sensitive groups" in result.lower()

    def test_good_aq_no_note(self):
        result = _allergy_from_conditions(None, None, None, None, "Good")
        assert result is None

    def test_moderate_aq_no_note(self):
        result = _allergy_from_conditions(None, None, None, None, "Moderate")
        assert result is None

    def test_pollen_and_bad_aq_combined(self):
        result = _allergy_from_conditions(None, "High", None, None, "Unhealthy")
        assert result is not None
        assert "high pollen" in result.lower()
        assert "limit outdoor exposure" in result.lower()


class TestAllergyPollenIndexFallback:
    def test_high_pollen_index(self):
        result = _allergy_from_conditions(12.0, None, None, None, None)
        assert result is not None
        assert "high pollen index" in result.lower()

    def test_moderate_pollen_index(self):
        result = _allergy_from_conditions(7.0, None, None, None, None)
        assert result is not None
        assert "moderate" in result.lower()

    def test_low_pollen_index(self):
        result = _allergy_from_conditions(2.0, None, None, None, None)
        assert result is not None
        assert "low" in result.lower()

    def test_boundary_exactly_10(self):
        result = _allergy_from_conditions(10.0, None, None, None, None)
        assert result is not None
        assert "high pollen index" in result.lower()

    def test_boundary_exactly_5(self):
        result = _allergy_from_conditions(5.0, None, None, None, None)
        assert result is not None
        assert "moderate" in result.lower()

    def test_category_takes_priority_over_index(self):
        # When both category and index given, category should dominate
        result = _allergy_from_conditions(15.0, "Low", None, None, None)
        assert result is not None
        assert "low pollen" in result.lower()


# ── build_impact_summary ──────────────────────────────────────────────────────


class TestBuildImpactSummary:
    def test_none_current_returns_empty(self):
        result = build_impact_summary(None)
        assert not result.has_content()

    def test_all_fields_populated(self):
        current = CurrentConditions(
            temperature_f=72.0,
            feels_like_f=72.0,
            condition="Sunny",
            wind_speed_mph=5.0,
            visibility_miles=10.0,
            uv_index=3.0,
        )
        env = EnvironmentalConditions(
            pollen_index=8.0,
            pollen_category="High",
            pollen_primary_allergen="Grass",
            air_quality_category="Good",
        )
        result = build_impact_summary(current, env)
        assert result.outdoor is not None
        assert result.driving is not None
        assert result.allergy is not None

    def test_outdoor_only_when_no_env(self):
        current = CurrentConditions(
            temperature_f=72.0,
            feels_like_f=72.0,
            condition="Sunny",
        )
        result = build_impact_summary(current)
        assert result.outdoor is not None
        assert result.allergy is None

    def test_driving_caution_icy(self):
        current = CurrentConditions(
            temperature_f=30.0,
            condition="Freezing Rain",
            wind_speed_mph=5.0,
            visibility_miles=5.0,
        )
        result = build_impact_summary(current)
        assert result.driving is not None
        assert "ice" in result.driving.lower()

    def test_allergy_high_pollen_with_wind(self):
        current = CurrentConditions(
            temperature_f=75.0,
            wind_speed_mph=20.0,
        )
        env = EnvironmentalConditions(pollen_category="High")
        result = build_impact_summary(current, env)
        assert result.allergy is not None
        assert "high pollen" in result.allergy.lower()
        assert "wind" in result.allergy.lower()

    def test_no_env_no_allergy(self):
        current = CurrentConditions(temperature_f=70.0)
        result = build_impact_summary(current)
        assert result.allergy is None

    def test_returns_impact_summary_type(self):
        current = CurrentConditions(temperature_f=70.0)
        result = build_impact_summary(current)
        assert isinstance(result, ImpactSummary)


# ── build_forecast_impact_summary ────────────────────────────────────────────


class TestBuildForecastImpactSummary:
    def test_basic_warm_sunny(self):
        period = ForecastPeriod(
            name="Today",
            temperature=75,
            temperature_unit="F",
            short_forecast="Sunny",
            wind_speed="10 mph",
        )
        result = build_forecast_impact_summary(period)
        assert result.outdoor is not None
        assert "warm" in result.outdoor.lower() or "comfortable" in result.outdoor.lower()
        assert result.driving == "Normal driving conditions"

    def test_snowy_period(self):
        period = ForecastPeriod(
            name="Tomorrow",
            temperature=28,
            temperature_unit="F",
            short_forecast="Heavy Snow",
            wind_speed="20 mph",
        )
        result = build_forecast_impact_summary(period)
        assert result.driving is not None
        assert "snow" in result.driving.lower()

    def test_wind_range_uses_max(self):
        period = ForecastPeriod(
            name="Tonight",
            temperature=50,
            temperature_unit="F",
            short_forecast="Windy",
            wind_speed="20 to 35 mph",
        )
        result = build_forecast_impact_summary(period)
        assert result.driving is not None
        assert "high winds" in result.driving.lower()

    def test_celsius_temperature_converted(self):
        period = ForecastPeriod(
            name="Today",
            temperature=22,
            temperature_unit="C",  # 71.6 °F → comfortable
            short_forecast="Clear",
        )
        result = build_forecast_impact_summary(period)
        assert result.outdoor is not None
        assert "comfortable" in result.outdoor.lower() or "warm" in result.outdoor.lower()

    def test_pollen_forecast_field(self):
        period = ForecastPeriod(
            name="Today",
            temperature=75,
            temperature_unit="F",
            short_forecast="Sunny",
            pollen_forecast="High",
        )
        result = build_forecast_impact_summary(period)
        assert result.allergy is not None
        assert "high pollen" in result.allergy.lower()

    def test_no_temperature_outdoor_none(self):
        period = ForecastPeriod(
            name="Unknown",
            temperature=None,
            short_forecast="Partly Cloudy",
        )
        result = build_forecast_impact_summary(period)
        assert result.outdoor is None

    def test_cold_snowy_period_outdoor_cold(self):
        period = ForecastPeriod(
            name="Tonight",
            temperature=20,
            temperature_unit="F",
            short_forecast="Snow",
            wind_speed="5 mph",
        )
        result = build_forecast_impact_summary(period)
        assert result.outdoor is not None
        assert "very cold" in result.outdoor.lower()
        assert result.driving is not None
        assert "snow" in result.driving.lower()

    def test_dangerous_wind_forecast(self):
        period = ForecastPeriod(
            name="Tomorrow",
            temperature=60,
            temperature_unit="F",
            short_forecast="Windy",
            wind_speed="50 mph",
        )
        result = build_forecast_impact_summary(period)
        assert result.driving is not None
        assert "dangerous winds" in result.driving.lower()

    def test_returns_impact_summary_type(self):
        period = ForecastPeriod(
            name="Today",
            temperature=70,
            temperature_unit="F",
            short_forecast="Clear",
        )
        result = build_forecast_impact_summary(period)
        assert isinstance(result, ImpactSummary)


# ── Integration: metrics appear in CurrentConditionsPresentation ──────────────


class TestImpactMetricsInPresentation:
    """Verify that impact metrics are wired into the presentation builder."""

    def test_impact_metrics_in_current_conditions(self):
        from accessiweather.display.presentation.current_conditions import build_current_conditions
        from accessiweather.models.weather import CurrentConditions, Location
        from accessiweather.utils import TemperatureUnit

        current = CurrentConditions(
            temperature_f=72.0,
            feels_like_f=72.0,
            condition="Sunny",
            wind_speed_mph=5.0,
            visibility_miles=10.0,
        )
        location = Location(name="Test City", latitude=40.0, longitude=-74.0)
        presentation = build_current_conditions(current, location, TemperatureUnit.FAHRENHEIT)

        metric_labels = [m.label for m in presentation.metrics]
        assert "Impact: Outdoor" in metric_labels
        assert "Impact: Driving" in metric_labels

    def test_impact_summary_attached_to_presentation(self):
        from accessiweather.display.presentation.current_conditions import build_current_conditions
        from accessiweather.models.weather import CurrentConditions, Location
        from accessiweather.utils import TemperatureUnit

        current = CurrentConditions(
            temperature_f=72.0,
            feels_like_f=72.0,
            condition="Sunny",
        )
        location = Location(name="Test City", latitude=40.0, longitude=-74.0)
        presentation = build_current_conditions(current, location, TemperatureUnit.FAHRENHEIT)

        assert presentation.impact_summary is not None
        assert presentation.impact_summary.outdoor is not None

    def test_impact_summary_in_fallback_text(self):
        from accessiweather.display.presentation.current_conditions import build_current_conditions
        from accessiweather.models.weather import CurrentConditions, Location
        from accessiweather.utils import TemperatureUnit

        current = CurrentConditions(
            temperature_f=72.0,
            feels_like_f=72.0,
            condition="Sunny",
        )
        location = Location(name="Test City", latitude=40.0, longitude=-74.0)
        presentation = build_current_conditions(current, location, TemperatureUnit.FAHRENHEIT)

        assert "Impact: Outdoor" in presentation.fallback_text

    def test_allergy_metric_present_with_env_data(self):
        from accessiweather.display.presentation.current_conditions import build_current_conditions
        from accessiweather.models.weather import (
            CurrentConditions,
            EnvironmentalConditions,
            Location,
        )
        from accessiweather.utils import TemperatureUnit

        current = CurrentConditions(
            temperature_f=72.0,
            feels_like_f=72.0,
            condition="Sunny",
            wind_speed_mph=5.0,
        )
        env = EnvironmentalConditions(pollen_category="High")
        location = Location(name="Test City", latitude=40.0, longitude=-74.0)
        presentation = build_current_conditions(
            current, location, TemperatureUnit.FAHRENHEIT, environmental=env
        )

        metric_labels = [m.label for m in presentation.metrics]
        assert "Impact: Allergy" in metric_labels

    def test_no_allergy_metric_without_env_data(self):
        from accessiweather.display.presentation.current_conditions import build_current_conditions
        from accessiweather.models.weather import CurrentConditions, Location
        from accessiweather.utils import TemperatureUnit

        current = CurrentConditions(
            temperature_f=72.0,
            feels_like_f=72.0,
            condition="Sunny",
        )
        location = Location(name="Test City", latitude=40.0, longitude=-74.0)
        presentation = build_current_conditions(current, location, TemperatureUnit.FAHRENHEIT)

        metric_labels = [m.label for m in presentation.metrics]
        assert "Impact: Allergy" not in metric_labels


class TestImpactMetricsInForecastPresentation:
    """Verify that forecast impact summary is populated in ForecastPresentation."""

    def test_forecast_impact_summary_attached(self):
        from datetime import UTC, datetime

        from accessiweather.display.presentation.forecast import build_forecast
        from accessiweather.models.weather import Forecast, ForecastPeriod, Location
        from accessiweather.utils import TemperatureUnit

        forecast = Forecast(
            periods=[
                ForecastPeriod(
                    name="Today",
                    temperature=75,
                    temperature_unit="F",
                    short_forecast="Sunny",
                    wind_speed="10 mph",
                )
            ],
            generated_at=datetime.now(UTC),
        )
        location = Location(name="Test City", latitude=40.0, longitude=-74.0, country_code="US")
        presentation = build_forecast(forecast, None, location, TemperatureUnit.FAHRENHEIT)

        assert presentation.impact_summary is not None
        assert presentation.impact_summary.outdoor is not None

    def test_forecast_impact_summary_none_when_no_periods(self):
        from datetime import UTC, datetime

        from accessiweather.display.presentation.forecast import build_forecast
        from accessiweather.models.weather import Forecast, Location
        from accessiweather.utils import TemperatureUnit

        forecast = Forecast(
            periods=[],
            generated_at=datetime.now(UTC),
        )
        location = Location(name="Test City", latitude=40.0, longitude=-74.0, country_code="US")
        presentation = build_forecast(forecast, None, location, TemperatureUnit.FAHRENHEIT)

        assert presentation.impact_summary is None

    def test_forecast_impact_driving_icy(self):
        from datetime import UTC, datetime

        from accessiweather.display.presentation.forecast import build_forecast
        from accessiweather.models.weather import Forecast, ForecastPeriod, Location
        from accessiweather.utils import TemperatureUnit

        forecast = Forecast(
            periods=[
                ForecastPeriod(
                    name="Tomorrow",
                    temperature=28,
                    temperature_unit="F",
                    short_forecast="Freezing Rain",
                    wind_speed="10 mph",
                )
            ],
            generated_at=datetime.now(UTC),
        )
        location = Location(name="Test City", latitude=40.0, longitude=-74.0, country_code="US")
        presentation = build_forecast(forecast, None, location, TemperatureUnit.FAHRENHEIT)

        assert presentation.impact_summary is not None
        assert presentation.impact_summary.driving is not None
        assert "ice" in presentation.impact_summary.driving.lower()
