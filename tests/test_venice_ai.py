"""Venice routing, prompt and safe error contracts."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from accessiweather.ai_explainer import AIExplainer
from accessiweather.ai_explainer_models import (
    AIExplainerError,
    InsufficientCreditsError,
    InvalidAPIKeyError,
    NetworkError,
    ProviderPermissionError,
    RateLimitError,
)
from accessiweather.ai_provider import (
    DEFAULT_VENICE_MODEL,
    ai_request_error,
    openrouter_error,
    validate_venice_api_key,
    venice_error,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("text_product", [False, True])
async def test_venice_preserves_prompts_and_never_calls_openrouter(text_product):
    explainer = AIExplainer(
        api_key="test-key",
        provider="venice",
        custom_system_prompt="My custom system prompt",
        custom_instructions="Use Celsius only",
    )
    client = MagicMock()
    client.chat.completions.create.return_value = SimpleNamespace(
        choices=[
            SimpleNamespace(message=SimpleNamespace(content="A useful weather explanation here."))
        ],
        model=DEFAULT_VENICE_MODEL,
        usage=None,
    )
    with (
        patch("accessiweather.ai_explainer.create_venice_client", return_value=client),
        patch.object(explainer, "_call_openrouter") as openrouter,
    ):
        if text_product:
            result = await explainer.explain_text_product("Rain tomorrow.", "AFD", "Venice")
        else:
            result = await explainer.explain_weather({"temperature": 20}, "Venice")
    openrouter.assert_not_called()
    request = client.chat.completions.create.call_args.kwargs
    assert request["model"] == DEFAULT_VENICE_MODEL
    assert request["extra_body"] == {"venice_parameters": {"include_venice_system_prompt": False}}
    assert "My custom system prompt" in request["messages"][0]["content"]
    assert "Use Celsius only" in request["messages"][1]["content"]
    assert result.model_attempts == (DEFAULT_VENICE_MODEL,)
    assert result.estimated_cost is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,error_type",
    [
        (401, InvalidAPIKeyError),
        (403, ProviderPermissionError),
        (402, InsufficientCreditsError),
        (429, RateLimitError),
        (503, NetworkError),
    ],
)
async def test_venice_failures_are_redacted_and_do_not_retry_other_models(
    status, error_type, caplog
):
    client = MagicMock()
    error = httpx.HTTPStatusError(
        "secret-key response body",
        request=httpx.Request("POST", "https://example.test"),
        response=httpx.Response(status),
    )
    client.chat.completions.create.side_effect = error
    explainer = AIExplainer(api_key="secret-key", provider="venice")
    with (
        patch("accessiweather.ai_explainer.create_venice_client", return_value=client),
        pytest.raises(error_type) as failure,
    ):
        await explainer.explain_weather({}, "Test")
    assert "secret-key" not in str(failure.value)
    assert "secret-key" not in caplog.text
    assert client.chat.completions.create.call_count == 1


@pytest.mark.asyncio
async def test_venice_missing_key_does_not_fall_back():
    with pytest.raises(InvalidAPIKeyError, match="Venice API key is required"):
        await AIExplainer(provider="venice").explain_weather({}, "Test")


@pytest.mark.asyncio
async def test_key_validation_uses_authenticated_read_without_inference():
    client = AsyncMock()
    response = MagicMock()
    response.json.return_value = {"data": {"accessPermitted": True}}
    client.get.return_value = response
    with patch("accessiweather.ai_provider.httpx.AsyncClient") as factory:
        factory.return_value.__aenter__.return_value = client
        valid, message = await validate_venice_api_key("test-key")
    assert valid
    assert "verified" in message
    assert client.get.call_args.args[0].endswith("/api_keys/rate_limits")
    assert client.get.call_args.kwargs["headers"]["Authorization"] == "Bearer test-key"
    client.post.assert_not_called()


def test_venice_connection_error_is_redacted():
    error = venice_error(httpx.ConnectError("sensitive request"))
    assert isinstance(error, NetworkError)
    assert "sensitive" not in str(error)


@pytest.mark.parametrize(
    "status,error_type,expected",
    [
        (401, InvalidAPIKeyError, "authenticate"),
        (402, InsufficientCreditsError, "credits"),
        (403, ProviderPermissionError, "permission"),
        (404, AIExplainerError, "model"),
        (429, RateLimitError, "rate limit"),
        (503, NetworkError, "temporarily unavailable"),
    ],
)
def test_openrouter_assistant_status_errors_are_specific_and_redacted(status, error_type, expected):
    error = httpx.HTTPStatusError(
        "secret-key upstream response",
        request=httpx.Request("POST", "https://example.test"),
        response=httpx.Response(status),
    )
    mapped = openrouter_error(error)
    assert isinstance(mapped, error_type)
    assert expected in str(mapped).lower()
    assert "secret-key" not in str(mapped)


@pytest.mark.parametrize(
    "error,expected",
    [
        (TimeoutError("secret-key"), "timed out"),
        (httpx.ConnectError("secret-key"), "internet connection"),
        (RuntimeError("secret-key"), "could not complete"),
    ],
)
def test_unexpected_openrouter_failures_never_expose_exception_text(error, expected):
    message = str(ai_request_error(error))
    assert expected in message.lower()
    assert "secret-key" not in message


def test_provider_cache_isolation():
    first = AIExplainer(provider="venice", api_key="test", model="same")
    second = AIExplainer(provider="openrouter", api_key="test", model="same")
    assert first._generate_cache_key({}, "Test") != second._generate_cache_key({}, "Test")


def test_weather_assistant_venice_uses_saved_prompt_and_provider():
    from accessiweather.ui.dialogs.weather_assistant_dialog import WeatherAssistantDialog

    settings = SimpleNamespace(
        ai_provider="venice",
        venice_api_key="test-key",
        venice_model=DEFAULT_VENICE_MODEL,
        openrouter_api_key="other-key",
        ai_model_preference="openrouter/free",
        custom_system_prompt="Custom assistant prompt",
        custom_instructions="Use Celsius",
    )
    dialog = MagicMock()
    dialog.app.config_manager.get_settings.return_value = settings
    dialog._conversation = [{"role": "user", "content": "Explain today's weather"}]
    dialog._get_tool_executor.return_value = None
    client = MagicMock()
    client.chat.completions.create.return_value = SimpleNamespace(
        model=DEFAULT_VENICE_MODEL,
        choices=[
            SimpleNamespace(
                finish_reason="stop",
                message=SimpleNamespace(content="Here is the weather.", tool_calls=None),
            )
        ],
    )
    module = "accessiweather.ui.dialogs.weather_assistant_dialog"
    with (
        patch(f"{module}._build_weather_context", return_value="Sunny"),
        patch(f"{module}.create_venice_client", return_value=client) as create,
        # Patching threading.Thread is process-wide, so the deadline timer is stubbed too.
        patch("accessiweather.ui.dialogs.weather_assistant_request.RequestDeadline"),
        patch(f"{module}.threading.Thread") as thread,
        patch(f"{module}.wx.CallAfter"),
    ):
        thread.side_effect = lambda target, **kwargs: SimpleNamespace(start=target)
        WeatherAssistantDialog._generate_response(dialog)
    create.assert_called_once_with("test-key")
    request = client.chat.completions.create.call_args.kwargs
    assert request["model"] == DEFAULT_VENICE_MODEL
    assert request["extra_body"]["venice_parameters"]["include_venice_system_prompt"] is False
    assert "Custom assistant prompt" in request["messages"][0]["content"]
    assert "Use Celsius" in request["messages"][0]["content"]


def test_weather_assistant_rejects_unknown_provider():
    from accessiweather.ui.dialogs.weather_assistant_dialog import WeatherAssistantDialog

    dialog = MagicMock()
    dialog.app.config_manager.get_settings.return_value = SimpleNamespace(ai_provider="unknown")
    with patch("accessiweather.ui.dialogs.weather_assistant_dialog.wx.CallAfter") as call:
        WeatherAssistantDialog._generate_response(dialog)
    assert "Unknown AI provider" in call.call_args.args[1]
    dialog._get_tool_executor.assert_not_called()


def test_weather_assistant_redacts_failure_then_recovers():
    from accessiweather.ui.dialogs.weather_assistant_dialog import WeatherAssistantDialog

    settings = SimpleNamespace(
        ai_provider="openrouter",
        openrouter_api_key="secret-key",
        ai_model_preference="openrouter/free",
        custom_system_prompt=None,
        custom_instructions=None,
    )
    dialog = MagicMock()
    dialog.app.config_manager.get_settings.return_value = settings
    dialog._conversation = [{"role": "user", "content": "Hello"}]
    dialog._get_tool_executor.return_value = None
    client = MagicMock()
    client.chat.completions.create.side_effect = [
        httpx.HTTPStatusError(
            "secret-key response body",
            request=httpx.Request("POST", "https://example.test"),
            response=httpx.Response(402),
        ),
        SimpleNamespace(
            model="openrouter/free",
            choices=[SimpleNamespace(message=SimpleNamespace(content="Ready.", tool_calls=None))],
        ),
    ]
    module = "accessiweather.ui.dialogs.weather_assistant_dialog"
    with (
        patch(f"{module}._build_weather_context", return_value="Sunny"),
        patch("openai.OpenAI", return_value=client),
        patch("accessiweather.ui.dialogs.weather_assistant_request.RequestDeadline"),
        patch(f"{module}.threading.Thread") as thread,
        patch(f"{module}.wx.CallAfter", side_effect=lambda callback, *args: callback(*args)),
    ):
        thread.side_effect = lambda target, **kwargs: SimpleNamespace(start=target)
        WeatherAssistantDialog._generate_response(dialog)
        error = dialog._on_response_error.call_args.args[0]
        assert "credits" in error
        assert "secret-key" not in error
        WeatherAssistantDialog._generate_response(dialog)
    dialog._on_response_received.assert_called_once()
    assert dialog._on_response_received.call_args.args[0] == "Ready."


def test_regeneration_error_focuses_and_announces_error():
    from accessiweather.ui.dialogs.explanation_dialog import ExplanationDialog

    dialog = MagicMock()
    with patch("accessiweather.ui.dialogs.explanation_dialog.ScreenReaderAnnouncer") as announcer:
        ExplanationDialog._on_regenerate_error(dialog, "Venice rate limit reached")
    dialog.text_ctrl.SetFocus.assert_called_once()
    dialog.regenerate_btn.Enable.assert_called_once()
    announcer.return_value.announce.assert_called_once_with(
        "Failed to regenerate. Venice rate limit reached"
    )


def test_summary_error_focuses_and_announces_error():
    from accessiweather.ui.dialogs.forecast_product_panel import ForecastProductPanel

    panel = MagicMock()
    ForecastProductPanel._on_explain_error(panel, "Venice account needs credits")
    panel.ai_summary_display.SetFocus.assert_called_once()
    panel._announce_explain_status.assert_called_once_with(
        "Summary failed. Venice account needs credits"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "balances, no_balance",
    [
        ({"USD": 0, "DIEM": 0, "BUNDLED_CREDITS": 0}, True),
        ({"USD": 0, "DIEM": 0, "BUNDLED_CREDITS": 2}, False),
        ({"USD": 0, "DIEM": 0}, False),
        ({"USD": 0, "DIEM": 1}, False),
        ({"USD": 2, "DIEM": 0}, False),
        ({"USD": 0, "DIEM": 0, "OTHER": 3}, False),
        ({"USD": 0}, False),
        ({"USD": None, "DIEM": 0}, False),
        ({"USD": False, "DIEM": 0}, False),
        ({}, False),
        (None, False),
    ],
)
async def test_venice_validation_reports_only_known_balance_shortfall(balances, no_balance):
    client = AsyncMock()
    response = MagicMock()
    response.json.return_value = {"data": {"accessPermitted": True, "balances": balances}}
    client.get.return_value = response
    with patch("accessiweather.ai_provider.httpx.AsyncClient") as factory:
        factory.return_value.__aenter__.return_value = client
        valid, message = await validate_venice_api_key("test-key")
    assert valid is True
    assert ("no positive balance is listed" in message) is no_balance
    client.post.assert_not_called()


@pytest.mark.asyncio
async def test_venice_denied_access_takes_precedence_over_zero_balance():
    client = AsyncMock()
    response = MagicMock()
    response.json.return_value = {
        "data": {"accessPermitted": False, "balances": {"USD": 0, "DIEM": 0}}
    }
    client.get.return_value = response
    with patch("accessiweather.ai_provider.httpx.AsyncClient") as factory:
        factory.return_value.__aenter__.return_value = client
        valid, message = await validate_venice_api_key("test-key")
    assert valid is False
    assert "not permitted" in message


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status, phrase", [(401, "rejected this API key"), (403, "denied permission")]
)
async def test_venice_key_validation_distinguishes_rejection_from_permission(
    status, phrase, caplog
):
    client = AsyncMock()
    response = httpx.Response(
        status,
        text="private-response-secret",
        request=httpx.Request("GET", "https://example.invalid"),
    )
    client.get.return_value = response
    with patch("accessiweather.ai_provider.httpx.AsyncClient") as factory:
        factory.return_value.__aenter__.return_value = client
        valid, message = await validate_venice_api_key("test-secret-key")
    assert valid is False
    assert phrase in message
    assert "private-response-secret" not in message + caplog.text
    assert "test-secret-key" not in message + caplog.text
    client.post.assert_not_called()
