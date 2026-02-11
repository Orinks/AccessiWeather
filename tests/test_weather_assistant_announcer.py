"""Tests for ScreenReaderAnnouncer integration in WeatherAssistantDialog."""

from __future__ import annotations

from unittest.mock import MagicMock


class TestAnnouncerIntegration:
    """Verify ScreenReaderAnnouncer is wired into WeatherAssistantDialog."""

    def test_announcer_import_in_module(self):
        """ScreenReaderAnnouncer is imported in the dialog module."""
        from accessiweather.ui.dialogs import weather_assistant_dialog as mod

        assert hasattr(mod, "ScreenReaderAnnouncer")

    def test_dialog_source_creates_announcer_in_init(self):
        """__init__ creates self._announcer = ScreenReaderAnnouncer()."""
        import inspect

        from accessiweather.ui.dialogs.weather_assistant_dialog import (
            WeatherAssistantDialog,
        )

        source = inspect.getsource(WeatherAssistantDialog.__init__)
        assert "ScreenReaderAnnouncer()" in source
        assert "_announcer" in source

    def test_on_response_received_calls_announce(self):
        """_on_response_received calls self._announcer.announce(text)."""
        import inspect

        from accessiweather.ui.dialogs.weather_assistant_dialog import (
            WeatherAssistantDialog,
        )

        source = inspect.getsource(WeatherAssistantDialog._on_response_received)
        assert "_announcer.announce" in source

    def test_on_response_error_calls_announce(self):
        """_on_response_error calls self._announcer.announce(error_message)."""
        import inspect

        from accessiweather.ui.dialogs.weather_assistant_dialog import (
            WeatherAssistantDialog,
        )

        source = inspect.getsource(WeatherAssistantDialog._on_response_error)
        assert "_announcer.announce" in source

    def test_on_close_calls_shutdown(self):
        """_on_close calls self._announcer.shutdown()."""
        import inspect

        from accessiweather.ui.dialogs.weather_assistant_dialog import (
            WeatherAssistantDialog,
        )

        source = inspect.getsource(WeatherAssistantDialog._on_close)
        assert "_announcer.shutdown()" in source

    def test_welcome_message_calls_announce(self):
        """_add_welcome_message calls self._announcer.announce(welcome)."""
        import inspect

        from accessiweather.ui.dialogs.weather_assistant_dialog import (
            WeatherAssistantDialog,
        )

        source = inspect.getsource(WeatherAssistantDialog._add_welcome_message)
        assert "_announcer.announce" in source


class TestScreenReaderAnnouncerGracefulFallback:
    """Verify ScreenReaderAnnouncer works when prismatoid is not installed."""

    def test_announcer_no_op_without_prismatoid(self):
        """ScreenReaderAnnouncer is a no-op when prismatoid is unavailable."""
        from unittest.mock import patch

        # Simulate prismatoid not being installed
        with patch("accessiweather.screen_reader.PRISM_AVAILABLE", False):
            from accessiweather.screen_reader import ScreenReaderAnnouncer

            announcer = ScreenReaderAnnouncer()
            assert not announcer.is_available()
            # Should not raise
            announcer.announce("test message")
            announcer.shutdown()

    def test_announcer_no_op_when_backend_not_running(self):
        """ScreenReaderAnnouncer is a no-op when backend exists but isn't running."""
        from unittest.mock import MagicMock, patch

        mock_features = MagicMock()
        mock_features.is_supported_at_runtime = False
        mock_backend = MagicMock()
        mock_backend.features = mock_features
        mock_backend.name = "MockReader"

        mock_ctx = MagicMock()
        mock_ctx.acquire_best.return_value = mock_backend

        with (
            patch("accessiweather.screen_reader.PRISM_AVAILABLE", True),
            patch("accessiweather.screen_reader.prism") as mock_prism,
        ):
            mock_prism.Context.return_value = mock_ctx

            from accessiweather.screen_reader import ScreenReaderAnnouncer

            announcer = ScreenReaderAnnouncer()
            assert not announcer.is_available()
            announcer.announce("test message")
            mock_backend.speak.assert_not_called()
            announcer.shutdown()

    def test_announcer_with_mocked_unavailable(self):
        """ScreenReaderAnnouncer with is_available=False works as no-op."""
        announcer = MagicMock()
        announcer.is_available.return_value = False
        # Simulates dialog usage pattern
        announcer.announce("hello")
        announcer.shutdown()
        announcer.announce.assert_called_with("hello")
        announcer.shutdown.assert_called_once()
