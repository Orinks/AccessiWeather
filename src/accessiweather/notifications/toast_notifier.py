"""
Toast notification module for AccessiWeather.

This module provides cross-platform toast notification functionality
with safe error handling for test environments.
"""

import asyncio
import logging
import sys
import threading

from .sound_player import play_notification_sound, play_notification_sound_candidates

logger = logging.getLogger(__name__)

try:
    from desktop_notifier import DesktopNotifier

    DESKTOP_NOTIFIER_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Desktop notifier not available: {e}")
    DesktopNotifier = None
    DESKTOP_NOTIFIER_AVAILABLE = False


class SafeDesktopNotifier:
    """
    A wrapper around desktop-notifier that provides synchronous interface.

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
        """Initialize the desktop notifier wrapper."""
        self.app_name = app_name

        # Sound configuration
        self.sound_enabled: bool = bool(sound_enabled)
        self.soundpack: str = soundpack or "default"

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
            self._worker_notifier = DesktopNotifier(app_name=self.app_name)
            logger.debug("Desktop notifier created in worker thread")

            self._worker_ready.set()

            # Keep the loop running so the notifier stays alive
            self._worker_loop.run_forever()
        except Exception as e:
            logger.error(f"Worker thread failed: {e}")
            self._worker_loop = None
            self._worker_notifier = None
            self._worker_ready.set()  # unblock waiters

    def _send_in_worker(self, title: str, message: str, timeout: int = 10) -> bool:
        """Send a notification via the persistent worker thread."""
        if not self._ensure_worker():
            return False

        loop = self._worker_loop
        notifier = self._worker_notifier
        if loop is None or notifier is None:
            return False

        future = asyncio.run_coroutine_threadsafe(
            notifier.send(title=title, message=message, timeout=timeout),
            loop,
        )

        try:
            future.result(timeout=10)
            logger.debug("Notification sent successfully via worker thread")
            return True
        except Exception as e:
            logger.error(f"Failed to send notification via worker: {e}")
            return False

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
        """
        Send a notification synchronously.

        Optionally specify a specific sound_event or a list of sound_candidates
        to determine which sound to play. candidates take precedence over event.

        Args:
            title: Notification title
            message: Notification message body
            timeout: Notification display timeout in seconds
            sound_event: Specific sound event key to play
            sound_candidates: List of sound event keys to try in order
            play_sound: Whether to play a sound (default True). Set to False
                       to send notification silently (useful when batching
                       multiple alerts to avoid overlapping sounds).

        """
        if not DESKTOP_NOTIFIER_AVAILABLE:
            logger.info(f"Notification (desktop notifier unavailable): {title} - {message}")
            # Still play sound if configured and requested, as a basic cue
            if self.sound_enabled and play_sound:
                self._play_sound(sound_event, sound_candidates)
            return True

        try:
            success = self._send_in_worker(title, message, timeout)
            if not success:
                logger.info(f"Notification (fallback): {title} - {message}")

            # Play alert sound when enabled and requested
            if self.sound_enabled and play_sound:
                self._play_sound(sound_event, sound_candidates)

            return success
        except Exception as e:
            logger.warning(f"Failed to send notification: {str(e)}")
            logger.info(f"Notification (fallback): {title} - {message}")
            return False

    def _play_sound(self, sound_event: str | None, sound_candidates: list[str] | None) -> None:
        """Play a notification sound."""
        try:
            if sound_candidates:
                play_notification_sound_candidates(sound_candidates, self.soundpack)
            else:
                play_notification_sound(sound_event or "alert", self.soundpack)
        except Exception as e:
            logger.debug(f"Sound playback failed: {e}")


class SafeToastNotifier:
    """
    A wrapper around the notification system that handles exceptions.

    Provides cross-platform notification support using desktop-notifier.
    """

    def __init__(self, sound_enabled: bool = True, soundpack: str | None = None):
        """Initialize the instance."""
        self.sound_enabled: bool = bool(sound_enabled)
        self.soundpack: str = soundpack if soundpack is not None else "default"
        # Initialize underlying desktop notifier with sound preferences as well
        if DESKTOP_NOTIFIER_AVAILABLE:
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
        logger.info(f"Notification (desktop notifier unavailable): {title} - {message}")
        return True

    def show_toast(self, **kwargs) -> bool:
        """Show a toast notification."""
        try:
            # If we're running tests, just log the notification
            if "pytest" in sys.modules:
                # For tests, just log the notification and return success
                title = kwargs.get("title", "")
                msg = kwargs.get("msg", "")
                logger.info(f"Toast notification: {title} - {msg}")
                return True

            # Map parameters to desktop-notifier format
            title = kwargs.get("title", "Notification")
            message = kwargs.get("msg", "")
            timeout = kwargs.get("duration", 10)
            alert_type = kwargs.get("alert_type", "notification")
            kwargs.get("severity")

            # Use desktop-notifier if available and callable
            success = self._safe_send_notification(title, message, timeout)

            # Play sound if enabled
            if self.sound_enabled:
                try:
                    # Map alert_type to supported sound events
                    # Use 'alert' for urgent/alert types, 'notify' for general notifications
                    sound_event = (
                        "alert" if str(alert_type).lower() in ("urgent", "alert") else "notify"
                    )
                    play_notification_sound(sound_event, self.soundpack)
                except Exception as e:
                    logger.error(f"Failed to play notification sound: {e}")

            return success
        except Exception as e:
            logger.warning(f"Failed to show toast notification: {str(e)}")
            logger.info(
                f"Toast notification would show: {kwargs.get('title')} - {kwargs.get('msg')}"
            )
            return False
