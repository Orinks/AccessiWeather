"""Prompt construction and response formatting helpers for AI explanations."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

from .ai_explainer_models import ExplanationStyle, WeatherContext

logger = logging.getLogger(__name__)


class AIExplainerPromptMixin:
    """Prompt, cache-key, and formatting helpers for AI explainers."""

    # Maximum allowed length for custom prompts to prevent abuse
    _MAX_PROMPT_LENGTH = 2000

    @staticmethod
    def _sanitize_prompt(prompt: str | None) -> str | None:
        """
        Sanitize a custom prompt to prevent prompt injection attacks.

        Enforces length limits and strips potentially dangerous patterns
        like attempts to override system behavior or extract data.

        Args:
            prompt: The custom prompt text to sanitize

        Returns:
            Sanitized prompt or None if input was None/empty

        """
        if not prompt or not prompt.strip():
            return None

        sanitized = prompt.strip()

        # Enforce length limit
        if len(sanitized) > AIExplainerPromptMixin._MAX_PROMPT_LENGTH:
            logger.warning(
                f"Custom prompt truncated from {len(sanitized)} to "
                f"{AIExplainerPromptMixin._MAX_PROMPT_LENGTH} characters"
            )
            sanitized = sanitized[: AIExplainerPromptMixin._MAX_PROMPT_LENGTH]

        # Strip common prompt injection patterns
        injection_patterns = [
            r"(?i)ignore\s+(all\s+)?(previous|above|prior)\s+(instructions?|prompts?|rules?)",
            r"(?i)you\s+are\s+now\s+(?:a|an|in)\s+(?:new|different|unrestricted)",
            r"(?i)disregard\s+(all\s+)?(previous|above|prior|your)\s+(instructions?|programming|rules?)",
            r"(?i)system\s*:\s*",
            r"(?i)\n\s*system\s*:",
        ]

        import re as _re

        for pattern in injection_patterns:
            if _re.search(pattern, sanitized):
                logger.warning(f"Prompt injection pattern detected and stripped: {pattern}")
                sanitized = _re.sub(pattern, "[filtered]", sanitized)

        return sanitized if sanitized.strip() else None

    def get_effective_system_prompt(self, style: ExplanationStyle) -> str:
        """
        Get the system prompt to use, preferring custom over default.

        Args:
            style: Explanation style for default prompt

        Returns:
            Custom system prompt if configured, otherwise default prompt

        """
        if self.custom_system_prompt:
            return self.custom_system_prompt
        return self._build_default_system_prompt(style)

    def _build_default_system_prompt(self, style: ExplanationStyle) -> str:
        """Build the default system prompt based on explanation style."""
        base_prompt = self.get_default_system_prompt()

        style_instructions = {
            ExplanationStyle.BRIEF: "Keep your response to 1-2 sentences.",
            ExplanationStyle.STANDARD: "Provide a 3-4 sentence explanation.",
            ExplanationStyle.DETAILED: (
                "Provide a comprehensive paragraph with context about "
                "how the weather might affect daily activities."
            ),
        }

        return f"{base_prompt}\n\n{style_instructions.get(style, style_instructions[ExplanationStyle.STANDARD])}"

    @staticmethod
    def get_default_system_prompt() -> str:
        """
        Return the default system prompt text for display in UI.

        Returns:
            The default system prompt string

        """
        return (
            "You are a helpful weather assistant that explains weather conditions "
            "in plain, accessible language. Your explanations should be easy to "
            "understand for screen reader users and people who prefer audio descriptions. "
            "Avoid using visual-only descriptions. Focus on how the weather will feel "
            "and what activities it's suitable for.\n\n"
            "IMPORTANT: Do NOT repeat the location name, date, time, or timezone in your response. "
            "The user already sees this information. Jump straight into describing the weather "
            "conditions and what to expect.\n\n"
            "IMPORTANT: Respond in plain text only. Do NOT use markdown formatting such as "
            "bold (**text**), italic (*text*), headers (#), bullet points, or any other "
            "markdown syntax. Use simple paragraph text."
        )

    def get_prompt_preview(
        self,
        style: ExplanationStyle = ExplanationStyle.STANDARD,
    ) -> dict[str, str]:
        """
        Generate a preview of the prompts that will be sent to the AI.

        Args:
            style: Explanation style to use for the preview

        Returns:
            Dict with 'system_prompt' and 'user_prompt' keys

        """
        sample_weather = {
            "temperature": 72,
            "temperature_unit": "F",
            "conditions": "Partly Cloudy",
            "humidity": 65,
            "wind_speed": 8,
            "wind_direction": "NW",
            "visibility": 10,
        }
        return {
            "system_prompt": self.get_effective_system_prompt(style),
            "user_prompt": self._build_prompt(sample_weather, "Sample Location", style),
        }

    def _build_prompt(
        self,
        weather_data: dict[str, Any],
        location_name: str,
        style: ExplanationStyle,
    ) -> str:
        """Construct prompt from weather data."""
        # Extract weather context from data
        context = WeatherContext(
            location=location_name,
            timestamp=datetime.now(),
            temperature=weather_data.get("temperature"),
            temperature_unit=weather_data.get("temperature_unit", "F"),
            conditions=weather_data.get("conditions"),
            humidity=weather_data.get("humidity"),
            wind_speed=weather_data.get("wind_speed"),
            wind_direction=weather_data.get("wind_direction"),
            visibility=weather_data.get("visibility"),
            pressure=weather_data.get("pressure"),
            alerts=weather_data.get("alerts", []),
            forecast_summary=weather_data.get("forecast_summary"),
            local_time=weather_data.get("local_time"),
            utc_time=weather_data.get("utc_time"),
            timezone=weather_data.get("timezone"),
            time_of_day=weather_data.get("time_of_day"),
        )

        prompt_parts = [
            "Please explain the following weather conditions:\n",
            context.to_prompt_text(),
        ]

        # Add forecast periods if available
        forecast_periods = weather_data.get("forecast_periods", [])
        if forecast_periods:
            prompt_parts.append("\n\nUpcoming Forecast:")
            for period in forecast_periods:
                period_text = f"\n- {period.get('name', 'Unknown')}: "
                period_text += (
                    f"{period.get('temperature', 'N/A')}°{period.get('temperature_unit', 'F')}"
                )
                if period.get("short_forecast"):
                    period_text += f", {period['short_forecast']}"
                if period.get("wind_speed"):
                    period_text += f" (Wind: {period['wind_speed']}"
                    if period.get("wind_direction"):
                        period_text += f" {period['wind_direction']}"
                    period_text += ")"
                prompt_parts.append(period_text)

        prompt_parts.append(
            "\n\nProvide a natural language explanation of the current conditions "
            "and what to expect over the coming days for someone planning their activities."
        )

        # Add custom instructions if configured
        if self.custom_instructions and self.custom_instructions.strip():
            prompt_parts.append(f"\n\nAdditional Instructions: {self.custom_instructions}")

        return "".join(prompt_parts)

    def _format_response(self, response_text: str, preserve_markdown: bool) -> str:
        """
        Format AI response based on HTML rendering setting.

        Args:
            response_text: Raw response from AI
            preserve_markdown: If True, keep markdown; if False, strip it

        Returns:
            Formatted response text

        """
        if preserve_markdown:
            return response_text

        # Strip markdown formatting for plain text output
        text = response_text

        # Remove bold/italic markers
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)  # **bold**
        text = re.sub(r"\*(.+?)\*", r"\1", text)  # *italic*
        text = re.sub(r"__(.+?)__", r"\1", text)  # __bold__
        text = re.sub(r"_(.+?)_", r"\1", text)  # _italic_

        # Remove headers
        text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)

        # Remove code blocks
        text = re.sub(r"```[\s\S]*?```", "", text)
        text = re.sub(r"`(.+?)`", r"\1", text)

        # Remove links but keep text
        text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)

        # Remove bullet points
        text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)

        # Clean up extra whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()

    def _generate_cache_key(self, weather_data: dict[str, Any], location_name: str) -> str:
        """Generate a cache key for the explanation."""
        # Create a key based on significant weather values
        key_parts = [
            f"loc:{location_name}",
            f"temp:{weather_data.get('temperature')}",
            f"cond:{weather_data.get('conditions')}",
            f"model:{self.get_effective_model()}",
        ]
        return "ai_explanation:" + ":".join(key_parts)

    @property
    def session_token_count(self) -> int:
        """Get total tokens used in this session."""
        return self._session_token_count
