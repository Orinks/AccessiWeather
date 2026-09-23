"""Bounded assistant tool conversation with live-data grounding."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

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
            r"\b(weather|forecast|alerts?|warnings?|temperature|rain|raining|snow|snowing|wind|windy|humidity|uv|outlook|conditions)\b",
            text,
        )
    )


@dataclass
class AssistantAnswer:
    """Completed text and the complete protocol history including tool results."""

    text: str
    model: str
    messages: list[dict]


def run_assistant_request(client, model, messages, executor, options, *, max_tool_rounds=5):
    """Run real completion/tool turns, refusing empty promises or unbounded calls."""
    history = list(messages)
    latest = next((m.get("content", "") for m in reversed(history) if m["role"] == "user"), "")
    require_lookup = needs_live_weather(latest) and executor is not None
    all_tools = options.get("tools", [])
    read_tools = [t for t in all_tools if t["function"]["name"] != "add_location"]
    tool_rounds = 0
    retried = False
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
                        result = executor.execute(call.function.name, arguments)
                except Exception:
                    result = "Error: the weather lookup failed. Do not report unavailable data as verified conditions."
                history.append({"role": "tool", "tool_call_id": call.id, "content": result})
            tool_rounds += 1
            continue
        if require_lookup and tool_rounds == 0 and read_tools:
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
        history.append({"role": "assistant", "content": content})
        return AssistantAnswer(content, response.model or model, history)
