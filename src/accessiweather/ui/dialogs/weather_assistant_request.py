"""Bounded assistant tool conversation with live-data grounding."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from ...ai_explainer_models import MODEL_REFUSAL_MESSAGE, is_model_refusal
from ...ai_provider import RequestDeadline


class AssistantRequestError(Exception):
    """A user-facing failure to complete a grounded answer."""


def needs_live_weather(message: str) -> bool:
    """Identify concrete weather lookups without forcing tools for conceptual chat."""
    text = message.lower().strip()
    live_cue = re.search(
        r"\b(now|today|tomorrow|tonight|currently|current|this week|next week)\b", text
    )
    if not live_cue and re.search(
        r"\b(explain|define|meaning|how does|how do|why does|what is a)\b", text
    ):
        return False
    return bool(
        re.search(
            r"\b(weather|forecast|alerts?|warnings?|advisories|advisory|temperature|rain|raining|snow|snowing|wind|windy|humidity|uv|outlook|conditions)\b",
            text,
        )
    )


@dataclass
class AssistantAnswer:
    """Completed text and the complete protocol history including tool results."""

    text: str
    model: str
    messages: list[dict]


_LOCATION_WEATHER_TOOLS = {
    "get_current_weather",
    "get_forecast",
    "get_hourly_forecast",
    "get_alerts",
    "query_open_meteo",
    "get_area_forecast_discussion",
}


def _explicitly_requested_location(user_text: str, tool_location: str, selected: str) -> bool:
    """Allow a different place only when the user's question identifies it."""
    text = user_text.casefold()
    requested = tool_location.strip().casefold()
    current = selected.strip().casefold()
    if requested == current:
        return True
    if requested and requested in text:
        return True
    requested_city = requested.split(",", 1)[0].strip()
    current_city = current.split(",", 1)[0].strip()
    return bool(
        requested_city != current_city and re.search(rf"\b{re.escape(requested_city)}\b", text)
    )


def run_assistant_request(
    client, model, messages, executor, options, *, selected_location=None, max_tool_rounds=5
):
    """Run real completion/tool turns, refusing empty promises or unbounded calls."""
    history = list(messages)
    latest = next((m.get("content", "") for m in reversed(history) if m["role"] == "user"), "")
    require_lookup = needs_live_weather(latest) and executor is not None
    all_tools = options.get("tools", [])
    read_tools = [t for t in all_tools if t["function"]["name"] in _LOCATION_WEATHER_TOOLS]
    if require_lookup and re.search(r"\b(alerts?|warnings?|advisories|advisory)\b", latest, re.I):
        alert_tools = [t for t in read_tools if t["function"]["name"] == "get_alerts"]
        if alert_tools:
            read_tools = alert_tools
    read_tools_by_name = {t["function"]["name"] for t in read_tools}
    tool_rounds = 0
    retried = False
    lookup_completed = False
    alert_result_has_alerts = False
    while True:
        request_options = dict(options)
        if require_lookup and tool_rounds == 0 and read_tools:
            request_options.update(tools=read_tools, tool_choice="required")
        with RequestDeadline(client):
            response = client.chat.completions.create(
                model=model,
                messages=history,
                max_tokens=2000,
                extra_headers={
                    "HTTP-Referer": "https://accessiweather.orinks.net",
                    "X-Title": "AccessiWeather Weather Assistant",
                },
                **request_options,
            )
        if not response.choices:
            raise AssistantRequestError(
                "Received an empty response. Try again or switch models in Settings."
            )
        reply = response.choices[0].message
        calls = reply.tool_calls or []
        if calls:
            if executor is None or tool_rounds >= max_tool_rounds:
                raise AssistantRequestError(
                    "The assistant could not finish its weather lookup. Please try a simpler question."
                )
            history.append(
                {
                    "role": "assistant",
                    "content": reply.content or "",
                    "tool_calls": [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {
                                "name": call.function.name,
                                "arguments": call.function.arguments,
                            },
                        }
                        for call in calls
                    ],
                }
            )
            allowed = {t["function"]["name"] for t in request_options.get("tools", [])}
            for call in calls:
                try:
                    arguments = json.loads(call.function.arguments)
                    if call.function.name not in allowed or not isinstance(arguments, dict):
                        result = "Error: this tool call is not available for this request."
                    else:
                        if selected_location and call.function.name in _LOCATION_WEATHER_TOOLS:
                            requested = arguments.get("location", "")
                            if not isinstance(requested, str) or not _explicitly_requested_location(
                                latest, requested, selected_location
                            ):
                                arguments["location"] = selected_location
                        result = executor.execute(call.function.name, arguments)
                        if call.function.name in read_tools_by_name and not result.startswith(
                            "Error"
                        ):
                            lookup_completed = True
                        if call.function.name == "get_alerts" and not result.startswith("Error:"):
                            alert_result_has_alerts |= bool(
                                "- " in result and "No active alerts" not in result
                            )
                except Exception:
                    result = "Error: the weather lookup failed. Do not report unavailable data as verified conditions."
                history.append({"role": "tool", "tool_call_id": call.id, "content": result})
            tool_rounds += 1
            continue
        if require_lookup and not lookup_completed and read_tools:
            if tool_rounds:
                raise AssistantRequestError(
                    "The weather lookup did not return usable data. Please try again."
                )
            if retried:
                raise AssistantRequestError(
                    "The model did not perform the requested weather lookup. Try another model."
                )
            retried = True
            continue
        content = (reply.content or "").strip()
        if not content:
            raise AssistantRequestError(
                "Received an empty response. Try again or switch models in Settings."
            )
        if is_model_refusal(content):
            raise AssistantRequestError(MODEL_REFUSAL_MESSAGE)
        if alert_result_has_alerts and re.search(
            r"\b(?:no|zero|without)\s+(?:active\s+)?(?:weather\s+)?alerts?\b",
            content,
            re.I,
        ):
            raise AssistantRequestError(
                "The model contradicted the alert lookup. Please try again or use the app's alert list."
            )
        if selected_location and "," in selected_location:
            city, region = (part.strip() for part in selected_location.rsplit(",", 1))
            if (
                len(region) == 2
                and re.search(
                    rf"\b{re.escape(city)},\s*(?!{re.escape(region)}\b)[A-Z]{{2}}\b",
                    content,
                    re.I,
                )
                and not re.search(rf"\b{re.escape(city)},\s*[A-Z]{{2}}\b", latest, re.I)
            ):
                raise AssistantRequestError(
                    "The model named a different place. Please try again or check the selected location."
                )
        history.append({"role": "assistant", "content": content})
        return AssistantAnswer(content, response.model or model, history)
