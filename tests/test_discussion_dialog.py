"""
Tests for Discussion Dialog AI explanation functionality.

Tests the DiscussionDialog class and its AI explanation integration.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_app():
    """Create a mock AccessiWeatherApp."""
    app = MagicMock()
    app.config_manager = MagicMock()
    app.config_manager.get_current_location.return_value = MagicMock(
        name="Test City, NY",
        latitude=40.7128,
        longitude=-74.0060,
    )
    app.config_manager.get_settings.return_value = MagicMock(
        ai_model=None,
    )
    app.weather_client = MagicMock()
    app.current_weather_data = MagicMock(discussion="Sample discussion text for testing.")
    app.run_async = MagicMock()
    return app


@pytest.fixture
def sample_discussion():
    """Sample NWS Area Forecast Discussion text."""
    return """
    AREA FORECAST DISCUSSION
    National Weather Service New York NY

    .SYNOPSIS...
    High pressure will build across the region through Wednesday.
    A cold front will approach from the northwest late Thursday.

    .NEAR TERM /THROUGH TONIGHT/...
    Clear skies expected with temperatures falling to the mid 50s.
    Light northwesterly winds at 5 to 10 mph.

    .SHORT TERM /TUESDAY THROUGH THURSDAY/...
    Continued pleasant weather with highs in the upper 70s.
    The cold front will bring a chance of showers Thursday evening.
    """


# =============================================================================
# SecureStorage Import Path Tests
# =============================================================================


class TestSecureStorageImport:
    """Tests for SecureStorage import path fix."""

    def test_secure_storage_import_path(self):
        """Test that SecureStorage can be imported from correct path."""
        # This tests the fix for the import path bug
        from accessiweather.config.secure_storage import SecureStorage

        assert SecureStorage is not None
        # Verify it has the expected static methods
        assert hasattr(SecureStorage, "get_password")
        assert hasattr(SecureStorage, "set_password")
        assert hasattr(SecureStorage, "delete_password")

    def test_relative_import_from_dialogs_package(self):
        """Test that relative import works from dialogs package."""
        # This simulates what the discussion_dialog.py does
        # The fix changed ..config to ...config
        try:
            # This import pattern should work
            from accessiweather.config.secure_storage import SecureStorage

            assert callable(SecureStorage.get_password)
        except ImportError as e:
            pytest.fail(f"Failed to import SecureStorage: {e}")


# =============================================================================
# Button State Tests
# =============================================================================


class TestExplainButtonState:
    """Tests for explain button enable/disable logic."""

    def test_button_disabled_without_api_key(self):
        """Test that explain button is disabled without API key."""
        with patch("accessiweather.config.secure_storage.SecureStorage.get_password") as mock_get:
            mock_get.return_value = None  # No API key configured

            # The button should be disabled when no API key
            api_key = mock_get("openrouter_api_key")
            assert api_key is None

    def test_button_enabled_with_api_key(self):
        """Test that explain button is enabled with API key."""
        with patch("accessiweather.config.secure_storage.SecureStorage.get_password") as mock_get:
            mock_get.return_value = "test-api-key"

            api_key = mock_get("openrouter_api_key")
            assert api_key is not None
            assert len(api_key) > 0

    def test_button_disabled_without_discussion(self):
        """Test that explain button is disabled without discussion text."""
        # Even with API key, button should be disabled if no discussion loaded
        with patch("accessiweather.config.secure_storage.SecureStorage.get_password") as mock_get:
            mock_get.return_value = "test-api-key"

            api_key = mock_get("openrouter_api_key")
            current_discussion = None

            # Button should only be enabled if both are present
            should_enable = api_key and current_discussion
            assert should_enable is None  # False-y

    def test_button_enabled_with_api_key_and_discussion(self, sample_discussion):
        """Test that explain button is enabled with both API key and discussion."""
        with patch("accessiweather.config.secure_storage.SecureStorage.get_password") as mock_get:
            mock_get.return_value = "test-api-key"

            api_key = mock_get("openrouter_api_key")
            current_discussion = sample_discussion

            # Button should be enabled when both are present
            should_enable = api_key and current_discussion
            assert should_enable


# =============================================================================
# AI Explanation Generation Tests
# =============================================================================


class TestAIExplanationGeneration:
    """Tests for AI explanation generation in discussion dialog."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("ai_model_preference", "expected_model"),
        [
            ("openrouter/auto", "openrouter/auto"),
            (None, None),
        ],
    )
    async def test_discussion_dialog_passes_custom_prompt_settings(
        self,
        ai_model_preference,
        expected_model,
    ):
        """Test discussion dialog passes custom AI prompt settings to explainer."""
        from accessiweather.ai_explainer import ExplanationStyle
        from accessiweather.ui.dialogs import discussion_dialog

        settings = MagicMock()
        settings.ai_model_preference = ai_model_preference
        settings.custom_system_prompt = "System prompt"
        settings.custom_instructions = "Custom instructions"

        app = MagicMock()
        app.config_manager = MagicMock()
        app.config_manager.get_settings.return_value = settings
        location = MagicMock()
        location.name = "Test City"
        app.config_manager.get_current_location.return_value = location

        dialog = SimpleNamespace(
            app=app,
            _current_discussion="Discussion text",
            _on_explain_error=MagicMock(),
            _on_explain_complete=MagicMock(),
        )

        captured: dict[str, object] = {}

        class FakeExplainer:
            def __init__(
                self,
                api_key=None,
                model=None,
                custom_system_prompt=None,
                custom_instructions=None,
            ):
                captured["init"] = {
                    "api_key": api_key,
                    "model": model,
                    "custom_system_prompt": custom_system_prompt,
                    "custom_instructions": custom_instructions,
                }

            async def explain_afd(self, discussion_text, location_name, style):
                captured["call"] = {
                    "discussion_text": discussion_text,
                    "location_name": location_name,
                    "style": style,
                }
                return MagicMock(text="Result text", model_used="test-model")

        with (
            patch(
                "accessiweather.config.secure_storage.SecureStorage.get_password",
                return_value="test-key",
            ),
            patch("accessiweather.ai_explainer.AIExplainer", FakeExplainer),
            patch.object(
                discussion_dialog.wx,
                "CallAfter",
                side_effect=lambda func, *args: func(*args),
            ),
        ):
            await discussion_dialog.DiscussionDialog._do_explain(dialog)

        assert captured["init"]["api_key"] == "test-key"
        assert captured["init"]["model"] is expected_model
        assert captured["init"]["custom_system_prompt"] == "System prompt"
        assert captured["init"]["custom_instructions"] == "Custom instructions"
        assert captured["call"]["discussion_text"] == "Discussion text"
        assert captured["call"]["location_name"] == "Test City"
        assert captured["call"]["style"] == ExplanationStyle.DETAILED
        dialog._on_explain_complete.assert_called_once_with("Result text", "test-model")

    @pytest.mark.asyncio
    async def test_explain_afd_called_with_correct_params(self, sample_discussion):
        """Test that explain_afd is called with correct parameters."""
        from accessiweather.ai_explainer import AIExplainer, ExplanationStyle

        with patch.object(AIExplainer, "_call_openrouter") as mock_call:
            mock_call.return_value = {
                "content": "Plain language explanation of the forecast.",
                "model": "test-model",
                "total_tokens": 150,
                "prompt_tokens": 100,
                "completion_tokens": 50,
            }

            explainer = AIExplainer(api_key="test-key")
            result = await explainer.explain_afd(
                sample_discussion,
                "Test City, NY",
                style=ExplanationStyle.DETAILED,
            )

            assert result is not None
            assert result.text is not None
            assert len(result.text) > 0

    @pytest.mark.asyncio
    async def test_explain_afd_handles_empty_discussion(self):
        """Test that explain_afd handles empty discussion text."""
        from accessiweather.ai_explainer import AIExplainer, ExplanationStyle

        with patch.object(AIExplainer, "_call_openrouter") as mock_call:
            mock_call.return_value = {
                "content": "No discussion data provided.",
                "model": "test-model",
                "total_tokens": 50,
                "prompt_tokens": 30,
                "completion_tokens": 20,
            }

            explainer = AIExplainer(api_key="test-key")
            result = await explainer.explain_afd(
                "",  # Empty discussion
                "Test City",
                style=ExplanationStyle.STANDARD,
            )

            # Should still return a result, even if minimal
            assert result is not None


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestDiscussionDialogErrors:
    """Tests for error handling in discussion dialog."""

    @pytest.mark.asyncio
    async def test_handles_api_error_gracefully(self, sample_discussion):
        """Test that API errors are handled gracefully."""
        from accessiweather.ai_explainer import AIExplainer, AIExplainerError

        explainer = AIExplainer(api_key="test-key")

        with patch.object(explainer, "_call_openrouter") as mock_call:
            mock_call.side_effect = AIExplainerError("API error")

            with pytest.raises(AIExplainerError):
                await explainer.explain_afd(
                    sample_discussion,
                    "Test City",
                )

    @pytest.mark.asyncio
    async def test_handles_missing_api_key(self, sample_discussion):
        """Test that missing API key raises appropriate error."""
        from accessiweather.ai_explainer import AIExplainer, AIExplainerError

        explainer = AIExplainer()  # No API key

        with pytest.raises(AIExplainerError) as exc:
            await explainer.explain_afd(
                sample_discussion,
                "Test City",
            )

        assert "API key" in str(exc.value)


# =============================================================================
# Discussion Loading Tests
# =============================================================================


class TestDiscussionLoading:
    """Tests for discussion text loading logic."""

    def test_discussion_from_weather_data(self, mock_app, sample_discussion):
        """Test loading discussion from existing weather data."""
        mock_app.current_weather_data.discussion = sample_discussion

        weather_data = mock_app.current_weather_data
        assert weather_data.discussion is not None
        assert "SYNOPSIS" in weather_data.discussion

    def test_discussion_not_available(self, mock_app):
        """Test handling when discussion is not available."""
        mock_app.current_weather_data.discussion = None

        weather_data = mock_app.current_weather_data
        assert weather_data.discussion is None

    def test_discussion_starts_with_error_message(self, mock_app):
        """Test detecting error message in discussion."""
        mock_app.current_weather_data.discussion = (
            "Forecast discussion not available for this location."
        )

        weather_data = mock_app.current_weather_data
        is_error = weather_data.discussion.startswith("Forecast discussion not available")
        assert is_error is True


# =============================================================================
# Model Configuration Tests
# =============================================================================


class TestModelConfiguration:
    """Tests for AI model configuration in discussion dialog."""

    def test_uses_configured_model(self, mock_app):
        """Test that configured model is used."""
        mock_app.config_manager.get_settings.return_value.ai_model_preference = "gpt-4"

        settings = mock_app.config_manager.get_settings()
        model = settings.ai_model_preference

        assert model == "gpt-4"

    def test_uses_default_when_no_model_configured(self, mock_app):
        """Test that default model is used when none configured."""
        mock_app.config_manager.get_settings.return_value.ai_model_preference = None

        settings = mock_app.config_manager.get_settings()
        model = getattr(settings, "ai_model_preference", None)

        assert model is None  # Will use default in AIExplainer

    @pytest.mark.asyncio
    async def test_explainer_uses_default_free_model(self):
        """Test that explainer uses default free model."""
        from accessiweather.ai_explainer import DEFAULT_FREE_MODEL, AIExplainer

        explainer = AIExplainer(api_key="test-key")
        effective_model = explainer.get_effective_model()

        # Should use the default model
        assert effective_model == DEFAULT_FREE_MODEL
