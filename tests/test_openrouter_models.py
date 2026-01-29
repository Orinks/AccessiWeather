"""Tests for OpenRouter models API client."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from accessiweather.api.openrouter_models import (
    OpenRouterModel,
    OpenRouterModelsClient,
    OpenRouterModelsError,
)
from accessiweather.ui.dialogs.model_browser_dialog import get_provider_display_name


class TestOpenRouterModel:
    """Tests for OpenRouterModel dataclass."""

    def test_model_properties(self):
        """Test model property calculations."""
        model = OpenRouterModel(
            id="openai/gpt-4",
            name="GPT-4",
            description="OpenAI's GPT-4",
            context_length=8192,
            pricing_prompt=0.03,
            pricing_completion=0.06,
            is_free=False,
            is_moderated=True,
            input_modalities=["text"],
            output_modalities=["text"],
        )
        assert model.provider == "openai"
        assert model.display_name == "GPT-4"
        assert model.context_display == "8K"

    def test_free_model_display_name(self):
        """Test that free models show (Free) suffix."""
        model = OpenRouterModel(
            id="meta-llama/llama-3:free",
            name="Llama 3",
            description="Meta's Llama 3",
            context_length=4096,
            pricing_prompt=0.0,
            pricing_completion=0.0,
            is_free=True,
            is_moderated=False,
            input_modalities=["text"],
            output_modalities=["text"],
        )
        assert model.display_name == "Llama 3 (Free)"
        assert model.is_free is True

    def test_context_display_formatting(self):
        """Test context length display formatting."""
        # Small context
        model1 = OpenRouterModel(
            id="test/small",
            name="Small",
            description="",
            context_length=500,
            pricing_prompt=0.0,
            pricing_completion=0.0,
            is_free=True,
            is_moderated=True,
            input_modalities=["text"],
            output_modalities=["text"],
        )
        assert model1.context_display == "500"

        # Medium context (K)
        model2 = OpenRouterModel(
            id="test/medium",
            name="Medium",
            description="",
            context_length=32000,
            pricing_prompt=0.0,
            pricing_completion=0.0,
            is_free=True,
            is_moderated=True,
            input_modalities=["text"],
            output_modalities=["text"],
        )
        assert model2.context_display == "32K"

        # Large context (M)
        model3 = OpenRouterModel(
            id="test/large",
            name="Large",
            description="",
            context_length=1000000,
            pricing_prompt=0.0,
            pricing_completion=0.0,
            is_free=True,
            is_moderated=True,
            input_modalities=["text"],
            output_modalities=["text"],
        )
        assert model3.context_display == "1.0M"

        # Unknown context
        model4 = OpenRouterModel(
            id="test/unknown",
            name="Unknown",
            description="",
            context_length=None,
            pricing_prompt=0.0,
            pricing_completion=0.0,
            is_free=True,
            is_moderated=True,
            input_modalities=["text"],
            output_modalities=["text"],
        )
        assert model4.context_display == "Unknown"


class TestOpenRouterModelsClient:
    """Tests for OpenRouterModelsClient."""

    def test_parse_pricing_values(self):
        """Test parsing various pricing value formats."""
        client = OpenRouterModelsClient()

        # Float
        assert client._parse_pricing(0.001) == 0.001
        # Int
        assert client._parse_pricing(1) == 1.0
        # String
        assert client._parse_pricing("0.002") == 0.002
        # None
        assert client._parse_pricing(None) == 0.0
        # Invalid string
        assert client._parse_pricing("invalid") == 0.0

    def test_parse_model_free_detection(self):
        """Test free model detection from ID suffix and pricing."""
        client = OpenRouterModelsClient()

        # Free by suffix
        data1 = {
            "id": "test/model:free",
            "name": "Test Free",
            "pricing": {"prompt": "0.001", "completion": "0.001"},
        }
        model1 = client._parse_model(data1)
        assert model1.is_free is True

        # Free by zero pricing
        data2 = {
            "id": "test/model",
            "name": "Test Zero Price",
            "pricing": {"prompt": "0", "completion": "0"},
        }
        model2 = client._parse_model(data2)
        assert model2.is_free is True

        # Paid model
        data3 = {
            "id": "test/paid",
            "name": "Test Paid",
            "pricing": {"prompt": "0.001", "completion": "0.002"},
        }
        model3 = client._parse_model(data3)
        assert model3.is_free is False

    @pytest.mark.asyncio
    async def test_validate_model_id_valid(self):
        """Test validating a model ID that exists."""
        client = OpenRouterModelsClient()

        # Mock the fetch_models method
        mock_models = [
            OpenRouterModel(
                id="test/valid-model",
                name="Valid Model",
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

        with patch.object(client, "fetch_models", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_models

            result = await client.validate_model_id("test/valid-model")
            assert result is True

            result = await client.validate_model_id("test/invalid-model")
            assert result is False

    @pytest.mark.asyncio
    async def test_validate_model_id_fetch_error(self):
        """Test that validation returns True if fetch fails (fail-open)."""
        client = OpenRouterModelsClient()

        with patch.object(client, "fetch_models", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.side_effect = OpenRouterModelsError("Network error")

            # Should return True (fail-open) to avoid blocking users
            result = await client.validate_model_id("any-model")
            assert result is True

    @pytest.mark.asyncio
    async def test_get_model_by_id(self):
        """Test getting a specific model by ID."""
        client = OpenRouterModelsClient()

        mock_model = OpenRouterModel(
            id="test/specific",
            name="Specific Model",
            description="A specific model",
            context_length=8192,
            pricing_prompt=0.01,
            pricing_completion=0.02,
            is_free=False,
            is_moderated=True,
            input_modalities=["text"],
            output_modalities=["text"],
        )

        with patch.object(client, "fetch_models", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = [mock_model]

            # Found
            result = await client.get_model_by_id("test/specific")
            assert result is not None
            assert result.id == "test/specific"
            assert result.name == "Specific Model"

            # Not found
            result = await client.get_model_by_id("test/nonexistent")
            assert result is None


class TestProviderDisplayNames:
    """Tests for provider display name mapping."""

    def test_known_providers(self):
        """Test display names for known providers."""
        assert get_provider_display_name("openai") == "OpenAI"
        assert get_provider_display_name("anthropic") == "Anthropic"
        assert get_provider_display_name("google") == "Google"
        assert get_provider_display_name("meta-llama") == "Meta"

    def test_unknown_provider(self):
        """Test fallback formatting for unknown providers."""
        assert get_provider_display_name("new-provider") == "New Provider"
        assert get_provider_display_name("somecompany") == "Somecompany"
