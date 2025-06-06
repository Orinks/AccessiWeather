"""Tests for the weather condition analyzer module."""

import pytest

from accessiweather.weather_condition_analyzer import (
    ConditionCategory,
    WeatherConditionAnalyzer,
    WeatherSeverity,
)


@pytest.fixture
def analyzer():
    """Create a WeatherConditionAnalyzer instance for testing."""
    return WeatherConditionAnalyzer()


@pytest.fixture
def sample_weather_data():
    """Sample weather data for testing."""
    return {
        "temp": 72.0,
        "temp_f": 72.0,
        "temp_c": 22.2,
        "condition": "Partly Cloudy",
        "humidity": 45,
        "wind_speed": 10.0,
        "wind_dir": "NW",
        "pressure": 29.92,
        "weather_code": 2,  # Partly cloudy
    }


@pytest.fixture
def sample_alerts_data():
    """Sample alerts data for testing."""
    return [
        {
            "id": "test-alert-1",
            "event": "Winter Storm Warning",
            "severity": "Severe",
            "headline": "Heavy snow expected",
            "description": "6-12 inches of snow expected",
        }
    ]


class TestWeatherConditionAnalyzer:
    """Test cases for WeatherConditionAnalyzer."""

    def test_init(self, analyzer):
        """Test analyzer initialization."""
        assert isinstance(analyzer, WeatherConditionAnalyzer)

    def test_analyze_clear_weather(self, analyzer):
        """Test analysis of clear weather conditions."""
        weather_data = {"weather_code": 0, "temp": 72.0, "wind_speed": 5.0}

        result = analyzer.analyze_weather_conditions(weather_data)

        assert result["category"] == ConditionCategory.CLEAR
        assert result["severity"] == WeatherSeverity.NORMAL
        assert result["primary_condition"] == 0
        assert result["recommended_template"] == "default"
        assert not result["has_alerts"]

    def test_analyze_cloudy_weather(self, analyzer, sample_weather_data):
        """Test analysis of cloudy weather conditions."""
        result = analyzer.analyze_weather_conditions(sample_weather_data)

        assert result["category"] == ConditionCategory.CLOUDY
        assert result["severity"] == WeatherSeverity.NORMAL
        assert result["primary_condition"] == 2
        assert result["recommended_template"] == "default"

    def test_analyze_precipitation(self, analyzer):
        """Test analysis of precipitation conditions."""
        weather_data = {"weather_code": 63, "temp": 65.0, "wind_speed": 8.0}  # Moderate rain

        result = analyzer.analyze_weather_conditions(weather_data)

        assert result["category"] == ConditionCategory.PRECIPITATION
        assert result["severity"] == WeatherSeverity.MODERATE
        assert result["primary_condition"] == 63
        assert result["recommended_template"] == "precipitation"

    def test_analyze_severe_weather(self, analyzer):
        """Test analysis of severe weather conditions."""
        weather_data = {"weather_code": 95, "temp": 75.0, "wind_speed": 25.0}  # Thunderstorm

        result = analyzer.analyze_weather_conditions(weather_data)

        assert result["category"] == ConditionCategory.THUNDERSTORM
        assert result["severity"] == WeatherSeverity.SEVERE
        assert result["primary_condition"] == 95
        assert result["recommended_template"] == "severe_weather"

    def test_analyze_freezing_conditions(self, analyzer):
        """Test analysis of freezing conditions."""
        weather_data = {"weather_code": 67, "temp": 28.0, "wind_speed": 15.0}  # Heavy freezing rain

        result = analyzer.analyze_weather_conditions(weather_data)

        assert result["category"] == ConditionCategory.FREEZING
        assert result["severity"] == WeatherSeverity.EXTREME
        assert result["recommended_template"] == "severe_weather"

    def test_analyze_with_alerts(self, analyzer, sample_weather_data, sample_alerts_data):
        """Test analysis with active weather alerts."""
        result = analyzer.analyze_weather_conditions(sample_weather_data, sample_alerts_data)

        assert result["has_alerts"] is True
        assert result["alert_severity"] == WeatherSeverity.SEVERE
        assert result["recommended_template"] == "alert"
        assert result["priority_score"] == 1000  # Alerts have highest priority

    def test_analyze_temperature_extremes(self, analyzer):
        """Test analysis of temperature extremes."""
        # Extreme cold
        cold_data = {"weather_code": 0, "temp": -10.0, "wind_speed": 5.0}
        result = analyzer.analyze_weather_conditions(cold_data)
        assert result["temperature_extreme"] == "extreme_cold"
        assert result["recommended_template"] == "temperature_extreme"

        # Extreme hot
        hot_data = {"weather_code": 0, "temp": 115.0, "wind_speed": 5.0}
        result = analyzer.analyze_weather_conditions(hot_data)
        assert result["temperature_extreme"] == "extreme_hot"
        assert result["recommended_template"] == "temperature_extreme"

    def test_analyze_wind_conditions(self, analyzer):
        """Test analysis of wind conditions."""
        # Strong wind
        windy_data = {"weather_code": 0, "temp": 70.0, "wind_speed": 40.0}
        result = analyzer.analyze_weather_conditions(windy_data)
        assert result["wind_condition"] == "strong"
        assert result["recommended_template"] == "wind_warning"

        # Extreme wind
        extreme_wind_data = {"weather_code": 0, "temp": 70.0, "wind_speed": 65.0}
        result = analyzer.analyze_weather_conditions(extreme_wind_data)
        assert result["wind_condition"] == "extreme"
        assert result["recommended_template"] == "wind_warning"

    def test_analyze_fog_conditions(self, analyzer):
        """Test analysis of fog conditions."""
        fog_data = {"weather_code": 45, "temp": 60.0, "wind_speed": 3.0}  # Fog

        result = analyzer.analyze_weather_conditions(fog_data)

        assert result["category"] == ConditionCategory.FOG
        assert result["severity"] == WeatherSeverity.MINOR
        assert result["recommended_template"] == "fog"

    def test_priority_score_calculation(self, analyzer):
        """Test priority score calculation."""
        # Normal conditions should have low score
        normal_data = {"weather_code": 0, "temp": 70.0, "wind_speed": 5.0}
        result = analyzer.analyze_weather_conditions(normal_data)
        assert result["priority_score"] < 50

        # Severe conditions should have higher score
        severe_data = {"weather_code": 95, "temp": 110.0, "wind_speed": 50.0}
        result = analyzer.analyze_weather_conditions(severe_data)
        assert result["priority_score"] > 100

    def test_weather_code_list_handling(self, analyzer):
        """Test handling of weather code as list."""
        weather_data = {"weather_code": [63, 61], "temp": 65.0, "wind_speed": 8.0}

        result = analyzer.analyze_weather_conditions(weather_data)

        assert result["primary_condition"] == 63  # Should use first element
        assert result["category"] == ConditionCategory.PRECIPITATION

    def test_missing_weather_data(self, analyzer):
        """Test handling of missing weather data."""
        incomplete_data = {"temp": 70.0}  # Missing weather_code

        result = analyzer.analyze_weather_conditions(incomplete_data)

        assert result["primary_condition"] == 0  # Default weather code
        assert result["category"] == ConditionCategory.CLEAR
        assert result["recommended_template"] == "default"

    def test_error_handling(self, analyzer):
        """Test error handling with invalid data."""
        invalid_data = {"weather_code": "invalid", "temp": "not_a_number"}

        result = analyzer.analyze_weather_conditions(invalid_data)

        assert "error" in result
        assert result["recommended_template"] == "default"
        assert result["priority_score"] == 0

    def test_alert_severity_mapping(self, analyzer):
        """Test alert severity mapping."""
        # Test different alert severities
        extreme_alert = [{"severity": "Extreme", "event": "Hurricane Warning"}]
        result = analyzer.analyze_weather_conditions({}, extreme_alert)
        assert result["alert_severity"] == WeatherSeverity.EXTREME

        minor_alert = [{"severity": "Minor", "event": "Frost Advisory"}]
        result = analyzer.analyze_weather_conditions({}, minor_alert)
        assert result["alert_severity"] == WeatherSeverity.MINOR

    def test_multiple_alerts_priority(self, analyzer):
        """Test handling of multiple alerts with different severities."""
        multiple_alerts = [
            {"severity": "Minor", "event": "Frost Advisory"},
            {"severity": "Severe", "event": "Tornado Warning"},
            {"severity": "Moderate", "event": "Flood Watch"},
        ]

        result = analyzer.analyze_weather_conditions({}, multiple_alerts)

        # Should prioritize the most severe alert
        assert result["alert_severity"] == WeatherSeverity.SEVERE
        assert result["primary_alert"]["event"] == "Tornado Warning"

    def test_template_determination_priority(self, analyzer):
        """Test template determination priority order."""
        # Alerts should override everything
        weather_with_alert = {"weather_code": 95, "temp": 110.0, "wind_speed": 60.0}
        alerts = [{"severity": "Minor", "event": "Test Alert"}]
        result = analyzer.analyze_weather_conditions(weather_with_alert, alerts)
        assert result["recommended_template"] == "alert"

        # Severe weather should override temperature/wind
        severe_weather = {"weather_code": 95, "temp": 110.0, "wind_speed": 60.0}
        result = analyzer.analyze_weather_conditions(severe_weather)
        assert result["recommended_template"] == "severe_weather"

        # Temperature extreme should override wind
        temp_extreme = {"weather_code": 0, "temp": 115.0, "wind_speed": 40.0}
        result = analyzer.analyze_weather_conditions(temp_extreme)
        assert result["recommended_template"] == "temperature_extreme"


if __name__ == "__main__":
    pytest.main([__file__])
