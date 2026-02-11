"""Tests for the screen_reader module."""

import importlib
import sys
from unittest import mock


class TestWithoutPrismatoid:
    """Test behavior when prismatoid is not installed."""

    def test_prism_available_false_when_not_installed(self):
        """PRISM_AVAILABLE should be False when prismatoid is missing."""
        # Remove prism from sys.modules if present, block import
        with mock.patch.dict(sys.modules, {"prism": None}):
            import accessiweather.screen_reader as sr_mod

            reloaded = importlib.reload(sr_mod)
            assert reloaded.PRISM_AVAILABLE is False

    def test_announcer_instantiates_without_prismatoid(self):
        """ScreenReaderAnnouncer should instantiate without error."""
        with mock.patch.dict(sys.modules, {"prism": None}):
            import accessiweather.screen_reader as sr_mod

            reloaded = importlib.reload(sr_mod)
            announcer = reloaded.ScreenReaderAnnouncer()
            assert announcer.is_available() is False

    def test_announce_is_noop_without_prismatoid(self):
        """announce() should not raise when prismatoid is missing."""
        with mock.patch.dict(sys.modules, {"prism": None}):
            import accessiweather.screen_reader as sr_mod

            reloaded = importlib.reload(sr_mod)
            announcer = reloaded.ScreenReaderAnnouncer()
            announcer.announce("hello")  # should not raise

    def test_shutdown_safe_without_prismatoid(self):
        """shutdown() should not raise when prismatoid is missing."""
        with mock.patch.dict(sys.modules, {"prism": None}):
            import accessiweather.screen_reader as sr_mod

            reloaded = importlib.reload(sr_mod)
            announcer = reloaded.ScreenReaderAnnouncer()
            announcer.shutdown()  # should not raise


class TestWithMockedPrismatoid:
    """Test behavior when prismatoid is available (mocked)."""

    def _reload_with_mock_prism(self):
        mock_features = mock.MagicMock()
        mock_features.is_supported_at_runtime = True
        mock_backend = mock.MagicMock()
        mock_backend.features = mock_features
        mock_backend.name = "MockReader"
        mock_ctx = mock.MagicMock()
        mock_ctx.acquire_best.return_value = mock_backend
        mock_prism = mock.MagicMock()
        mock_prism.Context.return_value = mock_ctx

        with mock.patch.dict(sys.modules, {"prism": mock_prism}):
            import accessiweather.screen_reader as sr_mod

            reloaded = importlib.reload(sr_mod)
            return reloaded, mock_backend, mock_prism

    def test_prism_available_true(self):
        reloaded, _, _ = self._reload_with_mock_prism()
        assert reloaded.PRISM_AVAILABLE is True

    def test_announcer_is_available(self):
        reloaded, _, _ = self._reload_with_mock_prism()
        announcer = reloaded.ScreenReaderAnnouncer()
        assert announcer.is_available() is True

    def test_announce_calls_speak(self):
        reloaded, mock_backend, _ = self._reload_with_mock_prism()
        announcer = reloaded.ScreenReaderAnnouncer()
        announcer.announce("test message")
        mock_backend.speak.assert_called_once_with("test message", interrupt=False)

    def test_shutdown_clears_backend(self):
        reloaded, _, _ = self._reload_with_mock_prism()
        announcer = reloaded.ScreenReaderAnnouncer()
        assert announcer.is_available() is True
        announcer.shutdown()
        assert announcer.is_available() is False

    def test_graceful_fallback_on_acquire_exception(self):
        """If acquire_best() raises, announcer should fall back gracefully."""
        mock_prism = mock.MagicMock()
        mock_prism.Context.return_value.acquire_best.side_effect = RuntimeError("no SR")

        with mock.patch.dict(sys.modules, {"prism": mock_prism}):
            import accessiweather.screen_reader as sr_mod

            reloaded = importlib.reload(sr_mod)
            announcer = reloaded.ScreenReaderAnnouncer()
            assert announcer.is_available() is False
            announcer.announce("test")  # no-op, no raise

    def test_announce_handles_speak_exception(self):
        """If speak() raises, announce should not propagate."""
        reloaded, mock_backend, _ = self._reload_with_mock_prism()
        mock_backend.speak.side_effect = RuntimeError("speak failed")
        announcer = reloaded.ScreenReaderAnnouncer()
        announcer.announce("test")  # should not raise
