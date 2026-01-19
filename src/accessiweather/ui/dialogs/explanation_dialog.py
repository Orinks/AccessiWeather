"""
AI explanation dialog using gui_builder.

Displays AI-generated weather explanations with loading state and metadata.
"""

from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import wx
from gui_builder import fields, forms

if TYPE_CHECKING:
    from ...ai_explainer import ExplanationResult
    from ...app import AccessiWeatherApp

logger = logging.getLogger(__name__)


class ExplanationDialog(forms.Dialog):
    """Dialog for displaying AI-generated weather explanations using gui_builder."""

    # Header
    header_label = fields.StaticText(label="")
    timestamp_label = fields.StaticText(label="")

    # Explanation text
    explanation_text = fields.Text(
        label="Weather explanation",
        multiline=True,
        readonly=True,
    )

    # Metadata section
    model_label = fields.StaticText(label="")
    usage_label = fields.StaticText(label="")
    cached_label = fields.StaticText(label="")

    # Close button
    close_button = fields.Button(label="&Close")

    def __init__(
        self,
        explanation: ExplanationResult,
        location: str,
        **kwargs,
    ):
        """
        Create explanation dialog with result.

        Args:
            explanation: The AI-generated explanation result
            location: The location name for the weather data
            **kwargs: Additional keyword arguments passed to Dialog

        """
        self.explanation = explanation
        self.location = location

        kwargs.setdefault("title", f"Weather Explanation - {location}")
        super().__init__(**kwargs)

    def render(self, **kwargs):
        """Render the dialog and populate with data."""
        super().render(**kwargs)
        self._populate_data()
        self._setup_accessibility()

    def _populate_data(self) -> None:
        """Populate the dialog with explanation data."""
        # Header
        self.header_label.set_label(f"Weather explanation for {self.location}")

        # Timestamp
        timestamp_text = self.explanation.timestamp.strftime("%B %d, %Y at %I:%M %p")
        self.timestamp_label.set_label(f"Generated: {timestamp_text}")

        # Explanation text
        explanation_text = self.explanation.text or "(No explanation text received)"
        self.explanation_text.set_value(explanation_text)

        # Model used
        self.model_label.set_label(f"Model: {self.explanation.model_used}")

        # Token count and cost
        cost_text = (
            "No cost"
            if self.explanation.estimated_cost == 0
            else f"~${self.explanation.estimated_cost:.6f}"
        )
        self.usage_label.set_label(f"Tokens: {self.explanation.token_count} | Cost: {cost_text}")

        # Cached indicator
        if self.explanation.cached:
            self.cached_label.set_label("(Cached result)")

    def _setup_accessibility(self) -> None:
        """Set up accessibility labels for screen readers."""
        self.explanation_text.set_accessible_label("Weather explanation")

    @close_button.add_callback
    def on_close(self):
        """Handle close button press."""
        self.widget.control.EndModal(wx.ID_OK)


class LoadingDialog(forms.Dialog):
    """Dialog showing loading state while generating explanation using gui_builder."""

    # Loading message
    loading_label = fields.StaticText(label="")

    # Status label
    status_label = fields.StaticText(label="Please wait...")

    # Cancel button
    cancel_button = fields.Button(label="&Cancel")

    def __init__(self, location: str, **kwargs):
        """
        Create loading dialog.

        Args:
            location: The location being explained
            **kwargs: Additional keyword arguments passed to Dialog

        """
        self.location = location
        self.is_cancelled = False
        self._gauge = None
        self._timer = None

        kwargs.setdefault("title", "Generating Explanation")
        super().__init__(**kwargs)

    def render(self, **kwargs):
        """Render the dialog and set up components."""
        super().render(**kwargs)
        self._setup_loading_state()

    def _setup_loading_state(self) -> None:
        """Set up the loading state."""
        self.loading_label.set_label(f"Generating explanation for {self.location}...")

        # Add a gauge for progress indication (using wx directly for gauge)
        # Note: gui_builder may not have a Gauge field, so we add it manually
        parent = self.widget.control
        self._gauge = wx.Gauge(parent, range=100, size=(200, 20), style=wx.GA_HORIZONTAL)
        self._gauge.Pulse()

        # Start pulse timer
        self._timer = wx.Timer(parent)
        parent.Bind(wx.EVT_TIMER, self._on_timer, self._timer)
        self._timer.Start(50)

    def _on_timer(self, event):
        """Update the gauge pulse."""
        if self._gauge:
            self._gauge.Pulse()

    @cancel_button.add_callback
    def on_cancel(self):
        """Handle cancel button press."""
        logger.info("User cancelled explanation generation")
        self.is_cancelled = True
        self.status_label.set_label("Cancelling...")
        self.cancel_button.disable()
        self.widget.control.EndModal(wx.ID_CANCEL)

    def close(self):
        """Close the loading dialog."""
        if self._timer:
            self._timer.Stop()
        self.widget.control.EndModal(wx.ID_OK)


def show_explanation_dialog(
    parent,
    app: AccessiWeatherApp,
) -> None:
    """
    Generate and show AI weather explanation.

    Args:
        parent: Parent window (gui_builder widget)
        app: Application instance

    """
    # Get the underlying wx control if parent is a gui_builder widget
    parent_ctrl = getattr(parent, "control", parent)

    # Get current location
    location = app.config_manager.get_current_location()
    if not location:
        wx.MessageBox(
            "No location selected. Please select a location first.",
            "AI Explanation Error",
            wx.OK | wx.ICON_WARNING,
        )
        return

    # Get current weather data
    weather_data = getattr(app, "current_weather_data", None)
    if not weather_data or not weather_data.current:
        wx.MessageBox(
            "No weather data available. Please refresh weather data first.",
            "AI Explanation Error",
            wx.OK | wx.ICON_WARNING,
        )
        return

    # Show loading dialog
    loading_dialog = LoadingDialog(location.name, parent=parent_ctrl)
    loading_dialog.render()

    def generate_explanation():
        """Generate explanation in background thread."""
        try:
            import asyncio

            from ...ai_explainer import AIExplainer, AIExplainerError, ExplanationStyle

            # Get AI settings
            settings = app.config_manager.get_settings()

            # Determine model based on settings
            if settings.ai_model_preference == "auto":
                model = "openrouter/auto"
            else:
                model = settings.ai_model_preference

            # Create explainer with custom prompts from settings
            explainer = AIExplainer(
                api_key=settings.openrouter_api_key or None,
                model=model,
                cache=getattr(app, "ai_explanation_cache", None),
                custom_system_prompt=getattr(settings, "custom_system_prompt", None),
                custom_instructions=getattr(settings, "custom_instructions", None),
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

            # Add local time info for the location
            now_utc = datetime.now(UTC)
            weather_dict["utc_time"] = now_utc.strftime("%Y-%m-%d %H:%M UTC")

            # Try to get local time at the weather location
            location_tz = getattr(location, "timezone", None)
            if location_tz:
                try:
                    local_tz = ZoneInfo(location_tz)
                    local_time = now_utc.astimezone(local_tz)
                    weather_dict["local_time"] = local_time.strftime("%Y-%m-%d %H:%M")
                    weather_dict["timezone"] = location_tz
                    hour = local_time.hour
                    if 5 <= hour < 12:
                        weather_dict["time_of_day"] = "morning"
                    elif 12 <= hour < 17:
                        weather_dict["time_of_day"] = "afternoon"
                    elif 17 <= hour < 21:
                        weather_dict["time_of_day"] = "evening"
                    else:
                        weather_dict["time_of_day"] = "night"
                except Exception as e:
                    logger.debug(f"Could not determine local time for {location_tz}: {e}")

            # Add alerts if present
            if weather_data.alerts and weather_data.alerts.alerts:
                weather_dict["alerts"] = [
                    {"title": alert.title, "severity": alert.severity}
                    for alert in weather_data.alerts.alerts
                ]

            # Add forecast periods if available
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

            # Run async explanation
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(
                    explainer.explain_weather(
                        weather_dict,
                        location.name,
                        style=style,
                        preserve_markdown=False,
                    )
                )
            finally:
                loop.close()

            # Show result on main thread
            if not loading_dialog.is_cancelled:
                wx.CallAfter(_show_result, result)

        except AIExplainerError as e:
            if not loading_dialog.is_cancelled:
                wx.CallAfter(_show_error, str(e))
            logger.warning(f"AI explanation error: {e}")

        except Exception as e:
            if not loading_dialog.is_cancelled:
                wx.CallAfter(_show_error, f"Unable to generate explanation.\n\nError: {e}")
            logger.error(f"Unexpected error generating AI explanation: {e}", exc_info=True)

    def _show_result(result):
        """Show the explanation result."""
        loading_dialog.close()
        dlg = ExplanationDialog(result, location.name, parent=parent_ctrl)
        dlg.render()
        dlg.widget.control.ShowModal()
        dlg.widget.control.Destroy()
        logger.info(
            f"Generated weather explanation for {location.name} "
            f"(tokens: {result.token_count}, cached: {result.cached})"
        )

    def _show_error(error_message):
        """Show error message."""
        loading_dialog.close()
        wx.MessageBox(
            error_message,
            "AI Explanation Error",
            wx.OK | wx.ICON_ERROR,
        )

    # Start generation in background thread
    thread = threading.Thread(target=generate_explanation, daemon=True)
    thread.start()

    # Show loading dialog modally
    loading_dialog.widget.control.ShowModal()
    loading_dialog.widget.control.Destroy()
