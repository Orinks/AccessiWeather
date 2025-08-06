"""Dynamic format string management system for taskbar icon customization.

This module provides functionality to dynamically switch between format string
templates based on weather conditions, alerts, and forecast data.
"""

import logging
from typing import Any

from accessiweather.weather_condition_analyzer import WeatherConditionAnalyzer

logger = logging.getLogger(__name__)


class DynamicFormatManager:
    """Manages dynamic format string templates for taskbar icon tooltips."""

    # Default format string templates for different conditions
    DEFAULT_TEMPLATES = {
        "default": "{location} {temp} {condition} • {humidity}%",
        "alert": "⚠️ {location}: {event} ({severity})",
        "severe_weather": "🌩️ {location} {condition} {temp} • {wind_dir} {wind_speed}",
        "temperature_extreme": "🌡️ {location} {temp} (feels {feels_like}) • {condition}",
        "wind_warning": "💨 {location} {wind_dir} {wind_speed} • {condition} {temp}",
        "precipitation": "🌧️ {location} {condition} {temp} • {precip_chance}% chance",
        "fog": "🌫️ {location} {condition} {temp} • Visibility {visibility}",
        "forecast": "{location} {condition} → {forecast_condition}",
    }

    def __init__(self, custom_templates: dict[str, str] | None = None):
        """Initialize the dynamic format manager.

        Args:
            custom_templates: Optional dictionary of custom format templates

        """
        self.analyzer = WeatherConditionAnalyzer()
        self.templates = self.DEFAULT_TEMPLATES.copy()

        # Add custom templates if provided
        if custom_templates:
            self.templates.update(custom_templates)

        # State management
        self.current_template_name = "default"
        self.current_format_string = self.templates["default"]
        self.last_analysis: dict[str, Any] | None = None
        self.update_count = 0

    def get_dynamic_format_string(
        self,
        weather_data: dict[str, Any],
        alerts_data: list | None = None,
        forecast_data: dict[str, Any] | None = None,
        user_format: str | None = None,
    ) -> str:
        """Get the appropriate format string based on current conditions.

        Args:
            weather_data: Current weather data dictionary
            alerts_data: Optional list of active weather alerts
            forecast_data: Optional forecast data for anticipatory updates
            user_format: Optional user-defined format string to use as base

        Returns:
            Format string to use for the taskbar icon tooltip

        """
        try:
            # Analyze current weather conditions
            analysis = self.analyzer.analyze_weather_conditions(weather_data, alerts_data)

            # Check if we need to update the format string
            if self._should_update_format(analysis):
                self._update_format_string(analysis, user_format, forecast_data)
                self.last_analysis = analysis
                self.update_count += 1

                logger.debug(
                    f"Format string updated to '{self.current_template_name}': "
                    f"{self.current_format_string}"
                )

            return self.current_format_string

        except Exception as e:
            logger.error(f"Error getting dynamic format string: {e}")
            # Fall back to user format or default
            return user_format or self.templates["default"]

    def _should_update_format(self, analysis: dict[str, Any]) -> bool:
        """Determine if the format string should be updated.

        Args:
            analysis: Current weather analysis

        Returns:
            True if format should be updated, False otherwise

        """
        # Always update if this is the first analysis
        if self.last_analysis is None:
            return True

        # Update if the recommended template has changed
        current_template = analysis.get("recommended_template", "default")
        last_template = self.last_analysis.get("recommended_template", "default")

        if current_template != last_template:
            return True

        # Update if alert status has changed
        current_alerts = analysis.get("has_alerts", False)
        last_alerts = self.last_analysis.get("has_alerts", False)

        if current_alerts != last_alerts:
            return True

        # Update if alert severity has changed significantly
        if current_alerts and last_alerts:
            current_severity = analysis.get("alert_severity")
            last_severity = self.last_analysis.get("alert_severity")

            if current_severity != last_severity:
                return True

        # Update if priority score has changed significantly (threshold: 20 points)
        current_priority = analysis.get("priority_score", 0)
        last_priority = self.last_analysis.get("priority_score", 0)

        return abs(current_priority - last_priority) >= 20

    def _update_format_string(
        self,
        analysis: dict[str, Any],
        user_format: str | None = None,
        forecast_data: dict[str, Any] | None = None,
    ):
        """Update the current format string based on analysis.

        Args:
            analysis: Weather condition analysis
            user_format: Optional user-defined base format
            forecast_data: Optional forecast data for anticipatory updates

        """
        template_name = analysis.get("recommended_template", "default")

        # Handle forecast-based updates
        if forecast_data and self._should_use_forecast_template(analysis, forecast_data):
            template_name = "forecast"

        # Get the template format string
        if template_name in self.templates:
            format_string = self.templates[template_name]
        else:
            # Fall back to user format or default
            format_string = user_format or self.templates["default"]
            template_name = "custom" if user_format else "default"

        # Handle alert-specific formatting
        if template_name == "alert" and analysis.get("has_alerts"):
            format_string = self._customize_alert_format(format_string, analysis)

        self.current_template_name = template_name
        self.current_format_string = format_string

    def _should_use_forecast_template(
        self, analysis: dict[str, Any], forecast_data: dict[str, Any]
    ) -> bool:
        """Determine if forecast template should be used.

        Args:
            analysis: Current weather analysis
            forecast_data: Forecast data

        Returns:
            True if forecast template should be used

        """
        # Only use forecast template for normal conditions
        severity = analysis.get("severity")
        if analysis.get("has_alerts") or (severity and severity.value >= 2):
            return False

        # Check if there's a significant weather change coming
        try:
            periods = forecast_data.get("properties", {}).get("periods", [])
            if not periods:
                return False

            # Look at the next few hours/periods
            next_period = periods[0] if periods else None
            if not next_period:
                return False

            # Simple check for different conditions
            # This would need more sophisticated logic to extract forecast weather codes
            # For now, return False to keep it simple
            return False

        except Exception as e:
            logger.debug(f"Error checking forecast template: {e}")
            return False

    def _customize_alert_format(self, format_string: str, analysis: dict[str, Any]) -> str:
        """Customize alert format string based on alert details.

        Args:
            format_string: Base alert format string
            analysis: Weather analysis with alert information

        Returns:
            Customized format string

        """
        try:
            primary_alert = analysis.get("primary_alert")
            if not primary_alert:
                return format_string

            # Customize based on alert severity
            severity = analysis.get("alert_severity")
            if (
                severity
                and severity.name in ["EXTREME", "SEVERE"]
                and not format_string.startswith("⚠️")
            ):
                # Add warning emoji for severe alerts
                format_string = f"⚠️ {format_string}"

            return format_string

        except Exception as e:
            logger.debug(f"Error customizing alert format: {e}")
            return format_string

    def add_custom_template(self, name: str, format_string: str):
        """Add a custom format template.

        Args:
            name: Template name
            format_string: Format string template

        """
        self.templates[name] = format_string
        logger.debug(f"Added custom template '{name}': {format_string}")

    def remove_custom_template(self, name: str) -> bool:
        """Remove a custom format template.

        Args:
            name: Template name to remove

        Returns:
            True if template was removed, False if not found

        """
        if name in self.DEFAULT_TEMPLATES:
            logger.warning(f"Cannot remove default template: {name}")
            return False

        if name in self.templates:
            del self.templates[name]
            logger.debug(f"Removed custom template: {name}")
            return True

        return False

    def get_available_templates(self) -> dict[str, str]:
        """Get all available format templates.

        Returns:
            Dictionary of template names and format strings

        """
        return self.templates.copy()

    def reset_to_default(self):
        """Reset to default template and clear state."""
        self.current_template_name = "default"
        self.current_format_string = self.templates["default"]
        self.last_analysis = None
        self.update_count = 0
        logger.debug("Reset to default format template")

    def get_current_state(self) -> dict[str, Any]:
        """Get current state information.

        Returns:
            Dictionary with current state information

        """
        return {
            "current_template_name": self.current_template_name,
            "current_format_string": self.current_format_string,
            "update_count": self.update_count,
            "last_analysis": self.last_analysis,
            "available_templates": list(self.templates.keys()),
        }

    def force_template(self, template_name: str) -> bool:
        """Force a specific template to be used.

        Args:
            template_name: Name of template to force

        Returns:
            True if template was set, False if template not found

        """
        if template_name not in self.templates:
            logger.warning(f"Template not found: {template_name}")
            return False

        self.current_template_name = template_name
        self.current_format_string = self.templates[template_name]
        logger.debug(f"Forced template to: {template_name}")
        return True
