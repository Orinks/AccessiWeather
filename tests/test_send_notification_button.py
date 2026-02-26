"""Tests for Send Notification button wiring in main window."""

from __future__ import annotations

import pathlib

import pytest


class TestSendNotificationButtonSource:
    """Verify Send Notification button exists and reuses existing test path."""

    @pytest.fixture
    def source(self):
        """Read main_window.py source."""
        return pathlib.Path("src/accessiweather/ui/main_window.py").read_text()

    def test_button_label_exists(self, source):
        """Button should be present with exact label text."""
        assert 'label="Send Notification"' in source

    def test_button_has_accessible_name(self, source):
        """Button should expose a screen-reader-friendly name."""
        assert 'self.send_notification_button.SetName("Send Notification")' in source

    def test_button_reuses_existing_notification_path(self, source):
        """Button callback should call existing test discussion notification handler."""
        assert "self.send_notification_button.Bind(" in source
        assert "self._on_test_discussion_notification()" in source
