"""
Weather condition analysis engine for dynamic taskbar icon customization.

This module provides functionality to analyze weather data and determine
appropriate format string templates for the taskbar icon tooltip.
"""

import logging
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class WeatherSeverity(Enum):
    """Weather severity levels for prioritization."""

    NORMAL = 0
    MINOR = 1
    MODERATE = 2
    SEVERE = 3
    EXTREME = 4


class ConditionCategory(Enum):
    """Weather condition categories."""

    CLEAR = "clear"
    CLOUDY = "cloudy"
    PRECIPITATION = "precipitation"
    SEVERE_WEATHER = "severe_weather"
    FOG = "fog"
    FREEZING = "freezing"
    THUNDERSTORM = "thunderstorm"


class WeatherConditionAnalyzer:
    """Analyzes weather conditions and determines appropriate format string templates."""

    # Open-Meteo weather code mappings to categories and severity
    WEATHER_CODE_MAPPING = {
        # Clear/Sunny conditions
        0: (ConditionCategory.CLEAR, WeatherSeverity.NORMAL),
        1: (ConditionCategory.CLEAR, WeatherSeverity.NORMAL),
        # Cloudy conditions
        2: (ConditionCategory.CLOUDY, WeatherSeverity.NORMAL),
        3: (ConditionCategory.CLOUDY, WeatherSeverity.NORMAL),
        # Fog conditions
        45: (ConditionCategory.FOG, WeatherSeverity.MINOR),
        48: (ConditionCategory.FOG, WeatherSeverity.MODERATE),
        # Drizzle
        51: (ConditionCategory.PRECIPITATION, WeatherSeverity.MINOR),
        53: (ConditionCategory.PRECIPITATION, WeatherSeverity.MINOR),
        55: (ConditionCategory.PRECIPITATION, WeatherSeverity.MODERATE),
        # Freezing drizzle
        56: (ConditionCategory.FREEZING, WeatherSeverity.MODERATE),
        57: (ConditionCategory.FREEZING, WeatherSeverity.SEVERE),
        # Rain
        61: (ConditionCategory.PRECIPITATION, WeatherSeverity.MINOR),
        63: (ConditionCategory.PRECIPITATION, WeatherSeverity.MODERATE),
        65: (ConditionCategory.PRECIPITATION, WeatherSeverity.SEVERE),
        # Freezing rain
        66: (ConditionCategory.FREEZING, WeatherSeverity.SEVERE),
        67: (ConditionCategory.FREEZING, WeatherSeverity.EXTREME),
        # Snow
        71: (ConditionCategory.PRECIPITATION, WeatherSeverity.MODERATE),
        73: (ConditionCategory.PRECIPITATION, WeatherSeverity.SEVERE),
        75: (ConditionCategory.PRECIPITATION, WeatherSeverity.EXTREME),
        77: (ConditionCategory.PRECIPITATION, WeatherSeverity.MINOR),
        # Rain showers
        80: (ConditionCategory.PRECIPITATION, WeatherSeverity.MINOR),
        81: (ConditionCategory.PRECIPITATION, WeatherSeverity.MODERATE),
        82: (ConditionCategory.PRECIPITATION, WeatherSeverity.SEVERE),
        # Snow showers
        85: (ConditionCategory.PRECIPITATION, WeatherSeverity.MODERATE),
        86: (ConditionCategory.PRECIPITATION, WeatherSeverity.SEVERE),
        # Thunderstorms
        95: (ConditionCategory.THUNDERSTORM, WeatherSeverity.SEVERE),
        96: (ConditionCategory.THUNDERSTORM, WeatherSeverity.EXTREME),
        99: (ConditionCategory.THUNDERSTORM, WeatherSeverity.EXTREME),
    }

    # Temperature thresholds (in Fahrenheit)
    TEMPERATURE_THRESHOLDS = {
        "extreme_cold": 0,
        "very_cold": 20,
        "cold": 32,
        "hot": 90,
        "very_hot": 100,
        "extreme_hot": 110,
    }

    # Wind speed thresholds (in mph)
    WIND_SPEED_THRESHOLDS = {
        "calm": 5,
        "light": 15,
        "moderate": 25,
        "strong": 35,
        "very_strong": 45,
        "extreme": 60,
    }

    def __init__(self):
        """Initialize the weather condition analyzer."""

    def analyze_weather_conditions(
        self, weather_data: dict[str, Any], alerts_data: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        """
        Analyze weather conditions and return analysis results.

        Args:
        ----
            weather_data: Current weather data dictionary
            alerts_data: Optional list of active weather alerts

        Returns:
        -------
            Dictionary containing analysis results with recommended format template

        """
        try:
            analysis = {
                "primary_condition": None,
                "severity": WeatherSeverity.NORMAL,
                "category": ConditionCategory.CLEAR,
                "temperature_extreme": None,
                "wind_condition": None,
                "has_alerts": bool(alerts_data),
                "alert_severity": None,
                "recommended_template": "default",
                "priority_score": 0,
            }

            # Check for active alerts first (highest priority)
            if alerts_data:
                alert_analysis = self._analyze_alerts(alerts_data)
                analysis.update(alert_analysis)
                analysis["priority_score"] = 1000  # Alerts have highest priority
                return analysis

            # Analyze weather code
            weather_code = weather_data.get("weather_code", 0)
            if isinstance(weather_code, list | tuple) and weather_code:
                weather_code = weather_code[0]

            category, severity = self.WEATHER_CODE_MAPPING.get(
                weather_code, (ConditionCategory.CLEAR, WeatherSeverity.NORMAL)
            )

            analysis["category"] = category
            analysis["severity"] = severity
            analysis["primary_condition"] = weather_code

            # Analyze temperature extremes
            temp_analysis = self._analyze_temperature(weather_data)
            analysis.update(temp_analysis)

            # Analyze wind conditions
            wind_analysis = self._analyze_wind(weather_data)
            analysis.update(wind_analysis)

            # Calculate priority score
            analysis["priority_score"] = self._calculate_priority_score(analysis)

            # Determine recommended template
            analysis["recommended_template"] = self._determine_template(analysis)

            logger.debug(f"Weather analysis complete: {analysis}")
            return analysis

        except Exception as e:
            logger.error(f"Error analyzing weather conditions: {e}")
            return {
                "primary_condition": None,
                "severity": WeatherSeverity.NORMAL,
                "category": ConditionCategory.CLEAR,
                "recommended_template": "default",
                "priority_score": 0,
                "error": str(e),
            }

    def _analyze_alerts(self, alerts_data: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Analyze weather alerts and return alert-specific analysis.

        Args:
        ----
            alerts_data: List of active weather alerts

        Returns:
        -------
            Dictionary with alert analysis results

        """
        if not alerts_data:
            return {"has_alerts": False, "alert_severity": None}

        # Find the highest severity alert
        max_severity = WeatherSeverity.NORMAL
        primary_alert = None

        for alert in alerts_data:
            severity_str = alert.get("severity", "Unknown")
            severity = self._map_alert_severity(severity_str)

            if severity.value > max_severity.value:
                max_severity = severity
                primary_alert = alert

        return {
            "has_alerts": True,
            "alert_severity": max_severity,
            "primary_alert": primary_alert,
            "recommended_template": "alert",
        }

    def _analyze_temperature(self, weather_data: dict[str, Any]) -> dict[str, Any]:
        """
        Analyze temperature conditions.

        Args:
        ----
            weather_data: Weather data dictionary

        Returns:
        -------
            Dictionary with temperature analysis

        """
        temp = weather_data.get("temp", weather_data.get("temp_f"))
        if temp is None:
            return {"temperature_extreme": None}

        if temp <= self.TEMPERATURE_THRESHOLDS["extreme_cold"]:
            return {"temperature_extreme": "extreme_cold"}
        if temp <= self.TEMPERATURE_THRESHOLDS["very_cold"]:
            return {"temperature_extreme": "very_cold"}
        if temp <= self.TEMPERATURE_THRESHOLDS["cold"]:
            return {"temperature_extreme": "cold"}
        if temp >= self.TEMPERATURE_THRESHOLDS["extreme_hot"]:
            return {"temperature_extreme": "extreme_hot"}
        if temp >= self.TEMPERATURE_THRESHOLDS["very_hot"]:
            return {"temperature_extreme": "very_hot"}
        if temp >= self.TEMPERATURE_THRESHOLDS["hot"]:
            return {"temperature_extreme": "hot"}

        return {"temperature_extreme": None}

    def _analyze_wind(self, weather_data: dict[str, Any]) -> dict[str, Any]:
        """
        Analyze wind conditions.

        Args:
        ----
            weather_data: Weather data dictionary

        Returns:
        -------
            Dictionary with wind analysis

        """
        wind_speed = weather_data.get("wind_speed")
        if wind_speed is None:
            return {"wind_condition": None}

        if wind_speed >= self.WIND_SPEED_THRESHOLDS["extreme"]:
            return {"wind_condition": "extreme"}
        if wind_speed >= self.WIND_SPEED_THRESHOLDS["very_strong"]:
            return {"wind_condition": "very_strong"}
        if wind_speed >= self.WIND_SPEED_THRESHOLDS["strong"]:
            return {"wind_condition": "strong"}
        if wind_speed >= self.WIND_SPEED_THRESHOLDS["moderate"]:
            return {"wind_condition": "moderate"}
        if wind_speed >= self.WIND_SPEED_THRESHOLDS["light"]:
            return {"wind_condition": "light"}

        return {"wind_condition": "calm"}

    def _map_alert_severity(self, severity_str: str) -> WeatherSeverity:
        """
        Map alert severity string to WeatherSeverity enum.

        Args:
        ----
            severity_str: Alert severity string

        Returns:
        -------
            WeatherSeverity enum value

        """
        severity_mapping = {
            "Extreme": WeatherSeverity.EXTREME,
            "Severe": WeatherSeverity.SEVERE,
            "Moderate": WeatherSeverity.MODERATE,
            "Minor": WeatherSeverity.MINOR,
        }
        return severity_mapping.get(severity_str, WeatherSeverity.NORMAL)

    def _calculate_priority_score(self, analysis: dict[str, Any]) -> int:
        """
        Calculate priority score for condition analysis.

        Args:
        ----
            analysis: Analysis dictionary

        Returns:
        -------
            Priority score (higher = more important)

        """
        score = 0

        # Base score from severity
        score += analysis["severity"].value * 10

        # Temperature extreme bonus
        temp_extreme = analysis.get("temperature_extreme")
        if temp_extreme:
            if "extreme" in temp_extreme:
                score += 50
            elif "very" in temp_extreme:
                score += 30
            else:
                score += 15

        # Wind condition bonus
        wind_condition = analysis.get("wind_condition")
        if wind_condition:
            if wind_condition == "extreme":
                score += 40
            elif wind_condition == "very_strong":
                score += 25
            elif wind_condition == "strong":
                score += 15

        return score

    def _determine_template(self, analysis: dict[str, Any]) -> str:
        """
        Determine the recommended format template based on analysis.

        Args:
        ----
            analysis: Analysis dictionary

        Returns:
        -------
            Template name string

        """
        # Alert template has highest priority
        if analysis.get("has_alerts"):
            return "alert"

        # Severe weather conditions
        if analysis["severity"] in [WeatherSeverity.SEVERE, WeatherSeverity.EXTREME]:
            return "severe_weather"

        # Temperature extremes
        temp_extreme = analysis.get("temperature_extreme")
        if temp_extreme and ("extreme" in temp_extreme or "very" in temp_extreme):
            return "temperature_extreme"

        # Strong wind conditions
        wind_condition = analysis.get("wind_condition")
        if wind_condition in ["extreme", "very_strong", "strong"]:
            return "wind_warning"

        # Precipitation conditions
        if analysis["category"] in [ConditionCategory.PRECIPITATION, ConditionCategory.FREEZING]:
            return "precipitation"

        # Fog conditions
        if analysis["category"] == ConditionCategory.FOG:
            return "fog"

        # Default template
        return "default"
