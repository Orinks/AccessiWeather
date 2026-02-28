"""
Toast notification module for AccessiWeather.

This module provides cross-platform toast notification functionality
with safe error handling for test environments.

On Windows, prefers the 'toasted' package (WinRT-based) for reliable
AUMID handling. Falls back to desktop-notifier on Mac/Linux or when
toasted is unavailable.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import threading

from ..constants import WINDOWS_APP_USER_MODEL_ID
from .sound_player import play_notification_sound, play_notification_sound_candidates

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Backend availability
# ---------------------------------------------------------------------------

# Try toasted first (Windows-only, WinRT-based)
TOASTED_AVAILABLE = False
_Toast = None
_Text = None

if sys.platform == "win32":
    try:
        from toasted import (  # type: ignore[assignment]
            Text as _Text,
            Toast as _Toast,
        )

        TOASTED_AVAILABLE = True
    except ImportError:
        logger.info("toasted not available on Windows, will try desktop-notifier")

# Try desktop-notifier (cross-platform fallback)
try:
    from desktop_notifier import DesktopNotifier

    DESKTOP_NOTIFIER_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Desktop notifier not available: {e}")
    DesktopNotifier = None  # type: ignore[assignment,misc]
    DESKTOP_NOTIFIER_AVAILABLE = False

# At least one notification backend is usable
NOTIFIER_AVAILABLE = TOASTED_AVAILABLE or DESKTOP_NOTIFIER_AVAILABLE


def _log_packaging_notifier_diagnostics() -> None:
    """Emit debug-only notifier dependency diagnostics for packaged troubleshooting."""
    logger.debug(
        "[packaging-diag] notifier deps: toasted_available=%s desktop_notifier_available=%s "
        "frozen=%s meipass=%s executable=%s",
        TOASTED_AVAILABLE,
        DESKTOP_NOTIFIER_AVAILABLE,
        getattr(sys, "frozen", False),
        getattr(sys, "_MEIPASS", None),
        getattr(sys, "executable", None),
    )


# ---------------------------------------------------------------------------
# ToastedWindowsNotifier — Windows backend using the 'toasted' package
# ---------------------------------------------------------------------------


class ToastedWindowsNotifier:
    """
    Windows notification backend using the 'toasted' package.

    Uses WinRT toast notifications via the toasted library, which handles
    AUMID/registry properly for non-UWP desktop apps.

    Exposes the same public interface as SafeDesktopNotifier so callers
    can use either interchangeably.
    """

    def __init__(
        self,
        app_name: str = "AccessiWeather",
        sound_enabled: bool = True,
        soundpack: str | None = None,
    ):
        """Initialize the Windows toasted notification backend."""
        self.app_name = app_name
        _log_packaging_notifier_diagnostics()

        # Sound configuration
        self.sound_enabled: bool = bool(sound_enabled)
        self.soundpack: str = soundpack or "default"

        # Optional fallback callable (same contract as SafeDesktopNotifier)
        self.balloon_fn = None  # Optional[Callable[[str, str], None]]

        # Persistent worker thread state
        self._worker_loop: asyncio.AbstractEventLoop | None = None
        self._worker_thread: threading.Thread | None = None
        self._worker_ready = threading.Event()
        self._lock = threading.Lock()
        self._app_id_registered = False

        if not TOASTED_AVAILABLE:
            logger.warning("toasted not available, notifications will be logged only")
            return

        logger.info("ToastedWindowsNotifier initialized (app_id=%s)", WINDOWS_APP_USER_MODEL_ID)
        # Eagerly start worker thread to avoid first-notification delay
        self._ensure_worker()

    # -- worker thread management ------------------------------------------

    def _ensure_worker(self) -> bool:
        """Start the persistent worker thread if not already running."""
        if not TOASTED_AVAILABLE:
            return False

        with self._lock:
            if self._worker_thread is not None and self._worker_thread.is_alive():
                return True

            self._worker_ready.clear()
            self._worker_thread = threading.Thread(
                target=self._worker_run, name="ToastedNotifierWorker", daemon=True
            )
            self._worker_thread.start()

        if not self._worker_ready.wait(timeout=5):
            logger.error("Toasted worker thread failed to start within timeout")
            return False

        return self._worker_loop is not None

    def _worker_run(self) -> None:
        """Run the persistent worker thread with its own event loop."""
        try:
            self._worker_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._worker_loop)

            # Register the AUMID in the Windows registry (one-time, idempotent)
            if not self._app_id_registered and _Toast is not None:
                try:
                    if not _Toast.is_registered_app_id(WINDOWS_APP_USER_MODEL_ID):
                        _Toast.register_app_id(
                            handle=WINDOWS_APP_USER_MODEL_ID,
                            display_name=self.app_name,
                            show_in_settings=True,
                        )
                    self._app_id_registered = True
                    logger.debug("Registered toasted app ID: %s", WINDOWS_APP_USER_MODEL_ID)
                except Exception as e:
                    logger.warning("Failed to register toasted app ID: %s", e)

            self._worker_ready.set()
            self._worker_loop.run_forever()
        except Exception as e:
            logger.error("Toasted worker thread failed: %s", e)
            self._worker_loop = None
            self._worker_ready.set()  # unblock waiters

    # -- sending ------------------------------------------------------------

    def _send_in_worker(self, title: str, message: str, timeout: int = 10) -> bool:
        """Send a notification via the persistent worker thread."""
        worker_ok = self._ensure_worker()
        logger.debug(
            "[toasted] _send_in_worker: ensure_worker=%s, loop_alive=%s, thread_alive=%s",
            worker_ok,
            self._worker_loop is not None and self._worker_loop.is_running(),
            self._worker_thread is not None and self._worker_thread.is_alive(),
        )
        if not worker_ok:
            logger.warning("[toasted] _send_in_worker: worker thread not ready, toast skipped")
            return False

        loop = self._worker_loop
        if loop is None:
            logger.warning("[toasted] _send_in_worker: loop is None — aborting")
            return False

        async def _show_toast() -> bool:
            toast = _Toast(  # type: ignore[misc]
                app_id=WINDOWS_APP_USER_MODEL_ID,
                sound=None,  # we handle sounds ourselves
            )
            toast.elements = [_Text(title), _Text(message)]  # type: ignore[misc]
            # Fire-and-forget: schedule show and return immediately
            asyncio.create_task(toast.show(mute_sound=True))
            return True

        # Fire and forget — don't block waiting for WinRT confirmation
        logger.debug("[toasted] Submitting toast to worker loop (fire-and-forget): title=%r", title)
        asyncio.run_coroutine_threadsafe(_show_toast(), loop)
        return True

    def send_notification(
        self,
        title: str,
        message: str,
        timeout: int = 10,
        *,
        sound_event: str | None = None,
        sound_candidates: list[str] | None = None,
        play_sound: bool = True,
    ) -> bool:
        """Send a notification synchronously (same interface as SafeDesktopNotifier)."""
        logger.debug(
            "[toasted] send_notification called: title=%r, "
            "play_sound=%s, sound_enabled=%s, toasted_available=%s, "
            "thread=%s",
            title,
            play_sound,
            self.sound_enabled,
            TOASTED_AVAILABLE,
            threading.current_thread().name,
        )

        if not TOASTED_AVAILABLE:
            logger.warning(
                "[toasted] toasted NOT available — toast skipped, sound_only=%s: %r",
                play_sound,
                title,
            )
            if self.sound_enabled and play_sound:
                self._play_sound(sound_event, sound_candidates)
            return True

        try:
            # Fire sound immediately in a thread — don't block on toast future
            if self.sound_enabled and play_sound:
                threading.Thread(
                    target=self._play_sound,
                    args=(sound_event, sound_candidates),
                    daemon=True,
                ).start()
                logger.debug("[toasted] Sound thread started")

            success = self._send_in_worker(title, message, timeout)
            if not success:
                logger.warning(
                    "[toasted] _send_in_worker returned False — toast NOT shown: %r", title
                )
                # Fallback to tray balloon when available
                if self.balloon_fn is not None:
                    try:
                        self.balloon_fn(title, message)
                        logger.debug("[toasted] Tray balloon fallback used for: %r", title)
                    except Exception as bf_exc:
                        logger.debug("[toasted] Tray balloon fallback failed: %s", bf_exc)
            else:
                logger.debug("[toasted] Toast dispatched successfully: %r", title)

            return success
        except Exception as e:
            logger.warning("[toasted] send_notification raised %s: %s", type(e).__name__, e)
            logger.info("[toasted] Notification (fallback): %s - %s", title, message)
            return False

    def _play_sound(self, sound_event: str | None, sound_candidates: list[str] | None) -> None:
        """Play a notification sound."""
        try:
            if sound_candidates:
                play_notification_sound_candidates(sound_candidates, self.soundpack)
            else:
                play_notification_sound(sound_event or "alert", self.soundpack)
        except Exception as e:
            logger.debug("Sound playback failed: %s", e)


# ---------------------------------------------------------------------------
# SafeDesktopNotifier — Mac/Linux backend using desktop-notifier
# ---------------------------------------------------------------------------


class _DesktopNotifierBackend:
    """
    Cross-platform notification backend using the desktop-notifier package.

    Uses a single persistent background thread with its own event loop and
    DesktopNotifier instance to avoid COM threading issues on Windows.
    The notifier is created once in the worker thread and reused for all
    subsequent notifications.
    """

    def __init__(
        self,
        app_name: str = "AccessiWeather",
        sound_enabled: bool = True,
        soundpack: str | None = None,
    ):
        self.app_name = app_name
        _log_packaging_notifier_diagnostics()

        # Sound configuration
        self.sound_enabled: bool = bool(sound_enabled)
        self.soundpack: str = soundpack or "default"

        # Optional fallback callable: balloon_fn(title, message) is called when the
        # WinRT/desktop-notifier toast fails (e.g. window hidden in system tray).
        # Set this after init — typically wired to tray_icon.ShowBalloon().
        self.balloon_fn = None  # Optional[Callable[[str, str], None]] — set after init

        # Persistent worker thread state
        self._worker_loop: asyncio.AbstractEventLoop | None = None
        self._worker_thread: threading.Thread | None = None
        self._worker_notifier: DesktopNotifier | None = None  # lives in worker thread
        self._worker_ready = threading.Event()
        self._lock = threading.Lock()

        if not DESKTOP_NOTIFIER_AVAILABLE:
            logger.warning("Desktop notifier not available, notifications will be logged only")
            return

        logger.info("SafeDesktopNotifier initialized")
        # Eagerly start worker thread to avoid first-notification delay
        self._ensure_worker()

    def _ensure_worker(self) -> bool:
        """Start the persistent worker thread if not already running."""
        if not DESKTOP_NOTIFIER_AVAILABLE:
            return False

        with self._lock:
            if self._worker_thread is not None and self._worker_thread.is_alive():
                return True

            self._worker_ready.clear()
            self._worker_thread = threading.Thread(
                target=self._worker_run, name="DesktopNotifierWorker", daemon=True
            )
            self._worker_thread.start()

        # Wait for worker to be ready (notifier created, loop running)
        if not self._worker_ready.wait(timeout=5):
            logger.error("Worker thread failed to start within timeout")
            return False

        return self._worker_loop is not None

    def _worker_run(self) -> None:
        """Run the persistent worker thread with its own event loop."""
        try:
            self._worker_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._worker_loop)

            # Create the notifier once in this thread (proper COM init on Windows)
            if sys.platform == "win32":
                try:
                    self._worker_notifier = DesktopNotifier(
                        app_name=self.app_name,
                        app_id=WINDOWS_APP_USER_MODEL_ID,
                    )
                except TypeError:
                    self._worker_notifier = DesktopNotifier(app_name=self.app_name)
            else:
                self._worker_notifier = DesktopNotifier(app_name=self.app_name)
            logger.debug("Desktop notifier created in worker thread")

            self._worker_ready.set()

            # Keep the loop running so the notifier stays alive
            self._worker_loop.run_forever()
        except Exception as e:
            logger.error("Worker thread failed: %s", e)
            self._worker_loop = None
            self._worker_notifier = None
            self._worker_ready.set()  # unblock waiters

    def _send_in_worker(self, title: str, message: str, timeout: int = 10) -> bool:
        """Send a notification via the persistent worker thread."""
        worker_ok = self._ensure_worker()
        logger.debug(
            "[toast] _send_in_worker: ensure_worker=%s, "
            "loop_alive=%s, thread_alive=%s, notifier_ready=%s",
            worker_ok,
            self._worker_loop is not None and self._worker_loop.is_running(),
            self._worker_thread is not None and self._worker_thread.is_alive(),
            self._worker_notifier is not None,
        )
        if not worker_ok:
            logger.warning("[toast] _send_in_worker: worker thread not ready, toast skipped")
            return False

        loop = self._worker_loop
        notifier = self._worker_notifier
        if loop is None or notifier is None:
            logger.warning(
                "[toast] _send_in_worker: loop=%s, notifier=%s — aborting",
                loop is not None,
                notifier is not None,
            )
            return False

        # Fire and forget — don't block waiting for desktop-notifier to complete
        logger.debug("[toast] Submitting toast to worker loop (fire-and-forget): title=%r", title)
        asyncio.run_coroutine_threadsafe(
            notifier.send(title=title, message=message, timeout=timeout),
            loop,
        )
        return True

    def send_notification(
        self,
        title: str,
        message: str,
        timeout: int = 10,
        *,
        sound_event: str | None = None,
        sound_candidates: list[str] | None = None,
        play_sound: bool = True,
    ) -> bool:
        """Send a notification synchronously."""
        logger.debug(
            "[toast] send_notification called: title=%r, "
            "play_sound=%s, sound_enabled=%s, "
            "desktop_notifier_available=%s, "
            "thread=%s",
            title,
            play_sound,
            self.sound_enabled,
            DESKTOP_NOTIFIER_AVAILABLE,
            threading.current_thread().name,
        )

        if not DESKTOP_NOTIFIER_AVAILABLE:
            logger.warning(
                "[toast] desktop-notifier NOT available — toast skipped, sound_only=%s: %r",
                play_sound,
                title,
            )
            # Still play sound if configured and requested, as a basic cue
            if self.sound_enabled and play_sound:
                self._play_sound(sound_event, sound_candidates)
            return True

        try:
            # Fire sound immediately in a thread — don't block on toast future
            if self.sound_enabled and play_sound:
                threading.Thread(
                    target=self._play_sound,
                    args=(sound_event, sound_candidates),
                    daemon=True,
                ).start()
                logger.debug("[toast] Sound thread started")

            logger.debug("[toast] Calling _send_in_worker for: %r", title)
            success = self._send_in_worker(title, message, timeout)
            if not success:
                logger.warning(
                    "[toast] _send_in_worker returned False — toast NOT shown: %r", title
                )
                # Fallback to tray balloon when available (e.g. window hidden in system tray)
                if self.balloon_fn is not None:
                    try:
                        self.balloon_fn(title, message)
                        logger.debug("[toast] Tray balloon fallback used for: %r", title)
                    except Exception as bf_exc:
                        logger.debug("[toast] Tray balloon fallback failed: %s", bf_exc)
            else:
                logger.debug("[toast] Toast dispatched successfully: %r", title)

            return success
        except Exception as e:
            logger.warning("[toast] send_notification raised %s: %s", type(e).__name__, e)
            logger.info("[toast] Notification (fallback): %s - %s", title, message)
            return False

    def _play_sound(self, sound_event: str | None, sound_candidates: list[str] | None) -> None:
        """Play a notification sound."""
        try:
            if sound_candidates:
                play_notification_sound_candidates(sound_candidates, self.soundpack)
            else:
                play_notification_sound(sound_event or "alert", self.soundpack)
        except Exception as e:
            logger.debug("Sound playback failed: %s", e)


# ---------------------------------------------------------------------------
# Platform selection: export SafeDesktopNotifier as the right backend
# ---------------------------------------------------------------------------

if sys.platform == "win32" and TOASTED_AVAILABLE:
    SafeDesktopNotifier = ToastedWindowsNotifier
    logger.info("Using toasted backend for Windows notifications")
else:
    SafeDesktopNotifier = _DesktopNotifierBackend  # type: ignore[assignment,misc]


# ---------------------------------------------------------------------------
# SafeToastNotifier — higher-level wrapper (legacy interface)
# ---------------------------------------------------------------------------


class SafeToastNotifier:
    """
    A wrapper around the notification system that handles exceptions.

    Provides cross-platform notification support.  Automatically picks the
    best available backend (toasted on Windows, desktop-notifier elsewhere).
    """

    def __init__(self, sound_enabled: bool = True, soundpack: str | None = None):
        """Initialize the notification wrapper."""
        self.sound_enabled: bool = bool(sound_enabled)
        self.soundpack: str = soundpack if soundpack is not None else "default"
        # Initialize underlying notifier with sound preferences
        if NOTIFIER_AVAILABLE:
            self._desktop_notifier = SafeDesktopNotifier(
                app_name="AccessiWeather",
                sound_enabled=self.sound_enabled,
                soundpack=self.soundpack,
            )
        else:
            self._desktop_notifier = None

    def _safe_send_notification(self, title: str, message: str, timeout: int) -> bool:
        m = (
            getattr(self._desktop_notifier, "send_notification", None)
            if self._desktop_notifier is not None
            else None
        )
        if m is not None and callable(m):
            return bool(m(title, message, timeout))
        logger.info("Notification (desktop notifier unavailable): %s - %s", title, message)
        return True

    def show_toast(self, **kwargs) -> bool:
        """Show a toast notification."""
        try:
            # If we're running tests, just log the notification
            if "pytest" in sys.modules:
                title = kwargs.get("title", "")
                msg = kwargs.get("msg", "")
                logger.info("Toast notification: %s - %s", title, msg)
                return True

            # Map parameters to desktop-notifier format
            title = kwargs.get("title", "Notification")
            message = kwargs.get("msg", "")
            timeout = kwargs.get("duration", 10)
            alert_type = kwargs.get("alert_type", "notification")
            kwargs.get("severity")

            success = self._safe_send_notification(title, message, timeout)

            # Play sound if enabled
            if self.sound_enabled:
                try:
                    sound_event = (
                        "alert" if str(alert_type).lower() in ("urgent", "alert") else "notify"
                    )
                    play_notification_sound(sound_event, self.soundpack)
                except Exception as e:
                    logger.error("Failed to play notification sound: %s", e)

            return success
        except Exception as e:
            logger.warning("Failed to show toast notification: %s", e)
            logger.info(
                "Toast notification would show: %s - %s", kwargs.get("title"), kwargs.get("msg")
            )
            return False
