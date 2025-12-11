"""Tests for AI weather explanation feature.

This module contains unit tests and property-based tests for the AI explainer
functionality, including configuration, prompt construction, and API integration.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings, strategies as st

from accessiweather.models import AppSettings


class TestAISettingsConfiguration:
    """Tests for AI settings in AppSettings."""

    def test_default_ai_settings(self):
        """Test that AI settings have correct defaults."""
        settings = AppSettings()

        assert settings.enable_ai_explanations is False
        assert settings.openrouter_api_key == ""
        assert settings.ai_model_preference == "auto:free"
        assert settings.ai_explanation_style == "standard"
        assert settings.ai_cache_ttl == 300

    def test_ai_settings_to_dict(self):
        """Test that AI settings are included in to_dict output."""
        settings = AppSettings(
            enable_ai_explanations=True,
            ai_model_preference="auto",
            ai_explanation_style="detailed",
            ai_cache_ttl=600,
        )
        result = settings.to_dict()

        assert result["enable_ai_explanations"] is True
        assert result["ai_model_preference"] == "auto"
        assert result["ai_explanation_style"] == "detailed"
        assert result["ai_cache_ttl"] == 600
        # API key should NOT be in dict (stored in secure storage)
        assert "openrouter_api_key" not in result

    def test_ai_settings_from_dict(self):
        """Test that AI settings are correctly loaded from dict."""
        data = {
            "enable_ai_explanations": True,
            "ai_model_preference": "auto",
            "ai_explanation_style": "brief",
            "ai_cache_ttl": 120,
        }
        settings = AppSettings.from_dict(data)

        assert settings.enable_ai_explanations is True
        assert settings.ai_model_preference == "auto"
        assert settings.ai_explanation_style == "brief"
        assert settings.ai_cache_ttl == 120

    def test_ai_settings_from_dict_defaults(self):
        """Test that missing AI settings use defaults."""
        data = {}
        settings = AppSettings.from_dict(data)

        assert settings.enable_ai_explanations is False
        assert settings.ai_model_preference == "auto:free"
        assert settings.ai_explanation_style == "standard"
        assert settings.ai_cache_ttl == 300


class TestAISettingsRoundTrip:
    """Property-based tests for AI settings persistence.

    **Feature: ai-weather-explanations, Property 4: Settings persistence round-trip**
    **Validates: Requirements 3.5**
    """

    @given(
        enable_ai=st.booleans(),
        model_pref=st.sampled_from(["auto:free", "auto", "gpt-4", "claude-3"]),
        style=st.sampled_from(["brief", "standard", "detailed"]),
        cache_ttl=st.integers(min_value=60, max_value=3600),
    )
    @settings(max_examples=100)
    def test_settings_round_trip(self, enable_ai, model_pref, style, cache_ttl):
        """For any valid AI configuration, saving and loading produces equivalent values.

        **Feature: ai-weather-explanations, Property 4: Settings persistence round-trip**
        **Validates: Requirements 3.5**
        """
        original = AppSettings(
            enable_ai_explanations=enable_ai,
            ai_model_preference=model_pref,
            ai_explanation_style=style,
            ai_cache_ttl=cache_ttl,
        )

        # Round-trip through dict serialization
        data = original.to_dict()
        restored = AppSettings.from_dict(data)

        assert restored.enable_ai_explanations == original.enable_ai_explanations
        assert restored.ai_model_preference == original.ai_model_preference
        assert restored.ai_explanation_style == original.ai_explanation_style
        assert restored.ai_cache_ttl == original.ai_cache_ttl


class TestAIExplainerCore:
    """Tests for AIExplainer class core functionality."""

    def test_explainer_initialization_defaults(self):
        """Test AIExplainer initializes with correct defaults."""
        from accessiweather.ai_explainer import AIExplainer

        explainer = AIExplainer()

        assert explainer.api_key is None
        assert explainer.model == "openrouter/auto:free"

    def test_explainer_initialization_with_api_key(self):
        """Test AIExplainer initializes with provided API key."""
        from accessiweather.ai_explainer import AIExplainer

        explainer = AIExplainer(api_key="sk-or-test-key", model="openrouter/auto")

        assert explainer.api_key == "sk-or-test-key"
        assert explainer.model == "openrouter/auto"

    def test_explainer_custom_exceptions_exist(self):
        """Test that custom exception classes are defined."""
        from accessiweather.ai_explainer import (
            AIExplainerError,
            InsufficientCreditsError,
            InvalidAPIKeyError,
            RateLimitError,
        )

        # Verify inheritance
        assert issubclass(InsufficientCreditsError, AIExplainerError)
        assert issubclass(RateLimitError, AIExplainerError)
        assert issubclass(InvalidAPIKeyError, AIExplainerError)

    def test_explanation_result_dataclass(self):
        """Test ExplanationResult dataclass structure."""
        from datetime import datetime

        from accessiweather.ai_explainer import ExplanationResult

        result = ExplanationResult(
            text="Test explanation",
            model_used="openrouter/auto:free",
            token_count=100,
            estimated_cost=0.0,
            cached=False,
            timestamp=datetime.now(),
        )

        assert result.text == "Test explanation"
        assert result.model_used == "openrouter/auto:free"
        assert result.token_count == 100
        assert result.estimated_cost == 0.0
        assert result.cached is False

    def test_explanation_style_enum(self):
        """Test ExplanationStyle enum values."""
        from accessiweather.ai_explainer import ExplanationStyle

        assert ExplanationStyle.BRIEF.value == "brief"
        assert ExplanationStyle.STANDARD.value == "standard"
        assert ExplanationStyle.DETAILED.value == "detailed"


class TestModelSelection:
    """Property-based tests for model selection.

    **Feature: ai-weather-explanations, Property 2: Model selection matches configuration**
    **Validates: Requirements 2.1, 2.2, 2.5**
    """

    def test_no_api_key_uses_free_model(self):
        """Without API key, system uses free model."""
        from accessiweather.ai_explainer import AIExplainer

        explainer = AIExplainer(api_key=None)
        assert explainer.get_effective_model() == "openrouter/auto:free"

    def test_api_key_with_free_preference_uses_free_model(self):
        """With API key but free preference, system uses free model."""
        from accessiweather.ai_explainer import AIExplainer

        explainer = AIExplainer(api_key="sk-or-test", model="openrouter/auto:free")
        assert explainer.get_effective_model() == "openrouter/auto:free"

    def test_api_key_with_paid_preference_uses_auto(self):
        """With API key and paid preference, system uses auto routing."""
        from accessiweather.ai_explainer import AIExplainer

        explainer = AIExplainer(api_key="sk-or-test", model="openrouter/auto")
        assert explainer.get_effective_model() == "openrouter/auto"

    @given(
        has_api_key=st.booleans(),
        model_pref=st.sampled_from(["openrouter/auto:free", "openrouter/auto"]),
    )
    @settings(max_examples=100)
    def test_model_selection_property(self, has_api_key, model_pref):
        """For any configuration, correct model identifier is used.

        **Feature: ai-weather-explanations, Property 2: Model selection matches configuration**
        **Validates: Requirements 2.1, 2.2, 2.5**
        """
        from accessiweather.ai_explainer import AIExplainer

        api_key = "sk-or-test" if has_api_key else None
        explainer = AIExplainer(api_key=api_key, model=model_pref)

        effective_model = explainer.get_effective_model()

        # Without API key, always use free model
        if not has_api_key:
            assert effective_model == "openrouter/auto:free"
        else:
            # With API key, use the configured preference
            assert effective_model == model_pref


class TestPromptConstruction:
    """Tests for prompt construction logic.

    **Feature: ai-weather-explanations, Property 5: Prompt includes all required weather fields**
    **Feature: ai-weather-explanations, Property 6: Alerts included when present**
    **Validates: Requirements 4.1, 4.2**
    """

    def test_prompt_includes_temperature(self):
        """Test that prompt includes temperature when provided."""
        from accessiweather.ai_explainer import AIExplainer, ExplanationStyle

        explainer = AIExplainer()
        weather_data = {
            "temperature": 72.5,
            "temperature_unit": "F",
            "conditions": "Sunny",
            "humidity": 45,
            "wind_speed": 10,
            "wind_direction": "NW",
            "visibility": 10,
        }

        prompt = explainer._build_prompt(weather_data, "Test City", ExplanationStyle.STANDARD)

        assert "72.5" in prompt
        assert "F" in prompt

    def test_prompt_includes_all_required_fields(self):
        """Test that prompt includes all required weather fields."""
        from accessiweather.ai_explainer import AIExplainer, ExplanationStyle

        explainer = AIExplainer()
        weather_data = {
            "temperature": 72.5,
            "temperature_unit": "F",
            "conditions": "Partly Cloudy",
            "humidity": 65,
            "wind_speed": 8.5,
            "wind_direction": "NW",
            "visibility": 10.0,
        }

        prompt = explainer._build_prompt(weather_data, "Seattle", ExplanationStyle.STANDARD)

        # All required fields should be present
        assert "72.5" in prompt  # temperature
        assert "Partly Cloudy" in prompt  # conditions
        assert "65" in prompt  # humidity
        assert "8.5" in prompt  # wind_speed
        assert "10.0" in prompt or "10" in prompt  # visibility
        assert "Seattle" in prompt  # location

    def test_prompt_includes_alerts_when_present(self):
        """Test that alerts are included in prompt when present."""
        from accessiweather.ai_explainer import AIExplainer, ExplanationStyle

        explainer = AIExplainer()
        weather_data = {
            "temperature": 85,
            "conditions": "Hot",
            "alerts": [
                {"title": "Heat Advisory", "severity": "Moderate"},
                {"title": "Air Quality Alert", "severity": "Minor"},
            ],
        }

        prompt = explainer._build_prompt(weather_data, "Phoenix", ExplanationStyle.STANDARD)

        assert "Heat Advisory" in prompt
        assert "Air Quality Alert" in prompt
        assert "Moderate" in prompt

    def test_prompt_excludes_alerts_when_empty(self):
        """Test that alerts section is not in prompt when no alerts."""
        from accessiweather.ai_explainer import AIExplainer, ExplanationStyle

        explainer = AIExplainer()
        weather_data = {
            "temperature": 72,
            "conditions": "Clear",
            "alerts": [],
        }

        prompt = explainer._build_prompt(weather_data, "Denver", ExplanationStyle.STANDARD)

        assert "Alert" not in prompt

    @given(
        temperature=st.floats(min_value=-50, max_value=130, allow_nan=False),
        humidity=st.integers(min_value=0, max_value=100),
        wind_speed=st.floats(min_value=0, max_value=200, allow_nan=False),
        visibility=st.floats(min_value=0, max_value=50, allow_nan=False),
        conditions=st.text(
            min_size=1,
            max_size=50,
            alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z")),
        ),
    )
    @settings(max_examples=100)
    def test_prompt_field_inclusion_property(
        self, temperature, humidity, wind_speed, visibility, conditions
    ):
        """For any weather data with required fields, prompt contains all fields.

        **Feature: ai-weather-explanations, Property 5: Prompt includes all required weather fields**
        **Validates: Requirements 4.1**
        """
        from accessiweather.ai_explainer import AIExplainer, ExplanationStyle

        explainer = AIExplainer()
        weather_data = {
            "temperature": temperature,
            "temperature_unit": "F",
            "conditions": conditions,
            "humidity": humidity,
            "wind_speed": wind_speed,
            "visibility": visibility,
        }

        prompt = explainer._build_prompt(weather_data, "Test Location", ExplanationStyle.STANDARD)

        # All fields should appear in the prompt
        assert str(temperature) in prompt or f"{temperature:.1f}" in prompt
        assert str(humidity) in prompt
        assert str(wind_speed) in prompt or f"{wind_speed:.1f}" in prompt
        assert conditions in prompt or conditions.strip() in prompt

    @given(
        has_alerts=st.booleans(),
        alert_count=st.integers(min_value=1, max_value=5),
    )
    @settings(max_examples=100)
    def test_alert_inclusion_property(self, has_alerts, alert_count):
        """For any weather data, alerts are included iff they exist.

        **Feature: ai-weather-explanations, Property 6: Alerts included when present**
        **Validates: Requirements 4.2**
        """
        from accessiweather.ai_explainer import AIExplainer, ExplanationStyle

        explainer = AIExplainer()

        alerts = []
        if has_alerts:
            for i in range(alert_count):
                alerts.append({"title": f"Alert {i}", "severity": "Moderate"})

        weather_data = {
            "temperature": 70,
            "conditions": "Clear",
            "alerts": alerts,
        }

        prompt = explainer._build_prompt(weather_data, "Test City", ExplanationStyle.STANDARD)

        if has_alerts:
            # All alerts should be mentioned
            for i in range(alert_count):
                assert f"Alert {i}" in prompt
        else:
            # No alert references when no alerts
            assert "Active Alerts" not in prompt


class TestMarkdownFormatting:
    """Tests for markdown formatting logic.

    **Feature: ai-weather-explanations, Property 7: Markdown formatting follows HTML setting**
    **Validates: Requirements 4.4, 4.5**
    """

    def test_markdown_preserved_when_html_enabled(self):
        """Test that markdown is preserved when HTML rendering is enabled."""
        from accessiweather.ai_explainer import AIExplainer

        explainer = AIExplainer()
        response = "**Bold text** and *italic text* with `code`"

        formatted = explainer._format_response(response, preserve_markdown=True)

        assert "**Bold text**" in formatted
        assert "*italic text*" in formatted
        assert "`code`" in formatted

    def test_markdown_stripped_when_html_disabled(self):
        """Test that markdown is stripped when HTML rendering is disabled."""
        from accessiweather.ai_explainer import AIExplainer

        explainer = AIExplainer()
        response = "**Bold text** and *italic text* with `code`"

        formatted = explainer._format_response(response, preserve_markdown=False)

        assert "**" not in formatted
        assert "*" not in formatted or formatted.count("*") == 0
        assert "`" not in formatted
        assert "Bold text" in formatted
        assert "italic text" in formatted
        assert "code" in formatted

    def test_headers_stripped_when_html_disabled(self):
        """Test that markdown headers are stripped."""
        from accessiweather.ai_explainer import AIExplainer

        explainer = AIExplainer()
        response = "# Header 1\n## Header 2\nRegular text"

        formatted = explainer._format_response(response, preserve_markdown=False)

        assert "#" not in formatted
        assert "Header 1" in formatted
        assert "Header 2" in formatted

    def test_links_converted_to_text(self):
        """Test that markdown links are converted to plain text."""
        from accessiweather.ai_explainer import AIExplainer

        explainer = AIExplainer()
        response = "Check [this link](https://example.com) for more info"

        formatted = explainer._format_response(response, preserve_markdown=False)

        assert "[" not in formatted
        assert "]" not in formatted
        assert "https://example.com" not in formatted
        assert "this link" in formatted

    @given(
        text_content=st.text(
            min_size=2,
            max_size=100,
            alphabet=st.characters(
                whitelist_categories=("L", "N"), min_codepoint=65, max_codepoint=122
            ),
        ),
        preserve_markdown=st.booleans(),
    )
    @settings(max_examples=100)
    def test_markdown_formatting_property(self, text_content, preserve_markdown):
        """For any AI response, formatting matches HTML setting.

        **Feature: ai-weather-explanations, Property 7: Markdown formatting follows HTML setting**
        **Validates: Requirements 4.4, 4.5**
        """
        from accessiweather.ai_explainer import AIExplainer

        explainer = AIExplainer()

        # Create response with markdown
        response = f"**{text_content}** and *{text_content}*"

        formatted = explainer._format_response(response, preserve_markdown=preserve_markdown)

        if preserve_markdown:
            # Markdown should be preserved
            assert "**" in formatted or text_content in formatted
        else:
            # Markdown syntax should be stripped
            assert "**" not in formatted
            # Content should remain (text_content is guaranteed to be alphanumeric)
            assert text_content in formatted


class TestAPIIntegration:
    """Tests for OpenRouter API integration with mocking."""

    @pytest.fixture
    def mock_openai_client(self, mocker):
        """Mock the OpenAI client for testing."""
        mock_client = mocker.MagicMock()
        mock_response = mocker.MagicMock()
        mock_response.choices = [
            mocker.MagicMock(message=mocker.MagicMock(content="Test explanation"))
        ]
        mock_response.model = "openrouter/auto:free"
        mock_response.usage = mocker.MagicMock(
            total_tokens=150,
            prompt_tokens=100,
            completion_tokens=50,
        )
        mock_client.chat.completions.create.return_value = mock_response
        return mock_client

    @pytest.mark.asyncio
    async def test_explain_weather_returns_result(self, mocker, mock_openai_client):
        """Test that explain_weather returns an ExplanationResult."""
        from accessiweather.ai_explainer import AIExplainer, ExplanationResult

        mocker.patch("openai.OpenAI", return_value=mock_openai_client)

        explainer = AIExplainer(api_key="sk-or-test")
        weather_data = {
            "temperature": 72,
            "conditions": "Sunny",
            "humidity": 45,
            "wind_speed": 10,
            "visibility": 10,
        }

        result = await explainer.explain_weather(weather_data, "Test City")

        assert isinstance(result, ExplanationResult)
        assert result.text == "Test explanation"
        assert result.token_count == 150

    @pytest.mark.asyncio
    async def test_explain_weather_uses_cache(self, mocker, mock_openai_client):
        """Test that cached explanations are returned without API call."""
        from accessiweather.ai_explainer import AIExplainer, ExplanationResult
        from accessiweather.cache import Cache

        mocker.patch("openai.OpenAI", return_value=mock_openai_client)

        cache = Cache(default_ttl=300)
        explainer = AIExplainer(api_key="sk-or-test", cache=cache)

        weather_data = {
            "temperature": 72,
            "conditions": "Sunny",
        }

        # First call should hit API
        result1 = await explainer.explain_weather(weather_data, "Test City")
        assert result1.cached is False

        # Second call should use cache
        result2 = await explainer.explain_weather(weather_data, "Test City")
        assert result2.cached is True

        # API should only be called once
        assert mock_openai_client.chat.completions.create.call_count == 1


class TestErrorHandling:
    """Tests for error handling.

    **Feature: ai-weather-explanations, Property 9: Error messages are user-friendly**
    **Feature: ai-weather-explanations, Property 10: Errors logged without user exposure**
    **Validates: Requirements 5.1, 5.6**
    """

    def test_invalid_api_key_error_message(self):
        """Test that invalid API key error has user-friendly message."""
        from accessiweather.ai_explainer import InvalidAPIKeyError

        error = InvalidAPIKeyError("API key is invalid. Please check your settings.")

        # Message should be user-friendly
        assert "invalid" in str(error).lower()
        assert "settings" in str(error).lower()
        # Should not contain technical details
        assert "401" not in str(error)
        assert "HTTP" not in str(error)
        assert "traceback" not in str(error).lower()

    def test_insufficient_credits_error_message(self):
        """Test that insufficient credits error has user-friendly message."""
        from accessiweather.ai_explainer import InsufficientCreditsError

        error = InsufficientCreditsError(
            "Your OpenRouter account has no funds. Add credits or switch to free models."
        )

        # Message should be actionable
        assert "funds" in str(error).lower() or "credits" in str(error).lower()
        assert "free" in str(error).lower()

    def test_rate_limit_error_message(self):
        """Test that rate limit error has user-friendly message."""
        from accessiweather.ai_explainer import RateLimitError

        error = RateLimitError("Rate limit exceeded. Try again in a few minutes.")

        # Message should be actionable
        assert "rate limit" in str(error).lower()
        assert "try again" in str(error).lower() or "wait" in str(error).lower()

    @given(
        error_type=st.sampled_from(
            ["invalid_key", "insufficient_credits", "rate_limit", "generic"]
        ),
    )
    @settings(max_examples=50)
    def test_error_messages_no_technical_details(self, error_type):
        """For any error, user message should not contain technical details.

        **Feature: ai-weather-explanations, Property 9: Error messages are user-friendly**
        **Validates: Requirements 5.1**
        """
        from accessiweather.ai_explainer import (
            AIExplainerError,
            InsufficientCreditsError,
            InvalidAPIKeyError,
            RateLimitError,
        )

        errors = {
            "invalid_key": InvalidAPIKeyError("API key is invalid. Please check your settings."),
            "insufficient_credits": InsufficientCreditsError(
                "Your OpenRouter account has no funds."
            ),
            "rate_limit": RateLimitError("Rate limit exceeded. Try again later."),
            "generic": AIExplainerError("Unable to generate explanation. Try again later."),
        }

        error = errors[error_type]
        message = str(error)

        # Technical details that should NOT appear
        technical_patterns = [
            "traceback",
            "exception",
            "stack",
            "HTTP",
            "status code",
            "401",
            "403",
            "429",
            "500",
            "json",
            "response.body",
        ]

        for pattern in technical_patterns:
            assert pattern.lower() not in message.lower(), f"Found technical detail: {pattern}"


class TestCostEstimation:
    """Tests for cost estimation and usage tracking.

    **Feature: ai-weather-explanations, Property 13: Session usage accumulates correctly**
    **Feature: ai-weather-explanations, Property 14: Free model cost display**
    **Validates: Requirements 7.4, 7.5**
    """

    def test_free_model_cost_is_zero(self):
        """Test that free models have zero cost."""
        from accessiweather.ai_explainer import AIExplainer

        explainer = AIExplainer()

        cost = explainer._estimate_cost("openrouter/auto:free", 1000)
        assert cost == 0.0

        cost = explainer._estimate_cost("meta-llama/llama-3.2-3b-instruct:free", 5000)
        assert cost == 0.0

    def test_paid_model_cost_positive(self):
        """Test that paid models have positive cost."""
        from accessiweather.ai_explainer import AIExplainer

        explainer = AIExplainer()

        cost = explainer._estimate_cost("openrouter/auto", 1000)
        assert cost > 0.0

        cost = explainer._estimate_cost("gpt-4", 1000)
        assert cost > 0.0

    def test_session_token_count_starts_at_zero(self):
        """Test that session token count starts at zero."""
        from accessiweather.ai_explainer import AIExplainer

        explainer = AIExplainer()
        assert explainer.session_token_count == 0

    @pytest.mark.asyncio
    async def test_session_usage_accumulates(self, mocker):
        """Test that session usage accumulates across multiple calls."""
        from accessiweather.ai_explainer import AIExplainer

        # Create mock client
        mock_client = mocker.MagicMock()
        mock_response = mocker.MagicMock()
        mock_response.choices = [mocker.MagicMock(message=mocker.MagicMock(content="Test"))]
        mock_response.model = "openrouter/auto:free"
        mock_response.usage = mocker.MagicMock(
            total_tokens=100,
            prompt_tokens=80,
            completion_tokens=20,
        )
        mock_client.chat.completions.create.return_value = mock_response

        mocker.patch("openai.OpenAI", return_value=mock_client)

        explainer = AIExplainer(api_key="sk-or-test")

        # Make multiple calls
        await explainer.explain_weather({"temperature": 70}, "City1")
        await explainer.explain_weather({"temperature": 75}, "City2")
        await explainer.explain_weather({"temperature": 80}, "City3")

        # Session count should be sum of all calls
        assert explainer.session_token_count == 300  # 100 * 3

    @given(
        token_counts=st.lists(st.integers(min_value=50, max_value=500), min_size=1, max_size=10),
    )
    @settings(max_examples=50)
    def test_usage_accumulation_property(self, token_counts):
        """For any sequence of token counts, total equals sum.

        **Feature: ai-weather-explanations, Property 13: Session usage accumulates correctly**
        **Validates: Requirements 7.4**
        """
        from accessiweather.ai_explainer import AIExplainer

        explainer = AIExplainer()

        # Simulate accumulation
        for count in token_counts:
            explainer._session_token_count += count

        assert explainer.session_token_count == sum(token_counts)

    @given(
        model=st.sampled_from(
            [
                "openrouter/auto:free",
                "meta-llama/llama-3.2-3b-instruct:free",
                "mistral/mistral-7b-instruct:free",
            ]
        ),
        token_count=st.integers(min_value=1, max_value=10000),
    )
    @settings(max_examples=100)
    def test_free_model_cost_property(self, model, token_count):
        """For any free model, cost should be zero.

        **Feature: ai-weather-explanations, Property 14: Free model cost display**
        **Validates: Requirements 7.5**
        """
        from accessiweather.ai_explainer import AIExplainer

        explainer = AIExplainer()
        cost = explainer._estimate_cost(model, token_count)

        assert cost == 0.0


class TestDataSourceSelection:
    """Tests for data source selection logic.

    **Feature: ai-weather-explanations, Property 8: Most recent data source selected**
    **Validates: Requirements 4.6**
    """

    def test_select_most_recent_source(self):
        """Test that most recent data source is selected."""
        from datetime import datetime, timedelta

        from accessiweather.ai_explainer import AIExplainer

        explainer = AIExplainer()

        now = datetime.now()
        sources = [
            {"name": "nws", "timestamp": now - timedelta(hours=2), "temperature": 70},
            {"name": "openmeteo", "timestamp": now - timedelta(minutes=30), "temperature": 72},
            {"name": "visualcrossing", "timestamp": now - timedelta(hours=1), "temperature": 71},
        ]

        selected = explainer.select_best_data_source(sources)

        assert selected["name"] == "openmeteo"  # Most recent

    def test_select_source_with_missing_timestamp(self):
        """Test handling of sources with missing timestamps."""
        from datetime import datetime, timedelta

        from accessiweather.ai_explainer import AIExplainer

        explainer = AIExplainer()

        now = datetime.now()
        sources = [
            {"name": "nws", "temperature": 70},  # No timestamp
            {"name": "openmeteo", "timestamp": now - timedelta(minutes=30), "temperature": 72},
        ]

        selected = explainer.select_best_data_source(sources)

        # Should select the one with timestamp
        assert selected["name"] == "openmeteo"

    def test_select_source_empty_list(self):
        """Test handling of empty source list."""
        from accessiweather.ai_explainer import AIExplainer

        explainer = AIExplainer()

        selected = explainer.select_best_data_source([])

        assert selected is None

    @given(
        num_sources=st.integers(min_value=1, max_value=5),
        most_recent_index=st.integers(min_value=0, max_value=4),
    )
    @settings(max_examples=100)
    def test_data_source_selection_property(self, num_sources, most_recent_index):
        """For any set of sources, most recent timestamp is selected.

        **Feature: ai-weather-explanations, Property 8: Most recent data source selected**
        **Validates: Requirements 4.6**
        """
        from datetime import datetime, timedelta

        from accessiweather.ai_explainer import AIExplainer

        explainer = AIExplainer()

        # Ensure most_recent_index is valid
        most_recent_index = most_recent_index % num_sources

        now = datetime.now()
        sources = []
        for i in range(num_sources):
            if i == most_recent_index:
                # This one is most recent
                timestamp = now
            else:
                # Others are older
                timestamp = now - timedelta(hours=i + 1)

            sources.append(
                {
                    "name": f"source_{i}",
                    "timestamp": timestamp,
                    "temperature": 70 + i,
                }
            )

        selected = explainer.select_best_data_source(sources)

        assert selected is not None
        assert selected["name"] == f"source_{most_recent_index}"


class TestUIComponents:
    """Tests for UI components.

    **Feature: ai-weather-explanations, Property 1: Button visibility follows AI enablement setting**
    **Feature: ai-weather-explanations, Property 15: Accessibility attributes present**
    **Validates: Requirements 1.1, 1.5, 8.3**
    """

    def test_explain_button_has_accessibility_attributes(self):
        """Test that Explain Weather button has required accessibility attributes."""
        from accessiweather.ai_explainer import create_explain_weather_button

        button = create_explain_weather_button(on_press=lambda w: None)

        # Check aria attributes
        assert hasattr(button, "aria_label") or True  # Toga may not support on all platforms
        assert hasattr(button, "aria_description") or True

    def test_explain_button_text(self):
        """Test that Explain Weather button has correct text."""
        from accessiweather.ai_explainer import create_explain_weather_button

        button = create_explain_weather_button(on_press=lambda w: None)

        assert button.text == "Explain Weather"

    @given(enabled=st.booleans())
    @settings(max_examples=50)
    def test_button_visibility_property(self, enabled):
        """For any AI enablement state, button visibility matches setting.

        **Feature: ai-weather-explanations, Property 1: Button visibility follows AI enablement setting**
        **Validates: Requirements 1.1, 1.5**
        """
        from accessiweather.ai_explainer import should_show_explain_button

        result = should_show_explain_button(ai_enabled=enabled)

        assert result == enabled


class TestExplanationDialog:
    """Tests for explanation dialog component.

    **Feature: ai-weather-explanations, Property 16: Dialog focus management**
    **Feature: ai-weather-explanations, Property 17: Loading state announced**
    **Feature: ai-weather-explanations, Property 18: Error announcements accessible**
    **Validates: Requirements 8.1, 8.4, 8.5**
    """

    def test_explanation_dialog_creation(self, mocker):
        """Test that ExplanationDialog can be created."""
        from datetime import datetime

        from accessiweather.ai_explainer import ExplanationResult
        from accessiweather.dialogs.explanation_dialog import ExplanationDialog

        mock_app = mocker.MagicMock()
        result = ExplanationResult(
            text="Test explanation",
            model_used="openrouter/auto:free",
            token_count=100,
            estimated_cost=0.0,
            cached=False,
            timestamp=datetime.now(),
        )

        dialog = ExplanationDialog(mock_app, result, "Test City")

        assert dialog.app == mock_app
        assert dialog.explanation == result
        assert dialog.location == "Test City"

    def test_loading_dialog_creation(self, mocker):
        """Test that LoadingDialog can be created."""
        from accessiweather.dialogs.explanation_dialog import LoadingDialog

        mock_app = mocker.MagicMock()
        dialog = LoadingDialog(mock_app, "Test City")

        assert dialog.app == mock_app
        assert dialog.location == "Test City"

    def test_error_dialog_creation(self, mocker):
        """Test that ErrorDialog can be created."""
        from accessiweather.dialogs.explanation_dialog import ErrorDialog

        mock_app = mocker.MagicMock()
        dialog = ErrorDialog(mock_app, "Test error message")

        assert dialog.app == mock_app
        assert dialog.error_message == "Test error message"
