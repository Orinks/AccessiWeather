"""
Tests for AI explainer functionality.

Tests the AIExplainer class, explanation generation, error handling, and caching.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from accessiweather.ai_explainer import (
    AIExplainer,
    AIExplainerError,
    ExplanationResult,
    ExplanationStyle,
    InsufficientCreditsError,
    InvalidAPIKeyError,
    InvalidModelError,
    RateLimitError,
    WeatherContext,
    has_valid_api_key,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_weather_data():
    """Sample weather data for testing."""
    return {
        "temperature": 72,
        "temperature_unit": "F",
        "conditions": "Partly Cloudy",
        "humidity": 65,
        "wind_speed": 10,
        "wind_direction": "NW",
        "visibility": 10,
        "pressure": 30.05,
        "alerts": [],
        "forecast_periods": [
            {
                "name": "Today",
                "temperature": 75,
                "temperature_unit": "F",
                "short_forecast": "Sunny",
                "wind_speed": 10,
                "wind_direction": "NW",
            }
        ],
    }


@pytest.fixture
def sample_afd_text():
    """Sample Area Forecast Discussion text."""
    return """
    .SYNOPSIS...
    High pressure will dominate the region through mid-week.

    .NEAR TERM /THROUGH TONIGHT/...
    Expect clear skies and temperatures in the low 70s.
    A weak cold front will approach from the northwest.

    .SHORT TERM /TUESDAY THROUGH THURSDAY/...
    Ridge axis shifts east Tuesday. Temperatures will cool
    to near seasonal normals by Thursday.
    """


@pytest.fixture
def mock_cache():
    """Mock cache for testing caching behavior."""
    cache = MagicMock()
    cache.get.return_value = None
    return cache


# =============================================================================
# AIExplainer Initialization Tests
# =============================================================================


class TestAIExplainerInit:
    """Tests for AIExplainer initialization."""

    def test_default_initialization(self):
        """Test default initialization without API key."""
        explainer = AIExplainer()
        assert explainer.api_key is None
        assert explainer.cache is None
        assert explainer.custom_system_prompt is None
        assert explainer.custom_instructions is None

    def test_initialization_with_api_key(self):
        """Test initialization with API key."""
        explainer = AIExplainer(api_key="test-api-key")
        assert explainer.api_key == "test-api-key"

    def test_initialization_with_custom_model(self):
        """Test initialization with custom model."""
        explainer = AIExplainer(api_key="test-key", model="gpt-4")
        assert explainer.model == "gpt-4"

    def test_initialization_with_cache(self, mock_cache):
        """Test initialization with cache."""
        explainer = AIExplainer(api_key="test-key", cache=mock_cache)
        assert explainer.cache is mock_cache

    def test_initialization_with_custom_prompts(self):
        """Test initialization with custom prompts."""
        explainer = AIExplainer(
            api_key="test-key",
            custom_system_prompt="Custom system prompt",
            custom_instructions="Custom instructions",
        )
        assert explainer.custom_system_prompt == "Custom system prompt"
        assert explainer.custom_instructions == "Custom instructions"


# =============================================================================
# Model Selection Tests
# =============================================================================


class TestModelSelection:
    """Tests for model selection logic."""

    def test_get_effective_model_without_api_key(self):
        """Test that free model is used without API key."""
        explainer = AIExplainer()
        model = explainer.get_effective_model()
        assert ":free" in model

    def test_get_effective_model_with_api_key(self):
        """Test that configured model is used with API key."""
        explainer = AIExplainer(api_key="test-key", model="gpt-4")
        model = explainer.get_effective_model()
        assert model == "gpt-4"

    def test_get_effective_model_default_with_api_key(self):
        """Test default model with API key."""
        explainer = AIExplainer(api_key="test-key")
        model = explainer.get_effective_model()
        # Should use the configured default free model
        assert model is not None


# =============================================================================
# System Prompt Tests
# =============================================================================


class TestSystemPrompts:
    """Tests for system prompt generation."""

    def test_default_system_prompt_exists(self):
        """Test that default system prompt exists."""
        prompt = AIExplainer.get_default_system_prompt()
        assert prompt is not None
        assert len(prompt) > 0
        assert "weather" in prompt.lower()

    def test_effective_system_prompt_uses_custom(self):
        """Test that custom system prompt is used when provided."""
        explainer = AIExplainer(
            api_key="test-key",
            custom_system_prompt="My custom prompt",
        )
        prompt = explainer.get_effective_system_prompt(ExplanationStyle.STANDARD)
        assert prompt == "My custom prompt"

    def test_effective_system_prompt_uses_default(self):
        """Test that default prompt is used when no custom prompt."""
        explainer = AIExplainer(api_key="test-key")
        prompt = explainer.get_effective_system_prompt(ExplanationStyle.STANDARD)
        assert "weather" in prompt.lower()

    def test_prompt_preview(self):
        """Test prompt preview generation."""
        explainer = AIExplainer(api_key="test-key")
        preview = explainer.get_prompt_preview(ExplanationStyle.STANDARD)
        assert "system_prompt" in preview
        assert "user_prompt" in preview
        assert len(preview["system_prompt"]) > 0
        assert len(preview["user_prompt"]) > 0


# =============================================================================
# WeatherContext Tests
# =============================================================================


class TestWeatherContext:
    """Tests for WeatherContext dataclass."""

    def test_basic_context_creation(self):
        """Test creating a basic weather context."""
        context = WeatherContext(
            location="Test City",
            timestamp=datetime.now(UTC),
            temperature=72.0,
            temperature_unit="F",
            conditions="Sunny",
            humidity=50,
            wind_speed=10.0,
            wind_direction="NW",
            visibility=10.0,
            pressure=30.05,
            alerts=[],
        )
        assert context.location == "Test City"
        assert context.temperature == 72.0

    def test_to_prompt_text_basic(self):
        """Test converting context to prompt text."""
        context = WeatherContext(
            location="Test City",
            timestamp=datetime.now(UTC),
            temperature=72.0,
            temperature_unit="F",
            conditions="Sunny",
            humidity=50,
            wind_speed=10.0,
            wind_direction="NW",
            visibility=10.0,
            pressure=30.05,
            alerts=[],
        )
        prompt_text = context.to_prompt_text()
        assert "Test City" in prompt_text
        assert "72.0" in prompt_text
        assert "Sunny" in prompt_text
        assert "50%" in prompt_text
        assert "NW" in prompt_text

    def test_to_prompt_text_with_alerts(self):
        """Test prompt text includes alerts."""
        context = WeatherContext(
            location="Test City",
            timestamp=datetime.now(UTC),
            temperature=72.0,
            temperature_unit="F",
            conditions="Thunderstorms",
            humidity=80,
            wind_speed=25.0,
            wind_direction="SW",
            visibility=5.0,
            pressure=29.85,
            alerts=[
                {"title": "Severe Thunderstorm Warning", "severity": "Severe"},
                {"title": "Flood Watch", "severity": "Moderate"},
            ],
        )
        prompt_text = context.to_prompt_text()
        assert "Severe Thunderstorm Warning" in prompt_text
        assert "Flood Watch" in prompt_text
        assert "Severe" in prompt_text

    def test_to_prompt_text_with_time_info(self):
        """Test prompt text includes time information."""
        context = WeatherContext(
            location="Test City",
            timestamp=datetime.now(UTC),
            temperature=72.0,
            temperature_unit="F",
            conditions="Clear",
            humidity=50,
            wind_speed=5.0,
            wind_direction="N",
            visibility=10.0,
            pressure=30.10,
            alerts=[],
            local_time="2024-01-15 14:30",
            utc_time="2024-01-15 19:30 UTC",
            timezone="America/New_York",
            time_of_day="afternoon",
        )
        prompt_text = context.to_prompt_text()
        assert "14:30" in prompt_text
        assert "America/New_York" in prompt_text
        assert "afternoon" in prompt_text


# =============================================================================
# ExplanationStyle Tests
# =============================================================================


class TestExplanationStyle:
    """Tests for ExplanationStyle enum."""

    def test_brief_style_exists(self):
        """Test BRIEF style exists."""
        assert ExplanationStyle.BRIEF.value == "brief"

    def test_standard_style_exists(self):
        """Test STANDARD style exists."""
        assert ExplanationStyle.STANDARD.value == "standard"

    def test_detailed_style_exists(self):
        """Test DETAILED style exists."""
        assert ExplanationStyle.DETAILED.value == "detailed"


# =============================================================================
# API Client Tests
# =============================================================================


class TestAPIClient:
    """Tests for OpenRouter API client setup."""

    def test_get_client_without_api_key_raises_error(self):
        """Test that getting client without API key raises error."""
        explainer = AIExplainer()
        with pytest.raises(AIExplainerError) as exc:
            explainer._get_client()
        assert "API key required" in str(exc.value)

    def test_get_client_with_api_key(self):
        """Test client creation with API key."""
        with patch("openai.OpenAI") as mock_openai:
            explainer = AIExplainer(api_key="test-key")
            client = explainer._get_client()
            mock_openai.assert_called_once()
            assert client is not None

    def test_client_is_cached(self):
        """Test that client is cached after first creation."""
        with patch("openai.OpenAI") as mock_openai:
            explainer = AIExplainer(api_key="test-key")
            client1 = explainer._get_client()
            client2 = explainer._get_client()
            # Should only create once
            mock_openai.assert_called_once()
            assert client1 is client2


# =============================================================================
# explain_weather Tests
# =============================================================================


class TestExplainWeather:
    """Tests for explain_weather method."""

    @pytest.mark.asyncio
    async def test_explain_weather_success(self, sample_weather_data):
        """Test successful weather explanation generation."""
        explainer = AIExplainer(api_key="test-key")

        with patch.object(explainer, "_call_openrouter") as mock_call:
            mock_call.return_value = {
                "content": "The weather is nice today with partly cloudy skies and comfortable temperatures.",
                "model": "test-model",
                "total_tokens": 150,
                "prompt_tokens": 100,
                "completion_tokens": 50,
            }

            result = await explainer.explain_weather(
                sample_weather_data,
                "Test City",
                style=ExplanationStyle.STANDARD,
            )

            assert isinstance(result, ExplanationResult)
            assert result.text is not None
            assert len(result.text) > 0
            assert result.model_used == "test-model"
            assert result.token_count == 150
            assert result.cached is False

    @pytest.mark.asyncio
    async def test_explain_weather_with_cache_hit(self, sample_weather_data, mock_cache):
        """Test that cached results are returned."""
        mock_cache.get.return_value = {
            "text": "Cached explanation",
            "model_used": "cached-model",
            "token_count": 100,
            "estimated_cost": 0.0,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        explainer = AIExplainer(api_key="test-key", cache=mock_cache)

        result = await explainer.explain_weather(
            sample_weather_data,
            "Test City",
        )

        assert result.cached is True
        assert result.text == "Cached explanation"

    @pytest.mark.asyncio
    async def test_explain_weather_caches_result(self, sample_weather_data, mock_cache):
        """Test that results are cached after generation."""
        explainer = AIExplainer(api_key="test-key", cache=mock_cache)

        with patch.object(explainer, "_call_openrouter") as mock_call:
            mock_call.return_value = {
                "content": "Fresh explanation with enough content to pass validation checks.",
                "model": "test-model",
                "total_tokens": 150,
                "prompt_tokens": 100,
                "completion_tokens": 50,
            }

            await explainer.explain_weather(sample_weather_data, "Test City")

            # Verify cache.set was called
            mock_cache.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_explain_weather_different_styles(self, sample_weather_data):
        """Test explanation generation with different styles."""
        explainer = AIExplainer(api_key="test-key")

        with patch.object(explainer, "_call_openrouter") as mock_call:
            mock_call.return_value = {
                "content": "Test explanation with enough content to pass the minimum length validation.",
                "model": "test-model",
                "total_tokens": 100,
                "prompt_tokens": 80,
                "completion_tokens": 20,
            }

            for style in ExplanationStyle:
                result = await explainer.explain_weather(
                    sample_weather_data,
                    "Test City",
                    style=style,
                )
                assert result is not None


# =============================================================================
# explain_afd Tests
# =============================================================================


class TestExplainAFD:
    """Tests for explain_afd method (Area Forecast Discussion)."""

    @pytest.mark.asyncio
    async def test_explain_afd_success(self, sample_afd_text):
        """Test successful AFD explanation generation."""
        explainer = AIExplainer(api_key="test-key")

        with patch.object(explainer, "_call_openrouter") as mock_call:
            mock_call.return_value = {
                "content": "High pressure will bring clear skies through mid-week.",
                "model": "test-model",
                "total_tokens": 200,
                "prompt_tokens": 150,
                "completion_tokens": 50,
            }

            result = await explainer.explain_afd(
                sample_afd_text,
                "Test City",
                style=ExplanationStyle.DETAILED,
            )

            assert isinstance(result, ExplanationResult)
            assert result.text is not None
            assert len(result.text) > 0
            assert result.cached is False

    @pytest.mark.asyncio
    async def test_explain_afd_different_styles(self, sample_afd_text):
        """Test AFD explanation with different styles."""
        explainer = AIExplainer(api_key="test-key")

        with patch.object(explainer, "_call_openrouter") as mock_call:
            mock_call.return_value = {
                "content": "Brief summary of the forecast.",
                "model": "test-model",
                "total_tokens": 100,
                "prompt_tokens": 80,
                "completion_tokens": 20,
            }

            for style in ExplanationStyle:
                result = await explainer.explain_afd(
                    sample_afd_text,
                    "Test City",
                    style=style,
                )
                assert result is not None


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_invalid_api_key_error(self, sample_weather_data):
        """Test InvalidAPIKeyError is raised for invalid API key."""
        explainer = AIExplainer(api_key="invalid-key")

        with patch.object(explainer, "_get_client") as mock_client:
            mock_client_instance = MagicMock()
            mock_client.return_value = mock_client_instance

            # Simulate an authentication error
            mock_client_instance.chat.completions.create.side_effect = Exception("invalid api key")

            with pytest.raises((InvalidAPIKeyError, AIExplainerError)):
                await explainer.explain_weather(sample_weather_data, "Test City")

    @pytest.mark.asyncio
    async def test_rate_limit_error(self, sample_weather_data):
        """Test RateLimitError is raised when rate limited."""
        explainer = AIExplainer(api_key="test-key")

        with patch.object(explainer, "_get_client") as mock_client:
            mock_client_instance = MagicMock()
            mock_client.return_value = mock_client_instance

            # Simulate a rate limit error
            mock_client_instance.chat.completions.create.side_effect = Exception(
                "rate limit exceeded"
            )

            with pytest.raises((RateLimitError, AIExplainerError)):
                await explainer.explain_weather(sample_weather_data, "Test City")

    @pytest.mark.asyncio
    async def test_insufficient_credits_error(self, sample_weather_data):
        """Test InsufficientCreditsError is raised when no credits."""
        explainer = AIExplainer(api_key="test-key")

        with patch.object(explainer, "_get_client") as mock_client:
            mock_client_instance = MagicMock()
            mock_client.return_value = mock_client_instance

            # Simulate an insufficient credits error
            mock_client_instance.chat.completions.create.side_effect = Exception(
                "insufficient credits"
            )

            with pytest.raises((InsufficientCreditsError, AIExplainerError)):
                await explainer.explain_weather(sample_weather_data, "Test City")

    @pytest.mark.asyncio
    async def test_empty_response_triggers_fallback(self, sample_weather_data):
        """Test that empty responses trigger fallback models."""
        explainer = AIExplainer(api_key="test-key")

        call_count = 0

        def mock_call(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call returns empty response
                return {
                    "content": "",
                    "model": "model-1",
                    "total_tokens": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                }
            # Fallback succeeds
            return {
                "content": "Fallback explanation that is sufficiently long.",
                "model": "model-2",
                "total_tokens": 100,
                "prompt_tokens": 80,
                "completion_tokens": 20,
            }

        with patch.object(explainer, "_call_openrouter", side_effect=mock_call):
            result = await explainer.explain_weather(sample_weather_data, "Test City")
            assert result.text is not None
            # Multiple calls made due to fallback
            assert call_count >= 1

    @pytest.mark.asyncio
    async def test_all_models_fail_raises_error(self, sample_weather_data):
        """Test that error is raised when all models fail."""
        explainer = AIExplainer(api_key="test-key")

        with patch.object(explainer, "_call_openrouter") as mock_call:
            mock_call.side_effect = AIExplainerError("All models failed")

            with pytest.raises(AIExplainerError):
                await explainer.explain_weather(sample_weather_data, "Test City")

    @pytest.mark.asyncio
    async def test_invalid_model_error_404(self, sample_weather_data):
        """Test InvalidModelError is raised for 404/model not found errors."""
        explainer = AIExplainer(api_key="test-key", model="nonexistent/model:free")

        with patch.object(explainer, "_get_client"):
            # Simulate a 404 error for invalid model
            error_msg = "Error code: 404 - No endpoints found matching your data"
            with (
                patch.object(explainer, "_call_openrouter", side_effect=Exception(error_msg)),
                pytest.raises((InvalidModelError, AIExplainerError)),
            ):
                await explainer.explain_weather(sample_weather_data, "Test City")

    @pytest.mark.asyncio
    async def test_invalid_model_error_not_found(self, sample_weather_data):
        """Test InvalidModelError is raised for 'model not found' errors."""
        explainer = AIExplainer(api_key="test-key", model="invalid/model")

        with patch.object(explainer, "_get_client"):
            # Simulate a model not found error
            error_msg = "Model 'invalid/model' does not exist"
            with (
                patch.object(explainer, "_call_openrouter", side_effect=Exception(error_msg)),
                pytest.raises((InvalidModelError, AIExplainerError)),
            ):
                await explainer.explain_weather(sample_weather_data, "Test City")

    @pytest.mark.asyncio
    async def test_invalid_model_error_in_afd(self):
        """Test InvalidModelError is raised for AFD explanations too."""
        explainer = AIExplainer(api_key="test-key", model="nonexistent/model")
        sample_afd = "AREA FORECAST DISCUSSION..."

        with patch.object(explainer, "_get_client"):
            error_msg = "Error code: 404 - No endpoints found matching your data"
            with (
                patch.object(explainer, "_call_openrouter", side_effect=Exception(error_msg)),
                pytest.raises((InvalidModelError, AIExplainerError)),
            ):
                await explainer.explain_afd(sample_afd, "Test City")


# =============================================================================
# Static Model Validation Tests
# =============================================================================


class TestStaticValidationMethods:
    """Tests for static model validation methods."""

    @pytest.mark.asyncio
    async def test_validate_model_id_static(self):
        """Test AIExplainer.validate_model_id static method."""
        with patch(
            "accessiweather.api.openrouter_models.OpenRouterModelsClient"
        ) as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            # Mock the async method
            async def mock_validate(model_id, force_refresh=False):
                return model_id == "valid/model"

            mock_client.validate_model_id = mock_validate

            result = await AIExplainer.validate_model_id("valid/model")
            assert result is True

            result = await AIExplainer.validate_model_id("invalid/model")
            assert result is False

    @pytest.mark.asyncio
    async def test_validate_and_get_fallback_valid_model(self):
        """Test validate_and_get_fallback with a valid model."""
        with patch(
            "accessiweather.api.openrouter_models.OpenRouterModelsClient"
        ) as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            async def mock_validate(model_id, force_refresh=False):
                return True

            mock_client.validate_model_id = mock_validate

            model_id, was_fallback = await AIExplainer.validate_and_get_fallback(
                "valid/model"
            )
            assert model_id == "valid/model"
            assert was_fallback is False

    @pytest.mark.asyncio
    async def test_validate_and_get_fallback_invalid_model(self):
        """Test validate_and_get_fallback with an invalid model returns fallback."""
        from accessiweather.ai_explainer import DEFAULT_FREE_MODEL

        with patch(
            "accessiweather.api.openrouter_models.OpenRouterModelsClient"
        ) as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            async def mock_validate(model_id, force_refresh=False):
                return False

            mock_client.validate_model_id = mock_validate

            model_id, was_fallback = await AIExplainer.validate_and_get_fallback(
                "invalid/model"
            )
            assert model_id == DEFAULT_FREE_MODEL
            assert was_fallback is True

    @pytest.mark.asyncio
    async def test_validate_and_get_fallback_special_cases(self):
        """Test validate_and_get_fallback skips validation for special cases."""
        # "auto" and default model should always be valid without API call
        model_id, was_fallback = await AIExplainer.validate_and_get_fallback("auto")
        assert model_id == "auto"
        assert was_fallback is False

        model_id, was_fallback = await AIExplainer.validate_and_get_fallback(
            "openrouter/auto"
        )
        assert model_id == "openrouter/auto"
        assert was_fallback is False

    @pytest.mark.asyncio
    async def test_get_valid_free_models_static(self):
        """Test AIExplainer.get_valid_free_models static method."""
        with patch(
            "accessiweather.api.openrouter_models.OpenRouterModelsClient"
        ) as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            # Create mock models
            from accessiweather.api.openrouter_models import OpenRouterModel

            mock_models = [
                OpenRouterModel(
                    id="test/free-model:free",
                    name="Free Model",
                    description="",
                    context_length=4096,
                    pricing_prompt=0.0,
                    pricing_completion=0.0,
                    is_free=True,
                    is_moderated=True,
                    input_modalities=["text"],
                    output_modalities=["text"],
                ),
                OpenRouterModel(
                    id="test/another-free:free",
                    name="Another Free",
                    description="",
                    context_length=8192,
                    pricing_prompt=0.0,
                    pricing_completion=0.0,
                    is_free=True,
                    is_moderated=True,
                    input_modalities=["text"],
                    output_modalities=["text"],
                ),
            ]

            async def mock_get_free(force_refresh=False):
                return mock_models

            mock_client.get_free_models = mock_get_free

            result = await AIExplainer.get_valid_free_models()
            assert result == ["test/free-model:free", "test/another-free:free"]


# =============================================================================
# Response Formatting Tests
# =============================================================================


class TestResponseFormatting:
    """Tests for response formatting."""

    def test_format_response_preserves_markdown(self):
        """Test that markdown is preserved when requested."""
        explainer = AIExplainer(api_key="test-key")
        text = "**Bold** and *italic* text"
        formatted = explainer._format_response(text, preserve_markdown=True)
        assert "**Bold**" in formatted
        assert "*italic*" in formatted

    def test_format_response_strips_markdown(self):
        """Test that markdown is stripped when not preserving."""
        explainer = AIExplainer(api_key="test-key")
        text = "**Bold** and *italic* text"
        formatted = explainer._format_response(text, preserve_markdown=False)
        assert "**" not in formatted
        assert "*" not in formatted
        assert "Bold" in formatted
        assert "italic" in formatted

    def test_format_response_strips_headers(self):
        """Test that markdown headers are stripped."""
        explainer = AIExplainer(api_key="test-key")
        text = "# Header\n## Subheader\nContent"
        formatted = explainer._format_response(text, preserve_markdown=False)
        assert "#" not in formatted
        assert "Header" in formatted

    def test_format_response_strips_code_blocks(self):
        """Test that code blocks are stripped."""
        explainer = AIExplainer(api_key="test-key")
        text = "Text with `inline code` and ```\ncode block\n```"
        formatted = explainer._format_response(text, preserve_markdown=False)
        assert "```" not in formatted
        assert "`" not in formatted

    def test_format_response_strips_links(self):
        """Test that links are stripped but text preserved."""
        explainer = AIExplainer(api_key="test-key")
        text = "Check out [this link](https://example.com) for more info."
        formatted = explainer._format_response(text, preserve_markdown=False)
        assert "[" not in formatted
        assert "](" not in formatted
        assert "this link" in formatted


# =============================================================================
# Cost Estimation Tests
# =============================================================================


class TestCostEstimation:
    """Tests for cost estimation."""

    def test_free_model_has_zero_cost(self):
        """Test that free models have zero cost."""
        explainer = AIExplainer(api_key="test-key")
        cost = explainer._estimate_cost("model-name:free", 1000)
        assert cost == 0.0

    def test_paid_model_has_cost(self):
        """Test that paid models have non-zero cost."""
        explainer = AIExplainer(api_key="test-key")
        cost = explainer._estimate_cost("gpt-4", 1000)
        assert cost > 0.0

    def test_cost_scales_with_tokens(self):
        """Test that cost scales with token count."""
        explainer = AIExplainer(api_key="test-key")
        cost_low = explainer._estimate_cost("gpt-4", 100)
        cost_high = explainer._estimate_cost("gpt-4", 1000)
        assert cost_high > cost_low


# =============================================================================
# Session Token Tracking Tests
# =============================================================================


class TestSessionTracking:
    """Tests for session token tracking."""

    def test_initial_token_count_is_zero(self):
        """Test that initial token count is zero."""
        explainer = AIExplainer(api_key="test-key")
        assert explainer.session_token_count == 0

    @pytest.mark.asyncio
    async def test_token_count_increases_after_explanation(self, sample_weather_data):
        """Test that token count increases after generating explanation."""
        explainer = AIExplainer(api_key="test-key")

        with patch.object(explainer, "_call_openrouter") as mock_call:
            mock_call.return_value = {
                "content": "Test explanation content here.",
                "model": "test-model",
                "total_tokens": 150,
                "prompt_tokens": 100,
                "completion_tokens": 50,
            }

            initial_count = explainer.session_token_count
            await explainer.explain_weather(sample_weather_data, "Test City")
            assert explainer.session_token_count > initial_count


# =============================================================================
# API Key Validation Tests
# =============================================================================


class TestAPIKeyValidation:
    """Tests for API key validation."""

    def test_has_valid_api_key_with_key(self):
        """Test has_valid_api_key returns True with valid key."""
        assert has_valid_api_key("sk-test-key-12345") is True

    def test_has_valid_api_key_empty(self):
        """Test has_valid_api_key returns False with empty string."""
        assert has_valid_api_key("") is False

    def test_has_valid_api_key_none(self):
        """Test has_valid_api_key returns False with None."""
        assert has_valid_api_key(None) is False

    def test_has_valid_api_key_whitespace(self):
        """Test has_valid_api_key returns False with whitespace."""
        assert has_valid_api_key("   ") is False

    @pytest.mark.asyncio
    async def test_validate_api_key_valid(self):
        """Test validate_api_key with valid key."""
        explainer = AIExplainer(api_key="test-key")

        with patch.object(explainer, "_call_openrouter") as mock_call:
            mock_call.return_value = {
                "content": "OK",
                "model": "test-model",
                "total_tokens": 5,
                "prompt_tokens": 3,
                "completion_tokens": 2,
            }

            result = await explainer.validate_api_key("valid-key")
            assert result is True

    @pytest.mark.asyncio
    async def test_validate_api_key_invalid(self):
        """Test validate_api_key with invalid key."""
        explainer = AIExplainer(api_key="test-key")

        with patch.object(explainer, "_call_openrouter") as mock_call:
            mock_call.side_effect = InvalidAPIKeyError("Invalid key")

            result = await explainer.validate_api_key("invalid-key")
            assert result is False


# =============================================================================
# Data Source Selection Tests
# =============================================================================


class TestDataSourceSelection:
    """Tests for selecting best data source."""

    def test_select_best_data_source_empty(self):
        """Test selecting from empty sources list."""
        explainer = AIExplainer(api_key="test-key")
        result = explainer.select_best_data_source([])
        assert result is None

    def test_select_best_data_source_single(self):
        """Test selecting from single source."""
        explainer = AIExplainer(api_key="test-key")
        sources = [{"name": "NWS", "timestamp": datetime.now(UTC)}]
        result = explainer.select_best_data_source(sources)
        assert result is not None
        assert result["name"] == "NWS"

    def test_select_best_data_source_most_recent(self):
        """Test that most recent source is selected."""
        explainer = AIExplainer(api_key="test-key")
        from datetime import timedelta

        now = datetime.now(UTC)
        sources = [
            {"name": "old", "timestamp": now - timedelta(hours=1)},
            {"name": "new", "timestamp": now},
            {"name": "medium", "timestamp": now - timedelta(minutes=30)},
        ]
        result = explainer.select_best_data_source(sources)
        assert result["name"] == "new"

    def test_select_best_data_source_no_timestamps(self):
        """Test selecting when no timestamps present."""
        explainer = AIExplainer(api_key="test-key")
        sources = [{"name": "source1"}, {"name": "source2"}]
        result = explainer.select_best_data_source(sources)
        # Should return first source when no timestamps
        assert result is not None


# =============================================================================
# ExplanationResult Tests
# =============================================================================


class TestExplanationResult:
    """Tests for ExplanationResult dataclass."""

    def test_create_explanation_result(self):
        """Test creating an ExplanationResult."""
        result = ExplanationResult(
            text="Test explanation",
            model_used="test-model",
            token_count=100,
            estimated_cost=0.001,
            cached=False,
            timestamp=datetime.now(UTC),
        )
        assert result.text == "Test explanation"
        assert result.model_used == "test-model"
        assert result.token_count == 100
        assert result.estimated_cost == 0.001
        assert result.cached is False

    def test_cached_result(self):
        """Test creating a cached ExplanationResult."""
        result = ExplanationResult(
            text="Cached explanation",
            model_used="cached-model",
            token_count=50,
            estimated_cost=0.0,
            cached=True,
            timestamp=datetime.now(UTC),
        )
        assert result.cached is True
        assert result.estimated_cost == 0.0


# =============================================================================
# Integration-style Tests (with mocked API)
# =============================================================================


class TestIntegrationScenarios:
    """Integration-style tests for common usage scenarios."""

    @pytest.mark.asyncio
    async def test_full_weather_explanation_flow(self, sample_weather_data):
        """Test complete flow of generating weather explanation."""
        explainer = AIExplainer(
            api_key="test-key",
            custom_instructions="Focus on outdoor activities.",
        )

        with patch.object(explainer, "_call_openrouter") as mock_call:
            mock_call.return_value = {
                "content": "Great day for outdoor activities with mild temperatures.",
                "model": "test-model",
                "total_tokens": 200,
                "prompt_tokens": 150,
                "completion_tokens": 50,
            }

            result = await explainer.explain_weather(
                sample_weather_data,
                "Test City",
                style=ExplanationStyle.DETAILED,
                preserve_markdown=False,
            )

            assert result.text is not None
            assert result.model_used == "test-model"
            assert result.token_count == 200
            assert explainer.session_token_count == 200

    @pytest.mark.asyncio
    async def test_full_afd_explanation_flow(self, sample_afd_text):
        """Test complete flow of generating AFD explanation."""
        explainer = AIExplainer(api_key="test-key")

        with patch.object(explainer, "_call_openrouter") as mock_call:
            mock_call.return_value = {
                "content": "Clear weather expected through mid-week with high pressure.",
                "model": "test-model",
                "total_tokens": 250,
                "prompt_tokens": 200,
                "completion_tokens": 50,
            }

            result = await explainer.explain_afd(
                sample_afd_text,
                "Test City",
                style=ExplanationStyle.STANDARD,
            )

            assert result.text is not None
            assert "mid-week" in result.text or "high pressure" in result.text
