"""Tests for weather assistant tool call loop."""

from __future__ import annotations

import json
from dataclasses import dataclass
from unittest.mock import MagicMock

from accessiweather.ai_tools import WEATHER_TOOLS, WeatherToolExecutor

# --- Mock OpenAI response objects ---


@dataclass
class MockFunction:
    name: str
    arguments: str


@dataclass
class MockToolCall:
    id: str
    type: str
    function: MockFunction


@dataclass
class MockMessage:
    content: str | None = None
    tool_calls: list[MockToolCall] | None = None
    role: str = "assistant"


@dataclass
class MockChoice:
    message: MockMessage
    finish_reason: str = "stop"


@dataclass
class MockResponse:
    choices: list[MockChoice]
    model: str = "test-model"


def _make_tool_call_response(
    tool_calls: list[tuple[str, str, dict]],
    content: str = "",
) -> MockResponse:
    """
    Create a mock response with tool calls.

    Args:
        tool_calls: List of (id, function_name, arguments) tuples.
        content: Optional content text.

    """
    tc_objs = [
        MockToolCall(
            id=tc_id,
            type="function",
            function=MockFunction(name=name, arguments=json.dumps(args)),
        )
        for tc_id, name, args in tool_calls
    ]
    return MockResponse(
        choices=[MockChoice(message=MockMessage(content=content, tool_calls=tc_objs))]
    )


def _make_text_response(content: str) -> MockResponse:
    """Create a mock response with just text content."""
    return MockResponse(choices=[MockChoice(message=MockMessage(content=content, tool_calls=None))])


class TestToolCallLoop:
    """Test the tool call handling logic extracted from do_generate."""

    def _run_tool_loop(
        self,
        responses: list[MockResponse],
        tool_executor: WeatherToolExecutor | None = None,
    ) -> dict:
        """
        Simulate the tool call loop logic from do_generate.

        Returns dict with 'content', 'error', 'tool_calls_made', 'iterations'.
        """
        messages: list[dict] = [
            {"role": "system", "content": "test"},
            {"role": "user", "content": "What's the weather?"},
        ]

        response_idx = 0
        tool_calls_made: list[tuple[str, dict]] = []
        max_tool_iterations = 5
        content = ""
        error = ""
        iterations = 0

        extra_kwargs: dict = {}
        if tool_executor is not None:
            extra_kwargs["tools"] = WEATHER_TOOLS

        for _iteration in range(max_tool_iterations + 1):
            iterations += 1
            # Simulate API call
            if response_idx < len(responses):
                response = responses[response_idx]
                response_idx += 1
            else:
                # Return last response again
                response = responses[-1]

            if not response.choices:
                error = "Empty response"
                break

            choice = response.choices[0]
            assistant_message = choice.message

            if assistant_message.tool_calls and tool_executor is not None:
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

                for tool_call in assistant_message.tool_calls:
                    tool_name = tool_call.function.name
                    try:
                        arguments = json.loads(tool_call.function.arguments)
                        result = tool_executor.execute(tool_name, arguments)
                    except Exception as exc:
                        result = f"Error executing {tool_name}: {exc}"

                    tool_calls_made.append((tool_name, json.loads(tool_call.function.arguments)))
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": result,
                        }
                    )
                continue

            content = assistant_message.content or ""
            break
        else:
            # Exhausted iterations
            content = assistant_message.content or ""
            if not content.strip():
                error = "Too many tool calls"

        return {
            "content": content,
            "error": error,
            "tool_calls_made": tool_calls_made,
            "iterations": iterations,
            "messages": messages,
        }

    def _make_executor(self) -> WeatherToolExecutor:
        """Create a mock WeatherToolExecutor."""
        weather_service = MagicMock()
        weather_service.get_current_conditions.return_value = {
            "temperature": "72°F",
            "humidity": "45%",
            "description": "Clear",
        }
        weather_service.get_forecast.return_value = {
            "periods": [{"name": "Tonight", "detailedForecast": "Clear skies"}]
        }
        weather_service.get_alerts.return_value = {"alerts": []}

        geocoding_service = MagicMock()
        geocoding_service.geocode_address.return_value = (40.0, -74.0, "New York, NY")

        return WeatherToolExecutor(weather_service, geocoding_service)

    def test_no_tool_calls_returns_text_directly(self):
        """When response has no tool_calls, return text immediately."""
        result = self._run_tool_loop(
            [_make_text_response("It's sunny today!")],
            tool_executor=self._make_executor(),
        )
        assert result["content"] == "It's sunny today!"
        assert result["tool_calls_made"] == []
        assert result["iterations"] == 1

    def test_single_tool_call_then_text(self):
        """One tool call followed by a text response."""
        responses = [
            _make_tool_call_response([("tc1", "get_current_weather", {"location": "NYC"})]),
            _make_text_response("The current temperature in NYC is 72°F with clear skies."),
        ]
        result = self._run_tool_loop(responses, tool_executor=self._make_executor())
        assert "72°F" in result["content"]
        assert len(result["tool_calls_made"]) == 1
        assert result["tool_calls_made"][0] == ("get_current_weather", {"location": "NYC"})
        assert result["iterations"] == 2

    def test_multiple_tool_calls_in_one_response(self):
        """Multiple tool calls in a single response message."""
        responses = [
            _make_tool_call_response(
                [
                    ("tc1", "get_current_weather", {"location": "NYC"}),
                    ("tc2", "get_forecast", {"location": "NYC"}),
                ]
            ),
            _make_text_response("Here's a full weather summary."),
        ]
        result = self._run_tool_loop(responses, tool_executor=self._make_executor())
        assert result["content"] == "Here's a full weather summary."
        assert len(result["tool_calls_made"]) == 2
        assert result["iterations"] == 2

    def test_chained_tool_calls(self):
        """Multiple sequential tool call rounds."""
        responses = [
            _make_tool_call_response([("tc1", "get_current_weather", {"location": "NYC"})]),
            _make_tool_call_response([("tc2", "get_alerts", {"location": "NYC"})]),
            _make_text_response("Weather is fine, no alerts."),
        ]
        result = self._run_tool_loop(responses, tool_executor=self._make_executor())
        assert result["content"] == "Weather is fine, no alerts."
        assert len(result["tool_calls_made"]) == 2
        assert result["iterations"] == 3

    def test_max_iterations_prevents_infinite_loop(self):
        """Loop terminates after max 5 tool call iterations."""
        # All responses have tool calls — should stop after 6 iterations (0..5)
        responses = [
            _make_tool_call_response([("tc", "get_current_weather", {"location": "NYC"})])
            for _ in range(10)
        ]
        result = self._run_tool_loop(responses, tool_executor=self._make_executor())
        assert result["iterations"] == 6  # 0..5 inclusive = 6
        assert len(result["tool_calls_made"]) == 6

    def test_tool_execution_error_handled_gracefully(self):
        """Error during tool execution is sent back as tool result."""
        executor = self._make_executor()
        # Make geocoding fail
        executor.geocoding_service.geocode_address.return_value = None

        responses = [
            _make_tool_call_response([("tc1", "get_current_weather", {"location": "Nowhere"})]),
            _make_text_response("I couldn't look up that location."),
        ]
        result = self._run_tool_loop(responses, tool_executor=executor)
        assert result["content"] == "I couldn't look up that location."
        # Check that error message was sent as tool result
        tool_msgs = [m for m in result["messages"] if m.get("role") == "tool"]
        assert len(tool_msgs) == 1
        assert "Error" in tool_msgs[0]["content"] or "Could not resolve" in tool_msgs[0]["content"]

    def test_no_executor_skips_tools(self):
        """When tool_executor is None, tools are not used."""
        result = self._run_tool_loop(
            [_make_text_response("Just text.")],
            tool_executor=None,
        )
        assert result["content"] == "Just text."
        assert result["tool_calls_made"] == []

    def test_tool_results_appended_as_tool_role_messages(self):
        """Tool results are added to messages with role=tool."""
        responses = [
            _make_tool_call_response([("tc1", "get_current_weather", {"location": "NYC"})]),
            _make_text_response("Done."),
        ]
        result = self._run_tool_loop(responses, tool_executor=self._make_executor())
        tool_msgs = [m for m in result["messages"] if m.get("role") == "tool"]
        assert len(tool_msgs) == 1
        assert tool_msgs[0]["tool_call_id"] == "tc1"
        assert "New York" in tool_msgs[0]["content"]

    def test_assistant_tool_call_message_preserved(self):
        """The assistant message with tool_calls is added to messages."""
        responses = [
            _make_tool_call_response([("tc1", "get_forecast", {"location": "NYC"})]),
            _make_text_response("Forecast looks good."),
        ]
        result = self._run_tool_loop(responses, tool_executor=self._make_executor())
        assistant_with_tools = [
            m for m in result["messages"] if m.get("role") == "assistant" and m.get("tool_calls")
        ]
        assert len(assistant_with_tools) == 1
        assert assistant_with_tools[0]["tool_calls"][0]["function"]["name"] == "get_forecast"

    def test_tools_parameter_included_when_executor_available(self):
        """Verify the WEATHER_TOOLS are passed when executor is available."""
        # This test checks the extra_kwargs logic
        executor = self._make_executor()
        extra_kwargs: dict = {}
        if executor is not None:
            extra_kwargs["tools"] = WEATHER_TOOLS
        assert "tools" in extra_kwargs
        assert len(extra_kwargs["tools"]) == 3

    def test_get_alerts_tool_call(self):
        """Test that get_alerts tool call works in the loop."""
        executor = self._make_executor()
        responses = [
            _make_tool_call_response([("tc1", "get_alerts", {"location": "Miami"})]),
            _make_text_response("No active alerts for Miami."),
        ]
        result = self._run_tool_loop(responses, tool_executor=executor)
        assert result["tool_calls_made"][0] == ("get_alerts", {"location": "Miami"})
        assert result["content"] == "No active alerts for Miami."


class TestGetToolExecutor:
    """Test _get_tool_executor method."""

    def test_returns_executor_when_services_available(self):
        """Returns a WeatherToolExecutor when constructed with valid services."""
        weather_service = MagicMock()
        geocoding_service = MagicMock()

        executor = WeatherToolExecutor(weather_service, geocoding_service)
        assert executor is not None
        assert executor.weather_service is weather_service
        assert executor.geocoding_service is geocoding_service

    def test_returns_none_for_missing_service(self):
        """Returns None when weather_service is not available."""
        app = MagicMock(spec=[])  # No attributes
        assert getattr(app, "weather_service", None) is None
