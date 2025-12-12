"""
Integration tests for AI weather explanation feature.

This module contains integration tests that make real API calls to OpenRouter.
These tests are marked with @pytest.mark.integration to skip in CI environments.

Requirements tested:
- Free model access without API key
- Paid model access with valid API key
- Rate limiting behavior
- Error scenarios (invalid key, network issues)
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime
from unittest.mock import patch

import pytest

from accessiweather.ai_explainer import (
    AIExplainer,
    AIExplainerError,
    ExplanationStyle,
    InvalidAPIKeyError,
    RateLimitError,
)

# Skip all integration tests in CI or if no API key is available
pytestmark = pytest.mark.integration


class TestRealAPIIntegration:
    """Integration tests with real OpenRouter API calls."""

    @pytest.fixture
    def test_api_key(self):
        """Get test API key from environment."""
        api_key = os.environ.get("OPENROUTER_TEST_API_KEY")
        if not api_key:
            pytest.skip("OPENROUTER_TEST_API_KEY environment variable not set")
        return api_key

    @pytest.fixture
    def sample_weather_data(self):
        """Sample weather data for testing."""
        return {
            "temperature": 72.5,
            "temperature_unit": "F",
            "conditions": "Partly Cloudy",
            "humidity": 65,
            "wind_speed": 8.5,
            "wind_direction": "NW",
            "visibility": 10.0,
            "pressure": 29.92,
            "alerts": [],
        }

    @pytest.mark.asyncio
    async def test_free_model_without_api_key(self, sample_weather_data):
        """
        Test free model access without API key.

        **Validates: Requirements 6.1, 2.1**
        """
        # Note: OpenRouter actually requires an API key even for free models
        # This test verifies the error handling when no key is provided
        explainer = AIExplainer(api_key=None)

        with pytest.raises(AIExplainerError) as exc_info:
            await explainer.explain_weather(sample_weather_data, "Test City")

        # Should get a clear error about needing an API key
        assert "API key required" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_free_model_with_api_key(self, test_api_key, sample_weather_data):
        """
        Test free model access with valid API key.

        **Validates: Requirements 6.1, 2.2**
        """
        explainer = AIExplainer(api_key=test_api_key, model="meta-llama/llama-3.2-3b-instruct:free")

        result = await explainer.explain_weather(sample_weather_data, "Seattle, WA")

        # Verify result structure
        assert result.text is not None
        assert len(result.text) > 0
        assert result.model_used is not None
        assert ":free" in result.model_used
        assert result.token_count > 0
        assert result.estimated_cost == 0.0  # Free models should have zero cost
        assert result.cached is False
        assert isinstance(result.timestamp, datetime)

    @pytest.mark.asyncio
    async def test_paid_model_with_api_key(self, test_api_key, sample_weather_data):
        """
        Test paid model access with valid API key.

        **Validates: Requirements 6.1, 2.5**
        """
        explainer = AIExplainer(
            api_key=test_api_key,
            model="openrouter/auto",  # Uses paid models
        )

        result = await explainer.explain_weather(sample_weather_data, "Denver, CO")

        # Verify result structure
        assert result.text is not None
        assert len(result.text) > 0
        assert result.model_used is not None
        assert result.token_count > 0
        # Paid models may have cost > 0 (depends on actual model used)
        assert result.estimated_cost >= 0.0
        assert result.cached is False
        assert isinstance(result.timestamp, datetime)

    @pytest.mark.asyncio
    async def test_explanation_styles(self, test_api_key, sample_weather_data):
        """
        Test different explanation styles produce different outputs.

        **Validates: Requirements 6.1**
        """
        explainer = AIExplainer(api_key=test_api_key, model="meta-llama/llama-3.2-3b-instruct:free")

        # Test brief style
        brief_result = await explainer.explain_weather(
            sample_weather_data, "Phoenix, AZ", ExplanationStyle.BRIEF
        )

        # Test detailed style
        detailed_result = await explainer.explain_weather(
            sample_weather_data, "Phoenix, AZ", ExplanationStyle.DETAILED
        )

        # Brief should be shorter than detailed
        assert len(brief_result.text) < len(detailed_result.text)
        assert brief_result.text != detailed_result.text

    @pytest.mark.asyncio
    async def test_weather_with_alerts(self, test_api_key):
        """
        Test explanation generation with weather alerts.

        **Validates: Requirements 6.1, 4.2**
        """
        weather_data_with_alerts = {
            "temperature": 95.0,
            "temperature_unit": "F",
            "conditions": "Hot and Sunny",
            "humidity": 30,
            "wind_speed": 5.0,
            "alerts": [
                {
                    "title": "Excessive Heat Warning",
                    "severity": "Major",
                    "description": "Dangerous heat conditions expected",
                }
            ],
        }

        explainer = AIExplainer(api_key=test_api_key, model="meta-llama/llama-3.2-3b-instruct:free")

        result = await explainer.explain_weather(weather_data_with_alerts, "Las Vegas, NV")

        # Explanation should mention the heat warning
        assert "heat" in result.text.lower() or "warning" in result.text.lower()
        assert len(result.text) > 0

    @pytest.mark.asyncio
    async def test_afd_explanation(self, test_api_key):
        """
        Test Area Forecast Discussion explanation.

        **Validates: Requirements 6.1**
        """
        sample_afd = """
        FXUS61 KBOU 081745
        AFDDEN

        Area Forecast Discussion
        National Weather Service Denver CO
        1045 AM MST Thu Dec 8 2024

        .SHORT TERM /TODAY THROUGH FRIDAY/...
        High pressure continues to dominate the weather pattern across
        the region. Expect mostly sunny skies with light winds.
        Temperatures will be near normal for this time of year.
        """

        explainer = AIExplainer(api_key=test_api_key, model="meta-llama/llama-3.2-3b-instruct:free")

        result = await explainer.explain_afd(sample_afd, "Denver, CO")

        # Should get a plain language explanation
        assert len(result.text) > 0
        assert "sunny" in result.text.lower() or "clear" in result.text.lower()
        # Should not contain technical jargon
        assert "FXUS61" not in result.text
        assert "KBOU" not in result.text


class TestErrorScenarios:
    """Integration tests for error scenarios."""

    @pytest.mark.asyncio
    async def test_invalid_api_key(self, sample_weather_data):
        """
        Test handling of invalid API key.

        **Validates: Requirements 6.4, 5.2**
        """
        explainer = AIExplainer(api_key="sk-or-invalid-key-12345")

        with pytest.raises(InvalidAPIKeyError) as exc_info:
            await explainer.explain_weather(sample_weather_data, "Test City")

        # Error message should be user-friendly
        error_msg = str(exc_info.value)
        assert "invalid" in error_msg.lower() or "authentication" in error_msg.lower()
        # Should not contain raw HTTP details
        assert "401" not in error_msg or "Details:" in error_msg  # Details section is OK

    @pytest.mark.asyncio
    async def test_api_key_validation(self):
        """
        Test API key validation method.

        **Validates: Requirements 6.4, 3.2**
        """
        explainer = AIExplainer()

        # Test invalid key
        is_valid = await explainer.validate_api_key("sk-or-invalid-key-12345")
        assert is_valid is False

        # Test malformed key
        is_valid = await explainer.validate_api_key("invalid-format")
        assert is_valid is False

    @pytest.mark.asyncio
    async def test_api_key_validation_with_valid_key(self):
        """
        Test API key validation with valid key.

        **Validates: Requirements 6.4, 3.2**
        """
        test_api_key = os.environ.get("OPENROUTER_TEST_API_KEY")
        if not test_api_key:
            pytest.skip("OPENROUTER_TEST_API_KEY environment variable not set")

        explainer = AIExplainer()

        # Test valid key
        is_valid = await explainer.validate_api_key(test_api_key)
        assert is_valid is True

    @pytest.mark.asyncio
    async def test_network_error_simulation(self, sample_weather_data):
        """
        Test handling of network errors.

        **Validates: Requirements 6.4, 5.1**
        """
        # Mock network failure
        with patch("openai.OpenAI") as mock_openai:
            mock_client = mock_openai.return_value
            mock_client.chat.completions.create.side_effect = Exception("Connection failed")

            explainer = AIExplainer(api_key="sk-or-test-key")

            with pytest.raises(AIExplainerError) as exc_info:
                await explainer.explain_weather(sample_weather_data, "Test City")

            # Should get user-friendly error
            error_msg = str(exc_info.value)
            assert len(error_msg) > 0
            # Should contain the original error for debugging
            assert "Connection failed" in error_msg

    @pytest.fixture
    def sample_weather_data(self):
        """Sample weather data for error testing."""
        return {
            "temperature": 70.0,
            "temperature_unit": "F",
            "conditions": "Clear",
            "humidity": 50,
            "wind_speed": 5.0,
        }


class TestCachingBehavior:
    """Integration tests for caching behavior."""

    @pytest.mark.asyncio
    async def test_cache_prevents_duplicate_calls(self):
        """
        Test that caching prevents duplicate API calls.

        **Validates: Requirements 6.1, 2.4**
        """
        test_api_key = os.environ.get("OPENROUTER_TEST_API_KEY")
        if not test_api_key:
            pytest.skip("OPENROUTER_TEST_API_KEY environment variable not set")

        from accessiweather.cache import Cache

        cache = Cache(default_ttl=300)
        explainer = AIExplainer(
            api_key=test_api_key, model="meta-llama/llama-3.2-3b-instruct:free", cache=cache
        )

        weather_data = {
            "temperature": 75.0,
            "conditions": "Sunny",
            "humidity": 40,
        }

        # First call should hit API
        result1 = await explainer.explain_weather(weather_data, "Miami, FL")
        assert result1.cached is False

        # Second call should use cache
        result2 = await explainer.explain_weather(weather_data, "Miami, FL")
        assert result2.cached is True

        # Results should be identical
        assert result1.text == result2.text
        assert result1.model_used == result2.model_used

    @pytest.mark.asyncio
    async def test_different_data_bypasses_cache(self):
        """
        Test that different weather data bypasses cache.

        **Validates: Requirements 6.1, 2.4**
        """
        test_api_key = os.environ.get("OPENROUTER_TEST_API_KEY")
        if not test_api_key:
            pytest.skip("OPENROUTER_TEST_API_KEY environment variable not set")

        from accessiweather.cache import Cache

        cache = Cache(default_ttl=300)
        explainer = AIExplainer(
            api_key=test_api_key, model="meta-llama/llama-3.2-3b-instruct:free", cache=cache
        )

        weather_data1 = {"temperature": 70.0, "conditions": "Sunny"}
        weather_data2 = {"temperature": 80.0, "conditions": "Hot"}

        # Both calls should hit API (different data)
        result1 = await explainer.explain_weather(weather_data1, "City A")
        result2 = await explainer.explain_weather(weather_data2, "City B")

        assert result1.cached is False
        assert result2.cached is False
        # Results should be different
        assert result1.text != result2.text


class TestRateLimiting:
    """Integration tests for rate limiting behavior."""

    @pytest.mark.asyncio
    async def test_rate_limit_handling(self):
        """
        Test rate limit error handling.

        Note: This test may not trigger actual rate limits in normal testing,
        but verifies the error handling code path.

        **Validates: Requirements 6.4, 5.4**
        """
        # Mock rate limit response
        with patch("openai.OpenAI") as mock_openai:
            mock_client = mock_openai.return_value

            # Simulate rate limit error
            rate_limit_error = Exception("Rate limit exceeded")
            rate_limit_error.response = type(
                "obj", (object,), {"status_code": 429, "text": "Rate limit exceeded"}
            )
            mock_client.chat.completions.create.side_effect = rate_limit_error

            explainer = AIExplainer(api_key="sk-or-test-key")

            with pytest.raises(AIExplainerError) as exc_info:
                await explainer.explain_weather(
                    {"temperature": 70, "conditions": "Clear"}, "Test City"
                )

            # Should get user-friendly rate limit message
            error_msg = str(exc_info.value)
            assert "rate limit" in error_msg.lower() or "too many" in error_msg.lower()

    @pytest.mark.asyncio
    async def test_multiple_rapid_requests(self):
        """
        Test behavior with multiple rapid requests.

        This test makes several requests in quick succession to test
        both caching and potential rate limiting.

        **Validates: Requirements 6.1, 2.4**
        """
        test_api_key = os.environ.get("OPENROUTER_TEST_API_KEY")
        if not test_api_key:
            pytest.skip("OPENROUTER_TEST_API_KEY environment variable not set")

        from accessiweather.cache import Cache

        cache = Cache(default_ttl=300)
        explainer = AIExplainer(
            api_key=test_api_key, model="meta-llama/llama-3.2-3b-instruct:free", cache=cache
        )

        weather_data = {
            "temperature": 68.0,
            "conditions": "Overcast",
            "humidity": 80,
        }

        # Make multiple requests rapidly
        tasks = []
        for i in range(3):
            task = explainer.explain_weather(weather_data, f"City {i}")
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # At least one should succeed
        successful_results = [r for r in results if not isinstance(r, Exception)]
        assert len(successful_results) > 0

        # If any failed, they should be proper exceptions
        failed_results = [r for r in results if isinstance(r, Exception)]
        for failure in failed_results:
            assert isinstance(failure, (AIExplainerError, RateLimitError))


class TestModelFallback:
    """Integration tests for model fallback behavior."""

    @pytest.mark.asyncio
    async def test_fallback_model_usage(self):
        """
        Test that fallback models are used when primary model fails.

        **Validates: Requirements 6.1**
        """
        test_api_key = os.environ.get("OPENROUTER_TEST_API_KEY")
        if not test_api_key:
            pytest.skip("OPENROUTER_TEST_API_KEY environment variable not set")

        explainer = AIExplainer(
            api_key=test_api_key,
            model="meta-llama/llama-3.2-3b-instruct:free",  # Primary free model
        )

        weather_data = {
            "temperature": 65.0,
            "conditions": "Cloudy",
            "humidity": 70,
        }

        # Should get a result (either from primary or fallback model)
        result = await explainer.explain_weather(weather_data, "Portland, OR")

        assert result.text is not None
        assert len(result.text) > 0
        assert result.model_used is not None
        # Should be a free model (either primary or fallback)
        assert ":free" in result.model_used or "free" in result.model_used.lower()

    @pytest.mark.asyncio
    async def test_all_models_fail_scenario(self):
        """
        Test behavior when all models fail to return content.

        **Validates: Requirements 6.4, 5.1**
        """
        # Mock all models returning empty responses
        with patch("openai.OpenAI") as mock_openai:
            mock_client = mock_openai.return_value
            mock_response = type(
                "obj",
                (object,),
                {
                    "choices": [
                        type("obj", (object,), {"message": type("obj", (object,), {"content": ""})})
                    ],
                    "model": "test-model",
                    "usage": type(
                        "obj",
                        (object,),
                        {"total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0},
                    ),
                },
            )
            mock_client.chat.completions.create.return_value = mock_response

            explainer = AIExplainer(api_key="sk-or-test-key")

            with pytest.raises(AIExplainerError) as exc_info:
                await explainer.explain_weather(
                    {"temperature": 70, "conditions": "Clear"}, "Test City"
                )

            # Should get appropriate error message
            error_msg = str(exc_info.value)
            assert "empty response" in error_msg.lower() or "try again" in error_msg.lower()


class TestForecastExplanationIntegration:
    """Integration tests for forecast explanation with real API."""

    @pytest.fixture
    def test_api_key(self):
        """Get test API key from environment."""
        api_key = os.environ.get("OPENROUTER_TEST_API_KEY")
        if not api_key:
            pytest.skip("OPENROUTER_TEST_API_KEY environment variable not set")
        return api_key

    @pytest.mark.asyncio
    async def test_forecast_periods_in_explanation(self, test_api_key):
        """
        Test that forecast periods are included in weather explanation.

        **Validates: Requirements 1.2, 1.6**
        """
        weather_data_with_forecast = {
            "temperature": 72.0,
            "temperature_unit": "F",
            "conditions": "Partly Cloudy",
            "humidity": 55,
            "wind_speed": 10.0,
            "wind_direction": "SW",
            "alerts": [],
            "forecast_periods": [
                {
                    "name": "Tonight",
                    "temperature": 58,
                    "temperature_unit": "F",
                    "short_forecast": "Mostly Clear",
                    "wind_speed": "5 mph",
                    "wind_direction": "W",
                },
                {
                    "name": "Tomorrow",
                    "temperature": 75,
                    "temperature_unit": "F",
                    "short_forecast": "Sunny",
                    "wind_speed": "10 mph",
                    "wind_direction": "SW",
                },
                {
                    "name": "Tomorrow Night",
                    "temperature": 60,
                    "temperature_unit": "F",
                    "short_forecast": "Clear",
                    "wind_speed": "5 mph",
                    "wind_direction": "NW",
                },
            ],
        }

        explainer = AIExplainer(api_key=test_api_key, model="meta-llama/llama-3.2-3b-instruct:free")

        result = await explainer.explain_weather(weather_data_with_forecast, "Seattle, WA")

        # Explanation should mention forecast information
        assert result.text is not None
        assert len(result.text) > 0
        # Should reference upcoming weather (tonight, tomorrow, etc.)
        text_lower = result.text.lower()
        assert any(
            word in text_lower
            for word in ["tonight", "tomorrow", "coming", "expect", "forecast", "later"]
        )

    @pytest.mark.asyncio
    async def test_explanation_without_forecast(self, test_api_key):
        """
        Test explanation generation without forecast periods.

        **Validates: Requirements 1.2**
        """
        weather_data_no_forecast = {
            "temperature": 68.0,
            "temperature_unit": "F",
            "conditions": "Clear",
            "humidity": 45,
            "wind_speed": 5.0,
            "alerts": [],
            "forecast_periods": [],
        }

        explainer = AIExplainer(api_key=test_api_key, model="meta-llama/llama-3.2-3b-instruct:free")

        result = await explainer.explain_weather(weather_data_no_forecast, "Denver, CO")

        # Should still get a valid explanation
        assert result.text is not None
        assert len(result.text) > 0


class TestAFDExplanationIntegration:
    """Integration tests for AFD explanation with real API."""

    @pytest.fixture
    def test_api_key(self):
        """Get test API key from environment."""
        api_key = os.environ.get("OPENROUTER_TEST_API_KEY")
        if not api_key:
            pytest.skip("OPENROUTER_TEST_API_KEY environment variable not set")
        return api_key

    @pytest.fixture
    def sample_afd_text(self):
        """Sample AFD text with technical meteorological content."""
        return """
        FXUS65 KBOU 111200
        AFDDEN

        Area Forecast Discussion
        National Weather Service Denver CO
        500 AM MST Wed Dec 11 2024

        .SYNOPSIS...
        A Pacific trough will move through the region today bringing
        increasing clouds and a chance of light snow to the mountains.
        High pressure builds in Thursday for dry conditions through
        the weekend. Another system approaches early next week.

        .NEAR TERM /TODAY THROUGH TONIGHT/...
        500mb heights around 560dm this morning with weak ridging over
        the intermountain west. A shortwave trough currently over the
        Pacific Northwest will dig southeast through the day. This will
        bring increasing mid and high clouds to the region by afternoon.

        QPF amounts remain light, generally under 0.10" liquid equivalent
        for the mountains. Snow levels will be around 9000 feet initially
        but drop to 7500 feet by tonight.

        .SHORT TERM /THURSDAY THROUGH SATURDAY/...
        Upper level ridging builds in behind the departing trough.
        Expect mostly sunny skies and near normal temperatures.
        Highs in the mid 40s to low 50s for the metro area.
        """

    @pytest.mark.asyncio
    async def test_afd_plain_language_explanation(self, test_api_key, sample_afd_text):
        """
        Test that AFD explanation translates technical jargon.

        **Validates: Requirements 9.2, 9.3**
        """
        explainer = AIExplainer(api_key=test_api_key, model="meta-llama/llama-3.2-3b-instruct:free")

        result = await explainer.explain_afd(sample_afd_text, "Denver, CO")

        # Should get a plain language explanation
        assert result.text is not None
        assert len(result.text) > 0

        # Should NOT contain technical jargon
        text_upper = result.text.upper()
        assert "FXUS65" not in text_upper
        assert "KBOU" not in text_upper
        assert "500MB" not in text_upper
        assert "560DM" not in text_upper
        assert "QPF" not in text_upper

    @pytest.mark.asyncio
    async def test_afd_highlights_key_events(self, test_api_key, sample_afd_text):
        """
        Test that AFD explanation highlights key weather events.

        **Validates: Requirements 9.4**
        """
        explainer = AIExplainer(api_key=test_api_key, model="meta-llama/llama-3.2-3b-instruct:free")

        result = await explainer.explain_afd(sample_afd_text, "Denver, CO")

        # Should mention key weather events
        text_lower = result.text.lower()
        # Should reference snow, clouds, or weather changes
        assert any(
            word in text_lower
            for word in ["snow", "cloud", "weather", "temperature", "sunny", "dry"]
        )

    @pytest.mark.asyncio
    async def test_afd_different_styles(self, test_api_key, sample_afd_text):
        """
        Test AFD explanation with different styles.

        **Validates: Requirements 9.2**
        """
        explainer = AIExplainer(api_key=test_api_key, model="meta-llama/llama-3.2-3b-instruct:free")

        # Test brief style
        brief_result = await explainer.explain_afd(
            sample_afd_text, "Denver, CO", ExplanationStyle.BRIEF
        )

        # Test detailed style (default)
        detailed_result = await explainer.explain_afd(
            sample_afd_text, "Denver, CO", ExplanationStyle.DETAILED
        )

        # Both should produce valid explanations
        assert brief_result.text is not None
        assert detailed_result.text is not None
        assert len(brief_result.text) > 0
        assert len(detailed_result.text) > 0

        # Brief should generally be shorter than detailed
        # (though AI responses can vary)
        assert len(brief_result.text) <= len(detailed_result.text) * 1.5
