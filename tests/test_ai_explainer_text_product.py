"""
Tests for the generic explain_text_product method on AIExplainer.

Covers the text-product AI explanation behavior:

1. All text products use the app default system prompt when no custom prompt is set.
2. Custom prompts and instructions apply to all text products.
3. Cache: repeated call with identical inputs returns cached=True without
   re-invoking the LLM.
4. Custom prompt: custom_system_prompt replaces the default (existing
   explain_afd semantics).
5. Wrapper: explain_afd delegates to explain_text_product("AFD", ...).
6. Error path: LLM errors propagate; failures are not cached.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from accessiweather.ai_explainer import (
    AIExplainer,
    AIExplainerError,
    ExplanationResult,
    ExplanationStyle,
    RateLimitError,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_afd_text():
    return (
        ".SYNOPSIS...\n"
        "High pressure will dominate the region through mid-week.\n"
        "\n"
        ".NEAR TERM /THROUGH TONIGHT/...\n"
        "Expect clear skies and temperatures in the low 70s.\n"
    )


@pytest.fixture
def sample_hwo_text():
    return (
        ".DAY ONE...Today and Tonight.\n"
        "No hazardous weather is expected at this time.\n"
        ".DAYS TWO THROUGH SEVEN...\n"
        "Thunderstorms possible Wednesday with locally heavy rain.\n"
    )


@pytest.fixture
def sample_sps_text():
    return (
        "...SPECIAL WEATHER STATEMENT...\n"
        "A strong thunderstorm will affect portions of the area through 4 PM.\n"
        "Locations impacted include Springfield and surrounding communities.\n"
    )


@pytest.fixture
def sample_cli_text():
    return (
        "CLIMATE REPORT\n"
        "...THE RALEIGH NC CLIMATE SUMMARY FOR MAY 23 2026...\n"
        "HIGH TEMPERATURE 82. LOW TEMPERATURE 61. PRECIPITATION 0.12 INCHES.\n"
    )


@pytest.fixture
def mock_response():
    return {
        "content": "This is a plain-language summary of the forecast discussion.",
        "model": "test-model",
        "total_tokens": 150,
        "prompt_tokens": 100,
        "completion_tokens": 50,
    }


@pytest.fixture
def in_memory_cache():
    """Real-ish cache stub matching Cache.get/set(ttl=...) shape."""

    class _Cache:
        def __init__(self):
            self.store: dict[str, object] = {}
            self.get_calls = 0
            self.set_calls = 0

        def get(self, key: str):
            self.get_calls += 1
            return self.store.get(key)

        def set(self, key: str, value, ttl: float | None = None):
            self.set_calls += 1
            self.store[key] = value

    return _Cache()


# ---------------------------------------------------------------------------
# Happy-path tests: shared system prompt for every product type
# ---------------------------------------------------------------------------


class TestExplainTextProductPrompts:
    """Verify every product type uses the same app default system prompt."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("product_type", ["AFD", "HWO", "SPS", "CLI", "SWODY1", "PMDMRD"])
    async def test_text_products_use_app_default_system_prompt(
        self, product_type, sample_cli_text, mock_response
    ):
        explainer = AIExplainer(api_key="test-key")
        with (
            patch.object(explainer, "_call_openrouter") as mock_call,
            patch(
                "accessiweather.ai_explainer_openrouter_client.get_available_free_models",
                return_value=[],
            ),
        ):
            mock_call.return_value = mock_response

            result = await explainer.explain_text_product(
                sample_cli_text,
                product_type,
                "Test City",
                style=ExplanationStyle.STANDARD,
            )

            assert isinstance(result, ExplanationResult)
            assert result.cached is False
            args, _ = mock_call.call_args
            system_prompt = args[0]
            user_prompt = args[1]
            assert system_prompt == explainer.get_effective_system_prompt(ExplanationStyle.STANDARD)
            assert (
                f"Please explain this National Weather Service text product ({product_type})"
                in user_prompt
            )
            assert sample_cli_text in user_prompt

    @pytest.mark.asyncio
    @pytest.mark.parametrize("product_type", ["AFD", "HWO", "SPS", "CLI", "SWODY1"])
    async def test_custom_prompt_and_instructions_apply_to_all_text_products(
        self, product_type, sample_cli_text, mock_response
    ):
        """User custom prompts and instructions apply to every text product."""
        custom_prompt = "Use the user's preferred weather-summary voice."
        custom_instructions = "Mention records and departures from normal."
        explainer = AIExplainer(
            api_key="test-key",
            custom_system_prompt=custom_prompt,
            custom_instructions=custom_instructions,
        )
        with patch.object(explainer, "_call_openrouter") as mock_call:
            mock_call.return_value = mock_response

            await explainer.explain_text_product(sample_cli_text, product_type, "Test City")

            args, _ = mock_call.call_args
            system_prompt = args[0]
            user_prompt = args[1]
            assert system_prompt == custom_prompt
            assert f"Additional Instructions: {custom_instructions}" in user_prompt


class TestExplainTextProductModelProgress:
    """Model fallback progress should be visible to calling UIs."""

    @pytest.mark.asyncio
    async def test_fallback_reason_uses_structured_error_cause(
        self, sample_cli_text, mock_response
    ):
        """Selection reasons should read structured API error fields first."""
        selected_model = "selected/free-model:free"
        backup_model = "backup/free-model:free"
        explainer = AIExplainer(api_key="test-key", model=selected_model)

        def fake_call(_system_prompt, _user_prompt, model_override=None):
            called_model = model_override or selected_model
            if called_model == selected_model:
                api_error = Exception("provider unavailable")
                api_error.status_code = 429  # type: ignore[attr-defined]
                api_error.body = {"error": {"code": "rate_limit_exceeded"}}  # type: ignore[attr-defined]
                raise RateLimitError("Selected model failed") from api_error
            return {**mock_response, "model": backup_model}

        with (
            patch.object(explainer, "_call_openrouter", side_effect=fake_call),
            patch(
                "accessiweather.ai_explainer_openrouter_client.get_available_free_models",
                return_value=[backup_model],
            ),
        ):
            result = await explainer.explain_text_product(
                sample_cli_text,
                "CLI",
                "Test City",
            )

        assert result.model_selection_reason
        assert "rate limits" in result.model_selection_reason.lower()

    @pytest.mark.asyncio
    async def test_free_model_fallback_reports_progress_and_selection_reason(
        self, sample_cli_text, mock_response
    ):
        """A selected free model can fall back, and the result explains why."""
        selected_model = "selected/free-model:free"
        backup_model = "backup/free-model:free"
        explainer = AIExplainer(api_key="test-key", model=selected_model)
        status_updates: list[str] = []

        def fake_call(_system_prompt, _user_prompt, model_override=None):
            called_model = model_override or selected_model
            if called_model == selected_model:
                raise RateLimitError("rate limit exceeded")
            return {
                **mock_response,
                "model": backup_model,
            }

        with (
            patch.object(explainer, "_call_openrouter", side_effect=fake_call),
            patch(
                "accessiweather.ai_explainer_openrouter_client.get_available_free_models",
                return_value=[backup_model],
            ),
        ):
            result = await explainer.explain_text_product(
                sample_cli_text,
                "CLI",
                "Test City",
                status_callback=status_updates.append,
            )

        assert result.model_used == backup_model
        assert result.requested_model == selected_model
        assert result.model_attempts == (selected_model, "openrouter/free")
        assert result.model_selection_reason
        assert "selected free model" in result.model_selection_reason.lower()
        assert "rate limits" in result.model_selection_reason.lower()
        assert any("Trying selected free model" in update for update in status_updates)
        assert any(
            "Trying OpenRouter's free router as a backup" in update for update in status_updates
        )

    @pytest.mark.asyncio
    async def test_free_router_selection_reason_names_router_choice(
        self, sample_cli_text, mock_response
    ):
        """The default free router can pick a concrete free model without a failure."""
        router_selected_model = "router/picked-model:free"
        explainer = AIExplainer(api_key="test-key", model="openrouter/free")

        with (
            patch.object(explainer, "_call_openrouter") as mock_call,
            patch(
                "accessiweather.ai_explainer_openrouter_client.get_available_free_models",
                return_value=[],
            ),
        ):
            mock_call.return_value = {**mock_response, "model": router_selected_model}

            result = await explainer.explain_text_product(
                sample_cli_text,
                "CLI",
                "Test City",
            )

        assert result.model_used == router_selected_model
        assert result.requested_model == "openrouter/free"
        assert result.model_selection_reason
        assert "free router selected" in result.model_selection_reason.lower()
        assert "did not answer" not in result.model_selection_reason.lower()


# ---------------------------------------------------------------------------
# Cache tests
# ---------------------------------------------------------------------------


class TestExplainTextProductCache:
    @pytest.mark.asyncio
    async def test_repeated_call_hits_cache(self, sample_afd_text, mock_response, in_memory_cache):
        """Second call with identical inputs returns cached=True; no LLM call."""
        explainer = AIExplainer(api_key="test-key", cache=in_memory_cache)

        with patch.object(explainer, "_call_openrouter") as mock_call:
            mock_call.return_value = mock_response

            first = await explainer.explain_text_product(sample_afd_text, "AFD", "Test City")
            second = await explainer.explain_text_product(sample_afd_text, "AFD", "Test City")

            assert first.cached is False
            assert second.cached is True
            assert second.text == first.text
            assert second.model_used == first.model_used
            # LLM invoked exactly once
            assert mock_call.call_count == 1

    @pytest.mark.asyncio
    async def test_cache_key_differs_across_product_types(
        self, sample_afd_text, mock_response, in_memory_cache
    ):
        """AFD and HWO with identical text must not share cache entries."""
        explainer = AIExplainer(api_key="test-key", cache=in_memory_cache)

        with patch.object(explainer, "_call_openrouter") as mock_call:
            mock_call.return_value = mock_response

            await explainer.explain_text_product(sample_afd_text, "AFD", "Test City")
            await explainer.explain_text_product(sample_afd_text, "HWO", "Test City")
            # Different product type = different cache key = 2 LLM calls
            assert mock_call.call_count == 2


# ---------------------------------------------------------------------------
# Custom prompt behavior
# ---------------------------------------------------------------------------


class TestCustomSystemPrompt:
    @pytest.mark.asyncio
    async def test_custom_system_prompt_replaces_default(self, sample_hwo_text, mock_response):
        """
        custom_system_prompt replaces the built-in prompt for all product types.

        Matches current explain_afd behavior (replace, not append).
        """
        custom = "You are a custom weather bot. Speak like a pirate."
        explainer = AIExplainer(api_key="test-key", custom_system_prompt=custom)

        with patch.object(explainer, "_call_openrouter") as mock_call:
            mock_call.return_value = mock_response

            await explainer.explain_text_product(sample_hwo_text, "HWO", "Test City")

            args, _ = mock_call.call_args
            system_prompt = args[0]
            assert system_prompt == custom
            assert explainer.get_default_system_prompt() not in system_prompt


# ---------------------------------------------------------------------------
# explain_afd wrapper
# ---------------------------------------------------------------------------


class TestExplainAFDWrapper:
    @pytest.mark.asyncio
    async def test_explain_afd_delegates_to_explain_text_product(
        self, sample_afd_text, mock_response
    ):
        """explain_afd must call explain_text_product with product_type='AFD'."""
        explainer = AIExplainer(api_key="test-key")

        sentinel = ExplanationResult(
            text="sentinel",
            model_used="sentinel-model",
            token_count=1,
            estimated_cost=0.0,
            cached=False,
            timestamp=MagicMock(),
        )

        async def fake_explain_text_product(product_text, product_type, location_name, **kwargs):
            assert product_text == sample_afd_text
            assert product_type == "AFD"
            assert location_name == "Test City"
            # Forwarded kwargs
            assert kwargs.get("style") == ExplanationStyle.BRIEF
            assert kwargs.get("preserve_markdown") is True
            return sentinel

        with patch.object(explainer, "explain_text_product", side_effect=fake_explain_text_product):
            result = await explainer.explain_afd(
                sample_afd_text,
                "Test City",
                style=ExplanationStyle.BRIEF,
                preserve_markdown=True,
            )

            assert result is sentinel

    @pytest.mark.asyncio
    async def test_explain_afd_end_to_end_still_works(self, sample_afd_text, mock_response):
        """End-to-end: explain_afd returns a proper ExplanationResult."""
        explainer = AIExplainer(api_key="test-key")
        with patch.object(explainer, "_call_openrouter") as mock_call:
            mock_call.return_value = mock_response

            result = await explainer.explain_afd(sample_afd_text, "Test City")

            assert isinstance(result, ExplanationResult)
            assert result.cached is False
            assert result.text  # non-empty
            # Verify the shared app default prompt was used.
            args, _ = mock_call.call_args
            assert args[0] == explainer.get_effective_system_prompt(ExplanationStyle.DETAILED)


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


class TestErrorPaths:
    @pytest.mark.asyncio
    async def test_llm_error_propagates_and_is_not_cached(self, sample_afd_text, in_memory_cache):
        """LLM failures propagate. A subsequent retry re-invokes the LLM."""
        explainer = AIExplainer(api_key="test-key", cache=in_memory_cache)

        with patch.object(
            explainer,
            "_call_openrouter",
            side_effect=Exception("catastrophic LLM failure"),
        ) as mock_call:
            with pytest.raises((AIExplainerError, Exception)):
                await explainer.explain_text_product(sample_afd_text, "AFD", "Test City")

            # Retry — cache must NOT have absorbed the failure
            with pytest.raises((AIExplainerError, Exception)):
                await explainer.explain_text_product(sample_afd_text, "AFD", "Test City")

            # The LLM was re-invoked for the retry (at least one call per
            # attempt; model-fallback loop may multiply this, but it must be
            # strictly greater than the first attempt's count).
            assert mock_call.call_count >= 2
            # Nothing was cached
            assert len(in_memory_cache.store) == 0
