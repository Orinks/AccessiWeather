"""
Tests for TrayTextFormatDialog contract and TaskbarIconUpdater.build_preview.

Covers:
  TRAY-02 - dialog get_format_string() contract (accessible, usable)
  TRAY-03 - live preview updates via build_preview
"""

from __future__ import annotations

from unittest.mock import MagicMock

from accessiweather.taskbar_icon_updater import (
    DEFAULT_TOOLTIP_FORMAT,
    TaskbarIconUpdater,
)

# ---------------------------------------------------------------------------
# Minimal stub that mirrors TrayTextFormatDialog.get_format_string logic
# without requiring a real wx.Dialog to be instantiated.
# ---------------------------------------------------------------------------


class _DialogStub:
    """Exercises TrayTextFormatDialog.get_format_string contract without wx."""

    def __init__(self, format_value: str) -> None:
        self._format_ctrl = MagicMock()
        self._format_ctrl.GetValue.return_value = format_value

    def get_format_string(self) -> str:
        value = self._format_ctrl.GetValue().strip()
        return value or DEFAULT_TOOLTIP_FORMAT


# =============================================================================
# Section 1 — Dialog contract (TRAY-02)
# =============================================================================


class TestTrayTextFormatDialogContract:
    """Verify TrayTextFormatDialog.get_format_string() contract."""

    def test_get_format_string_returns_entered_value(self):
        """get_format_string returns whatever the user typed."""
        stub = _DialogStub("{location}: {temp}")
        assert stub.get_format_string() == "{location}: {temp}"

    def test_get_format_string_strips_leading_trailing_whitespace(self):
        """get_format_string strips surrounding whitespace before returning."""
        stub = _DialogStub("  {temp}  ")
        assert stub.get_format_string() == "{temp}"

    def test_get_format_string_blank_returns_default(self):
        """Empty format string falls back to DEFAULT_TOOLTIP_FORMAT."""
        stub = _DialogStub("")
        assert stub.get_format_string() == DEFAULT_TOOLTIP_FORMAT

    def test_get_format_string_whitespace_only_returns_default(self):
        """Whitespace-only format string falls back to DEFAULT_TOOLTIP_FORMAT."""
        stub = _DialogStub("   ")
        assert stub.get_format_string() == DEFAULT_TOOLTIP_FORMAT

    def test_default_tooltip_format_is_nonempty(self):
        """Sanity: DEFAULT_TOOLTIP_FORMAT is a non-empty string."""
        assert DEFAULT_TOOLTIP_FORMAT and len(DEFAULT_TOOLTIP_FORMAT) > 0


# =============================================================================
# Section 2 — Live preview (TRAY-03)
# =============================================================================


class TestTrayTextFormatDialogPreview:
    """Verify TaskbarIconUpdater.build_preview drives the dialog's live preview."""

    def test_build_preview_returns_nonempty_string(self):
        """build_preview always returns a non-empty string."""
        updater = TaskbarIconUpdater(text_enabled=True)
        result = updater.build_preview("{location}: {temp}", weather_data=None)
        assert len(result) > 0

    def test_build_preview_substitutes_sample_location(self):
        """build_preview inserts the sample location name from DEFAULT_PREVIEW_DATA."""
        updater = TaskbarIconUpdater(text_enabled=True)
        result = updater.build_preview("{location}", weather_data=None)
        assert "Sample Location" in result

    def test_build_preview_different_formats_give_different_output(self):
        """Preview output is driven by the format string, not a fixed template."""
        updater = TaskbarIconUpdater(text_enabled=True)
        result_a = updater.build_preview("{temp}", weather_data=None)
        result_b = updater.build_preview("{condition}", weather_data=None)
        assert result_a != result_b

    def test_build_preview_unknown_placeholder_left_as_literal(self):
        """An unknown placeholder is left as literal text — build_preview does not crash."""
        updater = TaskbarIconUpdater(text_enabled=True)
        # FormatStringParser leaves unrecognised keys as-is (e.g. "{foo}") rather
        # than erroring or falling back, so the literal token appears in the result.
        result = updater.build_preview("{temp} {completely_unknown}", weather_data=None)
        assert "{completely_unknown}" in result

    def test_build_preview_with_location_name_override(self):
        """Passing location_name overrides the sample location in the preview."""
        updater = TaskbarIconUpdater(text_enabled=True)
        result = updater.build_preview("{location}", weather_data=None, location_name="My City")
        assert "My City" in result

    def test_build_preview_condition_placeholder(self):
        """build_preview correctly substitutes the condition placeholder."""
        updater = TaskbarIconUpdater(text_enabled=True)
        result = updater.build_preview("{condition}", weather_data=None)
        assert "Partly Cloudy" in result

    def test_build_preview_temp_placeholder(self):
        """build_preview correctly substitutes the temp placeholder."""
        updater = TaskbarIconUpdater(text_enabled=True)
        result = updater.build_preview("{temp}", weather_data=None)
        # DEFAULT_PREVIEW_DATA has temp "72F/22C"
        assert "72F" in result or "22C" in result
