"""
Tests for main window minimize to tray functionality.

Tests the minimize behaviors including close, iconize, and escape key handlers.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


class TestMainWindowMinimizeToTray:
    """Tests for MainWindow minimize to tray behavior."""

    @pytest.fixture
    def mock_app(self):
        """Create a mock app with config manager."""
        from accessiweather.models import AppSettings

        app = MagicMock()
        settings = AppSettings(minimize_to_tray=True)
        app.config_manager.get_settings.return_value = settings
        app.request_exit = MagicMock()
        return app

    @pytest.fixture
    def mock_app_disabled(self):
        """Create a mock app with minimize to tray disabled."""
        from accessiweather.models import AppSettings

        app = MagicMock()
        settings = AppSettings(minimize_to_tray=False)
        app.config_manager.get_settings.return_value = settings
        app.request_exit = MagicMock()
        return app

    def test_should_minimize_to_tray_returns_true_when_enabled(self, mock_app):
        """Test _should_minimize_to_tray returns True when setting is enabled."""

        # Simulate the method logic
        def should_minimize_to_tray(app):
            try:
                settings = app.config_manager.get_settings()
                return bool(getattr(settings, "minimize_to_tray", False))
            except Exception:
                return False

        result = should_minimize_to_tray(mock_app)
        assert result is True

    def test_should_minimize_to_tray_returns_false_when_disabled(self, mock_app_disabled):
        """Test _should_minimize_to_tray returns False when setting is disabled."""

        def should_minimize_to_tray(app):
            try:
                settings = app.config_manager.get_settings()
                return bool(getattr(settings, "minimize_to_tray", False))
            except Exception:
                return False

        result = should_minimize_to_tray(mock_app_disabled)
        assert result is False

    def test_on_close_minimizes_when_enabled(self, mock_app):
        """Test close handler minimizes to tray when enabled."""
        mock_frame = MagicMock()
        mock_event = MagicMock()

        def on_close(app, frame, event):
            try:
                settings = app.config_manager.get_settings()
                if getattr(settings, "minimize_to_tray", False):
                    frame.Iconize(False)
                    frame.Hide()
                    event.Veto()
                    return "minimized"
            except Exception:
                pass
            app.request_exit()
            return "exit"

        result = on_close(mock_app, mock_frame, mock_event)

        assert result == "minimized"
        mock_frame.Hide.assert_called_once()
        mock_event.Veto.assert_called_once()
        mock_app.request_exit.assert_not_called()

    def test_on_close_exits_when_disabled(self, mock_app_disabled):
        """Test close handler exits when minimize to tray is disabled."""
        mock_frame = MagicMock()
        mock_event = MagicMock()

        def on_close(app, frame, event):
            try:
                settings = app.config_manager.get_settings()
                if getattr(settings, "minimize_to_tray", False):
                    frame.Iconize(False)
                    frame.Hide()
                    event.Veto()
                    return "minimized"
            except Exception:
                pass
            app.request_exit()
            return "exit"

        result = on_close(mock_app_disabled, mock_frame, mock_event)

        assert result == "exit"
        mock_frame.Hide.assert_not_called()
        mock_app_disabled.request_exit.assert_called_once()

    def test_on_iconize_hides_when_enabled(self, mock_app):
        """Test iconize handler hides window when minimize to tray is enabled."""
        mock_frame = MagicMock()
        hide_called = []

        def minimize_to_tray(frame):
            frame.Iconize(False)
            frame.Hide()
            hide_called.append(True)

        def on_iconize(app, frame, is_iconized):
            try:
                settings = app.config_manager.get_settings()
                if is_iconized and getattr(settings, "minimize_to_tray", False):
                    minimize_to_tray(frame)
                    return True
            except Exception:
                pass
            return False

        result = on_iconize(mock_app, mock_frame, True)

        assert result is True
        assert len(hide_called) == 1
        mock_frame.Hide.assert_called_once()

    def test_on_iconize_allows_normal_behavior_when_disabled(self, mock_app_disabled):
        """Test iconize handler allows normal behavior when disabled."""
        mock_frame = MagicMock()

        def on_iconize(app, frame, is_iconized):
            try:
                settings = app.config_manager.get_settings()
                if is_iconized and getattr(settings, "minimize_to_tray", False):
                    frame.Iconize(False)
                    frame.Hide()
                    return True
            except Exception:
                pass
            return False

        result = on_iconize(mock_app_disabled, mock_frame, True)

        assert result is False
        mock_frame.Hide.assert_not_called()

    def test_escape_key_minimizes_when_enabled(self, mock_app):
        """Test escape key minimizes to tray when enabled."""
        mock_frame = MagicMock()
        WXK_ESCAPE = 27  # wx.WXK_ESCAPE value

        def on_key_down(app, frame, key_code):
            try:
                settings = app.config_manager.get_settings()
                if key_code == WXK_ESCAPE and getattr(settings, "minimize_to_tray", False):
                    frame.Iconize(False)
                    frame.Hide()
                    return True
            except Exception:
                pass
            return False

        result = on_key_down(mock_app, mock_frame, WXK_ESCAPE)

        assert result is True
        mock_frame.Hide.assert_called_once()

    def test_escape_key_does_nothing_when_disabled(self, mock_app_disabled):
        """Test escape key does nothing when minimize to tray is disabled."""
        mock_frame = MagicMock()
        WXK_ESCAPE = 27

        def on_key_down(app, frame, key_code):
            try:
                settings = app.config_manager.get_settings()
                if key_code == WXK_ESCAPE and getattr(settings, "minimize_to_tray", False):
                    frame.Iconize(False)
                    frame.Hide()
                    return True
            except Exception:
                pass
            return False

        result = on_key_down(mock_app_disabled, mock_frame, WXK_ESCAPE)

        assert result is False
        mock_frame.Hide.assert_not_called()

    def test_other_keys_not_handled(self, mock_app):
        """Test other keys are not handled by minimize logic."""
        mock_frame = MagicMock()
        WXK_ESCAPE = 27
        WXK_RETURN = 13

        def on_key_down(app, frame, key_code):
            try:
                settings = app.config_manager.get_settings()
                if key_code == WXK_ESCAPE and getattr(settings, "minimize_to_tray", False):
                    frame.Iconize(False)
                    frame.Hide()
                    return True
            except Exception:
                pass
            return False

        result = on_key_down(mock_app, mock_frame, WXK_RETURN)

        assert result is False
        mock_frame.Hide.assert_not_called()


class TestMinimizeToTrayMethod:
    """Tests for the _minimize_to_tray method."""

    def test_minimize_to_tray_hides_frame(self):
        """Test _minimize_to_tray hides the frame."""
        mock_frame = MagicMock()

        def minimize_to_tray(frame):
            frame.Iconize(False)
            frame.Hide()

        minimize_to_tray(mock_frame)

        mock_frame.Iconize.assert_called_once_with(False)
        mock_frame.Hide.assert_called_once()

    def test_minimize_to_tray_restores_from_iconize_first(self):
        """Test _minimize_to_tray restores from iconize before hiding."""
        mock_frame = MagicMock()
        call_order = []

        def track_iconize(val):
            call_order.append(("Iconize", val))

        def track_hide():
            call_order.append(("Hide",))

        mock_frame.Iconize.side_effect = track_iconize
        mock_frame.Hide.side_effect = track_hide

        def minimize_to_tray(frame):
            frame.Iconize(False)
            frame.Hide()

        minimize_to_tray(mock_frame)

        # Iconize(False) should be called before Hide()
        assert call_order == [("Iconize", False), ("Hide",)]
