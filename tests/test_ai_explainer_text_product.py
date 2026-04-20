"""
Tests for the generic explain_text_product method on AIExplainer.

Covers the seven scenarios defined in the Forecast Products PR 1 plan (B-R6):

1. Happy path AFD: system prompt is byte-identical to the current AFD prompt.
2. Happy path HWO: uses the HWO system prompt.
3. Happy path SPS: uses the SPS system prompt.
4. Cache: repeated call with identical inputs returns cached=True without
   re-invoking the LLM.
5. Custom prompt: custom_system_prompt replaces the default (existing
   explain_afd semantics).
6. Wrapper: explain_afd delegates to explain_text_product("AFD", ...).
7. Error path: LLM errors propagate; failures are not cached.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from accessiweather.ai_explainer import (
    _SYSTEM_PROMPTS,
    AIExplainer,
    AIExplainerError,
    ExplanationResult,
    ExplanationStyle,
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
# Happy-path tests: system prompt identity per product type
# ---------------------------------------------------------------------------


class TestExplainTextProductPrompts:
    """Verify the correct system prompt is routed for each product type."""

    @pytest.mark.asyncio
    async def test_afd_prompt_byte_identical(self, sample_afd_text, mock_response):
        """AFD prompt must match the historical explain_afd prompt byte-for-byte."""
        # The historical AFD system prompt — this string must remain stable
        # because user-customized prompt overrides in the wild are calibrated
        # against it. If this test fails, you changed the AFD prompt — don't.
        expected_afd_prompt = (
            "You are a helpful weather assistant that explains National Weather Service "
            "Area Forecast Discussions (AFDs) in plain, accessible language. AFDs contain "
            "technical meteorological terminology that most people don't understand. "
            "Your job is to translate this into clear, everyday language that anyone can "
            "understand. Focus on:\n"
            "- What weather to expect and when\n"
            "- Any significant weather events or changes\n"
            "- How confident forecasters are in their predictions\n"
            "- What this means for daily activities\n\n"
            "Avoid using technical jargon. If you must use a technical term, explain it.\n\n"
            "IMPORTANT: Do NOT start with a preamble like 'Here is a summary...' or "
            "'This forecast discussion explains...'. Do NOT repeat the location name. "
            "Jump straight into explaining the weather. The user already knows what they asked for.\n\n"
            "IMPORTANT: Respond in plain text only. Do NOT use markdown formatting such as "
            "bold (**text**), italic (*text*), headers (#), bullet points, or any other "
            "markdown syntax. Use simple paragraph text that can be read directly."
        )

        assert _SYSTEM_PROMPTS["AFD"] == expected_afd_prompt

        explainer = AIExplainer(api_key="test-key")
        with patch.object(explainer, "_call_openrouter") as mock_call:
            mock_call.return_value = mock_response

            result = await explainer.explain_text_product(
                sample_afd_text,
                "AFD",
                "Test City",
                style=ExplanationStyle.DETAILED,
            )

            assert isinstance(result, ExplanationResult)
            assert result.cached is False

            # The first positional argument to _call_openrouter is the
            # system prompt; it must start with the AFD prompt byte-for-byte.
            args, _ = mock_call.call_args
            system_prompt = args[0]
            assert system_prompt == expected_afd_prompt

    @pytest.mark.asyncio
    async def test_hwo_uses_hwo_prompt(self, sample_hwo_text, mock_response):
        explainer = AIExplainer(api_key="test-key")
        with patch.object(explainer, "_call_openrouter") as mock_call:
            mock_call.return_value = mock_response

            await explainer.explain_text_product(
                sample_hwo_text,
                "HWO",
                "Test City",
            )

            args, _ = mock_call.call_args
            system_prompt = args[0]
            assert system_prompt == _SYSTEM_PROMPTS["HWO"]
            # HWO prompt must not equal AFD prompt
            assert system_prompt != _SYSTEM_PROMPTS["AFD"]
            # Sanity: the HWO prompt should mention the product by name
            assert "Hazardous Weather Outlook" in system_prompt

    @pytest.mark.asyncio
    async def test_sps_uses_sps_prompt(self, sample_sps_text, mock_response):
        explainer = AIExplainer(api_key="test-key")
        with patch.object(explainer, "_call_openrouter") as mock_call:
            mock_call.return_value = mock_response

            await explainer.explain_text_product(
                sample_sps_text,
                "SPS",
                "Test City",
            )

            args, _ = mock_call.call_args
            system_prompt = args[0]
            assert system_prompt == _SYSTEM_PROMPTS["SPS"]
            assert system_prompt != _SYSTEM_PROMPTS["AFD"]
            assert system_prompt != _SYSTEM_PROMPTS["HWO"]
            assert "Special Weather Statement" in system_prompt


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
            # Default HWO prompt should NOT be present
            assert _SYSTEM_PROMPTS["HWO"] not in system_prompt


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
            # Verify AFD prompt was used
            args, _ = mock_call.call_args
            assert args[0] == _SYSTEM_PROMPTS["AFD"]


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
