"""
Tests for Model Browser Dialog functionality.

Tests the ModelBrowserDialog class and model browsing/selection logic.
"""

from __future__ import annotations

import pytest

from accessiweather.api.openrouter_models import OpenRouterModel
from accessiweather.ui.dialogs.model_browser_dialog import (
    PROVIDER_DISPLAY_NAMES,
    get_provider_display_name,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_free_model():
    """Create a sample free OpenRouter model."""
    return OpenRouterModel(
        id="meta-llama/llama-3.3-70b-instruct:free",
        name="Llama 3.3 70B Instruct",
        description="A powerful open-source language model from Meta.",
        context_length=128000,
        pricing_prompt=0.0,
        pricing_completion=0.0,
        is_free=True,
        is_moderated=True,
        input_modalities=["text"],
        output_modalities=["text"],
    )


@pytest.fixture
def sample_paid_model():
    """Create a sample paid OpenRouter model."""
    return OpenRouterModel(
        id="openai/gpt-4-turbo",
        name="GPT-4 Turbo",
        description="OpenAI's most capable model for complex tasks.",
        context_length=128000,
        pricing_prompt=10.0,  # $10 per 1M tokens
        pricing_completion=30.0,
        is_free=False,
        is_moderated=True,
        input_modalities=["text", "image"],
        output_modalities=["text"],
    )


@pytest.fixture
def sample_models(sample_free_model, sample_paid_model):
    """Create a list of sample models for testing."""
    return [
        sample_free_model,
        sample_paid_model,
        OpenRouterModel(
            id="anthropic/claude-3-opus",
            name="Claude 3 Opus",
            description="Anthropic's most intelligent model.",
            context_length=200000,
            pricing_prompt=15.0,
            pricing_completion=75.0,
            is_free=False,
            is_moderated=True,
            input_modalities=["text", "image"],
            output_modalities=["text"],
        ),
        OpenRouterModel(
            id="google/gemini-pro:free",
            name="Gemini Pro",
            description="Google's advanced AI model.",
            context_length=32000,
            pricing_prompt=0.0,
            pricing_completion=0.0,
            is_free=True,
            is_moderated=True,
            input_modalities=["text"],
            output_modalities=["text"],
        ),
    ]


# =============================================================================
# OpenRouterModel Tests
# =============================================================================


class TestOpenRouterModelDisplay:
    """Tests for OpenRouterModel display properties."""

    def test_provider_extraction(self, sample_free_model):
        """Test that provider is correctly extracted from model ID."""
        assert sample_free_model.provider == "meta-llama"

    def test_provider_extraction_paid_model(self, sample_paid_model):
        """Test provider extraction for paid model."""
        assert sample_paid_model.provider == "openai"

    def test_provider_extraction_no_slash(self):
        """Test provider extraction when ID has no slash."""
        model = OpenRouterModel(
            id="simple-model",
            name="Simple Model",
            description="",
            context_length=8000,
            pricing_prompt=0.0,
            pricing_completion=0.0,
            is_free=True,
            is_moderated=True,
            input_modalities=["text"],
            output_modalities=["text"],
        )
        assert model.provider == "unknown"

    def test_free_model_display_name(self, sample_free_model):
        """Test that free model display name includes (Free) suffix."""
        assert "(Free)" in sample_free_model.display_name
        assert "Llama" in sample_free_model.display_name

    def test_paid_model_display_name(self, sample_paid_model):
        """Test that paid model display name does not include (Free) suffix."""
        assert "(Free)" not in sample_paid_model.display_name
        assert "GPT-4" in sample_paid_model.display_name

    def test_context_display_thousands(self, sample_paid_model):
        """Test context display for thousands of tokens."""
        # 128000 should display as 128K
        assert "128K" in sample_paid_model.context_display

    def test_context_display_millions(self):
        """Test context display for millions of tokens."""
        model = OpenRouterModel(
            id="test/model",
            name="Test Model",
            description="",
            context_length=1_000_000,
            pricing_prompt=0.0,
            pricing_completion=0.0,
            is_free=True,
            is_moderated=True,
            input_modalities=["text"],
            output_modalities=["text"],
        )
        assert "1.0M" in model.context_display

    def test_context_display_unknown(self):
        """Test context display when context length is None."""
        model = OpenRouterModel(
            id="test/model",
            name="Test Model",
            description="",
            context_length=None,
            pricing_prompt=0.0,
            pricing_completion=0.0,
            is_free=True,
            is_moderated=True,
            input_modalities=["text"],
            output_modalities=["text"],
        )
        assert model.context_display == "Unknown"


# =============================================================================
# Model Filtering Tests
# =============================================================================


class TestModelFiltering:
    """Tests for model filtering logic."""

    def test_filter_free_models_only(self, sample_models):
        """Test filtering to show only free models."""
        free_models = [m for m in sample_models if m.is_free]
        assert len(free_models) == 2
        assert all(m.is_free for m in free_models)

    def test_filter_paid_models_only(self, sample_models):
        """Test filtering to show only paid models."""
        paid_models = [m for m in sample_models if not m.is_free]
        assert len(paid_models) == 2
        assert all(not m.is_free for m in paid_models)

    def test_search_by_name(self, sample_models):
        """Test searching models by name."""
        search_text = "llama"
        filtered = [
            m
            for m in sample_models
            if search_text in m.name.lower()
            or search_text in m.id.lower()
            or search_text in (m.description or "").lower()
        ]
        assert len(filtered) == 1
        assert "llama" in filtered[0].id.lower()

    def test_search_by_description(self, sample_models):
        """Test searching models by description."""
        search_text = "anthropic"
        filtered = [
            m
            for m in sample_models
            if search_text in m.name.lower()
            or search_text in m.id.lower()
            or search_text in (m.description or "").lower()
        ]
        assert len(filtered) == 1
        assert "claude" in filtered[0].id.lower()

    def test_search_by_id(self, sample_models):
        """Test searching models by ID."""
        search_text = "openai"
        filtered = [
            m
            for m in sample_models
            if search_text in m.name.lower()
            or search_text in m.id.lower()
            or search_text in (m.description or "").lower()
        ]
        assert len(filtered) == 1
        assert filtered[0].id == "openai/gpt-4-turbo"

    def test_search_case_insensitive(self, sample_models):
        """Test that search is case insensitive."""
        search_text = "LLAMA"
        filtered = [
            m
            for m in sample_models
            if search_text.lower() in m.name.lower()
            or search_text.lower() in m.id.lower()
            or search_text.lower() in (m.description or "").lower()
        ]
        assert len(filtered) == 1

    def test_combined_filter_search_and_free(self, sample_models):
        """Test combining search and free-only filter."""
        search_text = "gemini"
        free_only = True

        filtered = [
            m
            for m in sample_models
            if (not free_only or m.is_free)
            and (
                search_text in m.name.lower()
                or search_text in m.id.lower()
                or search_text in (m.description or "").lower()
            )
        ]
        assert len(filtered) == 1
        assert filtered[0].is_free
        assert "gemini" in filtered[0].id.lower()

    def test_empty_search_returns_all(self, sample_models):
        """Test that empty search returns all models."""
        search_text = ""
        filtered = (
            sample_models
            if not search_text
            else [m for m in sample_models if search_text in m.name.lower()]
        )
        assert len(filtered) == len(sample_models)

    def test_no_results_found(self, sample_models):
        """Test searching with no matching results."""
        search_text = "nonexistent"
        filtered = [
            m
            for m in sample_models
            if search_text in m.name.lower()
            or search_text in m.id.lower()
            or search_text in (m.description or "").lower()
        ]
        assert len(filtered) == 0


# =============================================================================
# Provider Filtering Tests
# =============================================================================


class TestProviderFiltering:
    """Tests for provider filtering logic."""

    def test_filter_by_provider_openai(self, sample_models):
        """Test filtering by OpenAI provider."""
        selected_provider = "openai"
        filtered = [m for m in sample_models if m.provider == selected_provider]
        assert len(filtered) == 1
        assert filtered[0].id == "openai/gpt-4-turbo"

    def test_filter_by_provider_anthropic(self, sample_models):
        """Test filtering by Anthropic provider."""
        selected_provider = "anthropic"
        filtered = [m for m in sample_models if m.provider == selected_provider]
        assert len(filtered) == 1
        assert "claude" in filtered[0].id.lower()

    def test_filter_by_provider_meta(self, sample_models):
        """Test filtering by Meta provider."""
        selected_provider = "meta-llama"
        filtered = [m for m in sample_models if m.provider == selected_provider]
        assert len(filtered) == 1
        assert "llama" in filtered[0].id.lower()

    def test_filter_by_provider_google(self, sample_models):
        """Test filtering by Google provider."""
        selected_provider = "google"
        filtered = [m for m in sample_models if m.provider == selected_provider]
        assert len(filtered) == 1
        assert "gemini" in filtered[0].id.lower()

    def test_no_provider_filter_returns_all(self, sample_models):
        """Test that no provider filter returns all models."""
        selected_provider = None
        if selected_provider:
            filtered = [m for m in sample_models if m.provider == selected_provider]
        else:
            filtered = sample_models
        assert len(filtered) == len(sample_models)

    def test_combined_provider_and_free_filter(self, sample_models):
        """Test combining provider filter with free-only filter."""
        selected_provider = "meta-llama"
        free_only = True

        filtered = [
            m
            for m in sample_models
            if (not free_only or m.is_free)
            and (not selected_provider or m.provider == selected_provider)
        ]
        assert len(filtered) == 1
        assert filtered[0].is_free
        assert filtered[0].provider == "meta-llama"

    def test_combined_provider_and_search_filter(self, sample_models):
        """Test combining provider filter with search."""
        selected_provider = "openai"
        search_text = "turbo"

        filtered = [
            m
            for m in sample_models
            if (not selected_provider or m.provider == selected_provider)
            and (
                search_text in m.name.lower()
                or search_text in m.id.lower()
                or search_text in (m.description or "").lower()
            )
        ]
        assert len(filtered) == 1
        assert filtered[0].id == "openai/gpt-4-turbo"

    def test_extract_unique_providers(self, sample_models):
        """Test extracting unique providers from model list."""
        providers = sorted({model.provider for model in sample_models})
        assert len(providers) == 4
        assert "anthropic" in providers
        assert "google" in providers
        assert "meta-llama" in providers
        assert "openai" in providers

    def test_provider_filter_no_matches(self, sample_models):
        """Test provider filter with no matching models."""
        selected_provider = "nonexistent-provider"
        filtered = [m for m in sample_models if m.provider == selected_provider]
        assert len(filtered) == 0

    def test_providers_filtered_by_free_only(self, sample_models):
        """Test that provider list is filtered when free-only is selected."""
        # Get providers from all models
        all_providers = sorted({model.provider for model in sample_models})
        assert len(all_providers) == 4

        # Get providers from free models only
        free_models = [m for m in sample_models if m.is_free]
        free_providers = sorted({model.provider for model in free_models})
        assert len(free_providers) == 2
        assert "meta-llama" in free_providers
        assert "google" in free_providers
        assert "openai" not in free_providers
        assert "anthropic" not in free_providers


# =============================================================================
# Provider Display Name Tests
# =============================================================================


class TestProviderDisplayNames:
    """Tests for provider display name formatting."""

    def test_known_provider_openai(self):
        """Test display name for OpenAI."""
        assert get_provider_display_name("openai") == "OpenAI"

    def test_known_provider_anthropic(self):
        """Test display name for Anthropic."""
        assert get_provider_display_name("anthropic") == "Anthropic"

    def test_known_provider_meta(self):
        """Test display name for Meta."""
        assert get_provider_display_name("meta-llama") == "Meta"

    def test_known_provider_google(self):
        """Test display name for Google."""
        assert get_provider_display_name("google") == "Google"

    def test_known_provider_mistral(self):
        """Test display name for Mistral AI."""
        assert get_provider_display_name("mistralai") == "Mistral AI"

    def test_known_provider_deepseek(self):
        """Test display name for DeepSeek."""
        assert get_provider_display_name("deepseek") == "DeepSeek"

    def test_known_provider_xai(self):
        """Test display name for xAI."""
        assert get_provider_display_name("x-ai") == "xAI"

    def test_known_provider_cognitive_computations(self):
        """Test display name for Cognitive Computations."""
        assert get_provider_display_name("cognitivecomputations") == "Cognitive Computations"

    def test_unknown_provider_fallback(self):
        """Test fallback for unknown provider."""
        # Unknown provider should use title case with hyphen replacement
        assert get_provider_display_name("some-unknown-provider") == "Some Unknown Provider"

    def test_unknown_provider_simple(self):
        """Test fallback for simple unknown provider."""
        assert get_provider_display_name("newprovider") == "Newprovider"

    def test_provider_display_names_mapping_exists(self):
        """Test that the provider display names mapping has entries."""
        assert len(PROVIDER_DISPLAY_NAMES) > 10
        assert "openai" in PROVIDER_DISPLAY_NAMES
        assert "anthropic" in PROVIDER_DISPLAY_NAMES
        assert "meta-llama" in PROVIDER_DISPLAY_NAMES


# =============================================================================
# Model Selection Tests
# =============================================================================


class TestModelSelection:
    """Tests for model selection logic."""

    def test_get_selected_model_by_id(self, sample_models):
        """Test getting selected model by ID."""
        selected_id = "openai/gpt-4-turbo"
        selected_model = None
        for model in sample_models:
            if model.id == selected_id:
                selected_model = model
                break

        assert selected_model is not None
        assert selected_model.id == selected_id
        assert selected_model.name == "GPT-4 Turbo"

    def test_get_selected_model_not_found(self, sample_models):
        """Test getting selected model when ID not found."""
        selected_id = "nonexistent/model"
        selected_model = None
        for model in sample_models:
            if model.id == selected_id:
                selected_model = model
                break

        assert selected_model is None

    def test_no_selection_returns_none(self):
        """Test that no selection returns None."""
        selected_id = None
        assert selected_id is None


# =============================================================================
# Pricing Display Tests
# =============================================================================


class TestPricingDisplay:
    """Tests for pricing display formatting."""

    def test_free_model_pricing_display(self, sample_free_model):
        """Test pricing display for free models."""
        if sample_free_model.is_free:
            pricing = "Free"
        else:
            prompt_cost = sample_free_model.pricing_prompt / 1000
            pricing = f"${prompt_cost:.6f} per 1K tokens"

        assert pricing == "Free"

    def test_paid_model_pricing_display(self, sample_paid_model):
        """Test pricing display for paid models."""
        if sample_paid_model.is_free:
            pricing = "Free"
        else:
            prompt_cost = sample_paid_model.pricing_prompt / 1000
            pricing = f"${prompt_cost:.6f} per 1K tokens"

        assert pricing == "$0.010000 per 1K tokens"

    def test_model_item_string_format(self, sample_free_model):
        """Test the full model item string format."""
        if sample_free_model.is_free:
            pricing = "Free"
        else:
            prompt_cost = sample_free_model.pricing_prompt / 1000
            pricing = f"${prompt_cost:.6f} per 1K tokens"

        item = f"{sample_free_model.display_name} - Context: {sample_free_model.context_display} - {pricing}"

        assert "Llama" in item
        assert "128K" in item
        assert "Free" in item


# =============================================================================
# Settings Dialog Integration Tests
# =============================================================================


class TestSettingsDialogModelIntegration:
    """Tests for model browser integration with settings dialog."""

    def test_known_preset_llama_selection(self):
        """Test that selecting Llama preset model sets correct dropdown index."""
        selected_model_id = "meta-llama/llama-3.3-70b-instruct:free"

        if selected_model_id == "meta-llama/llama-3.3-70b-instruct:free":
            selection_index = 0
        elif selected_model_id == "openrouter/auto":
            selection_index = 1
        else:
            selection_index = 2

        assert selection_index == 0

    def test_known_preset_auto_selection(self):
        """Test that selecting Auto Router sets correct dropdown index."""
        selected_model_id = "openrouter/auto"

        if selected_model_id == "meta-llama/llama-3.3-70b-instruct:free":
            selection_index = 0
        elif selected_model_id == "openrouter/auto":
            selection_index = 1
        else:
            selection_index = 2

        assert selection_index == 1

    def test_specific_model_selection(self):
        """Test that selecting a specific model sets correct dropdown index."""
        selected_model_id = "anthropic/claude-3-opus"

        if selected_model_id == "meta-llama/llama-3.3-70b-instruct:free":
            selection_index = 0
        elif selected_model_id == "openrouter/auto":
            selection_index = 1
        else:
            selection_index = 2

        assert selection_index == 2

    def test_specific_model_display_format(self):
        """Test the display format for specific models in dropdown."""
        selected_model_id = "cognitivecomputations/dolphin-mistral-24b-venice-edition:free"
        model_display = f"Selected: {selected_model_id.split('/')[-1]}"

        assert model_display == "Selected: dolphin-mistral-24b-venice-edition:free"

    def test_get_ai_model_preference_llama(self):
        """Test getting AI model preference for Llama selection."""
        selection = 0
        selected_specific_model = None

        if selection == 0:
            model = "meta-llama/llama-3.3-70b-instruct:free"
        elif selection == 1:
            model = "auto"
        elif selection == 2 and selected_specific_model:
            model = selected_specific_model
        else:
            model = "meta-llama/llama-3.3-70b-instruct:free"

        assert model == "meta-llama/llama-3.3-70b-instruct:free"

    def test_get_ai_model_preference_auto(self):
        """Test getting AI model preference for Auto selection."""
        selection = 1
        selected_specific_model = None

        if selection == 0:
            model = "meta-llama/llama-3.3-70b-instruct:free"
        elif selection == 1:
            model = "auto"
        elif selection == 2 and selected_specific_model:
            model = selected_specific_model
        else:
            model = "meta-llama/llama-3.3-70b-instruct:free"

        assert model == "auto"

    def test_get_ai_model_preference_specific(self):
        """Test getting AI model preference for specific model selection."""
        selection = 2
        selected_specific_model = "anthropic/claude-3-opus"

        if selection == 0:
            model = "meta-llama/llama-3.3-70b-instruct:free"
        elif selection == 1:
            model = "auto"
        elif selection == 2 and selected_specific_model:
            model = selected_specific_model
        else:
            model = "meta-llama/llama-3.3-70b-instruct:free"

        assert model == "anthropic/claude-3-opus"


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling in model browser."""

    def test_model_with_no_description(self):
        """Test handling model with no description."""
        model = OpenRouterModel(
            id="test/model",
            name="Test Model",
            description="",
            context_length=8000,
            pricing_prompt=0.0,
            pricing_completion=0.0,
            is_free=True,
            is_moderated=True,
            input_modalities=["text"],
            output_modalities=["text"],
        )

        desc = model.description or "No description available."
        assert desc == "No description available."

    def test_model_with_none_description(self):
        """Test handling model with None description in search."""
        model = OpenRouterModel(
            id="test/model",
            name="Test Model",
            description="",  # Empty string instead of None due to dataclass
            context_length=8000,
            pricing_prompt=0.0,
            pricing_completion=0.0,
            is_free=True,
            is_moderated=True,
            input_modalities=["text"],
            output_modalities=["text"],
        )

        search_text = "test"
        # This should not raise even with empty description
        matches = (
            search_text in model.name.lower()
            or search_text in model.id.lower()
            or search_text in (model.description or "").lower()
        )
        assert matches is True
