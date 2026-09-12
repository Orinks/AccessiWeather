"""
Weather Assistant dialog — conversational AI weather assistant.

Phase 2: Multi-turn chat with function calling for weather lookups.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import TYPE_CHECKING

import wx

from ...ai_provider import (
    DEFAULT_VENICE_MODEL,
    create_venice_client,
    venice_error,
    venice_request_options,
)
from ...ai_settings import selected_provider
from ...ai_tools import WeatherToolExecutor, get_tools_for_message
from ...screen_reader import ScreenReaderAnnouncer
from .async_guard import guard_destroyed
from .weather_assistant_context import build_weather_context as _build_weather_context
from .weather_assistant_prompt import SYSTEM_PROMPT
from .weather_assistant_request import AssistantRequestError, run_assistant_request
from .weather_assistant_widgets import create_weather_assistant_widgets

if TYPE_CHECKING:
    from ...app import AccessiWeatherApp

logger = logging.getLogger(__name__)

# Maximum conversation turns to keep in context
MAX_CONTEXT_TURNS = 20
DEFAULT_WEATHER_ASSISTANT_MODEL = "openrouter/free"


def _build_completion_request(
    configured_model: str,
    messages: list[dict],
    tool_executor: WeatherToolExecutor | None,
) -> tuple[str, dict]:
    """Choose the model and optional tools for an assistant completion."""
    effective_model = configured_model or DEFAULT_WEATHER_ASSISTANT_MODEL
    extra_kwargs: dict = {}

    if tool_executor is None:
        return effective_model, extra_kwargs

    user_msg = ""
    for message in reversed(messages):
        if message.get("role") == "user":
            user_msg = message.get("content", "")
            break

    tools = get_tools_for_message(user_msg)
    if tools:
        extra_kwargs["tools"] = tools

    return effective_model, extra_kwargs


class WeatherAssistantDialog(wx.Dialog):
    """Multi-turn conversational weather chat dialog."""

    def __init__(
        self,
        parent: wx.Window,
        app: AccessiWeatherApp,
        title: str = "Weather Assistant",
    ):
        """Initialize the Weather Assistant dialog."""
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
        self.input_ctrl.SetFocus()

    def _create_widgets(self) -> None:
        """Create all UI widgets."""
        create_weather_assistant_widgets(self)

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
        user_turns = [i for i, item in enumerate(self._conversation) if item["role"] == "user"]
        if len(user_turns) > MAX_CONTEXT_TURNS:
            self._conversation = self._conversation[user_turns[-MAX_CONTEXT_TURNS] :]

        self._set_generating(True)
        self._generate_response()

    def _get_tool_executor(self) -> WeatherToolExecutor | None:
        """Create a WeatherToolExecutor from the app's services."""
        try:
            import asyncio

            from ...api_client import NoaaApiClient
            from ...geocoding import GeocodingService
            from ...openmeteo_client import OpenMeteoApiClient

            class _CombinedWeatherClient:
                """Bridges NWS and Open-Meteo for tool executor."""

                def __init__(self):
                    self.nws = NoaaApiClient()
                    self.openmeteo = OpenMeteoApiClient()

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

                def get_current_conditions(self, lat, lon, **kw):
                    try:
                        return self.nws.get_current_conditions(lat, lon, **kw)
                    except Exception:
                        pass
                    # Fall back to Open-Meteo (global, free)
                    return self.openmeteo.get_current_weather(lat, lon)

                def get_forecast(self, lat, lon, **kw):
                    days = kw.pop("days", 7)
                    try:
                        return self.nws.get_forecast(lat, lon, **kw)
                    except Exception:
                        pass
                    return self.openmeteo.get_forecast(lat, lon, days=days)

                def get_hourly_forecast(self, lat, lon, **kw):
                    try:
                        return self.nws.get_hourly_forecast(lat, lon, **kw)
                    except Exception:
                        pass
                    return self.openmeteo.get_hourly_forecast(lat, lon)

                def get_alerts(self, lat, lon, **kw):
                    try:
                        return self.nws.get_alerts(lat, lon, **kw)
                    except Exception as error:
                        raise RuntimeError(
                            "Weather alerts could not be checked. Alert status is unknown."
                        ) from error

                def get_discussion(self, lat, lon, **kw):
                    return self.nws.get_discussion(lat, lon, **kw)

            config_manager = getattr(self.app, "config_manager", None)
            weather_client = _CombinedWeatherClient()
            geocoding_service = GeocodingService()
            location = config_manager.get_current_location() if config_manager else None
            return WeatherToolExecutor(
                weather_client,
                geocoding_service,
                config_manager=config_manager,
                default_lat=location.latitude if location else None,
                default_lon=location.longitude if location else None,
                default_name=location.name if location else None,
            )
        except Exception:
            logger.debug("Could not create WeatherToolExecutor", exc_info=True)
            return None

    def _generate_response(self) -> None:
        """Generate AI response in a background thread."""
        # Get config
        settings = self.app.config_manager.get_settings() if self.app.config_manager else None
        provider = getattr(settings, "ai_provider", "openrouter")
        try:
            provider = selected_provider(settings)
        except Exception as error:
            wx.CallAfter(self._on_response_error, str(error))
            return
        is_venice = provider == "venice"
        api_key = (
            (settings.venice_api_key if is_venice else settings.openrouter_api_key)
            if settings
            else ""
        )
        model = (
            (settings.venice_model if is_venice else settings.ai_model_preference)
            if settings
            else ""
        )
        if is_venice:
            model = model or DEFAULT_VENICE_MODEL

        if not api_key:
            wx.CallAfter(
                self._on_response_error,
                f"No {'Venice' if is_venice else 'OpenRouter'} API key configured. Set one in Settings > AI Explanations.",
            )
            return

        # Build weather context
        weather_context = _build_weather_context(self.app)

        # Build messages for API
        custom_prompt = getattr(settings, "custom_system_prompt", None)
        prompt = (
            custom_prompt.strip()
            if isinstance(custom_prompt, str) and custom_prompt.strip()
            else SYSTEM_PROMPT
        )
        system_message = (
            f"{prompt}\n\nCurrent local time: {datetime.now().astimezone().isoformat()}"
            f"\nTreat weather observation timestamps as the time of that data, not as the current time."
            f"\n\nCurrent weather data:\n{weather_context}"
        )
        instructions = getattr(settings, "custom_instructions", None)
        if isinstance(instructions, str) and instructions.strip():
            system_message += f"\n\nAdditional instructions: {instructions.strip()}"

        messages: list[dict] = [{"role": "system", "content": system_message}]
        messages.extend(self._conversation)

        tool_executor = self._get_tool_executor()
        logger.info("Tool executor: %s", "available" if tool_executor else "NONE")

        def do_generate():
            try:
                from openai import OpenAI

                client = (
                    create_venice_client(api_key)
                    if is_venice
                    else OpenAI(
                        base_url="https://openrouter.ai/api/v1",
                        api_key=api_key,
                        timeout=30.0,
                    )
                )

                effective_model, extra_kwargs = _build_completion_request(
                    model,
                    messages,
                    tool_executor,
                )
                if is_venice:
                    extra_kwargs.update(venice_request_options())
                tools = extra_kwargs.get("tools", [])
                if tools:
                    logger.info(
                        "Tools enabled: %d tools, model: %s",
                        len(tools),
                        effective_model,
                    )

                answer = run_assistant_request(
                    client, effective_model, messages, tool_executor, extra_kwargs
                )
                wx.CallAfter(
                    self._on_response_received, answer.text, answer.model, answer.messages[1:]
                )

            except AssistantRequestError as error:
                wx.CallAfter(self._on_response_error, str(error))

            except Exception as e:
                if is_venice:
                    wx.CallAfter(self._on_response_error, str(venice_error(e)))
                    return
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

    @guard_destroyed
    def _on_response_received(
        self, text: str, model_used: str, conversation: list[dict] | None = None
    ) -> None:
        """Handle successful AI response."""
        if conversation is not None:
            self._conversation = conversation
        else:
            self._conversation.append({"role": "assistant", "content": text})
        self._append_to_display("Weather Assistant", text)
        self._announcer.announce(f"Weather Assistant: {text}")
        self._set_status(f"Model: {model_used}")
        self._set_generating(False)

    @guard_destroyed
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
