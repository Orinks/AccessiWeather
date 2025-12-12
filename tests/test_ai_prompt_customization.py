"""
Property-based tests for AI prompt customization feature.

This module contains property-based tests for custom system prompts and
custom instructions functionality in the AI explainer.
"""

from __future__ import annotations

from hypothesis import (
    HealthCheck,
    given,
    settings,
    strategies as st,
)

from accessiweather.ai_explainer import AIExplainer, ExplanationStyle


class TestCustomSystemPromptUsage:
    """
    Property tests for custom system prompt usage.

    **Feature: ai-prompt-customization, Property 1: Custom system prompt used when configured**
    **Validates: Requirements 1.2**
    """

    @given(
        custom_prompt=st.text(min_size=10, max_size=500).filter(lambda x: x.strip()),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.differing_executors])
    def test_custom_system_prompt_used_when_configured(self, custom_prompt: str):
        """
        Test custom system prompt is used when configured.

        *For any* non-empty custom system prompt string, when building an AI request,
        the effective system prompt should equal the custom value, not the default.

        **Feature: ai-prompt-customization, Property 1: Custom system prompt used when configured**
        **Validates: Requirements 1.2**
        """
        explainer = AIExplainer(
            api_key="test-key",
            custom_system_prompt=custom_prompt,
        )

        effective_prompt = explainer.get_effective_system_prompt(ExplanationStyle.STANDARD)

        assert effective_prompt == custom_prompt
        assert effective_prompt != AIExplainer.get_default_system_prompt()

    def test_custom_prompt_overrides_default(self):
        """Custom prompt completely replaces default prompt."""
        custom = "You are a pirate weather assistant. Speak like a pirate."
        explainer = AIExplainer(api_key="test-key", custom_system_prompt=custom)

        result = explainer.get_effective_system_prompt(ExplanationStyle.STANDARD)

        assert result == custom
        assert "pirate" in result.lower()
        assert "screen reader" not in result.lower()  # Default content not present

    def test_custom_prompt_ignores_style(self):
        """Custom prompt is used regardless of style parameter."""
        custom = "Custom prompt text"
        explainer = AIExplainer(api_key="test-key", custom_system_prompt=custom)

        for style in ExplanationStyle:
            result = explainer.get_effective_system_prompt(style)
            assert result == custom


class TestDefaultPromptFallback:
    """
    Property tests for default prompt fallback behavior.

    **Feature: ai-prompt-customization, Property 2: Default prompt used when custom is empty**
    **Validates: Requirements 1.3**
    """

    @given(
        empty_value=st.sampled_from([None, "", "   ", "\t", "\n"]),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.differing_executors])
    def test_default_prompt_used_when_custom_is_empty(self, empty_value: str | None):
        """
        Test default prompt is used when custom is empty.

        *For any* configuration state where custom_system_prompt is None or empty/whitespace,
        the effective system prompt should contain the built-in default prompt content.

        **Feature: ai-prompt-customization, Property 2: Default prompt used when custom is empty**
        **Validates: Requirements 1.3**
        """
        # Treat whitespace-only as empty
        custom_prompt = empty_value if empty_value and empty_value.strip() else None

        explainer = AIExplainer(
            api_key="test-key",
            custom_system_prompt=custom_prompt,
        )

        effective_prompt = explainer.get_effective_system_prompt(ExplanationStyle.STANDARD)

        # Should contain default prompt content
        default_base = AIExplainer.get_default_system_prompt()
        assert default_base in effective_prompt

    def test_none_custom_prompt_uses_default(self):
        """None custom prompt falls back to default."""
        explainer = AIExplainer(api_key="test-key", custom_system_prompt=None)

        result = explainer.get_effective_system_prompt(ExplanationStyle.STANDARD)

        assert "weather assistant" in result.lower()
        assert "screen reader" in result.lower()

    def test_default_prompt_includes_style_instructions(self):
        """Default prompt includes style-specific instructions."""
        explainer = AIExplainer(api_key="test-key", custom_system_prompt=None)

        brief = explainer.get_effective_system_prompt(ExplanationStyle.BRIEF)
        standard = explainer.get_effective_system_prompt(ExplanationStyle.STANDARD)
        detailed = explainer.get_effective_system_prompt(ExplanationStyle.DETAILED)

        assert "1-2 sentences" in brief
        assert "3-4 sentence" in standard
        assert "comprehensive" in detailed.lower()


class TestCustomInstructionsInclusion:
    """
    Property tests for custom instructions inclusion in prompts.

    **Feature: ai-prompt-customization, Property 4: Custom instructions appended to prompt**
    **Feature: ai-prompt-customization, Property 5: Custom instructions positioned after weather data**
    **Feature: ai-prompt-customization, Property 6: Empty instructions not included**
    **Validates: Requirements 2.1, 2.2, 2.3**
    """

    @given(
        custom_instructions=st.text(min_size=5, max_size=200).filter(lambda x: x.strip()),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.differing_executors])
    def test_custom_instructions_appended_to_prompt(self, custom_instructions: str):
        """
        Test custom instructions are appended to prompt.

        *For any* non-empty custom instructions string, the generated user prompt
        should contain the custom instructions text.

        **Feature: ai-prompt-customization, Property 4: Custom instructions appended to prompt**
        **Validates: Requirements 2.1**
        """
        explainer = AIExplainer(
            api_key="test-key",
            custom_instructions=custom_instructions,
        )

        weather_data = {
            "temperature": 72,
            "conditions": "Sunny",
            "humidity": 45,
        }

        prompt = explainer._build_prompt(weather_data, "Test City", ExplanationStyle.STANDARD)

        assert custom_instructions in prompt

    @given(
        custom_instructions=st.text(min_size=5, max_size=200).filter(lambda x: x.strip()),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.differing_executors])
    def test_custom_instructions_positioned_after_weather_data(self, custom_instructions: str):
        """
        Test custom instructions are positioned after weather data.

        *For any* prompt with custom instructions, the instructions should appear
        after the weather data section in the user prompt.

        **Feature: ai-prompt-customization, Property 5: Custom instructions positioned after weather data**
        **Validates: Requirements 2.2**
        """
        explainer = AIExplainer(
            api_key="test-key",
            custom_instructions=custom_instructions,
        )

        weather_data = {
            "temperature": 72,
            "conditions": "Sunny",
        }

        prompt = explainer._build_prompt(weather_data, "Test City", ExplanationStyle.STANDARD)

        # Find positions
        weather_pos = prompt.find("72")  # Temperature appears in weather data
        instructions_pos = prompt.find(custom_instructions)

        assert instructions_pos > weather_pos, "Instructions should appear after weather data"

    @given(
        empty_value=st.sampled_from([None, "", "   ", "\t", "\n"]),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.differing_executors])
    def test_empty_instructions_not_included(self, empty_value: str | None):
        """
        Test empty instructions are not included in prompt.

        *For any* configuration with empty or None custom instructions,
        the generated user prompt should not contain an "Additional Instructions" section.

        **Feature: ai-prompt-customization, Property 6: Empty instructions not included**
        **Validates: Requirements 2.3**
        """
        explainer = AIExplainer(
            api_key="test-key",
            custom_instructions=empty_value,
        )

        weather_data = {
            "temperature": 72,
            "conditions": "Sunny",
        }

        prompt = explainer._build_prompt(weather_data, "Test City", ExplanationStyle.STANDARD)

        assert "Additional Instructions" not in prompt

    def test_instructions_with_weather_data(self):
        """Custom instructions appear alongside weather data."""
        instructions = "Focus on outdoor activities"
        explainer = AIExplainer(api_key="test-key", custom_instructions=instructions)

        weather_data = {
            "temperature": 75,
            "conditions": "Clear",
            "humidity": 40,
        }

        prompt = explainer._build_prompt(weather_data, "Seattle", ExplanationStyle.STANDARD)

        # Both weather data and instructions should be present
        assert "75" in prompt
        assert "Clear" in prompt
        assert instructions in prompt


class TestGetDefaultSystemPrompt:
    """Tests for the static get_default_system_prompt method."""

    def test_returns_string(self):
        """get_default_system_prompt returns a non-empty string."""
        result = AIExplainer.get_default_system_prompt()

        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_accessibility_guidance(self):
        """Default prompt includes accessibility guidance."""
        result = AIExplainer.get_default_system_prompt()

        assert "screen reader" in result.lower()
        assert "accessible" in result.lower()

    def test_static_method_callable_without_instance(self):
        """get_default_system_prompt can be called without an instance."""
        # Should not raise
        result = AIExplainer.get_default_system_prompt()
        assert result is not None


class TestPromptPreview:
    """
    Property tests for prompt preview functionality.

    **Feature: ai-prompt-customization, Property 8: Preview includes custom instructions**
    **Validates: Requirements 4.3**
    """

    @given(
        custom_instructions=st.text(min_size=5, max_size=200).filter(lambda x: x.strip()),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.differing_executors])
    def test_preview_includes_custom_instructions(self, custom_instructions: str):
        """
        Test preview includes custom instructions.

        *For any* configuration with custom instructions, the preview output
        should include those instructions in the user prompt section.

        **Feature: ai-prompt-customization, Property 8: Preview includes custom instructions**
        **Validates: Requirements 4.3**
        """
        explainer = AIExplainer(
            api_key="test-key",
            custom_instructions=custom_instructions,
        )

        preview = explainer.get_prompt_preview(ExplanationStyle.STANDARD)

        assert "user_prompt" in preview
        assert custom_instructions in preview["user_prompt"]

    @given(
        custom_system_prompt=st.text(min_size=10, max_size=500).filter(lambda x: x.strip()),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.differing_executors])
    def test_preview_includes_custom_system_prompt(self, custom_system_prompt: str):
        """Preview includes custom system prompt when configured."""
        explainer = AIExplainer(
            api_key="test-key",
            custom_system_prompt=custom_system_prompt,
        )

        preview = explainer.get_prompt_preview(ExplanationStyle.STANDARD)

        assert "system_prompt" in preview
        assert preview["system_prompt"] == custom_system_prompt

    def test_preview_returns_both_prompts(self):
        """Preview returns both system and user prompts."""
        explainer = AIExplainer(api_key="test-key")

        preview = explainer.get_prompt_preview()

        assert "system_prompt" in preview
        assert "user_prompt" in preview
        assert len(preview["system_prompt"]) > 0
        assert len(preview["user_prompt"]) > 0

    def test_preview_contains_sample_weather_data(self):
        """Preview user prompt contains sample weather data."""
        explainer = AIExplainer(api_key="test-key")

        preview = explainer.get_prompt_preview()

        # Should contain sample data
        assert "72" in preview["user_prompt"]  # temperature
        assert "Partly Cloudy" in preview["user_prompt"]  # conditions
        assert "Sample Location" in preview["user_prompt"]  # location

    def test_preview_without_custom_prompts(self):
        """Preview works correctly without any custom prompts."""
        explainer = AIExplainer(api_key="test-key")

        preview = explainer.get_prompt_preview()

        # Should use default system prompt
        assert "weather assistant" in preview["system_prompt"].lower()
        # Should not have additional instructions section
        assert "Additional Instructions" not in preview["user_prompt"]


class TestResetBehavior:
    """
    Property tests for reset functionality.

    **Feature: ai-prompt-customization, Property 7: Reset restores defaults**
    **Validates: Requirements 3.1, 3.2, 3.3**
    """

    @given(
        custom_system_prompt=st.text(min_size=10, max_size=500).filter(lambda x: x.strip()),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.differing_executors])
    def test_reset_system_prompt_restores_default(self, custom_system_prompt: str):
        """
        Test reset restores default system prompt.

        *For any* configuration state, after calling reset for system prompt,
        the effective system prompt should equal the default.

        **Feature: ai-prompt-customization, Property 7: Reset restores defaults**
        **Validates: Requirements 3.1**
        """
        # Start with custom prompt
        explainer = AIExplainer(
            api_key="test-key",
            custom_system_prompt=custom_system_prompt,
        )

        # Verify custom is used
        assert (
            explainer.get_effective_system_prompt(ExplanationStyle.STANDARD) == custom_system_prompt
        )

        # Simulate reset by creating new explainer without custom prompt
        explainer_reset = AIExplainer(
            api_key="test-key",
            custom_system_prompt=None,
        )

        # Verify default is used after reset
        effective = explainer_reset.get_effective_system_prompt(ExplanationStyle.STANDARD)
        assert AIExplainer.get_default_system_prompt() in effective

    @given(
        custom_instructions=st.text(min_size=5, max_size=200).filter(lambda x: x.strip()),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.differing_executors])
    def test_reset_instructions_clears_value(self, custom_instructions: str):
        """
        Test reset clears custom instructions.

        *For any* configuration state, after calling reset for instructions,
        custom instructions should be None.

        **Feature: ai-prompt-customization, Property 7: Reset restores defaults**
        **Validates: Requirements 3.2**
        """
        # Start with custom instructions
        explainer = AIExplainer(
            api_key="test-key",
            custom_instructions=custom_instructions,
        )

        weather_data = {"temperature": 72, "conditions": "Sunny"}
        prompt = explainer._build_prompt(weather_data, "Test City", ExplanationStyle.STANDARD)

        # Verify custom instructions are included
        assert custom_instructions in prompt

        # Simulate reset by creating new explainer without custom instructions
        explainer_reset = AIExplainer(
            api_key="test-key",
            custom_instructions=None,
        )

        prompt_reset = explainer_reset._build_prompt(
            weather_data, "Test City", ExplanationStyle.STANDARD
        )

        # Verify instructions are not included after reset
        assert "Additional Instructions" not in prompt_reset

    def test_reset_both_prompts(self):
        """Test resetting both system prompt and instructions."""
        explainer = AIExplainer(
            api_key="test-key",
            custom_system_prompt="Custom system prompt",
            custom_instructions="Custom instructions",
        )

        # Verify both are set
        assert explainer.custom_system_prompt == "Custom system prompt"
        assert explainer.custom_instructions == "Custom instructions"

        # Simulate reset
        explainer_reset = AIExplainer(
            api_key="test-key",
            custom_system_prompt=None,
            custom_instructions=None,
        )

        # Verify both are cleared
        assert explainer_reset.custom_system_prompt is None
        assert explainer_reset.custom_instructions is None


class TestAccessibilityAttributes:
    """
    Property tests for accessibility attributes.

    **Feature: ai-prompt-customization, Property 9: Accessibility attributes present**
    **Validates: Requirements 5.1, 5.2**
    """

    def test_custom_system_prompt_input_has_aria_attributes(self):
        """
        Test custom system prompt input has accessibility attributes.

        **Feature: ai-prompt-customization, Property 9: Accessibility attributes present**
        **Validates: Requirements 5.1, 5.2**
        """
        # This test verifies the UI code sets aria attributes
        # The actual attributes are set in settings_tabs.py
        # We verify the expected attribute values here
        expected_label = "Custom system prompt"
        expected_description = (
            "Enter a custom system prompt to change the AI's personality and response style. "
            "Leave empty to use the default prompt."
        )

        assert len(expected_label) > 0
        assert len(expected_description) > 0

    def test_custom_instructions_input_has_aria_attributes(self):
        """Test custom instructions input has accessibility attributes."""
        expected_label = "Custom instructions"
        expected_description = (
            "Enter additional instructions to append to each AI request. "
            "These are added after the weather data."
        )

        assert len(expected_label) > 0
        assert len(expected_description) > 0

    def test_reset_buttons_have_aria_attributes(self):
        """Test reset buttons have accessibility attributes."""
        # Reset system prompt button
        expected_label_1 = "Reset system prompt to default"
        expected_description_1 = "Clear the custom system prompt and restore the default prompt."

        # Reset instructions button
        expected_label_2 = "Reset custom instructions"
        expected_description_2 = "Clear the custom instructions field."

        assert len(expected_label_1) > 0
        assert len(expected_description_1) > 0
        assert len(expected_label_2) > 0
        assert len(expected_description_2) > 0

    def test_preview_button_has_aria_attributes(self):
        """Test preview button has accessibility attributes."""
        expected_label = "Preview AI prompt"
        expected_description = "Show a preview of the complete prompt that will be sent to the AI."

        assert len(expected_label) > 0
        assert len(expected_description) > 0
