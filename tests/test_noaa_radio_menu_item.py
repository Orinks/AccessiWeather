"""Tests for NOAA Weather Radio menu item in main window."""

from __future__ import annotations

import pathlib

import pytest


class _FakeLocation:
    """Fake location with lat/lon."""

    def __init__(self, name="Test City", latitude=39.0, longitude=-77.0):
        """Initialize fake location."""
        self.name = name
        self.latitude = latitude
        self.longitude = longitude


class TestNoaaRadioMenuItemSource:
    """Test NOAA Radio menu item exists in main window source."""

    @pytest.fixture
    def source(self):
        """Read main_window.py source."""
        return pathlib.Path("src/accessiweather/ui/main_window.py").read_text()

    def test_menu_item_exists(self, source):
        """Test that NOAA Weather Radio menu item is in the source."""
        assert "NOAA Weather &Radio..." in source

    def test_keyboard_shortcut(self, source):
        """Test that Ctrl+R shortcut is assigned."""
        assert "NOAA Weather &Radio...\\tCtrl+R" in source

    def test_handler_method_exists(self, source):
        """Test that _on_noaa_radio handler method exists."""
        assert "def _on_noaa_radio(self)" in source

    def test_handler_bound_to_menu_item(self, source):
        """Test that the handler is bound to the menu item."""
        assert "_on_noaa_radio" in source
        assert "noaa_radio_item" in source

    def test_no_location_check(self, source):
        """Test that handler checks for no location."""
        assert "get_current_location" in source
        # Find the _on_noaa_radio method and check it has location check
        method_start = source.index("def _on_noaa_radio")
        method_end = source.index("\n    def ", method_start + 1)
        method_body = source[method_start:method_end]
        assert "get_current_location" in method_body
        assert "MessageBox" in method_body
        assert "select a location" in method_body.lower()

    def test_show_noaa_radio_dialog_called(self, source):
        """Test that show_noaa_radio_dialog is called with lat/lon."""
        method_start = source.index("def _on_noaa_radio")
        method_end = source.index("\n    def ", method_start + 1)
        method_body = source[method_start:method_end]
        assert "show_noaa_radio_dialog" in method_body
        assert "latitude" in method_body
        assert "longitude" in method_body

    def test_menu_item_after_uv_index(self, source):
        """Test that NOAA Radio item appears after UV Index."""
        uv_pos = source.index("UV Index")
        noaa_pos = source.index("NOAA Weather &Radio")
        separator_after_noaa = source.index("AppendSeparator", noaa_pos)
        assert uv_pos < noaa_pos < separator_after_noaa

    def test_menu_item_before_weather_assistant(self, source):
        """Test that NOAA Radio item appears before Weather Assistant."""
        noaa_pos = source.index("NOAA Weather &Radio")
        chat_pos = source.index("Weather &Assistant")
        assert noaa_pos < chat_pos
