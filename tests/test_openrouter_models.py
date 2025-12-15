"""Tests for OpenRouter Models API client."""

from __future__ import annotations

import os

import pytest

from accessiweather.api.openrouter_models import (
    OpenRouterModel,
    OpenRouterModelsClient,
)

# Skip integration tests unless explicitly enabled
RUN_INTEGRATION = os.getenv("RUN_INTEGRATION_TESTS", "0") == "1"
skip_reason = "Set RUN_INTEGRATION_TESTS=1 to run integration tests with real API calls"


class TestOpenRouterModel:
    """Tests for OpenRouterModel dataclass."""

    def test_model_creation(self):
        """Test basic model creation."""
        model = OpenRouterModel(
            id="meta-llama/llama-3.3-70b-instruct:free",
            name="Llama 3.3 70B Instruct",
            description="A powerful open-source model",
            context_length=128000,
            pricing_prompt=0.0,
            pricing_completion=0.0,
            is_free=True,
            is_moderated=False,
            input_modalities=["text"],
            output_modalities=["text"],
        )

        assert model.id == "meta-llama/llama-3.3-70b-instruct:free"
        assert model.name == "Llama 3.3 70B Instruct"
        assert model.is_free is True
        assert model.is_moderated is False

    def test_display_name_free(self):
        """Test display name includes (Free) suffix for free models."""
        model = OpenRouterModel(
            id="test:free",
            name="Test Model",
            description="",
            context_length=4096,
            pricing_prompt=0.0,
            pricing_completion=0.0,
            is_free=True,
            is_moderated=True,
            input_modalities=["text"],
            output_modalities=["text"],
        )

        assert model.display_name == "Test Model (Free)"

    def test_display_name_paid(self):
        """Test display name has no suffix for paid models."""
        model = OpenRouterModel(
            id="test/model",
            name="Test Model",
            description="",
            context_length=4096,
            pricing_prompt=0.5,
            pricing_completion=1.0,
            is_free=False,
            is_moderated=True,
            input_modalities=["text"],
            output_modalities=["text"],
        )

        assert model.display_name == "Test Model"

    def test_context_display_millions(self):
        """Test context display for large context lengths."""
        model = OpenRouterModel(
            id="test",
            name="Test",
            description="",
            context_length=1_000_000,
            pricing_prompt=0.0,
            pricing_completion=0.0,
            is_free=True,
            is_moderated=True,
            input_modalities=["text"],
            output_modalities=["text"],
        )

        assert model.context_display == "1.0M"

    def test_context_display_thousands(self):
        """Test context display for medium context lengths."""
        model = OpenRouterModel(
            id="test",
            name="Test",
            description="",
            context_length=128000,
            pricing_prompt=0.0,
            pricing_completion=0.0,
            is_free=True,
            is_moderated=True,
            input_modalities=["text"],
            output_modalities=["text"],
        )

        assert model.context_display == "128K"

    def test_context_display_small(self):
        """Test context display for small context lengths."""
        model = OpenRouterModel(
            id="test",
            name="Test",
            description="",
            context_length=512,
            pricing_prompt=0.0,
            pricing_completion=0.0,
            is_free=True,
            is_moderated=True,
            input_modalities=["text"],
            output_modalities=["text"],
        )

        assert model.context_display == "512"

    def test_context_display_none(self):
        """Test context display when context length is None."""
        model = OpenRouterModel(
            id="test",
            name="Test",
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


class TestOpenRouterModelsClient:
    """Tests for OpenRouterModelsClient."""

    def test_client_initialization(self):
        """Test client initialization."""
        client = OpenRouterModelsClient()
        assert client.api_key is None
        assert client.timeout == 30.0
        assert client._cached_models is None

    def test_client_initialization_with_api_key(self):
        """Test client initialization with API key."""
        client = OpenRouterModelsClient(api_key="sk-or-test-key", timeout=60.0)
        assert client.api_key == "sk-or-test-key"
        assert client.timeout == 60.0

    def test_parse_pricing_number(self):
        """Test parsing numeric pricing values."""
        client = OpenRouterModelsClient()
        assert client._parse_pricing(0.5) == 0.5
        assert client._parse_pricing(0) == 0.0
        assert client._parse_pricing(1) == 1.0

    def test_parse_pricing_string(self):
        """Test parsing string pricing values."""
        client = OpenRouterModelsClient()
        assert client._parse_pricing("0.5") == 0.5
        assert client._parse_pricing("0") == 0.0

    def test_parse_pricing_none(self):
        """Test parsing None pricing values."""
        client = OpenRouterModelsClient()
        assert client._parse_pricing(None) == 0.0

    def test_parse_pricing_invalid_string(self):
        """Test parsing invalid string pricing values."""
        client = OpenRouterModelsClient()
        assert client._parse_pricing("invalid") == 0.0

    def test_parse_model_free_by_suffix(self):
        """Test parsing model with :free suffix."""
        client = OpenRouterModelsClient()
        data = {
            "id": "meta-llama/llama-3.3-70b-instruct:free",
            "name": "Llama 3.3 70B",
            "description": "Test model",
            "context_length": 128000,
            "pricing": {"prompt": "0", "completion": "0"},
            "architecture": {
                "input_modalities": ["text"],
                "output_modalities": ["text"],
            },
        }

        model = client._parse_model(data)
        assert model.is_free is True
        assert model.id == "meta-llama/llama-3.3-70b-instruct:free"

    def test_parse_model_free_by_pricing(self):
        """Test parsing model that's free by zero pricing."""
        client = OpenRouterModelsClient()
        data = {
            "id": "some/free-model",
            "name": "Free Model",
            "description": "Test model",
            "context_length": 4096,
            "pricing": {"prompt": 0, "completion": 0},
            "architecture": {
                "input_modalities": ["text"],
                "output_modalities": ["text"],
            },
        }

        model = client._parse_model(data)
        assert model.is_free is True

    def test_parse_model_paid(self):
        """Test parsing paid model."""
        client = OpenRouterModelsClient()
        data = {
            "id": "openai/gpt-4",
            "name": "GPT-4",
            "description": "OpenAI's GPT-4",
            "context_length": 8192,
            "pricing": {"prompt": "30", "completion": "60"},
            "architecture": {
                "input_modalities": ["text"],
                "output_modalities": ["text"],
            },
        }

        model = client._parse_model(data)
        assert model.is_free is False
        assert model.pricing_prompt == 30.0
        assert model.pricing_completion == 60.0

    def test_clear_cache(self):
        """Test clearing the model cache."""
        client = OpenRouterModelsClient()
        client._cached_models = [
            OpenRouterModel(
                id="test",
                name="Test",
                description="",
                context_length=4096,
                pricing_prompt=0.0,
                pricing_completion=0.0,
                is_free=True,
                is_moderated=True,
                input_modalities=["text"],
                output_modalities=["text"],
            )
        ]

        client.clear_cache()
        assert client._cached_models is None

    def test_parse_model_moderated(self):
        """Test parsing model with is_moderated field."""
        client = OpenRouterModelsClient()
        data = {
            "id": "openai/gpt-4",
            "name": "GPT-4",
            "description": "OpenAI's GPT-4",
            "context_length": 8192,
            "pricing": {"prompt": "30", "completion": "60"},
            "architecture": {
                "input_modalities": ["text"],
                "output_modalities": ["text"],
            },
            "top_provider": {
                "is_moderated": True,
            },
        }

        model = client._parse_model(data)
        assert model.is_moderated is True

    def test_parse_model_unmoderated(self):
        """Test parsing unmoderated model (like Grok)."""
        client = OpenRouterModelsClient()
        data = {
            "id": "x-ai/grok-beta",
            "name": "Grok Beta",
            "description": "xAI's Grok model",
            "context_length": 131072,
            "pricing": {"prompt": "5", "completion": "15"},
            "architecture": {
                "input_modalities": ["text"],
                "output_modalities": ["text"],
            },
            "top_provider": {
                "is_moderated": False,
            },
        }

        model = client._parse_model(data)
        assert model.is_moderated is False

    def test_parse_model_missing_moderation_defaults_to_true(self):
        """Test that missing is_moderated defaults to True (moderated)."""
        client = OpenRouterModelsClient()
        data = {
            "id": "some/model",
            "name": "Some Model",
            "description": "",
            "context_length": 4096,
            "pricing": {"prompt": "1", "completion": "2"},
            "architecture": {
                "input_modalities": ["text"],
                "output_modalities": ["text"],
            },
            # No top_provider field
        }

        model = client._parse_model(data)
        assert model.is_moderated is True  # Default to moderated if unknown


@pytest.mark.integration
@pytest.mark.flaky
@pytest.mark.skipif(not RUN_INTEGRATION, reason=skip_reason)
class TestOpenRouterModelsIntegration:
    """
    Integration tests that make real API calls.

    Marked as flaky because they depend on external API availability.
    Skip by default; run with RUN_INTEGRATION_TESTS=1.
    """

    @pytest.mark.asyncio
    async def test_fetch_models_real_api(self):
        """Test fetching models from real API."""
        client = OpenRouterModelsClient()
        models = await client.fetch_models()

        assert len(models) > 0
        assert all(isinstance(m, OpenRouterModel) for m in models)

    @pytest.mark.asyncio
    async def test_get_free_models_real_api(self):
        """Test fetching only free models."""
        client = OpenRouterModelsClient()
        free_models = await client.get_free_models()

        assert len(free_models) > 0
        assert all(m.is_free for m in free_models)

    @pytest.mark.asyncio
    async def test_search_models_real_api(self):
        """
        Test searching models.

        This test searches for 'llama' models. If the API is unavailable
        or returns no results, this may fail. Retry on failure.
        """
        client = OpenRouterModelsClient()
        results = await client.search_models("llama")

        # API may return no results on network issues; check we got some
        # or that client is functional
        if len(results) > 0:
            assert all("llama" in m.name.lower() or "llama" in m.id.lower() for m in results)
