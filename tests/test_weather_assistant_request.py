"""Exercise the production completion loop with protocol-shaped responses."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from accessiweather.ui.dialogs.weather_assistant_request import (
    AssistantRequestError,
    needs_live_weather,
    run_assistant_request,
)


def response(text="", tool=None):
    calls = (
        [
            SimpleNamespace(
                id="call-1", function=SimpleNamespace(name=tool, arguments='{"location":"Home"}')
            )
        ]
        if tool
        else []
    )
    return SimpleNamespace(
        model="chosen",
        choices=[SimpleNamespace(message=SimpleNamespace(content=text, tool_calls=calls))],
    )


def setup(responses):
    client = MagicMock()
    client.chat.completions.create.side_effect = responses
    executor = MagicMock()
    executor.execute.return_value = "Observed at noon: 70 F"
    options = {
        "tools": [
            {"type": "function", "function": {"name": name}}
            for name in ["get_current_weather", "add_location"]
        ]
    }
    return client, executor, options


def test_live_request_requires_read_only_tool_then_allows_answer_with_preserved_history():
    client, executor, options = setup(
        [response("Checking", "get_current_weather"), response("It is 70 F.")]
    )
    answer = run_assistant_request(
        client,
        "model",
        [{"role": "user", "content": "Current weather at Home?"}],
        executor,
        options,
    )
    first, second = client.chat.completions.create.call_args_list
    assert first.kwargs["tool_choice"] == "required"
    assert [t["function"]["name"] for t in first.kwargs["tools"]] == ["get_current_weather"]
    assert "tool_choice" not in second.kwargs
    assert answer.text == "It is 70 F."
    assert [m["role"] for m in answer.messages] == ["user", "assistant", "tool", "assistant"]
    assert answer.messages[2]["content"] == "Observed at noon: 70 F"


def test_model_ignoring_required_tool_never_returns_promise_as_answer():
    client, executor, options = setup([response("I'll check."), response("Let me fetch that.")])
    with pytest.raises(AssistantRequestError, match="did not perform"):
        run_assistant_request(
            client, "model", [{"role": "user", "content": "Weather tomorrow?"}], executor, options
        )
    assert client.chat.completions.create.call_count == 2
    executor.execute.assert_not_called()


def test_conceptual_question_does_not_force_tool():
    client, executor, options = setup([response("Rain forms from condensed moisture.")])
    run_assistant_request(
        client, "model", [{"role": "user", "content": "How does rain form?"}], executor, options
    )
    assert "tool_choice" not in client.chat.completions.create.call_args.kwargs
    executor.execute.assert_not_called()


def test_tool_round_exhaustion_does_not_return_intermediate_promise():
    client, executor, options = setup([response("Checking", "get_current_weather")] * 3)
    with pytest.raises(AssistantRequestError, match="could not finish"):
        run_assistant_request(
            client,
            "model",
            [{"role": "user", "content": "Weather now?"}],
            executor,
            options,
            max_tool_rounds=2,
        )
    assert executor.execute.call_count == 2


def test_model_cannot_execute_write_tool_during_required_read_lookup():
    client, executor, options = setup(
        [response("Saving", "add_location"), response("I could not check.")]
    )
    with pytest.raises(AssistantRequestError, match="did not return usable data"):
        run_assistant_request(
            client, "model", [{"role": "user", "content": "Weather now?"}], executor, options
        )
    executor.execute.assert_not_called()


def test_alert_question_uses_selected_location_despite_model_namesake():
    client, executor, options = setup(
        [response("Checking", "get_alerts"), response("Alert checked.")]
    )
    options["tools"].insert(1, {"type": "function", "function": {"name": "get_alerts"}})

    run_assistant_request(
        client,
        "model",
        [{"role": "user", "content": "Are there alerts for Lumberton right now?"}],
        executor,
        options,
        selected_location="Lumberton, NJ",
    )

    first = client.chat.completions.create.call_args_list[0]
    assert [tool["function"]["name"] for tool in first.kwargs["tools"]] == ["get_alerts"]
    executor.execute.assert_called_once_with("get_alerts", {"location": "Lumberton, NJ"})


def test_explicit_other_location_remains_available():
    client, executor, options = setup(
        [response("Checking", "get_current_weather"), response("Done")]
    )
    run_assistant_request(
        client,
        "model",
        [{"role": "user", "content": "What is the current weather in Home?"}],
        executor,
        options,
        selected_location="Lumberton, NJ",
    )
    executor.execute.assert_called_once_with("get_current_weather", {"location": "Home"})


def test_assistant_rejects_no_alert_claim_after_alert_tool_reports_warning():
    client, executor, options = setup(
        [response("Checking", "get_alerts"), response("There are no active alerts.")]
    )
    options["tools"].append({"type": "function", "function": {"name": "get_alerts"}})
    executor.execute.return_value = "Weather alerts for Home:\n- Coastal Flood Warning"

    with pytest.raises(AssistantRequestError, match="contradicted"):
        run_assistant_request(
            client,
            "model",
            [{"role": "user", "content": "Any alerts now?"}],
            executor,
            options,
            selected_location="Home",
        )


def test_assistant_rejects_unrequested_namesake_in_answer():
    client, executor, options = setup(
        [response("Checking", "get_current_weather"), response("Lumberton, NC is sunny.")]
    )

    with pytest.raises(AssistantRequestError, match="different place"):
        run_assistant_request(
            client,
            "model",
            [{"role": "user", "content": "What is the weather now?"}],
            executor,
            options,
            selected_location="Lumberton, NJ",
        )


def test_completed_tool_messages_are_sent_on_followup():
    client, executor, options = setup(
        [response("", "get_current_weather"), response("70 F"), response("That is mild.")]
    )
    answer = run_assistant_request(
        client,
        "model",
        [{"role": "user", "content": "What are current conditions?"}],
        executor,
        options,
    )
    followup = answer.messages + [{"role": "user", "content": "What does that mean?"}]
    run_assistant_request(client, "model", followup, executor, options)
    sent = client.chat.completions.create.call_args.kwargs["messages"]
    assert any(item["role"] == "tool" and "70 F" in item["content"] for item in sent)


def test_adapter_uses_current_location_and_alert_failures_are_unknown(monkeypatch):
    from accessiweather import api_client, geocoding, openmeteo_client
    from accessiweather.ui.dialogs.weather_assistant_dialog import WeatherAssistantDialog

    nws = MagicMock()
    nws.get_alerts.side_effect = RuntimeError("service down")
    monkeypatch.setattr(api_client, "NoaaApiClient", lambda: nws)
    monkeypatch.setattr(openmeteo_client, "OpenMeteoApiClient", MagicMock())
    monkeypatch.setattr(geocoding, "GeocodingService", MagicMock())
    manager = MagicMock()
    manager.get_current_location.return_value = SimpleNamespace(
        name="Home", latitude=40.1, longitude=-74.2
    )
    dialog = SimpleNamespace(app=SimpleNamespace(config_manager=manager))
    executor = WeatherAssistantDialog._get_tool_executor(dialog)
    assert executor.location_resolver.resolve("Home") == (40.1, -74.2, "Home")
    with pytest.raises(RuntimeError, match="Alert status is unknown"):
        executor.weather_service.get_alerts(40.1, -74.2)


def test_adapter_passes_only_selected_locations_displayed_alerts(monkeypatch):
    from accessiweather import api_client, geocoding, openmeteo_client
    from accessiweather.ui.dialogs.weather_assistant_dialog import WeatherAssistantDialog

    monkeypatch.setattr(api_client, "NoaaApiClient", MagicMock())
    monkeypatch.setattr(openmeteo_client, "OpenMeteoApiClient", MagicMock())
    monkeypatch.setattr(geocoding, "GeocodingService", MagicMock())
    manager = MagicMock()
    manager.get_current_location.return_value = SimpleNamespace(
        name="Lumberton, NJ", latitude=39.97, longitude=-74.8
    )
    warning = SimpleNamespace(event="Coastal Flood Warning")
    weather = SimpleNamespace(
        location=SimpleNamespace(latitude=39.97, longitude=-74.8),
        alerts=SimpleNamespace(alerts=[warning]),
    )
    dialog = SimpleNamespace(
        app=SimpleNamespace(config_manager=manager, current_weather_data=weather)
    )

    executor = WeatherAssistantDialog._get_tool_executor(dialog)
    assert executor.displayed_alerts == [warning]

    weather.location.longitude = -80.0
    other = WeatherAssistantDialog._get_tool_executor(dialog)
    assert other.displayed_alerts is None


def test_generation_disables_clear_and_completion_keeps_model_status():
    from accessiweather.ui.dialogs.weather_assistant_dialog import WeatherAssistantDialog

    dialog = WeatherAssistantDialog.__new__(WeatherAssistantDialog)
    dialog.send_button = MagicMock()
    dialog.clear_button = MagicMock()
    dialog.input_ctrl = MagicMock()
    dialog.status_label = MagicMock()
    dialog._conversation = [{"role": "user", "content": "Weather?"}]
    dialog._append_to_display = MagicMock()
    dialog._announcer = MagicMock()
    dialog._set_generating(True)
    dialog._announcer.announce.assert_called_once_with("Thinking...")
    dialog.clear_button.Enable.assert_called_with(False)
    dialog._on_clear(None)
    assert dialog._conversation == [{"role": "user", "content": "Weather?"}]
    dialog._on_response_received("Sunny", "model-used")
    dialog.clear_button.Enable.assert_called_with(True)
    dialog.status_label.SetLabel.assert_called_with("Model: model-used")
    dialog.input_ctrl.SetFocus.assert_called_once()


def test_grounding_error_is_announced_and_returns_focus_to_input():
    from accessiweather.ui.dialogs.weather_assistant_dialog import WeatherAssistantDialog

    dialog = WeatherAssistantDialog.__new__(WeatherAssistantDialog)
    dialog.send_button = MagicMock()
    dialog.clear_button = MagicMock()
    dialog.input_ctrl = MagicMock()
    dialog.status_label = MagicMock()
    dialog._conversation = [{"role": "user", "content": "Any alerts?"}]
    dialog.input_ctrl.GetValue.return_value = ""
    dialog._append_to_display = MagicMock()
    dialog._announcer = MagicMock()

    dialog._on_response_error("The model contradicted the alert lookup.")

    expected = "Sorry, I couldn't respond: The model contradicted the alert lookup."
    dialog._append_to_display.assert_called_once_with("Weather Assistant", expected)
    dialog._announcer.announce.assert_called_once_with(
        f"Weather Assistant: {expected} Your question is restored in the input for editing."
    )
    dialog.input_ctrl.SetValue.assert_called_once_with("Any alerts?")
    dialog.input_ctrl.SetInsertionPointEnd.assert_called_once()
    dialog.input_ctrl.SetFocus.assert_called_once()
    assert dialog._conversation == []


@pytest.mark.parametrize(
    "question",
    ["Explain today’s forecast", "Why is it so windy now?", "Explain current conditions"],
)
def test_explanatory_live_questions_still_require_weather(question):
    assert needs_live_weather(question)


@pytest.mark.parametrize(
    "question", ["Explain how forecasts work", "What is a weather warning?", "How does rain form?"]
)
def test_general_weather_concepts_do_not_require_lookup(question):
    assert not needs_live_weather(question)


def test_assistant_geocoding_keeps_international_match_ahead_of_us_namesake(monkeypatch):
    from accessiweather import api_client, geocoding, openmeteo_client
    from accessiweather.ui.dialogs.weather_assistant_dialog import WeatherAssistantDialog

    results = [
        SimpleNamespace(
            country_code="GB", latitude=51.5, longitude=-0.12, display_name="London, United Kingdom"
        ),
        SimpleNamespace(
            country_code="US", latitude=39.88, longitude=-83.45, display_name="London, Ohio"
        ),
    ]
    monkeypatch.setattr(
        geocoding.OpenMeteoGeocodingClient, "search", lambda self, address, count: results
    )
    monkeypatch.setattr(api_client, "NoaaApiClient", MagicMock())
    monkeypatch.setattr(openmeteo_client, "OpenMeteoApiClient", MagicMock())
    manager = MagicMock()
    manager.get_current_location.return_value = None
    dialog = SimpleNamespace(app=SimpleNamespace(config_manager=manager))
    executor = WeatherAssistantDialog._get_tool_executor(dialog)
    assert executor.location_resolver.resolve("London, UK") == (
        51.5,
        -0.12,
        "London, United Kingdom",
    )
