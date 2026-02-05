"""Tests for WeatherConditionAnalyzer."""

from accessiweather.weather_condition_analyzer import (
    ConditionCategory,
    WeatherConditionAnalyzer,
    WeatherSeverity,
)


class TestWeatherCodeAnalysis:
    """Test weather code to category/severity mapping."""

    def test_clear_weather_codes(self):
        """Clear sky codes map to CLEAR category with NORMAL severity."""
        analyzer = WeatherConditionAnalyzer()

        for code in [0, 1]:
            result = analyzer.analyze_weather_conditions({"weather_code": code})
            assert result["category"] == ConditionCategory.CLEAR
            assert result["severity"] == WeatherSeverity.NORMAL

    def test_cloudy_weather_codes(self):
        """Cloudy codes map to CLOUDY category."""
        analyzer = WeatherConditionAnalyzer()

        for code in [2, 3]:
            result = analyzer.analyze_weather_conditions({"weather_code": code})
            assert result["category"] == ConditionCategory.CLOUDY
            assert result["severity"] == WeatherSeverity.NORMAL

    def test_fog_weather_codes(self):
        """Fog codes map to FOG category with appropriate severity."""
        analyzer = WeatherConditionAnalyzer()

        result = analyzer.analyze_weather_conditions({"weather_code": 45})
        assert result["category"] == ConditionCategory.FOG
        assert result["severity"] == WeatherSeverity.MINOR

        result = analyzer.analyze_weather_conditions({"weather_code": 48})
        assert result["category"] == ConditionCategory.FOG
        assert result["severity"] == WeatherSeverity.MODERATE

    def test_drizzle_weather_codes(self):
        """Drizzle codes map to PRECIPITATION category."""
        analyzer = WeatherConditionAnalyzer()

        result = analyzer.analyze_weather_conditions({"weather_code": 51})
        assert result["category"] == ConditionCategory.PRECIPITATION
        assert result["severity"] == WeatherSeverity.MINOR

        result = analyzer.analyze_weather_conditions({"weather_code": 55})
        assert result["category"] == ConditionCategory.PRECIPITATION
        assert result["severity"] == WeatherSeverity.MODERATE

    def test_freezing_drizzle_codes(self):
        """Freezing drizzle codes map to FREEZING category."""
        analyzer = WeatherConditionAnalyzer()

        result = analyzer.analyze_weather_conditions({"weather_code": 56})
        assert result["category"] == ConditionCategory.FREEZING
        assert result["severity"] == WeatherSeverity.MODERATE

        result = analyzer.analyze_weather_conditions({"weather_code": 57})
        assert result["category"] == ConditionCategory.FREEZING
        assert result["severity"] == WeatherSeverity.SEVERE

    def test_rain_weather_codes(self):
        """Rain codes map to PRECIPITATION with increasing severity."""
        analyzer = WeatherConditionAnalyzer()

        result = analyzer.analyze_weather_conditions({"weather_code": 61})
        assert result["category"] == ConditionCategory.PRECIPITATION
        assert result["severity"] == WeatherSeverity.MINOR

        result = analyzer.analyze_weather_conditions({"weather_code": 63})
        assert result["severity"] == WeatherSeverity.MODERATE

        result = analyzer.analyze_weather_conditions({"weather_code": 65})
        assert result["severity"] == WeatherSeverity.SEVERE

    def test_freezing_rain_codes(self):
        """Freezing rain codes map to FREEZING with high severity."""
        analyzer = WeatherConditionAnalyzer()

        result = analyzer.analyze_weather_conditions({"weather_code": 66})
        assert result["category"] == ConditionCategory.FREEZING
        assert result["severity"] == WeatherSeverity.SEVERE

        result = analyzer.analyze_weather_conditions({"weather_code": 67})
        assert result["severity"] == WeatherSeverity.EXTREME

    def test_snow_weather_codes(self):
        """Snow codes map to PRECIPITATION with varying severity."""
        analyzer = WeatherConditionAnalyzer()

        result = analyzer.analyze_weather_conditions({"weather_code": 71})
        assert result["category"] == ConditionCategory.PRECIPITATION
        assert result["severity"] == WeatherSeverity.MODERATE

        result = analyzer.analyze_weather_conditions({"weather_code": 75})
        assert result["severity"] == WeatherSeverity.EXTREME

        # Snow grains
        result = analyzer.analyze_weather_conditions({"weather_code": 77})
        assert result["severity"] == WeatherSeverity.MINOR

    def test_thunderstorm_codes(self):
        """Thunderstorm codes map to THUNDERSTORM with high severity."""
        analyzer = WeatherConditionAnalyzer()

        result = analyzer.analyze_weather_conditions({"weather_code": 95})
        assert result["category"] == ConditionCategory.THUNDERSTORM
        assert result["severity"] == WeatherSeverity.SEVERE

        for code in [96, 99]:
            result = analyzer.analyze_weather_conditions({"weather_code": code})
            assert result["category"] == ConditionCategory.THUNDERSTORM
            assert result["severity"] == WeatherSeverity.EXTREME

    def test_unknown_weather_code_defaults_to_clear(self):
        """Unknown weather codes default to CLEAR with NORMAL severity."""
        analyzer = WeatherConditionAnalyzer()

        result = analyzer.analyze_weather_conditions({"weather_code": 999})
        assert result["category"] == ConditionCategory.CLEAR
        assert result["severity"] == WeatherSeverity.NORMAL

    def test_weather_code_as_list(self):
        """Weather code provided as list uses first element."""
        analyzer = WeatherConditionAnalyzer()

        result = analyzer.analyze_weather_conditions({"weather_code": [95, 0]})
        assert result["category"] == ConditionCategory.THUNDERSTORM
        assert result["severity"] == WeatherSeverity.SEVERE

    def test_weather_code_as_tuple(self):
        """Weather code provided as tuple uses first element."""
        analyzer = WeatherConditionAnalyzer()

        result = analyzer.analyze_weather_conditions({"weather_code": (45, 0)})
        assert result["category"] == ConditionCategory.FOG


class TestTemperatureAnalysis:
    """Test temperature extreme detection."""

    def test_extreme_cold(self):
        """Temperatures at or below 0F are extreme cold."""
        analyzer = WeatherConditionAnalyzer()

        result = analyzer.analyze_weather_conditions({"weather_code": 0, "temp": -10})
        assert result["temperature_extreme"] == "extreme_cold"

        result = analyzer.analyze_weather_conditions({"weather_code": 0, "temp": 0})
        assert result["temperature_extreme"] == "extreme_cold"

    def test_very_cold(self):
        """Temperatures between 1-20F are very cold."""
        analyzer = WeatherConditionAnalyzer()

        result = analyzer.analyze_weather_conditions({"weather_code": 0, "temp": 10})
        assert result["temperature_extreme"] == "very_cold"

        result = analyzer.analyze_weather_conditions({"weather_code": 0, "temp": 20})
        assert result["temperature_extreme"] == "very_cold"

    def test_cold(self):
        """Temperatures between 21-32F are cold."""
        analyzer = WeatherConditionAnalyzer()

        result = analyzer.analyze_weather_conditions({"weather_code": 0, "temp": 25})
        assert result["temperature_extreme"] == "cold"

        result = analyzer.analyze_weather_conditions({"weather_code": 0, "temp": 32})
        assert result["temperature_extreme"] == "cold"

    def test_hot(self):
        """Temperatures between 90-99F are hot."""
        analyzer = WeatherConditionAnalyzer()

        result = analyzer.analyze_weather_conditions({"weather_code": 0, "temp": 92})
        assert result["temperature_extreme"] == "hot"

    def test_very_hot(self):
        """Temperatures between 100-109F are very hot."""
        analyzer = WeatherConditionAnalyzer()

        result = analyzer.analyze_weather_conditions({"weather_code": 0, "temp": 105})
        assert result["temperature_extreme"] == "very_hot"

    def test_extreme_hot(self):
        """Temperatures at or above 110F are extreme hot."""
        analyzer = WeatherConditionAnalyzer()

        result = analyzer.analyze_weather_conditions({"weather_code": 0, "temp": 115})
        assert result["temperature_extreme"] == "extreme_hot"

    def test_normal_temperature(self):
        """Normal temperatures (33-89F) have no extreme."""
        analyzer = WeatherConditionAnalyzer()

        result = analyzer.analyze_weather_conditions({"weather_code": 0, "temp": 70})
        assert result["temperature_extreme"] is None

    def test_temp_f_alternative_key(self):
        """Temperature can be provided as temp_f."""
        analyzer = WeatherConditionAnalyzer()

        result = analyzer.analyze_weather_conditions({"weather_code": 0, "temp_f": -5})
        assert result["temperature_extreme"] == "extreme_cold"

    def test_no_temperature_provided(self):
        """Missing temperature results in None extreme."""
        analyzer = WeatherConditionAnalyzer()

        result = analyzer.analyze_weather_conditions({"weather_code": 0})
        assert result["temperature_extreme"] is None


class TestWindAnalysis:
    """Test wind condition analysis."""

    def test_calm_wind(self):
        """Wind speeds below 15 mph are calm."""
        analyzer = WeatherConditionAnalyzer()

        result = analyzer.analyze_weather_conditions({"weather_code": 0, "wind_speed": 10})
        assert result["wind_condition"] == "calm"

    def test_light_wind(self):
        """Wind speeds 15-24 mph are light."""
        analyzer = WeatherConditionAnalyzer()

        result = analyzer.analyze_weather_conditions({"weather_code": 0, "wind_speed": 20})
        assert result["wind_condition"] == "light"

    def test_moderate_wind(self):
        """Wind speeds 25-34 mph are moderate."""
        analyzer = WeatherConditionAnalyzer()

        result = analyzer.analyze_weather_conditions({"weather_code": 0, "wind_speed": 30})
        assert result["wind_condition"] == "moderate"

    def test_strong_wind(self):
        """Wind speeds 35-44 mph are strong."""
        analyzer = WeatherConditionAnalyzer()

        result = analyzer.analyze_weather_conditions({"weather_code": 0, "wind_speed": 40})
        assert result["wind_condition"] == "strong"

    def test_very_strong_wind(self):
        """Wind speeds 45-59 mph are very strong."""
        analyzer = WeatherConditionAnalyzer()

        result = analyzer.analyze_weather_conditions({"weather_code": 0, "wind_speed": 50})
        assert result["wind_condition"] == "very_strong"

    def test_extreme_wind(self):
        """Wind speeds 60+ are extreme."""
        analyzer = WeatherConditionAnalyzer()

        result = analyzer.analyze_weather_conditions({"weather_code": 0, "wind_speed": 65})
        assert result["wind_condition"] == "extreme"

    def test_no_wind_provided(self):
        """Missing wind speed results in None condition."""
        analyzer = WeatherConditionAnalyzer()

        result = analyzer.analyze_weather_conditions({"weather_code": 0})
        assert result["wind_condition"] is None


class TestAlertAnalysis:
    """Test weather alert handling."""

    def test_no_alerts(self):
        """No alerts returns appropriate analysis."""
        analyzer = WeatherConditionAnalyzer()

        result = analyzer.analyze_weather_conditions({"weather_code": 0}, alerts_data=None)
        assert result["has_alerts"] is False

        result = analyzer.analyze_weather_conditions({"weather_code": 0}, alerts_data=[])
        assert result["has_alerts"] is False

    def test_alert_takes_priority(self):
        """Alerts have highest priority and return immediately."""
        analyzer = WeatherConditionAnalyzer()

        alerts = [{"severity": "Moderate", "headline": "Wind Advisory"}]
        result = analyzer.analyze_weather_conditions({"weather_code": 0}, alerts_data=alerts)

        assert result["has_alerts"] is True
        assert result["priority_score"] == 1000
        assert result["recommended_template"] == "alert"

    def test_highest_severity_alert_selected(self):
        """When multiple alerts exist, highest severity is selected."""
        analyzer = WeatherConditionAnalyzer()

        alerts = [
            {"severity": "Minor", "headline": "Wind Advisory"},
            {"severity": "Severe", "headline": "Tornado Warning"},
            {"severity": "Moderate", "headline": "Flood Watch"},
        ]
        result = analyzer.analyze_weather_conditions({"weather_code": 0}, alerts_data=alerts)

        assert result["alert_severity"] == WeatherSeverity.SEVERE
        assert result["primary_alert"]["headline"] == "Tornado Warning"

    def test_extreme_alert_severity(self):
        """Extreme severity alerts are properly mapped."""
        analyzer = WeatherConditionAnalyzer()

        alerts = [{"severity": "Extreme", "headline": "Tsunami Warning"}]
        result = analyzer.analyze_weather_conditions({"weather_code": 0}, alerts_data=alerts)

        assert result["alert_severity"] == WeatherSeverity.EXTREME

    def test_unknown_alert_severity_defaults_to_normal(self):
        """Unknown severity strings default to NORMAL."""
        analyzer = WeatherConditionAnalyzer()

        alerts = [{"severity": "Unknown", "headline": "Test Alert"}]
        result = analyzer.analyze_weather_conditions({"weather_code": 0}, alerts_data=alerts)

        assert result["alert_severity"] == WeatherSeverity.NORMAL


class TestPriorityScoreCalculation:
    """Test priority score calculation."""

    def test_base_score_from_severity(self):
        """Priority score includes base from severity level."""
        analyzer = WeatherConditionAnalyzer()

        # NORMAL severity (0) = base 0
        result = analyzer.analyze_weather_conditions({"weather_code": 0})
        assert result["priority_score"] == 0

        # SEVERE severity (3) = base 30
        result = analyzer.analyze_weather_conditions({"weather_code": 95})
        assert result["priority_score"] >= 30

    def test_temperature_extreme_bonus(self):
        """Temperature extremes add to priority score."""
        analyzer = WeatherConditionAnalyzer()

        # Extreme temperature adds 50
        result = analyzer.analyze_weather_conditions({"weather_code": 0, "temp": -10})
        assert result["priority_score"] >= 50

        # Very cold adds 30
        result = analyzer.analyze_weather_conditions({"weather_code": 0, "temp": 15})
        assert result["priority_score"] >= 30

        # Cold adds 15
        result = analyzer.analyze_weather_conditions({"weather_code": 0, "temp": 30})
        assert result["priority_score"] >= 15

    def test_wind_condition_bonus(self):
        """Wind conditions add to priority score."""
        analyzer = WeatherConditionAnalyzer()

        # Extreme wind adds 40
        result = analyzer.analyze_weather_conditions({"weather_code": 0, "wind_speed": 70})
        assert result["priority_score"] >= 40

        # Very strong wind adds 25
        result = analyzer.analyze_weather_conditions({"weather_code": 0, "wind_speed": 50})
        assert result["priority_score"] >= 25

        # Strong wind adds 15
        result = analyzer.analyze_weather_conditions({"weather_code": 0, "wind_speed": 40})
        assert result["priority_score"] >= 15


class TestTemplateRecommendation:
    """Test recommended template selection."""

    def test_alert_template_for_alerts(self):
        """Alert template is used when alerts are present."""
        analyzer = WeatherConditionAnalyzer()

        alerts = [{"severity": "Minor", "headline": "Test"}]
        result = analyzer.analyze_weather_conditions({"weather_code": 0}, alerts_data=alerts)
        assert result["recommended_template"] == "alert"

    def test_severe_weather_template(self):
        """Severe weather template for SEVERE/EXTREME conditions."""
        analyzer = WeatherConditionAnalyzer()

        # Thunderstorm with hail (code 99) = EXTREME
        result = analyzer.analyze_weather_conditions({"weather_code": 99})
        assert result["recommended_template"] == "severe_weather"

        # Heavy rain (code 65) = SEVERE
        result = analyzer.analyze_weather_conditions({"weather_code": 65})
        assert result["recommended_template"] == "severe_weather"

    def test_temperature_extreme_template(self):
        """Temperature extreme template for extreme/very temperatures."""
        analyzer = WeatherConditionAnalyzer()

        result = analyzer.analyze_weather_conditions({"weather_code": 0, "temp": -10})
        assert result["recommended_template"] == "temperature_extreme"

        result = analyzer.analyze_weather_conditions({"weather_code": 0, "temp": 105})
        assert result["recommended_template"] == "temperature_extreme"

    def test_wind_warning_template(self):
        """Wind warning template for strong+ winds."""
        analyzer = WeatherConditionAnalyzer()

        result = analyzer.analyze_weather_conditions({"weather_code": 0, "wind_speed": 35})
        assert result["recommended_template"] == "wind_warning"

    def test_precipitation_template(self):
        """Precipitation template for rain/snow conditions."""
        analyzer = WeatherConditionAnalyzer()

        # Light rain (not severe)
        result = analyzer.analyze_weather_conditions({"weather_code": 61})
        assert result["recommended_template"] == "precipitation"

        # Freezing drizzle (moderate)
        result = analyzer.analyze_weather_conditions({"weather_code": 56})
        assert result["recommended_template"] == "precipitation"

    def test_fog_template(self):
        """Fog template for fog conditions."""
        analyzer = WeatherConditionAnalyzer()

        result = analyzer.analyze_weather_conditions({"weather_code": 45})
        assert result["recommended_template"] == "fog"

    def test_default_template_for_clear(self):
        """Default template for clear/cloudy conditions."""
        analyzer = WeatherConditionAnalyzer()

        result = analyzer.analyze_weather_conditions({"weather_code": 0})
        assert result["recommended_template"] == "default"

        result = analyzer.analyze_weather_conditions({"weather_code": 3})
        assert result["recommended_template"] == "default"


class TestErrorHandling:
    """Test error handling in analysis."""

    def test_empty_weather_data(self):
        """Empty weather data is handled gracefully."""
        analyzer = WeatherConditionAnalyzer()

        result = analyzer.analyze_weather_conditions({})
        assert result["category"] == ConditionCategory.CLEAR
        assert result["severity"] == WeatherSeverity.NORMAL
        assert result["recommended_template"] == "default"

    def test_invalid_weather_data_returns_error(self):
        """Invalid data that causes exceptions returns error analysis."""
        analyzer = WeatherConditionAnalyzer()

        # This should trigger error handling (weather_code attribute access fails)
        class BadData:
            def get(self, key, default=None):
                raise RuntimeError("Test error")

        result = analyzer.analyze_weather_conditions(BadData())
        assert "error" in result
        assert result["recommended_template"] == "default"


class TestEnumValues:
    """Test enum definitions."""

    def test_weather_severity_ordering(self):
        """WeatherSeverity enum values are correctly ordered."""
        assert WeatherSeverity.NORMAL.value < WeatherSeverity.MINOR.value
        assert WeatherSeverity.MINOR.value < WeatherSeverity.MODERATE.value
        assert WeatherSeverity.MODERATE.value < WeatherSeverity.SEVERE.value
        assert WeatherSeverity.SEVERE.value < WeatherSeverity.EXTREME.value

    def test_condition_category_values(self):
        """ConditionCategory enum has expected values."""
        assert ConditionCategory.CLEAR.value == "clear"
        assert ConditionCategory.THUNDERSTORM.value == "thunderstorm"
