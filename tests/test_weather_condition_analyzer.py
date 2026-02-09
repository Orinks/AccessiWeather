"""
Tests for weather_condition_analyzer module.

Covers:
- WEATHER_CODE_MAPPING for different weather codes
- Temperature threshold analysis
- Wind speed threshold analysis
- Format string template generation
- Severity and category classification
- Alert analysis
- Priority score calculation
"""

from accessiweather.weather_condition_analyzer import (
    ConditionCategory,
    WeatherConditionAnalyzer,
    WeatherSeverity,
)


class TestWeatherCodeMapping:
    """Test WEATHER_CODE_MAPPING coverage."""

    def test_clear_conditions(self):
        """Clear/sunny codes map to CLEAR category with NORMAL severity."""
        analyzer = WeatherConditionAnalyzer()

        for code in [0, 1]:
            category, severity = analyzer.WEATHER_CODE_MAPPING[code]
            assert category == ConditionCategory.CLEAR
            assert severity == WeatherSeverity.NORMAL

    def test_cloudy_conditions(self):
        """Cloudy codes map to CLOUDY category with NORMAL severity."""
        analyzer = WeatherConditionAnalyzer()

        for code in [2, 3]:
            category, severity = analyzer.WEATHER_CODE_MAPPING[code]
            assert category == ConditionCategory.CLOUDY
            assert severity == WeatherSeverity.NORMAL

    def test_fog_conditions(self):
        """Fog codes map to FOG category with varying severity."""
        analyzer = WeatherConditionAnalyzer()

        cat, sev = analyzer.WEATHER_CODE_MAPPING[45]
        assert cat == ConditionCategory.FOG
        assert sev == WeatherSeverity.MINOR

        cat, sev = analyzer.WEATHER_CODE_MAPPING[48]
        assert cat == ConditionCategory.FOG
        assert sev == WeatherSeverity.MODERATE

    def test_drizzle_conditions(self):
        """Drizzle codes map to PRECIPITATION category."""
        analyzer = WeatherConditionAnalyzer()

        for code in [51, 53]:
            cat, sev = analyzer.WEATHER_CODE_MAPPING[code]
            assert cat == ConditionCategory.PRECIPITATION
            assert sev == WeatherSeverity.MINOR

        cat, sev = analyzer.WEATHER_CODE_MAPPING[55]
        assert cat == ConditionCategory.PRECIPITATION
        assert sev == WeatherSeverity.MODERATE

    def test_freezing_drizzle_conditions(self):
        """Freezing drizzle codes map to FREEZING category."""
        analyzer = WeatherConditionAnalyzer()

        cat, sev = analyzer.WEATHER_CODE_MAPPING[56]
        assert cat == ConditionCategory.FREEZING
        assert sev == WeatherSeverity.MODERATE

        cat, sev = analyzer.WEATHER_CODE_MAPPING[57]
        assert cat == ConditionCategory.FREEZING
        assert sev == WeatherSeverity.SEVERE

    def test_rain_conditions(self):
        """Rain codes map to PRECIPITATION with varying severity."""
        analyzer = WeatherConditionAnalyzer()

        cat, sev = analyzer.WEATHER_CODE_MAPPING[61]
        assert cat == ConditionCategory.PRECIPITATION
        assert sev == WeatherSeverity.MINOR

        cat, sev = analyzer.WEATHER_CODE_MAPPING[63]
        assert cat == ConditionCategory.PRECIPITATION
        assert sev == WeatherSeverity.MODERATE

        cat, sev = analyzer.WEATHER_CODE_MAPPING[65]
        assert cat == ConditionCategory.PRECIPITATION
        assert sev == WeatherSeverity.SEVERE

    def test_freezing_rain_conditions(self):
        """Freezing rain codes map to FREEZING with high severity."""
        analyzer = WeatherConditionAnalyzer()

        cat, sev = analyzer.WEATHER_CODE_MAPPING[66]
        assert cat == ConditionCategory.FREEZING
        assert sev == WeatherSeverity.SEVERE

        cat, sev = analyzer.WEATHER_CODE_MAPPING[67]
        assert cat == ConditionCategory.FREEZING
        assert sev == WeatherSeverity.EXTREME

    def test_snow_conditions(self):
        """Snow codes map to PRECIPITATION with varying severity."""
        analyzer = WeatherConditionAnalyzer()

        cat, sev = analyzer.WEATHER_CODE_MAPPING[71]
        assert cat == ConditionCategory.PRECIPITATION
        assert sev == WeatherSeverity.MODERATE

        cat, sev = analyzer.WEATHER_CODE_MAPPING[73]
        assert cat == ConditionCategory.PRECIPITATION
        assert sev == WeatherSeverity.SEVERE

        cat, sev = analyzer.WEATHER_CODE_MAPPING[75]
        assert cat == ConditionCategory.PRECIPITATION
        assert sev == WeatherSeverity.EXTREME

        cat, sev = analyzer.WEATHER_CODE_MAPPING[77]
        assert cat == ConditionCategory.PRECIPITATION
        assert sev == WeatherSeverity.MINOR

    def test_rain_showers_conditions(self):
        """Rain shower codes map to PRECIPITATION."""
        analyzer = WeatherConditionAnalyzer()

        for code, expected_sev in [
            (80, WeatherSeverity.MINOR),
            (81, WeatherSeverity.MODERATE),
            (82, WeatherSeverity.SEVERE),
        ]:
            cat, sev = analyzer.WEATHER_CODE_MAPPING[code]
            assert cat == ConditionCategory.PRECIPITATION
            assert sev == expected_sev

    def test_snow_showers_conditions(self):
        """Snow shower codes map to PRECIPITATION."""
        analyzer = WeatherConditionAnalyzer()

        cat, sev = analyzer.WEATHER_CODE_MAPPING[85]
        assert cat == ConditionCategory.PRECIPITATION
        assert sev == WeatherSeverity.MODERATE

        cat, sev = analyzer.WEATHER_CODE_MAPPING[86]
        assert cat == ConditionCategory.PRECIPITATION
        assert sev == WeatherSeverity.SEVERE

    def test_thunderstorm_conditions(self):
        """Thunderstorm codes map to THUNDERSTORM with high severity."""
        analyzer = WeatherConditionAnalyzer()

        cat, sev = analyzer.WEATHER_CODE_MAPPING[95]
        assert cat == ConditionCategory.THUNDERSTORM
        assert sev == WeatherSeverity.SEVERE

        for code in [96, 99]:
            cat, sev = analyzer.WEATHER_CODE_MAPPING[code]
            assert cat == ConditionCategory.THUNDERSTORM
            assert sev == WeatherSeverity.EXTREME


class TestTemperatureAnalysis:
    """Test temperature threshold analysis."""

    def test_extreme_cold(self):
        """Temps at or below 0F are extreme cold."""
        analyzer = WeatherConditionAnalyzer()
        result = analyzer._analyze_temperature({"temp": 0})
        assert result["temperature_extreme"] == "extreme_cold"

        result = analyzer._analyze_temperature({"temp": -10})
        assert result["temperature_extreme"] == "extreme_cold"

    def test_very_cold(self):
        """Temps between 1-20F are very cold."""
        analyzer = WeatherConditionAnalyzer()
        result = analyzer._analyze_temperature({"temp": 15})
        assert result["temperature_extreme"] == "very_cold"

        result = analyzer._analyze_temperature({"temp": 20})
        assert result["temperature_extreme"] == "very_cold"

    def test_cold(self):
        """Temps between 21-32F are cold."""
        analyzer = WeatherConditionAnalyzer()
        result = analyzer._analyze_temperature({"temp": 25})
        assert result["temperature_extreme"] == "cold"

        result = analyzer._analyze_temperature({"temp": 32})
        assert result["temperature_extreme"] == "cold"

    def test_normal_temperature(self):
        """Temps between 33-89F have no extreme."""
        analyzer = WeatherConditionAnalyzer()
        result = analyzer._analyze_temperature({"temp": 70})
        assert result["temperature_extreme"] is None

    def test_hot(self):
        """Temps between 90-99F are hot."""
        analyzer = WeatherConditionAnalyzer()
        result = analyzer._analyze_temperature({"temp": 90})
        assert result["temperature_extreme"] == "hot"

        result = analyzer._analyze_temperature({"temp": 95})
        assert result["temperature_extreme"] == "hot"

    def test_very_hot(self):
        """Temps between 100-109F are very hot."""
        analyzer = WeatherConditionAnalyzer()
        result = analyzer._analyze_temperature({"temp": 100})
        assert result["temperature_extreme"] == "very_hot"

        result = analyzer._analyze_temperature({"temp": 105})
        assert result["temperature_extreme"] == "very_hot"

    def test_extreme_hot(self):
        """Temps at or above 110F are extreme hot."""
        analyzer = WeatherConditionAnalyzer()
        result = analyzer._analyze_temperature({"temp": 110})
        assert result["temperature_extreme"] == "extreme_hot"

        result = analyzer._analyze_temperature({"temp": 120})
        assert result["temperature_extreme"] == "extreme_hot"

    def test_temp_f_fallback_key(self):
        """Should use temp_f if temp is not present."""
        analyzer = WeatherConditionAnalyzer()
        result = analyzer._analyze_temperature({"temp_f": -5})
        assert result["temperature_extreme"] == "extreme_cold"

    def test_missing_temperature(self):
        """Should return None for missing temperature."""
        analyzer = WeatherConditionAnalyzer()
        result = analyzer._analyze_temperature({})
        assert result["temperature_extreme"] is None


class TestWindAnalysis:
    """Test wind speed threshold analysis."""

    def test_calm_wind(self):
        """Wind under 5 mph is calm."""
        analyzer = WeatherConditionAnalyzer()
        result = analyzer._analyze_wind({"wind_speed": 3})
        assert result["wind_condition"] == "calm"

    def test_light_wind(self):
        """Wind 15-24 mph is light."""
        analyzer = WeatherConditionAnalyzer()
        result = analyzer._analyze_wind({"wind_speed": 15})
        assert result["wind_condition"] == "light"

    def test_moderate_wind(self):
        """Wind 25-34 mph is moderate."""
        analyzer = WeatherConditionAnalyzer()
        result = analyzer._analyze_wind({"wind_speed": 25})
        assert result["wind_condition"] == "moderate"

    def test_strong_wind(self):
        """Wind 35-44 mph is strong."""
        analyzer = WeatherConditionAnalyzer()
        result = analyzer._analyze_wind({"wind_speed": 35})
        assert result["wind_condition"] == "strong"

    def test_very_strong_wind(self):
        """Wind 45-59 mph is very strong."""
        analyzer = WeatherConditionAnalyzer()
        result = analyzer._analyze_wind({"wind_speed": 50})
        assert result["wind_condition"] == "very_strong"

    def test_extreme_wind(self):
        """Wind 60+ mph is extreme."""
        analyzer = WeatherConditionAnalyzer()
        result = analyzer._analyze_wind({"wind_speed": 70})
        assert result["wind_condition"] == "extreme"

    def test_missing_wind_speed(self):
        """Should return None for missing wind speed."""
        analyzer = WeatherConditionAnalyzer()
        result = analyzer._analyze_wind({})
        assert result["wind_condition"] is None


class TestAlertAnalysis:
    """Test alert severity analysis."""

    def test_no_alerts(self):
        """Should return has_alerts False for empty alerts."""
        analyzer = WeatherConditionAnalyzer()
        result = analyzer._analyze_alerts([])
        assert result["has_alerts"] is False
        assert result["alert_severity"] is None

    def test_single_alert(self):
        """Should analyze single alert correctly."""
        analyzer = WeatherConditionAnalyzer()
        alerts = [{"severity": "Severe", "event": "Tornado Warning"}]
        result = analyzer._analyze_alerts(alerts)

        assert result["has_alerts"] is True
        assert result["alert_severity"] == WeatherSeverity.SEVERE
        assert result["primary_alert"] == alerts[0]

    def test_multiple_alerts_highest_severity(self):
        """Should pick highest severity from multiple alerts."""
        analyzer = WeatherConditionAnalyzer()
        alerts = [
            {"severity": "Minor", "event": "Wind Advisory"},
            {"severity": "Extreme", "event": "Tornado Emergency"},
            {"severity": "Moderate", "event": "Flood Watch"},
        ]
        result = analyzer._analyze_alerts(alerts)

        assert result["alert_severity"] == WeatherSeverity.EXTREME
        assert result["primary_alert"]["event"] == "Tornado Emergency"

    def test_unknown_alert_severity(self):
        """Unknown severity should map to NORMAL."""
        analyzer = WeatherConditionAnalyzer()
        result = analyzer._map_alert_severity("Unknown")
        assert result == WeatherSeverity.NORMAL

    def test_all_alert_severity_mappings(self):
        """Test all alert severity string mappings."""
        analyzer = WeatherConditionAnalyzer()

        assert analyzer._map_alert_severity("Extreme") == WeatherSeverity.EXTREME
        assert analyzer._map_alert_severity("Severe") == WeatherSeverity.SEVERE
        assert analyzer._map_alert_severity("Moderate") == WeatherSeverity.MODERATE
        assert analyzer._map_alert_severity("Minor") == WeatherSeverity.MINOR


class TestPriorityScoreCalculation:
    """Test priority score calculation."""

    def test_base_score_from_severity(self):
        """Severity value * 10 contributes to score."""
        analyzer = WeatherConditionAnalyzer()
        analysis = {
            "severity": WeatherSeverity.SEVERE,  # value = 3
            "temperature_extreme": None,
            "wind_condition": None,
        }
        score = analyzer._calculate_priority_score(analysis)
        assert score == 30  # 3 * 10

    def test_extreme_temperature_bonus(self):
        """Extreme temperatures add 50 points."""
        analyzer = WeatherConditionAnalyzer()
        analysis = {
            "severity": WeatherSeverity.NORMAL,
            "temperature_extreme": "extreme_cold",
            "wind_condition": None,
        }
        score = analyzer._calculate_priority_score(analysis)
        assert score == 50

    def test_very_temperature_bonus(self):
        """Very cold/hot temperatures add 30 points."""
        analyzer = WeatherConditionAnalyzer()
        analysis = {
            "severity": WeatherSeverity.NORMAL,
            "temperature_extreme": "very_hot",
            "wind_condition": None,
        }
        score = analyzer._calculate_priority_score(analysis)
        assert score == 30

    def test_cold_hot_bonus(self):
        """Cold/hot temperatures add 15 points."""
        analyzer = WeatherConditionAnalyzer()
        analysis = {
            "severity": WeatherSeverity.NORMAL,
            "temperature_extreme": "cold",
            "wind_condition": None,
        }
        score = analyzer._calculate_priority_score(analysis)
        assert score == 15

    def test_extreme_wind_bonus(self):
        """Extreme wind adds 40 points."""
        analyzer = WeatherConditionAnalyzer()
        analysis = {
            "severity": WeatherSeverity.NORMAL,
            "temperature_extreme": None,
            "wind_condition": "extreme",
        }
        score = analyzer._calculate_priority_score(analysis)
        assert score == 40

    def test_very_strong_wind_bonus(self):
        """Very strong wind adds 25 points."""
        analyzer = WeatherConditionAnalyzer()
        analysis = {
            "severity": WeatherSeverity.NORMAL,
            "temperature_extreme": None,
            "wind_condition": "very_strong",
        }
        score = analyzer._calculate_priority_score(analysis)
        assert score == 25

    def test_strong_wind_bonus(self):
        """Strong wind adds 15 points."""
        analyzer = WeatherConditionAnalyzer()
        analysis = {
            "severity": WeatherSeverity.NORMAL,
            "temperature_extreme": None,
            "wind_condition": "strong",
        }
        score = analyzer._calculate_priority_score(analysis)
        assert score == 15

    def test_combined_score(self):
        """Multiple factors combine correctly."""
        analyzer = WeatherConditionAnalyzer()
        analysis = {
            "severity": WeatherSeverity.MODERATE,  # 20
            "temperature_extreme": "very_cold",  # 30
            "wind_condition": "strong",  # 15
        }
        score = analyzer._calculate_priority_score(analysis)
        assert score == 65


class TestTemplateGeneration:
    """Test format string template determination."""

    def test_alert_template(self):
        """Alerts should return alert template."""
        analyzer = WeatherConditionAnalyzer()
        analysis = {"has_alerts": True}
        template = analyzer._determine_template(analysis)
        assert template == "alert"

    def test_severe_weather_template(self):
        """Severe/extreme severity returns severe_weather template."""
        analyzer = WeatherConditionAnalyzer()

        for severity in [WeatherSeverity.SEVERE, WeatherSeverity.EXTREME]:
            analysis = {
                "has_alerts": False,
                "severity": severity,
                "temperature_extreme": None,
                "wind_condition": None,
                "category": ConditionCategory.CLEAR,
            }
            template = analyzer._determine_template(analysis)
            assert template == "severe_weather"

    def test_temperature_extreme_template(self):
        """Extreme/very temps return temperature_extreme template."""
        analyzer = WeatherConditionAnalyzer()

        for temp in ["extreme_cold", "extreme_hot", "very_cold", "very_hot"]:
            analysis = {
                "has_alerts": False,
                "severity": WeatherSeverity.NORMAL,
                "temperature_extreme": temp,
                "wind_condition": None,
                "category": ConditionCategory.CLEAR,
            }
            template = analyzer._determine_template(analysis)
            assert template == "temperature_extreme"

    def test_wind_warning_template(self):
        """Strong winds return wind_warning template."""
        analyzer = WeatherConditionAnalyzer()

        for wind in ["extreme", "very_strong", "strong"]:
            analysis = {
                "has_alerts": False,
                "severity": WeatherSeverity.NORMAL,
                "temperature_extreme": None,
                "wind_condition": wind,
                "category": ConditionCategory.CLEAR,
            }
            template = analyzer._determine_template(analysis)
            assert template == "wind_warning"

    def test_precipitation_template(self):
        """Precipitation/freezing categories return precipitation template."""
        analyzer = WeatherConditionAnalyzer()

        for category in [ConditionCategory.PRECIPITATION, ConditionCategory.FREEZING]:
            analysis = {
                "has_alerts": False,
                "severity": WeatherSeverity.NORMAL,
                "temperature_extreme": None,
                "wind_condition": None,
                "category": category,
            }
            template = analyzer._determine_template(analysis)
            assert template == "precipitation"

    def test_fog_template(self):
        """Fog category returns fog template."""
        analyzer = WeatherConditionAnalyzer()
        analysis = {
            "has_alerts": False,
            "severity": WeatherSeverity.NORMAL,
            "temperature_extreme": None,
            "wind_condition": None,
            "category": ConditionCategory.FOG,
        }
        template = analyzer._determine_template(analysis)
        assert template == "fog"

    def test_default_template(self):
        """Default conditions return default template."""
        analyzer = WeatherConditionAnalyzer()
        analysis = {
            "has_alerts": False,
            "severity": WeatherSeverity.NORMAL,
            "temperature_extreme": None,
            "wind_condition": None,
            "category": ConditionCategory.CLEAR,
        }
        template = analyzer._determine_template(analysis)
        assert template == "default"


class TestAnalyzeWeatherConditions:
    """Test main analysis function."""

    def test_basic_clear_weather(self):
        """Basic clear weather analysis."""
        analyzer = WeatherConditionAnalyzer()
        result = analyzer.analyze_weather_conditions({"weather_code": 0, "temp": 70})

        assert result["category"] == ConditionCategory.CLEAR
        assert result["severity"] == WeatherSeverity.NORMAL
        assert result["recommended_template"] == "default"
        assert result["has_alerts"] is False

    def test_alerts_take_priority(self):
        """Alerts should override other conditions."""
        analyzer = WeatherConditionAnalyzer()
        alerts = [{"severity": "Severe", "event": "Test Alert"}]
        result = analyzer.analyze_weather_conditions(
            {"weather_code": 0, "temp": 70}, alerts_data=alerts
        )

        assert result["has_alerts"] is True
        assert result["recommended_template"] == "alert"
        assert result["priority_score"] == 1000

    def test_weather_code_as_list(self):
        """Should handle weather_code as list/tuple."""
        analyzer = WeatherConditionAnalyzer()
        result = analyzer.analyze_weather_conditions({"weather_code": [95, 96]})

        assert result["primary_condition"] == 95
        assert result["category"] == ConditionCategory.THUNDERSTORM

    def test_unknown_weather_code_defaults(self):
        """Unknown weather code defaults to CLEAR/NORMAL."""
        analyzer = WeatherConditionAnalyzer()
        result = analyzer.analyze_weather_conditions({"weather_code": 999})

        assert result["category"] == ConditionCategory.CLEAR
        assert result["severity"] == WeatherSeverity.NORMAL

    def test_exception_handling(self):
        """Should handle exceptions gracefully."""
        analyzer = WeatherConditionAnalyzer()
        # Pass something that would cause issues
        result = analyzer.analyze_weather_conditions(None)

        assert "error" in result
        assert result["recommended_template"] == "default"

    def test_full_analysis_with_all_conditions(self):
        """Full analysis with temperature and wind."""
        analyzer = WeatherConditionAnalyzer()
        result = analyzer.analyze_weather_conditions(
            {
                "weather_code": 65,  # Heavy rain
                "temp": 40,
                "wind_speed": 35,  # Strong wind threshold
            }
        )

        assert result["category"] == ConditionCategory.PRECIPITATION
        assert result["severity"] == WeatherSeverity.SEVERE
        assert result["temperature_extreme"] is None
        assert result["wind_condition"] == "strong"
        assert result["recommended_template"] == "severe_weather"


class TestEnums:
    """Test enum values."""

    def test_weather_severity_values(self):
        """Severity enum has correct ordered values."""
        assert WeatherSeverity.NORMAL.value == 0
        assert WeatherSeverity.MINOR.value == 1
        assert WeatherSeverity.MODERATE.value == 2
        assert WeatherSeverity.SEVERE.value == 3
        assert WeatherSeverity.EXTREME.value == 4

    def test_condition_category_values(self):
        """Category enum has correct string values."""
        assert ConditionCategory.CLEAR.value == "clear"
        assert ConditionCategory.CLOUDY.value == "cloudy"
        assert ConditionCategory.PRECIPITATION.value == "precipitation"
        assert ConditionCategory.SEVERE_WEATHER.value == "severe_weather"
        assert ConditionCategory.FOG.value == "fog"
        assert ConditionCategory.FREEZING.value == "freezing"
        assert ConditionCategory.THUNDERSTORM.value == "thunderstorm"
