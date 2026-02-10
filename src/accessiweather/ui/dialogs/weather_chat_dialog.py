"""
WeatherChat dialog — conversational AI weather assistant.

Phase 1: Basic multi-turn chat with current weather context.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import TYPE_CHECKING

import wx

if TYPE_CHECKING:
    from ...app import AccessiWeatherApp

logger = logging.getLogger(__name__)

# Maximum conversation turns to keep in context
MAX_CONTEXT_TURNS = 20


def _build_weather_context(app: AccessiWeatherApp) -> str:
    """Build a weather context string from the app's current data."""
    weather = app.current_weather_data
    if not weather:
        return "No weather data currently loaded."

    parts: list[str] = []
    loc = weather.location
    parts.append(f"Location: {loc.name} ({loc.latitude}, {loc.longitude})")

    cur = weather.current
    if cur:
        if cur.temperature_f is not None:
            parts.append(f"Temperature: {cur.temperature_f:.0f}°F")
        if cur.feels_like_f is not None:
            parts.append(f"Feels like: {cur.feels_like_f:.0f}°F")
        if cur.condition:
            parts.append(f"Conditions: {cur.condition}")
        if cur.humidity is not None:
            parts.append(f"Humidity: {cur.humidity}%")
        if cur.wind_speed_mph is not None:
            wind = f"Wind: {cur.wind_speed_mph:.0f} mph"
            if cur.wind_direction:
                wind += f" from {cur.wind_direction}"
            parts.append(wind)
        if cur.pressure_in is not None:
            parts.append(f"Pressure: {cur.pressure_in:.2f} inHg")
        if cur.visibility_miles is not None:
            parts.append(f"Visibility: {cur.visibility_miles:.1f} miles")
        if cur.uv_index is not None:
            parts.append(f"UV Index: {cur.uv_index}")

    forecast = weather.forecast
    if forecast and forecast.periods:
        parts.append("\nForecast:")
        for period in forecast.periods[:6]:
            line = f"  {period.name}: {period.temperature}°{period.temperature_unit}"
            if period.short_forecast:
                line += f", {period.short_forecast}"
            parts.append(line)

    if weather.alerts and weather.alerts.has_alerts():
        parts.append("\nActive Alerts:")
        for alert in weather.alerts.alerts[:5]:
            title = getattr(alert, "event", None) or getattr(alert, "title", "Alert")
            severity = getattr(alert, "severity", "Unknown")
            parts.append(f"  - {title} (Severity: {severity})")

    if weather.trend_insights:
        parts.append("\nTrend Insights:")
        for insight in weather.trend_insights[:3]:
            parts.append(f"  - {insight.description}")

    return "\n".join(parts)


SYSTEM_PROMPT = (
    "You are WeatherChat, a friendly and knowledgeable weather assistant built into "
    "AccessiWeather. You help users understand weather conditions in plain, accessible "
    "language optimized for screen reader users.\n\n"
    "Guidelines:\n"
    "- Be conversational and helpful\n"
    "- Explain weather in practical terms (what to wear, activity suitability, etc.)\n"
    "- Avoid visual-only descriptions\n"
    "- When referencing data, use the weather context provided\n"
    "- If asked about locations you don't have data for, say so honestly\n"
    "- Keep responses concise but thorough\n"
    "- Respond in plain text only — no markdown formatting\n"
    "- Do not repeat information the user can already see\n\n"
    "IMPORTANT: Respond in plain text. No bold, italic, headers, or bullet markers."
)


class WeatherChatDialog(wx.Dialog):
    """Multi-turn conversational weather chat dialog."""

    def __init__(
        self,
        parent: wx.Window,
        app: AccessiWeatherApp,
        title: str = "WeatherChat",
    ):
        """
        Initialize the WeatherChat dialog.

        Args:
            parent: Parent window
            app: Application instance
            title: Dialog title

        """
        super().__init__(
            parent,
            title=title,
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self.app = app
        self._conversation: list[dict[str, str]] = []
        self._is_generating = False

        self._create_widgets()
        self._bind_events()
        self._add_welcome_message()

        self.SetSize((650, 500))
        self.CenterOnParent()

    def _create_widgets(self) -> None:
        """Create all UI widgets."""
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Chat history label
        history_label = wx.StaticText(panel, label="&Conversation:")
        main_sizer.Add(history_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)

        # Chat history display (read-only)
        self.history_display = wx.TextCtrl(
            panel,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_WORDWRAP | wx.TE_RICH2,
            name="Conversation history",
        )
        main_sizer.Add(self.history_display, 1, wx.ALL | wx.EXPAND, 10)

        # Status label
        self.status_label = wx.StaticText(panel, label="")
        main_sizer.Add(self.status_label, 0, wx.LEFT | wx.RIGHT | wx.EXPAND, 10)

        # Input area
        input_sizer = wx.BoxSizer(wx.HORIZONTAL)

        input_label = wx.StaticText(panel, label="&Message:")
        input_sizer.Add(input_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)

        self.input_ctrl = wx.TextCtrl(
            panel,
            style=wx.TE_PROCESS_ENTER,
            name="Type your message",
        )
        input_sizer.Add(self.input_ctrl, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)

        self.send_button = wx.Button(panel, label="&Send")
        input_sizer.Add(self.send_button, 0, wx.ALIGN_CENTER_VERTICAL)

        main_sizer.Add(input_sizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)

        # Bottom buttons
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.clear_button = wx.Button(panel, label="C&lear Chat")
        button_sizer.Add(self.clear_button, 0, wx.RIGHT, 5)

        self.copy_button = wx.Button(panel, label="Cop&y Chat")
        button_sizer.Add(self.copy_button, 0, wx.RIGHT, 5)

        button_sizer.AddStretchSpacer()

        close_button = wx.Button(panel, wx.ID_CLOSE, label="&Close")
        button_sizer.Add(close_button, 0)

        main_sizer.Add(button_sizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)

        panel.SetSizer(main_sizer)

    def _bind_events(self) -> None:
        """Bind event handlers."""
        self.send_button.Bind(wx.EVT_BUTTON, self._on_send)
        self.input_ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_send)
        self.clear_button.Bind(wx.EVT_BUTTON, self._on_clear)
        self.copy_button.Bind(wx.EVT_BUTTON, self._on_copy)
        self.Bind(wx.EVT_BUTTON, self._on_close, id=wx.ID_CLOSE)
        self.Bind(wx.EVT_CLOSE, self._on_close)

        # Escape to close
        self.Bind(wx.EVT_CHAR_HOOK, self._on_key)

    def _on_key(self, event: wx.KeyEvent) -> None:
        """Handle key events."""
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.Close()
        else:
            event.Skip()

    def _add_welcome_message(self) -> None:
        """Add initial welcome message to the chat."""
        location = self.app.config_manager.get_current_location() if self.app.config_manager else None
        loc_name = location.name if location else "your area"

        welcome = (
            f"Welcome to WeatherChat! I can help you understand the weather "
            f"conditions for {loc_name}. Ask me anything about the current "
            f"weather, forecast, what to wear, or how conditions might affect "
            f"your plans."
        )
        self._append_to_display("WeatherChat", welcome)

    def _append_to_display(self, speaker: str, text: str) -> None:
        """Append a message to the chat display."""
        timestamp = datetime.now().strftime("%I:%M %p")
        formatted = f"[{timestamp}] {speaker}:\n{text}\n\n"
        self.history_display.AppendText(formatted)
        # Scroll to bottom
        self.history_display.ShowPosition(self.history_display.GetLastPosition())

    def _set_status(self, text: str) -> None:
        """Update the status label."""
        self.status_label.SetLabel(text)

    def _set_generating(self, generating: bool) -> None:
        """Toggle generating state."""
        self._is_generating = generating
        self.send_button.Enable(not generating)
        self.input_ctrl.Enable(not generating)
        if generating:
            self._set_status("Thinking...")
        else:
            self._set_status("")
            self.input_ctrl.SetFocus()

    def _on_send(self, event: wx.Event) -> None:
        """Handle send button or Enter key."""
        message = self.input_ctrl.GetValue().strip()
        if not message or self._is_generating:
            return

        self.input_ctrl.SetValue("")
        self._append_to_display("You", message)

        # Add to conversation history
        self._conversation.append({"role": "user", "content": message})

        # Trim conversation if too long
        if len(self._conversation) > MAX_CONTEXT_TURNS * 2:
            self._conversation = self._conversation[-(MAX_CONTEXT_TURNS * 2):]

        self._set_generating(True)
        self._generate_response()

    def _generate_response(self) -> None:
        """Generate AI response in a background thread."""
        # Get config
        settings = self.app.config_manager.get_settings() if self.app.config_manager else None
        api_key = settings.openrouter_api_key if settings else ""
        model = settings.ai_model_preference if settings else ""

        if not api_key:
            wx.CallAfter(self._on_response_error, "No OpenRouter API key configured. Set one in Settings > AI Explanations.")
            return

        # Build weather context
        weather_context = _build_weather_context(self.app)

        # Build messages for API
        system_message = f"{SYSTEM_PROMPT}\n\nCurrent weather data:\n{weather_context}"

        messages = [{"role": "system", "content": system_message}]
        messages.extend(self._conversation)

        def do_generate():
            try:
                from openai import OpenAI

                client = OpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=api_key,
                    timeout=30.0,
                )

                effective_model = model if model else "meta-llama/llama-3.3-70b-instruct:free"

                response = client.chat.completions.create(
                    model=effective_model,
                    messages=messages,
                    max_tokens=2000,
                    extra_headers={
                        "HTTP-Referer": "https://accessiweather.orinks.net",
                        "X-Title": "AccessiWeather WeatherChat",
                    },
                )

                content = ""
                model_used = effective_model
                if response.choices:
                    content = response.choices[0].message.content or ""
                    model_used = response.model or effective_model

                if content.strip():
                    wx.CallAfter(self._on_response_received, content.strip(), model_used)
                else:
                    wx.CallAfter(self._on_response_error, "Received an empty response. Try again or switch models in Settings.")

            except Exception as e:
                error_msg = str(e)
                logger.error(f"WeatherChat generation error: {e}", exc_info=True)

                if "api key" in error_msg.lower() or "401" in error_msg:
                    friendly = "API key is invalid. Check Settings > AI Explanations."
                elif "429" in error_msg or "rate limit" in error_msg.lower():
                    friendly = "Rate limited. Wait a moment and try again, or switch to a different model."
                elif "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                    friendly = "Request timed out. The AI service may be busy, try again."
                else:
                    friendly = f"Error: {error_msg}"

                wx.CallAfter(self._on_response_error, friendly)

        thread = threading.Thread(target=do_generate, daemon=True)
        thread.start()

    def _on_response_received(self, text: str, model_used: str) -> None:
        """Handle successful AI response."""
        self._conversation.append({"role": "assistant", "content": text})
        self._append_to_display("WeatherChat", text)
        self._set_status(f"Model: {model_used}")
        self._set_generating(False)

    def _on_response_error(self, error: str) -> None:
        """Handle AI response error."""
        self._append_to_display("WeatherChat", f"Sorry, I couldn't respond: {error}")
        # Remove the last user message from conversation since we failed
        if self._conversation and self._conversation[-1]["role"] == "user":
            self._conversation.pop()
        self._set_generating(False)

    def _on_clear(self, event: wx.Event) -> None:
        """Clear chat history."""
        self._conversation.clear()
        self.history_display.SetValue("")
        self._set_status("")
        self._add_welcome_message()
        self.input_ctrl.SetFocus()

    def _on_copy(self, event: wx.Event) -> None:
        """Copy chat to clipboard."""
        text = self.history_display.GetValue()
        if text and wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(text))
            wx.TheClipboard.Close()
            self._set_status("Chat copied to clipboard.")

    def _on_close(self, event: wx.Event) -> None:
        """Handle dialog close."""
        self.EndModal(wx.ID_CLOSE)


def show_weather_chat_dialog(parent: wx.Window, app: AccessiWeatherApp) -> None:
    """Show the WeatherChat dialog."""
    dlg = WeatherChatDialog(parent, app)
    try:
        dlg.ShowModal()
    finally:
        dlg.Destroy()
