"""Windows toasted notification backend."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import threading
from collections.abc import Callable
from concurrent.futures import Future
from typing import Any
from xml.sax.saxutils import escape as _xml_escape

from ..constants import WINDOWS_APP_USER_MODEL_ID
from ..sound_events import DEFAULT_MUTED_SOUND_EVENTS
from . import toast_notifier as _state
from .sound_player import normalize_muted_sound_events

logger = logging.getLogger(__name__)


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
        muted_sound_events: list[str] | None = None,
    ):
        """Initialize the Windows toasted notification backend."""
        self.app_name = app_name
        _state._log_packaging_notifier_diagnostics()

        # Sound configuration
        self.sound_enabled: bool = bool(sound_enabled)
        self.soundpack: str = soundpack or "default"
        initial_muted_events = (
            DEFAULT_MUTED_SOUND_EVENTS if muted_sound_events is None else muted_sound_events
        )
        self.muted_sound_events: list[str] = normalize_muted_sound_events(initial_muted_events)

        # Persistent worker thread state
        self._worker_loop: asyncio.AbstractEventLoop | None = None
        self._worker_thread: threading.Thread | None = None
        self._worker_ready = threading.Event()
        self._lock = threading.Lock()
        self._app_id_registered = False
        self._pending_tasks: set[asyncio.Task] = set()
        self._submitted_futures: set[Future[bool]] = set()
        # Callback invoked (from worker thread) when user clicks a toast.
        # Signature: on_activation(result) where result.arguments contains
        # the serialized activation request string.
        self.on_activation: Callable[[Any], None] | None = None
        # Keep WinRT ToastNotification objects alive so their activated
        # handlers persist for Action Center clicks (the toasted library's
        # show() deregisters handlers after popup dismissal).
        self._live_notifications: list[Any] = []
        self._MAX_LIVE_NOTIFICATIONS = 20

        if not _state.TOASTED_AVAILABLE:
            logger.warning("toasted not available, notifications will be logged only")
            return

        logger.info("ToastedWindowsNotifier initialized (app_id=%s)", WINDOWS_APP_USER_MODEL_ID)
        # Eagerly start worker thread to avoid first-notification delay
        self._ensure_worker()

    # -- worker thread management ------------------------------------------

    def _start_watchdog(self, interval: int = 30) -> None:
        """Start a periodic watchdog timer that restarts the worker if it dies."""
        if not _state.TOASTED_AVAILABLE:
            return
        self._watchdog_timer: threading.Timer | None = None
        self._watchdog_interval = interval
        self._schedule_watchdog()

    def _schedule_watchdog(self) -> None:
        """Schedule the next watchdog check."""
        t = threading.Timer(self._watchdog_interval, self._watchdog_check)
        t.daemon = True
        t.start()
        self._watchdog_timer = t

    def _watchdog_check(self) -> None:
        """Check if the worker thread is alive; restart it if not."""
        thread = self._worker_thread
        if thread is not None and not thread.is_alive():
            logger.warning("[toasted] Worker thread died — restarting")
            with self._lock:
                self._worker_thread = None
                self._worker_loop = None
            ok = self._ensure_worker()
            if ok:
                logger.info("[toasted] Worker thread restarted successfully")
            else:
                logger.error("[toasted] Worker thread restart failed")
        else:
            logger.debug("[toasted] Watchdog: worker thread alive")
        self._schedule_watchdog()

    def _ensure_worker(self) -> bool:
        """Start the persistent worker thread if not already running."""
        if not _state.TOASTED_AVAILABLE:
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
            if not self._app_id_registered and _state._Toast is not None:
                try:
                    if not _state._Toast.is_registered_app_id(WINDOWS_APP_USER_MODEL_ID):
                        _state._Toast.register_app_id(
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
        finally:
            loop = self._worker_loop
            if loop is not None and not loop.is_closed():
                loop.close()

    def close(self, timeout: float = 2.0) -> None:
        """Stop the worker loop and release pending notification tasks."""
        timer = getattr(self, "_watchdog_timer", None)
        if timer is not None:
            timer.cancel()

        loop = self._worker_loop
        if loop is not None and loop.is_running():
            if self._submitted_futures and threading.current_thread() is not self._worker_thread:
                futures = list(self._submitted_futures)
                for future in futures:
                    if future.done():
                        continue
                    with contextlib.suppress(Exception):
                        future.result(timeout=timeout)
                    if not future.done():
                        future.cancel()

            if self._pending_tasks:

                async def _cancel_pending_tasks() -> None:
                    tasks = list(self._pending_tasks)
                    for task in tasks:
                        if not task.done():
                            task.cancel()
                    if tasks:
                        await asyncio.gather(*tasks, return_exceptions=True)

                future = asyncio.run_coroutine_threadsafe(_cancel_pending_tasks(), loop)
                with contextlib.suppress(Exception):
                    future.result(timeout=timeout)
            loop.call_soon_threadsafe(loop.stop)

        thread = self._worker_thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=timeout)
        self._worker_thread = None
        self._worker_loop = None
        self._submitted_futures.clear()
        self._pending_tasks.clear()

    # -- sending ------------------------------------------------------------

    def _set_activation_arguments(self, toast, activation_arguments: str | None) -> None:
        """Attach launch arguments to the toast when the backend supports it."""
        if not activation_arguments:
            return
        escaped_arguments = _state._escape_xml_attribute(activation_arguments)
        for attr in ("arguments", "launch"):
            with contextlib.suppress(Exception):
                setattr(toast, attr, escaped_arguments)
        if _state._uses_protocol_activation(activation_arguments):
            for attr in ("activation_type", "activationType"):
                with contextlib.suppress(Exception):
                    setattr(toast, attr, "protocol")

    def _send_in_worker(
        self,
        title: str,
        message: str,
        timeout: int = 10,
        *,
        activation_arguments: str | None = None,
    ) -> bool:
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
            toast = _state._Toast(  # type: ignore[misc]
                app_id=WINDOWS_APP_USER_MODEL_ID,
                sound=None,  # we handle sounds ourselves
            )
            # The toasted library does not XML-escape text content, so
            # characters like & < > in alert descriptions would produce
            # invalid XML and a silent 0xc00ce50d error from WinRT.
            toast.elements = [_state._Text(_xml_escape(title)), _state._Text(_xml_escape(message))]  # type: ignore[misc]
            self._set_activation_arguments(toast, activation_arguments)

            # Bypass toasted's show() which deregisters WinRT event handlers
            # after popup dismissal, breaking Action Center click activation.
            # Instead, use WinRT directly so our activated handler persists.
            if _state.WINRT_AVAILABLE and self._show_toast_direct(toast, activation_arguments):
                return True

            # Fallback: use toasted's show() (Action Center clicks won't work
            # after popup dismissal, but popup-click still works).
            logger.debug("[toasted] Falling back to toasted.show()")
            if activation_arguments and self.on_activation is not None:
                on_activation = self.on_activation

                @toast.on_result
                def _on_result(result):
                    if not getattr(result, "is_dismissed", False):
                        on_activation(result)

            task = asyncio.create_task(toast.show(mute_sound=True))
            self._pending_tasks.add(task)
            task.add_done_callback(self._pending_tasks.discard)
            return True

        # Fire and forget — don't block waiting for WinRT confirmation
        logger.debug("[toasted] Submitting toast to worker loop (fire-and-forget): title=%r", title)
        future = asyncio.run_coroutine_threadsafe(_show_toast(), loop)
        self._submitted_futures.add(future)
        future.add_done_callback(self._submitted_futures.discard)
        return True

    def _show_toast_direct(self, toast, activation_arguments: str | None) -> bool:
        """
        Show a toast via WinRT directly, keeping the activated handler alive.

        The toasted library's ``show()`` awaits ``asyncio.wait(futures,
        return_when=FIRST_COMPLETED)`` then **deregisters all WinRT event
        handlers** — including the ``activated`` handler.  When the popup
        times out and moves to Action Center, ``dismissed`` fires first,
        so the ``activated`` token is removed.  Later Action Center clicks
        find no handler and silently do nothing.

        By creating and showing the ``ToastNotification`` ourselves we keep
        the ``activated`` handler registered for the lifetime of the object
        reference in ``_live_notifications``.
        """
        if not _state.WINRT_AVAILABLE:
            return False

        try:
            # Generate XML from the toasted Toast object
            xml_string = toast.to_xml_string()
            xml_string = _state._apply_protocol_activation_to_xml(xml_string, activation_arguments)

            xml_doc = _state._WinRT_XmlDocument()
            xml_doc.load_xml(xml_string)
            notification = _state._WinRT_ToastNotification(xml_doc)

            # Register persistent activated handler
            if (
                activation_arguments
                and self.on_activation is not None
                and not _state._uses_protocol_activation(activation_arguments)
            ):
                on_activation = self.on_activation

                def _on_activated(sender, args):
                    try:
                        event_args = _state._WinRT_ToastActivatedEventArgs._from(args)
                        # Build a result-like object matching what _on_result expects
                        result = _state._ActivationResult(arguments=event_args.arguments)
                        on_activation(result)
                    except Exception:
                        logger.debug("[toasted] Activation handler error", exc_info=True)

                notification.add_activated(_on_activated)

            # Show via WinRT ToastNotificationManager
            notifier = _state._WinRT_ToastNotificationManager.create_toast_notifier(
                WINDOWS_APP_USER_MODEL_ID
            )
            notifier.show(notification)

            # Keep the notification object alive so the activated handler
            # persists for Action Center clicks.  Trim old entries to
            # prevent unbounded growth.
            self._live_notifications.append(notification)
            if len(self._live_notifications) > self._MAX_LIVE_NOTIFICATIONS:
                self._live_notifications = self._live_notifications[-self._MAX_LIVE_NOTIFICATIONS :]

            logger.debug(
                "[toasted] Toast shown via direct WinRT (persistent activation): live_count=%d",
                len(self._live_notifications),
            )
            return True
        except Exception:
            logger.warning("[toasted] Direct WinRT show failed", exc_info=True)
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
        activation_arguments: str | None = None,
    ) -> bool:
        """Send a notification synchronously (same interface as SafeDesktopNotifier)."""
        logger.debug(
            "[toasted] send_notification called: title=%r, "
            "play_sound=%s, sound_enabled=%s, toasted_available=%s, "
            "thread=%s",
            title,
            play_sound,
            self.sound_enabled,
            _state.TOASTED_AVAILABLE,
            threading.current_thread().name,
        )

        if not _state.TOASTED_AVAILABLE:
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

            success = self._send_in_worker(
                title,
                message,
                timeout,
                activation_arguments=activation_arguments,
            )
            if not success:
                logger.warning(
                    "[toasted] _send_in_worker returned False — toast NOT shown: %r", title
                )
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
            effective_event = sound_event or (sound_candidates[0] if sound_candidates else None)
            if sound_candidates:
                _state.play_notification_sound_candidates(
                    sound_candidates,
                    self.soundpack,
                    logical_event=effective_event,
                    muted_events=self.muted_sound_events,
                )
            else:
                _state.play_notification_sound(
                    sound_event or "alert",
                    self.soundpack,
                    muted_events=self.muted_sound_events,
                )
        except Exception as e:
            logger.debug("Sound playback failed: %s", e)
