"""
Integration tests for the weather assistant tool call flow.

Tests the full loop: user message -> tool_call response -> tool execution ->
tool result -> final text response. Uses mock OpenAI client and mock services.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from unittest.mock import MagicMock

from accessiweather.ai_tools import WeatherToolExecutor

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
        tool_calls: List of (call_id, function_name, arguments_dict).
        content: Optional text content alongside tool calls.

    """
    return MockResponse(
        choices=[
            MockChoice(
                message=MockMessage(
                    content=content,
                    tool_calls=[
                        MockToolCall(
                            id=call_id,
                            type="function",
                            function=MockFunction(
                                name=name,
                                arguments=json.dumps(args),
                            ),
                        )
                        for call_id, name, args in tool_calls
                    ],
                ),
                finish_reason="tool_calls",
            )
        ]
    )


def _make_text_response(text: str) -> MockResponse:
    """Create a mock response with only text content."""
    return MockResponse(
        choices=[
            MockChoice(
                message=MockMessage(content=text, tool_calls=None),
                finish_reason="stop",
            )
        ]
    )


def _create_mock_services():
    """Create mock WeatherService and GeocodingService."""
    weather_service = MagicMock()
    geocoding_service = MagicMock()

    # geocode_address returns (lat, lon, display_name)
    geocoding_service.geocode_address.return_value = (40.7128, -74.0060, "New York, NY")

    # Mock weather data
    weather_service.get_current_conditions.return_value = {
        "temperature": 72,
        "temperatureUnit": "F",
        "shortForecast": "Partly Cloudy",
        "windSpeed": "10 mph",
        "windDirection": "NW",
        "relativeHumidity": {"value": 55},
    }

    weather_service.get_forecast.return_value = {
        "periods": [
            {
                "name": "Today",
                "temperature": 72,
                "temperatureUnit": "F",
                "shortForecast": "Partly Cloudy",
                "detailedForecast": "Partly cloudy with a high near 72.",
                "windSpeed": "10 mph",
                "windDirection": "NW",
            }
        ]
    }

    weather_service.get_alerts.return_value = {"alerts": []}

    return weather_service, geocoding_service


def _simulate_tool_call_loop(
    messages: list[dict],
    mock_responses: list[MockResponse],
    tool_executor: WeatherToolExecutor,
    max_iterations: int = 5,
) -> str:
    """
    Simulate the tool call loop from weather_assistant_dialog.do_generate.

    This mirrors the exact logic in the dialog's do_generate method.

    Returns:
        The final text response from the assistant.

    """
    response_index = 0

    for _iteration in range(max_iterations + 1):
        assert response_index < len(mock_responses), "Ran out of mock responses"
        response = mock_responses[response_index]
        response_index += 1

        if not response.choices:
            raise RuntimeError("Empty response")

        choice = response.choices[0]
        assistant_message = choice.message

        if assistant_message.tool_calls and tool_executor is not None:
            # Append assistant message with tool calls
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
                    result = f"Error executing {tool_name}: {exc}"

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result,
                    }
                )
            # Continue loop for next API call
            continue

        # No tool calls — final text response
        final_text = assistant_message.content or ""
        messages.append({"role": "assistant", "content": final_text})
        return final_text

    raise RuntimeError("Exceeded max tool iterations")


class TestFullToolCallFlow:
    """Integration tests for the complete tool call flow."""

    def test_single_tool_call_flow(self):
        """Test: user asks about weather -> tool call -> execute -> final response."""
        weather_service, geocoding_service = _create_mock_services()
        executor = WeatherToolExecutor(weather_service, geocoding_service)

        messages: list[dict] = [
            {"role": "system", "content": "You are a weather assistant."},
            {"role": "user", "content": "What's the weather in New York?"},
        ]

        # First response: AI calls get_current_weather
        # Second response: AI gives final text
        mock_responses = [
            _make_tool_call_response(
                [
                    ("call_001", "get_current_weather", {"location": "New York"}),
                ]
            ),
            _make_text_response(
                "The current weather in New York is 72°F and partly cloudy "
                "with northwest winds at 10 mph."
            ),
        ]

        final = _simulate_tool_call_loop(messages, mock_responses, executor)

        assert "72" in final
        assert "New York" in final

        # Verify conversation history structure
        roles = [m["role"] for m in messages]
        assert roles == ["system", "user", "assistant", "tool", "assistant"]

        # Verify tool call message
        tool_call_msg = messages[2]
        assert tool_call_msg["role"] == "assistant"
        assert len(tool_call_msg["tool_calls"]) == 1
        assert tool_call_msg["tool_calls"][0]["function"]["name"] == "get_current_weather"

        # Verify tool result message
        tool_result_msg = messages[3]
        assert tool_result_msg["role"] == "tool"
        assert tool_result_msg["tool_call_id"] == "call_001"
        assert len(tool_result_msg["content"]) > 0  # Has weather data

        # Verify geocoding was called
        geocoding_service.geocode_address.assert_called_once_with("New York")
        weather_service.get_current_conditions.assert_called_once()

    def test_multiple_tool_calls_flow(self):
        """Test: AI calls multiple tools in one response."""
        weather_service, geocoding_service = _create_mock_services()
        executor = WeatherToolExecutor(weather_service, geocoding_service)

        messages: list[dict] = [
            {"role": "system", "content": "You are a weather assistant."},
            {"role": "user", "content": "Give me weather and alerts for New York"},
        ]

        mock_responses = [
            _make_tool_call_response(
                [
                    ("call_001", "get_current_weather", {"location": "New York"}),
                    ("call_002", "get_alerts", {"location": "New York"}),
                ]
            ),
            _make_text_response("New York is 72°F and partly cloudy. No active weather alerts."),
        ]

        final = _simulate_tool_call_loop(messages, mock_responses, executor)

        assert "New York" in final

        # Should have: system, user, assistant(tool_calls), tool, tool, assistant(final)
        roles = [m["role"] for m in messages]
        assert roles == ["system", "user", "assistant", "tool", "tool", "assistant"]

        # Both tool results present
        tool_msgs = [m for m in messages if m["role"] == "tool"]
        assert len(tool_msgs) == 2
        assert tool_msgs[0]["tool_call_id"] == "call_001"
        assert tool_msgs[1]["tool_call_id"] == "call_002"

    def test_chained_tool_calls_flow(self):
        """Test: AI makes a tool call, then makes another tool call based on results."""
        weather_service, geocoding_service = _create_mock_services()
        executor = WeatherToolExecutor(weather_service, geocoding_service)

        messages: list[dict] = [
            {"role": "system", "content": "You are a weather assistant."},
            {"role": "user", "content": "What's the weather and forecast for NYC?"},
        ]

        mock_responses = [
            # First: get current weather
            _make_tool_call_response(
                [
                    ("call_001", "get_current_weather", {"location": "NYC"}),
                ]
            ),
            # Second: get forecast
            _make_tool_call_response(
                [
                    ("call_002", "get_forecast", {"location": "NYC"}),
                ]
            ),
            # Third: final text
            _make_text_response("NYC is currently 72°F. Today's forecast: partly cloudy."),
        ]

        final = _simulate_tool_call_loop(messages, mock_responses, executor)

        assert "NYC" in final

        # system, user, assistant(tc1), tool, assistant(tc2), tool, assistant(final)
        roles = [m["role"] for m in messages]
        assert roles == ["system", "user", "assistant", "tool", "assistant", "tool", "assistant"]

        # Verify both tool calls and results are in history
        tool_call_msgs = [m for m in messages if m["role"] == "assistant" and "tool_calls" in m]
        assert len(tool_call_msgs) == 2

        tool_result_msgs = [m for m in messages if m["role"] == "tool"]
        assert len(tool_result_msgs) == 2

    def test_no_tool_calls_direct_response(self):
        """Test: AI responds directly without tool calls (e.g., general question)."""
        weather_service, geocoding_service = _create_mock_services()
        executor = WeatherToolExecutor(weather_service, geocoding_service)

        messages: list[dict] = [
            {"role": "system", "content": "You are a weather assistant."},
            {"role": "user", "content": "What does humidity mean?"},
        ]

        mock_responses = [
            _make_text_response("Humidity measures the amount of water vapor in the air."),
        ]

        final = _simulate_tool_call_loop(messages, mock_responses, executor)

        assert "humidity" in final.lower()

        # No tool messages in history
        roles = [m["role"] for m in messages]
        assert roles == ["system", "user", "assistant"]
        assert not any(m["role"] == "tool" for m in messages)

    def test_tool_execution_error_in_flow(self):
        """Test: tool execution fails, error is sent back, AI recovers."""
        weather_service, geocoding_service = _create_mock_services()
        # Make geocoding fail
        geocoding_service.geocode_address.return_value = None
        executor = WeatherToolExecutor(weather_service, geocoding_service)

        messages: list[dict] = [
            {"role": "system", "content": "You are a weather assistant."},
            {"role": "user", "content": "Weather in Nonexistentville?"},
        ]

        mock_responses = [
            _make_tool_call_response(
                [
                    ("call_001", "get_current_weather", {"location": "Nonexistentville"}),
                ]
            ),
            _make_text_response(
                "I couldn't find weather data for Nonexistentville. Could you check the spelling?"
            ),
        ]

        final = _simulate_tool_call_loop(messages, mock_responses, executor)

        assert "Nonexistentville" in final

        # Tool result should contain error info
        tool_result = [m for m in messages if m["role"] == "tool"][0]
        assert (
            "could not" in tool_result["content"].lower()
            or "error" in tool_result["content"].lower()
            or "unable" in tool_result["content"].lower()
        )


def _read_system_prompt() -> str:
    """
    Read SYSTEM_PROMPT from the source file without importing the module.

    The dialog module imports wx and prism which are unavailable on Linux CI,
    so we parse the constant directly from the source.
    """
    import ast
    from pathlib import Path

    src = Path(__file__).resolve().parent.parent / (
        "src/accessiweather/ui/dialogs/weather_assistant_dialog.py"
    )
    tree = ast.parse(src.read_text())
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "SYSTEM_PROMPT":
                    return ast.literal_eval(node.value)
    raise RuntimeError("SYSTEM_PROMPT not found in source")


class TestSystemPrompt:
    """Tests for the updated system prompt."""

    def test_system_prompt_mentions_tools(self):
        """SYSTEM_PROMPT mentions available weather tools."""
        prompt = _read_system_prompt()
        assert "get_current_weather" in prompt
        assert "get_forecast" in prompt
        assert "get_alerts" in prompt

    def test_system_prompt_guides_tool_usage(self):
        """SYSTEM_PROMPT guides AI to use tools for location-specific queries."""
        prompt = _read_system_prompt()
        assert "tools" in prompt.lower()
        assert "location" in prompt.lower()
        assert "fetch" in prompt.lower()

    def test_system_prompt_lists_tool_capabilities(self):
        """SYSTEM_PROMPT describes what each tool does."""
        prompt = _read_system_prompt()
        assert "current" in prompt.lower()
        assert "forecast" in prompt.lower()
        assert "alert" in prompt.lower()
