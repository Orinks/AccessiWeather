"""AI explanation event handlers for AccessiWeather."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..app import AccessiWeatherApp

logger = logging.getLogger(__name__)


async def on_explain_weather_pressed(app: AccessiWeatherApp, widget) -> None:
    """
    Handle Explain Weather button press.

    Generates an AI explanation of current weather conditions and displays
    it in a dialog.

    Args:
        app: The AccessiWeather application instance
        widget: The button widget that triggered the event

    """
    from ..ai_explainer import (
        AIExplainer,
        AIExplainerError,
        ExplanationStyle,
    )
    from ..dialogs.explanation_dialog import (
        ErrorDialog,
        ExplanationDialog,
        LoadingDialog,
    )

    # Get current location
    location = app.config_manager.get_current_location()
    if not location:
        error_dialog = ErrorDialog(app, "No location selected. Please select a location first.")
        error_dialog.show()
        return

    # Get current weather data
    weather_data = getattr(app, "current_weather_data", None)
    if not weather_data or not weather_data.current:
        error_dialog = ErrorDialog(
            app, "No weather data available. Please refresh weather data first."
        )
        error_dialog.show()
        return

    # Show loading dialog
    loading_dialog = LoadingDialog(app, location.name)
    loading_dialog.show()

    try:
        # Get AI settings
        settings = app.config_manager.get_settings()

        # Determine model based on settings
        if settings.ai_model_preference == "auto:free":
            model = "openrouter/auto:free"
        elif settings.ai_model_preference == "auto":
            model = "openrouter/auto"
        else:
            model = settings.ai_model_preference

        # Create explainer
        explainer = AIExplainer(
            api_key=settings.openrouter_api_key or None,
            model=model,
            cache=getattr(app, "ai_explanation_cache", None),
        )

        # Build weather data dict from current conditions
        current = weather_data.current
        weather_dict = {
            "temperature": current.temperature_f,
            "temperature_unit": "F",
            "conditions": current.condition,
            "humidity": current.humidity,
            "wind_speed": current.wind_speed_mph,
            "wind_direction": current.wind_direction,
            "visibility": current.visibility_miles,
            "pressure": current.pressure_in,
            "alerts": [],
            "forecast_periods": [],
        }

        # Add alerts if present
        if weather_data.alerts and weather_data.alerts.alerts:
            weather_dict["alerts"] = [
                {"title": alert.title, "severity": alert.severity}
                for alert in weather_data.alerts.alerts
            ]

        # Add forecast periods if available (first 4-6 periods for context)
        if weather_data.forecast and weather_data.forecast.periods:
            forecast_periods = []
            for period in weather_data.forecast.periods[:6]:
                forecast_periods.append(
                    {
                        "name": period.name,
                        "temperature": period.temperature,
                        "temperature_unit": period.temperature_unit,
                        "short_forecast": period.short_forecast,
                        "wind_speed": period.wind_speed,
                        "wind_direction": period.wind_direction,
                    }
                )
            weather_dict["forecast_periods"] = forecast_periods

        # Determine explanation style
        style_map = {
            "brief": ExplanationStyle.BRIEF,
            "standard": ExplanationStyle.STANDARD,
            "detailed": ExplanationStyle.DETAILED,
        }
        style = style_map.get(settings.ai_explanation_style, ExplanationStyle.STANDARD)

        # Determine if markdown should be preserved
        preserve_markdown = getattr(settings, "html_render_current_conditions", False)

        # Generate explanation
        result = await explainer.explain_weather(
            weather_dict,
            location.name,
            style=style,
            preserve_markdown=preserve_markdown,
        )

        # Close loading dialog
        loading_dialog.close()

        # Debug: log the explanation text
        logger.debug(f"Explanation text length: {len(result.text) if result.text else 0}")
        logger.debug(f"Explanation text: {result.text[:200] if result.text else 'EMPTY'}")

        # Show explanation dialog
        explanation_dialog = ExplanationDialog(app, result, location.name)
        explanation_dialog.show()

        logger.info(
            f"Generated weather explanation for {location.name} "
            f"(tokens: {result.token_count}, cached: {result.cached}, text_len: {len(result.text) if result.text else 0})"
        )

    except AIExplainerError as e:
        loading_dialog.close()
        error_dialog = ErrorDialog(app, str(e))
        error_dialog.show()
        logger.warning(f"AI explanation error: {e}")

    except Exception as e:
        loading_dialog.close()
        # Include actual error details for debugging
        error_message = f"Unable to generate explanation.\n\nError: {e}"
        error_dialog = ErrorDialog(app, error_message)
        error_dialog.show()
        logger.error(f"Unexpected error generating AI explanation: {e}", exc_info=True)
