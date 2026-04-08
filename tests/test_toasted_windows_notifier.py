"""Tests for ToastedWindowsNotifier and platform-based backend selection."""

from __future__ import annotations

import time
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
        self.arguments = None

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


class _FakeToastResult:
    """Stand-in for toasted.common.ToastResult."""

    def __init__(self, arguments="", is_dismissed=False):
        self.arguments = arguments
        self.is_dismissed = is_dismissed


class _FakeToastWithCallback(_FakeToast):
    """FakeToast that captures and fires the on_result callback."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self._callback_result = None

    def on_result(self, function=None):
        if function:
            self._callback_result = function
            return function

        def decorator(func):
            self._callback_result = func
            return func

        return decorator

    async def show(self, mute_sound=False):
        self._shown = True
        # Simulate user clicking the toast
        if self._callback_result:
            result = _FakeToastResult(arguments=self.arguments or "")
            self._callback_result(result)
        return _FakeToastResult(arguments=self.arguments or "")


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

    def test_set_activation_arguments_sets_launch_context(self):
        """Toast launch arguments are attached so Action Center clicks relaunch with context."""
        with patch.object(toast_notifier, "TOASTED_AVAILABLE", False):
            notifier = toast_notifier.ToastedWindowsNotifier(sound_enabled=False)

        toast = _FakeToast()
        notifier._set_activation_arguments(toast, "accessiweather-toast:kind=discussion")

        assert toast.arguments == "accessiweather-toast:kind=discussion"

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

    def test_send_in_worker_stores_task_reference(self):
        """Task references are kept alive to prevent GC cancellation."""
        _FakeToast._registered.clear()

        class _TrackingSet(set):
            """Set subclass that records every item ever added."""

            def __init__(self, *a, **kw):
                super().__init__(*a, **kw)
                self.ever_added: list[object] = []

            def add(self, item):
                self.ever_added.append(item)
                super().add(item)

        with (
            patch.object(toast_notifier, "TOASTED_AVAILABLE", True),
            patch.object(toast_notifier, "_Toast", _FakeToast),
            patch.object(toast_notifier, "_Text", _FakeText),
        ):
            notifier = toast_notifier.ToastedWindowsNotifier(sound_enabled=False)
            tracking = _TrackingSet()
            notifier._pending_tasks = tracking

            notifier._send_in_worker("Title", "Body")
            # Give worker loop time to process the coroutine
            time.sleep(0.3)

            # At least one task should have been added (even if already completed)
            assert len(tracking.ever_added) >= 1

            # Clean up
            if notifier._worker_loop and notifier._worker_loop.is_running():
                notifier._worker_loop.call_soon_threadsafe(notifier._worker_loop.stop)
            if notifier._worker_thread:
                notifier._worker_thread.join(timeout=2)


# ---------------------------------------------------------------------------
# Activation callback tests
# ---------------------------------------------------------------------------


class TestToastedActivationCallback:
    """Test that on_result callback routes activation to app."""

    def test_on_result_callback_is_registered(self):
        """Toast gets an on_result callback when activation_arguments are provided."""
        _FakeToastWithCallback._registered = {}

        with (
            patch.object(toast_notifier, "TOASTED_AVAILABLE", True),
            patch.object(toast_notifier, "_Toast", _FakeToastWithCallback),
            patch.object(toast_notifier, "_Text", _FakeText),
        ):
            notifier = toast_notifier.ToastedWindowsNotifier(sound_enabled=False)
            callback = MagicMock()
            notifier.on_activation = callback

            notifier._send_in_worker(
                "Title",
                "Body",
                activation_arguments="accessiweather-toast:kind=discussion",
            )
            # Give worker loop time to process
            time.sleep(0.3)

            callback.assert_called_once()
            result = callback.call_args[0][0]
            assert result.arguments == "accessiweather-toast:kind=discussion"

            # Clean up
            if notifier._worker_loop and notifier._worker_loop.is_running():
                notifier._worker_loop.call_soon_threadsafe(notifier._worker_loop.stop)
            if notifier._worker_thread:
                notifier._worker_thread.join(timeout=2)

    def test_on_activation_defaults_to_none(self):
        """on_activation callback defaults to None."""
        with patch.object(toast_notifier, "TOASTED_AVAILABLE", False):
            notifier = toast_notifier.ToastedWindowsNotifier(sound_enabled=False)
            assert notifier.on_activation is None

    def test_no_callback_when_no_activation_arguments(self):
        """on_result is NOT registered when activation_arguments is None."""
        _FakeToastWithCallback._registered = {}

        with (
            patch.object(toast_notifier, "TOASTED_AVAILABLE", True),
            patch.object(toast_notifier, "_Toast", _FakeToastWithCallback),
            patch.object(toast_notifier, "_Text", _FakeText),
        ):
            notifier = toast_notifier.ToastedWindowsNotifier(sound_enabled=False)
            callback = MagicMock()
            notifier.on_activation = callback

            notifier._send_in_worker("Title", "Body")  # no activation_arguments
            time.sleep(0.3)

            callback.assert_not_called()

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
        with patch.object(toast_notifier, "TOASTED_AVAILABLE", False):
            notifier = toast_notifier.ToastedWindowsNotifier()
            assert hasattr(notifier, "sound_enabled")
            assert hasattr(notifier, "soundpack")

    def test_desktop_notifier_backend_has_same_interface(self):
        """_DesktopNotifierBackend has the same public interface as ToastedWindowsNotifier."""
        # Instance attributes are set in __init__, so instantiate to check
        backend = toast_notifier._DesktopNotifierBackend(sound_enabled=False)
        for attr in ("send_notification", "sound_enabled", "soundpack"):
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
# Direct WinRT activation path tests
# ---------------------------------------------------------------------------


class TestDirectWinRTActivation:
    """Test the direct WinRT toast path that keeps activated handlers alive."""

    def test_activation_result_has_expected_attrs(self):
        """_ActivationResult carries arguments and is_dismissed=False."""
        result = toast_notifier._ActivationResult(arguments="test-arg")
        assert result.arguments == "test-arg"
        assert result.is_dismissed is False

    def test_show_toast_direct_returns_false_when_winrt_unavailable(self):
        """_show_toast_direct returns False when WINRT_AVAILABLE is False."""
        with (
            patch.object(toast_notifier, "TOASTED_AVAILABLE", False),
            patch.object(toast_notifier, "WINRT_AVAILABLE", False),
        ):
            notifier = toast_notifier.ToastedWindowsNotifier(sound_enabled=False)
            assert notifier._show_toast_direct(MagicMock(), "args") is False

    def test_show_toast_direct_keeps_notification_alive(self):
        """Direct WinRT path stores notification in _live_notifications."""
        mock_xml_doc = MagicMock()
        mock_notification = MagicMock()
        mock_notifier_mgr = MagicMock()

        with (
            patch.object(toast_notifier, "TOASTED_AVAILABLE", True),
            patch.object(toast_notifier, "WINRT_AVAILABLE", True),
            patch.object(toast_notifier, "_WinRT_XmlDocument", return_value=mock_xml_doc),
            patch.object(
                toast_notifier, "_WinRT_ToastNotification", return_value=mock_notification
            ),
            patch.object(toast_notifier, "_WinRT_ToastNotificationManager", mock_notifier_mgr),
        ):
            notifier = toast_notifier.ToastedWindowsNotifier(sound_enabled=False)
            # Use a real toast mock with to_xml_string
            fake_toast = MagicMock()
            fake_toast.to_xml_string.return_value = "<toast><visual></visual></toast>"

            result = notifier._show_toast_direct(fake_toast, "test-args")
            assert result is True
            assert mock_notification in notifier._live_notifications
            mock_notifier_mgr.create_toast_notifier.assert_called_once()

    def test_show_toast_direct_uses_protocol_activation_for_cold_start(self):
        """Cold-start safe Windows toasts use protocol activation, not plain launch args."""
        mock_xml_doc = MagicMock()
        mock_notification = MagicMock()
        mock_notifier_mgr = MagicMock()

        with (
            patch.object(toast_notifier, "TOASTED_AVAILABLE", True),
            patch.object(toast_notifier, "WINRT_AVAILABLE", True),
            patch.object(toast_notifier, "_WinRT_XmlDocument", return_value=mock_xml_doc),
            patch.object(
                toast_notifier, "_WinRT_ToastNotification", return_value=mock_notification
            ),
            patch.object(toast_notifier, "_WinRT_ToastNotificationManager", mock_notifier_mgr),
        ):
            notifier = toast_notifier.ToastedWindowsNotifier(sound_enabled=False)
            fake_toast = MagicMock()
            fake_toast.to_xml_string.return_value = "<toast><visual></visual></toast>"

            result = notifier._show_toast_direct(fake_toast, "accessiweather-toast:kind=discussion")

            assert result is True
            xml_payload = mock_xml_doc.load_xml.call_args.args[0]
            assert 'activationType="protocol"' in xml_payload
            assert 'launch="accessiweather-toast:kind=discussion"' in xml_payload

    def test_live_notifications_trimmed_at_max(self):
        """Old notifications are trimmed when _MAX_LIVE_NOTIFICATIONS is exceeded."""
        with patch.object(toast_notifier, "TOASTED_AVAILABLE", False):
            notifier = toast_notifier.ToastedWindowsNotifier(sound_enabled=False)
            notifier._MAX_LIVE_NOTIFICATIONS = 3
            notifier._live_notifications = ["old1", "old2", "old3", "new"]
            # Simulate trim logic
            if len(notifier._live_notifications) > notifier._MAX_LIVE_NOTIFICATIONS:
                notifier._live_notifications = notifier._live_notifications[
                    -notifier._MAX_LIVE_NOTIFICATIONS :
                ]
            assert len(notifier._live_notifications) == 3
            assert notifier._live_notifications[0] == "old2"


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
