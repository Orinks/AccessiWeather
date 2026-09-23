"""Generation failures must remain distinct from key-validation failures."""

from unittest.mock import MagicMock, patch

import pytest

from accessiweather.ai_explainer import AIExplainer
from accessiweather.ai_explainer_models import (
    AIExplainerError,
    EmptyResponseError,
    InsufficientCreditsError,
    InvalidAPIKeyError,
    ProviderPermissionError,
    RateLimitError,
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status, kind",
    [(401, InvalidAPIKeyError), (403, ProviderPermissionError), (402, InsufficientCreditsError)],
)
@pytest.mark.parametrize("text_product", [False, True])
async def test_generation_access_failures_stop_without_fallback(status, kind, caplog, text_product):
    explainer = AIExplainer(api_key="test-secret", model="openrouter/free")
    error = Exception("secret response containing api key and authentication")
    error.status_code = status
    client = MagicMock()
    client.chat.completions.create.side_effect = error
    with patch.object(explainer, "_get_client", return_value=client), pytest.raises(kind) as caught:
        if text_product:
            await explainer.explain_text_product("Forecast discussion", "AFD", "Test")
        else:
            await explainer.explain_weather({}, "Test")
    client.chat.completions.create.assert_called_once()
    assert "secret" not in str(caught.value) + caplog.text
    assert caught.value.__cause__ is None
    if status == 401:
        assert "could not authenticate this generation request" in str(caught.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "first",
    [
        {"content": "User Safety: safe"},
        RateLimitError("busy"),
    ],
)
@pytest.mark.parametrize("text_product", [False, True])
async def test_empty_or_busy_free_model_can_use_one_fallback(first, text_product):
    explainer = AIExplainer(api_key="test-key", model="openrouter/free")
    success = {
        "content": "A clear weather summary with enough useful detail.",
        "model": "backup:free",
        "total_tokens": 10,
    }
    with patch.object(explainer, "_call_provider", side_effect=[first, success]) as call:
        if text_product:
            result = await explainer.explain_text_product("Forecast discussion", "AFD", "Test")
        else:
            result = await explainer.explain_weather({}, "Test")
    assert result.text == success["content"]
    assert call.call_count == 2


@pytest.mark.asyncio
async def test_empty_responses_stop_after_two_attempts():
    explainer = AIExplainer(api_key="test-key", model="openrouter/free")
    with (
        patch.object(explainer, "_call_provider", return_value={"content": ""}) as call,
        pytest.raises(EmptyResponseError),
    ):
        await explainer.explain_weather({}, "Test")
    assert call.call_count == 2


def test_client_disables_sdk_retries_and_sets_request_timeout():
    with patch("openai.OpenAI") as factory:
        AIExplainer(api_key="test-key")._get_client()
    assert factory.call_args.kwargs["max_retries"] == 0
    assert factory.call_args.kwargs["timeout"] == 20.0


def test_unrecognized_error_details_are_redacted(caplog):
    explainer = AIExplainer(api_key="test-key")
    client = MagicMock()
    client.chat.completions.create.side_effect = Exception("private-response-secret")
    with (
        patch.object(explainer, "_get_client", return_value=client),
        pytest.raises(AIExplainerError) as caught,
    ):
        explainer._call_openrouter("system", "user")
    assert "private-response-secret" not in str(caught.value) + caplog.text
