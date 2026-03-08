"""Tests for ToastedWindowsNotifier and platform-based backend selection."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from accessiweather.notifications import toast_notifier

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeToast:
    """Minimal stand-in for toasted.Toast used in unit tests."""

    _registered: dict[str, bool] = {}

    def __init__(self, app_id=None, sound=None, **_kw):
        self.app_id = app_id
        self.sound = sound
        self.elements = []
        self._shown = False

    async def show(self, mute_sound=False):
        self._shown = True
        return MagicMock(is_dismissed=False)

    @staticmethod
    def register_app_id(handle, **_kw):
        _FakeToast._registered[handle] = True
        return handle

    @staticmethod
    def is_registered_app_id(handle):
        return _FakeToast._registered.get(handle, False)


class _FakeText:
    """Minimal stand-in for toasted.Text."""

    def __init__(self, content):
        self.content = content


# ---------------------------------------------------------------------------
# ToastedWindowsNotifier unit tests
# ---------------------------------------------------------------------------


class TestToastedWindowsNotifierInit:
    """Test initialization of ToastedWindowsNotifier."""

    def test_init_when_toasted_unavailable(self):
        """When TOASTED_AVAILABLE is False, init logs warning but doesn't crash."""
        with patch.object(toast_notifier, "TOASTED_AVAILABLE", False):
            notifier = toast_notifier.ToastedWindowsNotifier(app_name="Test", sound_enabled=False)
            assert notifier.app_name == "Test"
            assert notifier.sound_enabled is False
            assert notifier.balloon_fn is None

    def test_init_when_toasted_available(self):
        """When TOASTED_AVAILABLE is True, init succeeds."""
        with patch.object(toast_notifier, "TOASTED_AVAILABLE", True):
            notifier = toast_notifier.ToastedWindowsNotifier(
                app_name="AccessiWeather", sound_enabled=True, soundpack="custom"
            )
            assert notifier.app_name == "AccessiWeather"
            assert notifier.sound_enabled is True
            assert notifier.soundpack == "custom"

    def test_default_soundpack(self):
        """Default soundpack is 'default'."""
        with patch.object(toast_notifier, "TOASTED_AVAILABLE", False):
            notifier = toast_notifier.ToastedWindowsNotifier()
            assert notifier.soundpack == "default"


class TestToastedWindowsNotifierSend:
    """Test send_notification on ToastedWindowsNotifier."""

    def test_send_when_toasted_unavailable_returns_true(self):
        """When toasted is unavailable, send returns True (logged-only)."""
        with patch.object(toast_notifier, "TOASTED_AVAILABLE", False):
            notifier = toast_notifier.ToastedWindowsNotifier(sound_enabled=False)
            result = notifier.send_notification("Title", "Body")
            assert result is True

    def test_send_when_toasted_unavailable_plays_sound_if_enabled(self):
        """When toasted unavailable but sound enabled, sound still plays."""
        with (
            patch.object(toast_notifier, "TOASTED_AVAILABLE", False),
            patch.object(toast_notifier, "play_notification_sound") as mock_sound,
        ):
            notifier = toast_notifier.ToastedWindowsNotifier(sound_enabled=True)
            notifier.send_notification("Title", "Body", play_sound=True)
            mock_sound.assert_called_once_with("alert", "default", muted_events=["data_updated"])

    def test_send_skips_sound_when_play_sound_false(self):
        """When play_sound=False, no sound is played."""
        with (
            patch.object(toast_notifier, "TOASTED_AVAILABLE", False),
            patch.object(toast_notifier, "play_notification_sound") as mock_sound,
        ):
            notifier = toast_notifier.ToastedWindowsNotifier(sound_enabled=True)
            notifier.send_notification("Title", "Body", play_sound=False)
            mock_sound.assert_not_called()

    def test_send_uses_sound_candidates_when_provided(self):
        """When sound_candidates are provided, they take precedence."""
        with (
            patch.object(toast_notifier, "TOASTED_AVAILABLE", False),
            patch.object(toast_notifier, "play_notification_sound_candidates") as mock_candidates,
        ):
            notifier = toast_notifier.ToastedWindowsNotifier(sound_enabled=True)
            notifier.send_notification("Title", "Body", sound_candidates=["alert", "notify"])
            mock_candidates.assert_called_once_with(
                ["alert", "notify"],
                "default",
                logical_event="alert",
                muted_events=["data_updated"],
            )

    def test_balloon_fallback_called_on_failure(self):
        """When _send_in_worker fails, balloon_fn fallback is tried."""
        with patch.object(toast_notifier, "TOASTED_AVAILABLE", True):
            notifier = toast_notifier.ToastedWindowsNotifier(sound_enabled=False)
            notifier.balloon_fn = MagicMock()
            # Mock _send_in_worker to return False
            notifier._send_in_worker = MagicMock(return_value=False)

            result = notifier.send_notification("Title", "Body")
            assert result is False
            notifier.balloon_fn.assert_called_once_with("Title", "Body")

    def test_send_catches_exceptions(self):
        """send_notification catches and logs exceptions."""
        with patch.object(toast_notifier, "TOASTED_AVAILABLE", True):
            notifier = toast_notifier.ToastedWindowsNotifier(sound_enabled=False)
            notifier._send_in_worker = MagicMock(side_effect=RuntimeError("boom"))

            result = notifier.send_notification("Title", "Body")
            assert result is False


class TestToastedWindowsNotifierWorker:
    """Test worker thread management."""

    def test_ensure_worker_returns_false_when_unavailable(self):
        """_ensure_worker returns False when toasted is not available."""
        with patch.object(toast_notifier, "TOASTED_AVAILABLE", False):
            notifier = toast_notifier.ToastedWindowsNotifier()
            assert notifier._ensure_worker() is False

    def test_send_in_worker_returns_false_when_unavailable(self):
        """_send_in_worker returns False when worker can't start."""
        with patch.object(toast_notifier, "TOASTED_AVAILABLE", False):
            notifier = toast_notifier.ToastedWindowsNotifier()
            assert notifier._send_in_worker("T", "M") is False

    def test_worker_thread_sends_toast(self):
        """Integration-style test: worker thread sends a toast using fake toasted."""
        _FakeToast._registered.clear()

        with (
            patch.object(toast_notifier, "TOASTED_AVAILABLE", True),
            patch.object(toast_notifier, "_Toast", _FakeToast),
            patch.object(toast_notifier, "_Text", _FakeText),
        ):
            notifier = toast_notifier.ToastedWindowsNotifier(sound_enabled=False)
            result = notifier._send_in_worker("Test Title", "Test Body")
            assert result is True

            # Clean up the worker thread
            if notifier._worker_loop and notifier._worker_loop.is_running():
                notifier._worker_loop.call_soon_threadsafe(notifier._worker_loop.stop)
            if notifier._worker_thread:
                notifier._worker_thread.join(timeout=2)

    def test_worker_registers_app_id(self):
        """Worker thread registers the AUMID on first run."""
        _FakeToast._registered.clear()

        with (
            patch.object(toast_notifier, "TOASTED_AVAILABLE", True),
            patch.object(toast_notifier, "_Toast", _FakeToast),
            patch.object(toast_notifier, "_Text", _FakeText),
        ):
            notifier = toast_notifier.ToastedWindowsNotifier(sound_enabled=False)
            notifier._send_in_worker("T", "M")

            from accessiweather.constants import WINDOWS_APP_USER_MODEL_ID

            assert _FakeToast._registered.get(WINDOWS_APP_USER_MODEL_ID) is True

            # Clean up
            if notifier._worker_loop and notifier._worker_loop.is_running():
                notifier._worker_loop.call_soon_threadsafe(notifier._worker_loop.stop)
            if notifier._worker_thread:
                notifier._worker_thread.join(timeout=2)


# ---------------------------------------------------------------------------
# Platform selection tests
# ---------------------------------------------------------------------------


class TestPlatformSelection:
    """Test that SafeDesktopNotifier resolves to the right backend."""

    def test_on_windows_with_toasted(self):
        """On win32 + toasted available, ToastedWindowsNotifier has correct interface."""
        assert hasattr(toast_notifier.ToastedWindowsNotifier, "send_notification")
        # balloon_fn is an instance attribute, verify via instantiation
        with patch.object(toast_notifier, "TOASTED_AVAILABLE", False):
            notifier = toast_notifier.ToastedWindowsNotifier()
            assert hasattr(notifier, "balloon_fn")
            assert hasattr(notifier, "sound_enabled")
            assert hasattr(notifier, "soundpack")

    def test_desktop_notifier_backend_has_same_interface(self):
        """_DesktopNotifierBackend has the same public interface as ToastedWindowsNotifier."""
        # Instance attributes are set in __init__, so instantiate to check
        backend = toast_notifier._DesktopNotifierBackend(sound_enabled=False)
        for attr in ("send_notification", "balloon_fn", "sound_enabled", "soundpack"):
            assert hasattr(backend, attr), f"_DesktopNotifierBackend missing: {attr}"

    def test_safe_desktop_notifier_is_correct_type(self):
        """SafeDesktopNotifier is one of the two backend classes."""
        assert toast_notifier.SafeDesktopNotifier in (
            toast_notifier.ToastedWindowsNotifier,
            toast_notifier._DesktopNotifierBackend,
        )

    def test_notifier_available_flag(self):
        """NOTIFIER_AVAILABLE reflects at least one backend being usable."""
        assert (
            toast_notifier.TOASTED_AVAILABLE or toast_notifier.DESKTOP_NOTIFIER_AVAILABLE
        ) == toast_notifier.NOTIFIER_AVAILABLE


# ---------------------------------------------------------------------------
# SafeToastNotifier with new backend
# ---------------------------------------------------------------------------


class TestSafeToastNotifierBackendSelection:
    """Test that SafeToastNotifier works with the platform-selected backend."""

    def test_creates_notifier_when_available(self):
        """When NOTIFIER_AVAILABLE is True, _desktop_notifier is created."""
        with patch.object(toast_notifier, "NOTIFIER_AVAILABLE", True):
            # SafeDesktopNotifier is already aliased, so it should work
            notifier = toast_notifier.SafeToastNotifier(sound_enabled=False)
            assert notifier._desktop_notifier is not None

    def test_no_notifier_when_unavailable(self):
        """When NOTIFIER_AVAILABLE is False, _desktop_notifier is None."""
        with patch.object(toast_notifier, "NOTIFIER_AVAILABLE", False):
            notifier = toast_notifier.SafeToastNotifier(sound_enabled=False)
            assert notifier._desktop_notifier is None

    def test_show_toast_in_test_mode(self):
        """show_toast returns True immediately when pytest is in sys.modules."""
        with patch.object(toast_notifier, "NOTIFIER_AVAILABLE", False):
            notifier = toast_notifier.SafeToastNotifier(sound_enabled=False)
            result = notifier.show_toast(title="Test", msg="Test message")
            assert result is True
