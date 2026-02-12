"""
Weather Assistant dialog — conversational AI weather assistant.

Phase 2: Multi-turn chat with function calling for weather lookups.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime
from typing import TYPE_CHECKING

import wx

from ...ai_tools import WeatherToolExecutor, get_tools_for_message
from ...screen_reader import ScreenReaderAnnouncer

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
            text = insight.summary or f"{insight.metric}: {insight.direction}"
            if insight.change is not None and insight.unit:
                text += f" ({insight.change:+.1f}{insight.unit})"
            parts.append(f"  - {text}")

    return "\n".join(parts)


SYSTEM_PROMPT = (
    "You are Weather Assistant, a friendly and knowledgeable weather assistant built into "
    "AccessiWeather. You help users understand weather conditions in plain, accessible "
    "language optimized for screen reader users.\n\n"
    "You have access to live weather tools that can fetch current conditions, forecasts, "
    "and active alerts for any location. The available tools are:\n"
    "- get_current_weather: Get current weather conditions for a location\n"
    "- get_forecast: Get the weather forecast for a location\n"
    "- get_hourly_forecast: Get hourly forecast (great for specific time questions)\n"
    "- get_alerts: Get active weather alerts for a location\n"
    "- search_location: Search for a location by name or ZIP code\n"
    "- add_location: Save a location to the user's locations list\n"
    "- list_locations: Show all saved locations\n"
    "- query_open_meteo: Custom Open-Meteo API query for any weather variable "
    "(soil temp, UV, cloud cover, dew point, snow depth, visibility, etc.)\n"
    "- get_area_forecast_discussion: Local NWS forecaster's detailed discussion\n"
    "- get_wpc_discussion: National WPC short range forecast discussion\n"
    "- get_spc_outlook: Storm Prediction Center severe weather outlook\n\n"
    "Use the provided tools to fetch weather data when users ask about specific locations "
    "or conditions not in the current context. You can call multiple tools if needed to "
    "give a complete answer. Use search_location when a place name is ambiguous. "
    "When adding locations, first resolve coordinates with search_location, then use "
    "add_location with the resolved name and coordinates.\n\n"
    "Guidelines:\n"
    "- Be conversational and helpful\n"
    "- Explain weather in practical terms (what to wear, activity suitability, etc.)\n"
    "- Avoid visual-only descriptions\n"
    "- When referencing data, use the weather context provided\n"
    "- Keep responses concise but thorough\n"
    "- Respond in plain text only — no markdown formatting\n"
    "- Do not repeat information the user can already see\n\n"
    "IMPORTANT: Respond in plain text. No bold, italic, headers, or bullet markers."
)


class WeatherAssistantDialog(wx.Dialog):
    """Multi-turn conversational weather chat dialog."""

    def __init__(
        self,
        parent: wx.Window,
        app: AccessiWeatherApp,
        title: str = "Weather Assistant",
    ):
        """
        Initialize the Weather Assistant dialog.

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
        self._announcer = ScreenReaderAnnouncer()

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
        location = (
            self.app.config_manager.get_current_location() if self.app.config_manager else None
        )
        loc_name = location.name if location else "your area"

        welcome = (
            f"Welcome to Weather Assistant! I can help you understand the weather "
            f"conditions for {loc_name}. Ask me anything about the current "
            f"weather, forecast, what to wear, or how conditions might affect "
            f"your plans."
        )
        self._append_to_display("Weather Assistant", welcome)
        self._announcer.announce(f"Weather Assistant: {welcome}")

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
        # Keep input_ctrl always enabled so screen readers don't lose focus.
        # The _is_generating flag prevents sends during generation.
        if generating:
            self._set_status("Thinking...")
        else:
            self._set_status("Ready")
            self.input_ctrl.SetFocus()

    def _on_send(self, event: wx.Event) -> None:
        """Handle send button or Enter key."""
        message = self.input_ctrl.GetValue().strip()
        if not message or self._is_generating:
            return

        self.input_ctrl.SetValue("")
        self._append_to_display("You", message)
        self._announcer.announce(f"You: {message}")

        # Add to conversation history
        self._conversation.append({"role": "user", "content": message})

        # Trim conversation if too long
        if len(self._conversation) > MAX_CONTEXT_TURNS * 2:
            self._conversation = self._conversation[-(MAX_CONTEXT_TURNS * 2) :]

        self._set_generating(True)
        self._generate_response()

    def _get_tool_executor(self) -> WeatherToolExecutor | None:
        """
        Create a WeatherToolExecutor from the app's services.

        Returns:
            A WeatherToolExecutor, or None if required services are unavailable.

        """
        try:
            import asyncio

            from ...api_client import NoaaApiClient
            from ...geocoding import GeocodingService
            from ...models.location import Location
            from ...openmeteo_client import OpenMeteoApiClient
            from ...visual_crossing_client import VisualCrossingClient

            class _CombinedWeatherClient:
                """Bridges NWS, Open-Meteo, and Visual Crossing for tool executor."""

                def __init__(self, vc_api_key: str = ""):
                    self.nws = NoaaApiClient()
                    self.openmeteo = OpenMeteoApiClient()
                    self.vc: VisualCrossingClient | None = None
                    if vc_api_key:
                        self.vc = VisualCrossingClient(api_key=vc_api_key)

                def _run_async(self, coro):
                    """Run an async coroutine from sync context."""
                    try:
                        loop = asyncio.get_running_loop()
                    except RuntimeError:
                        loop = None
                    if loop and loop.is_running():
                        # We're in a thread; create a new loop
                        return asyncio.run(coro)
                    return asyncio.run(coro)

                def _make_location(self, lat, lon):
                    return Location(name="", latitude=lat, longitude=lon)

                def get_current_conditions(self, lat, lon, **kw):
                    try:
                        return self.nws.get_current_conditions(lat, lon, **kw)
                    except Exception:
                        pass
                    # Fall back to Open-Meteo (global, free)
                    return self.openmeteo.get_current_weather(lat, lon)

                def get_forecast(self, lat, lon, **kw):
                    try:
                        return self.nws.get_forecast(lat, lon, **kw)
                    except Exception:
                        pass
                    return self.openmeteo.get_forecast(lat, lon)

                def get_hourly_forecast(self, lat, lon, **kw):
                    try:
                        return self.nws.get_hourly_forecast(lat, lon, **kw)
                    except Exception:
                        pass
                    return self.openmeteo.get_hourly_forecast(lat, lon)

                def get_alerts(self, lat, lon, **kw):
                    try:
                        return self.nws.get_alerts(lat, lon, **kw)
                    except Exception:
                        pass
                    # Visual Crossing has global alerts
                    if self.vc:
                        try:
                            loc = self._make_location(lat, lon)
                            result = self._run_async(self.vc.get_alerts(loc))
                            if result:
                                return result.to_dict() if hasattr(result, "to_dict") else result
                        except Exception:
                            pass
                    return {"features": []}

                def get_discussion(self, lat, lon, **kw):
                    return self.nws.get_discussion(lat, lon, **kw)

            config_manager = getattr(self.app, "config_manager", None)
            settings = config_manager.get_settings() if config_manager else None
            vc_key = settings.visual_crossing_api_key if settings else ""
            weather_client = _CombinedWeatherClient(vc_api_key=vc_key)
            geocoding_service = GeocodingService()
            return WeatherToolExecutor(
                weather_client, geocoding_service, config_manager=config_manager
            )
        except Exception:
            logger.debug("Could not create WeatherToolExecutor", exc_info=True)
            return None

    def _generate_response(self) -> None:
        """Generate AI response in a background thread."""
        # Get config
        settings = self.app.config_manager.get_settings() if self.app.config_manager else None
        api_key = settings.openrouter_api_key if settings else ""
        model = settings.ai_model_preference if settings else ""

        if not api_key:
            wx.CallAfter(
                self._on_response_error,
                "No OpenRouter API key configured. Set one in Settings > AI Explanations.",
            )
            return

        # Build weather context
        weather_context = _build_weather_context(self.app)

        # Build messages for API
        system_message = f"{SYSTEM_PROMPT}\n\nCurrent weather data:\n{weather_context}"

        messages: list[dict] = [{"role": "system", "content": system_message}]
        messages.extend(self._conversation)

        tool_executor = self._get_tool_executor()
        logger.info("Tool executor: %s", "available" if tool_executor else "NONE")

        def do_generate():
            try:
                from openai import OpenAI

                client = OpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=api_key,
                    timeout=30.0,
                )

                effective_model = model if model else "meta-llama/llama-3.3-70b-instruct:free"

                # Models with reliable function calling on free tier (in preference order)
                TOOL_CAPABLE_MODELS = [
                    "qwen/qwen3-coder:free",
                    "mistralai/mistral-small-3.1-24b-instruct:free",
                    "meta-llama/llama-3.3-70b-instruct:free",
                ]

                extra_kwargs: dict = {}
                use_tool_fallback = False
                if tool_executor is not None:
                    # Get last user message for tool selection
                    user_msg = ""
                    for msg in reversed(messages):
                        if msg.get("role") == "user":
                            user_msg = msg.get("content", "")
                            break
                    tools = get_tools_for_message(user_msg)
                    if tools:
                        extra_kwargs["tools"] = tools
                        # When tools are present, use a model known for
                        # reliable function calling if user hasn't picked
                        # a specific model (free router doesn't guarantee
                        # tool support)
                        # Use whatever the user selected; only flag
                        # fallback so rate-limit retry logic can kick in
                        # for free models
                        free_routers = {
                            "openrouter/auto",
                            "openrouter/free",
                            "meta-llama/llama-3.3-70b-instruct:free",
                        }
                        if effective_model in free_routers:
                            use_tool_fallback = True
                        logger.info(
                            "Tools enabled: %d tools, model: %s",
                            len(tools),
                            effective_model,
                        )

                max_tool_iterations = 5
                for _iteration in range(max_tool_iterations + 1):
                    # Try the API call, with fallback models on rate limit
                    last_error = None
                    for _model_attempt in range(3):
                        try:
                            response = client.chat.completions.create(
                                model=effective_model,
                                messages=messages,
                                max_tokens=2000,
                                extra_headers={
                                    "HTTP-Referer": "https://accessiweather.orinks.net",
                                    "X-Title": "AccessiWeather Weather Assistant",
                                },
                                **extra_kwargs,
                            )
                            last_error = None
                            break
                        except Exception as api_err:
                            err_str = str(api_err).lower()
                            is_retryable = (
                                "429" in str(api_err)
                                or "rate" in err_str
                                or "400" in str(api_err)
                                or "tool_calls" in err_str
                                or "provider returned error" in err_str
                            )
                            if is_retryable and use_tool_fallback:
                                # Try next model in the fallback chain
                                try:
                                    idx = TOOL_CAPABLE_MODELS.index(effective_model)
                                    if idx + 1 < len(TOOL_CAPABLE_MODELS):
                                        effective_model = TOOL_CAPABLE_MODELS[idx + 1]
                                        logger.info(
                                            "Provider error, falling back to %s", effective_model
                                        )
                                        last_error = api_err
                                        continue
                                except ValueError:
                                    pass
                            raise
                    if last_error is not None:
                        raise last_error

                    model_used = response.model or effective_model

                    if not response.choices:
                        if extra_kwargs.get("tools") and use_tool_fallback:
                            # Model returned empty with tools; retry without
                            logger.warning(
                                "Empty response with tools on %s, retrying without tools",
                                effective_model,
                            )
                            extra_kwargs.pop("tools", None)
                            continue
                        wx.CallAfter(
                            self._on_response_error,
                            "Received an empty response. Try again or switch models in Settings.",
                        )
                        return

                    choice = response.choices[0]
                    assistant_message = choice.message

                    # Check for tool calls
                    logger.info(
                        "Response finish_reason=%s, tool_calls=%s",
                        choice.finish_reason,
                        bool(assistant_message.tool_calls),
                    )
                    if assistant_message.tool_calls and tool_executor is not None:
                        # Append assistant message with tool calls to messages
                        tool_call_msg: dict = {
                            "role": "assistant",
                            "content": assistant_message.content or "",
                            "tool_calls": [
                                {
                                    "id": tc.id,
                                    "type": "function",
                                    "function": {
                                        "name": tc.function.name,
                                        "arguments": tc.function.arguments,
                                    },
                                }
                                for tc in assistant_message.tool_calls
                            ],
                        }
                        messages.append(tool_call_msg)

                        # Execute each tool call
                        for tool_call in assistant_message.tool_calls:
                            tool_name = tool_call.function.name
                            try:
                                arguments = json.loads(tool_call.function.arguments)
                                result = tool_executor.execute(tool_name, arguments)
                            except Exception as exc:
                                logger.warning(
                                    "Tool call %s failed: %s", tool_name, exc, exc_info=True
                                )
                                result = f"Error executing {tool_name}: {exc}"

                            messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tool_call.id,
                                    "content": result,
                                }
                            )

                        # Continue loop to get next response
                        continue

                    # No tool calls — we have the final text response
                    content = assistant_message.content or ""
                    if content.strip():
                        wx.CallAfter(self._on_response_received, content.strip(), model_used)
                    else:
                        wx.CallAfter(
                            self._on_response_error,
                            "Received an empty response. Try again or switch models in Settings.",
                        )
                    return

                # Exhausted max iterations — use whatever content we have
                fallback = assistant_message.content or "" if assistant_message else ""
                if fallback.strip():
                    wx.CallAfter(self._on_response_received, fallback.strip(), model_used)
                else:
                    wx.CallAfter(
                        self._on_response_error,
                        "The assistant made too many tool calls. Please try a simpler question.",
                    )

            except Exception as e:
                error_msg = str(e)
                logger.error(f"Weather Assistant generation error: {e}", exc_info=True)

                if "api key" in error_msg.lower() or "401" in error_msg:
                    friendly = "API key is invalid. Check Settings > AI Explanations."
                elif "429" in error_msg or "rate limit" in error_msg.lower():
                    friendly = (
                        "Rate limited. Wait a moment and try again, or switch to a different model."
                    )
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
        self._append_to_display("Weather Assistant", text)
        self._announcer.announce(f"Weather Assistant: {text}")
        self._set_status(f"Model: {model_used}")
        self._set_generating(False)

    def _on_response_error(self, error: str) -> None:
        """Handle AI response error."""
        error_message = f"Sorry, I couldn't respond: {error}"
        self._append_to_display("Weather Assistant", error_message)
        self._announcer.announce(f"Weather Assistant: {error_message}")
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
        self._announcer.shutdown()
        self.EndModal(wx.ID_CLOSE)


def show_weather_assistant_dialog(parent: wx.Window, app: AccessiWeatherApp) -> None:
    """Show the Weather Assistant dialog."""
    dlg = WeatherAssistantDialog(parent, app)
    try:
        dlg.ShowModal()
    finally:
        dlg.Destroy()
