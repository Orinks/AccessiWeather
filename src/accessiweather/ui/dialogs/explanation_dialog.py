"""
AI explanation dialog for wxPython.

Displays AI-generated weather explanations with loading state and metadata.
"""

from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import wx

if TYPE_CHECKING:
    from ...ai_explainer import ExplanationResult
    from ...app import AccessiWeatherApp

logger = logging.getLogger(__name__)


class ExplanationDialog(wx.Dialog):
    """Dialog for displaying AI-generated weather explanations."""

    def __init__(
        self,
        parent,
        explanation: ExplanationResult,
        location: str,
    ):
        """
        Create explanation dialog with result.

        Args:
            parent: Parent window
            explanation: The AI-generated explanation result
            location: The location name for the weather data

        """
        super().__init__(
            parent,
            title=f"Weather Explanation - {location}",
            size=(550, 450),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self.explanation = explanation
        self.location = location
        self._create_ui()
        self._setup_accessibility()

    def _create_ui(self):
        """Create the dialog UI."""
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Header with location
        header = wx.StaticText(
            self,
            label=f"Weather explanation for {self.location}",
        )
        header_font = header.GetFont()
        header_font.SetWeight(wx.FONTWEIGHT_BOLD)
        header_font.SetPointSize(header_font.GetPointSize() + 2)
        header.SetFont(header_font)
        main_sizer.Add(header, 0, wx.ALL, 10)

        # Timestamp
        timestamp_text = self.explanation.timestamp.strftime("%B %d, %Y at %I:%M %p")
        timestamp = wx.StaticText(self, label=f"Generated: {timestamp_text}")
        timestamp_font = timestamp.GetFont()
        timestamp_font.SetStyle(wx.FONTSTYLE_ITALIC)
        timestamp.SetFont(timestamp_font)
        main_sizer.Add(timestamp, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # Explanation text (main content)
        explanation_text = self.explanation.text or "(No explanation text received)"
        self.text_ctrl = wx.TextCtrl(
            self,
            value=explanation_text,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_WORDWRAP,
        )
        main_sizer.Add(self.text_ctrl, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        # Model information
        cost_text = (
            "No cost"
            if self.explanation.estimated_cost == 0
            else f"~${self.explanation.estimated_cost:.6f}"
        )
        info = (
            f"Model: {self.explanation.model_used}"
            f" | Tokens: {self.explanation.token_count}"
            f" | Cost: {cost_text}"
        )
        if self.explanation.cached:
            info += " (cached)"
        model_info = wx.TextCtrl(
            self, value=info, style=wx.TE_READONLY, name="Model information"
        )
        main_sizer.Add(model_info, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)

        # Close button
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_sizer.AddStretchSpacer()
        close_btn = wx.Button(self, wx.ID_CLOSE, "Close")
        close_btn.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_OK))
        btn_sizer.Add(close_btn, 0)
        main_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 10)

        self.SetSizer(main_sizer)

        # Set focus to text for screen readers
        self.text_ctrl.SetFocus()

    def _setup_accessibility(self):
        """Set up accessibility labels."""
        self.text_ctrl.SetName("Weather explanation")


class LoadingDialog(wx.Dialog):
    """Dialog showing loading state while generating explanation."""

    def __init__(self, parent, location: str):
        """
        Create loading dialog.

        Args:
            parent: Parent window
            location: The location being explained

        """
        super().__init__(
            parent,
            title="Generating Explanation",
            size=(350, 150),
            style=wx.DEFAULT_DIALOG_STYLE,
        )
        self.location = location
        self.is_cancelled = False
        self._create_ui()

    def _create_ui(self):
        """Create the loading dialog UI."""
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Loading message
        loading_label = wx.StaticText(self, label=f"Generating explanation for {self.location}...")
        main_sizer.Add(loading_label, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 15)

        # Activity indicator (gauge in indeterminate mode)
        self.gauge = wx.Gauge(self, range=100, size=(200, 20), style=wx.GA_HORIZONTAL)
        self.gauge.Pulse()
        main_sizer.Add(self.gauge, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.LEFT | wx.RIGHT, 15)

        # Status label
        self.status_label = wx.StaticText(self, label="Please wait...")
        status_font = self.status_label.GetFont()
        status_font.SetStyle(wx.FONTSTYLE_ITALIC)
        self.status_label.SetFont(status_font)
        main_sizer.Add(self.status_label, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 10)

        # Cancel button
        self.cancel_btn = wx.Button(self, wx.ID_CANCEL, "Cancel")
        self.cancel_btn.Bind(wx.EVT_BUTTON, self._on_cancel)
        main_sizer.Add(self.cancel_btn, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.BOTTOM, 10)

        self.SetSizer(main_sizer)

        # Start pulse timer
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_timer, self.timer)
        self.timer.Start(50)

    def _on_timer(self, event):
        """Update the gauge pulse."""
        self.gauge.Pulse()

    def _on_cancel(self, event):
        """Handle cancel button press."""
        logger.info("User cancelled explanation generation")
        self.is_cancelled = True
        self.timer.Stop()  # Stop timer before closing to prevent post-destroy crashes
        self.status_label.SetLabel("Cancelling...")
        self.cancel_btn.Enable(False)
        self.EndModal(wx.ID_CANCEL)

    def close(self):
        """Close the loading dialog safely."""
        if self.is_cancelled:
            return  # Already closed via cancel
        try:
            self.timer.Stop()
            self.EndModal(wx.ID_OK)
        except RuntimeError:
            # Dialog already destroyed
            pass


def show_explanation_dialog(
    parent,
    app: AccessiWeatherApp,
) -> None:
    """
    Generate and show AI weather explanation.

    Args:
        parent: Parent window
        app: Application instance

    """
    parent_ctrl = parent

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

    # Use a mutable container for cancelled state that survives dialog destruction
    state = {"cancelled": False, "dialog_closed": False}

    # Show loading dialog (non-modal so we can update it)
    loading_dialog = LoadingDialog(parent_ctrl, location.name)

    # Hook into the dialog's cancel to set our independent flag
    original_on_cancel = loading_dialog._on_cancel

    def wrapped_on_cancel(event):
        state["cancelled"] = True
        original_on_cancel(event)

    loading_dialog._on_cancel = wrapped_on_cancel
    loading_dialog.cancel_btn.Unbind(wx.EVT_BUTTON)
    loading_dialog.cancel_btn.Bind(wx.EVT_BUTTON, wrapped_on_cancel)

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
            if not state["cancelled"]:
                wx.CallAfter(_show_result, result)

        except AIExplainerError as e:
            if not state["cancelled"]:
                wx.CallAfter(_show_error, str(e))
            logger.warning(f"AI explanation error: {e}")

        except Exception as e:
            if not state["cancelled"]:
                wx.CallAfter(_show_error, f"Unable to generate explanation.\n\nError: {e}")
            logger.error(f"Unexpected error generating AI explanation: {e}", exc_info=True)

    def _show_result(result):
        """Show the explanation result."""
        # Don't try to close if already cancelled/destroyed
        if state["cancelled"] or state["dialog_closed"]:
            return
        state["dialog_closed"] = True
        loading_dialog.close()
        dlg = ExplanationDialog(parent_ctrl, result, location.name)
        dlg.ShowModal()
        dlg.Destroy()
        logger.info(
            f"Generated weather explanation for {location.name} "
            f"(tokens: {result.token_count}, cached: {result.cached})"
        )

    def _show_error(error_message):
        """Show error message."""
        # Don't try to close if already cancelled/destroyed
        if state["cancelled"] or state["dialog_closed"]:
            return
        state["dialog_closed"] = True
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
    result = loading_dialog.ShowModal()
    if result == wx.ID_CANCEL:
        state["cancelled"] = True
    state["dialog_closed"] = True
    loading_dialog.Destroy()
