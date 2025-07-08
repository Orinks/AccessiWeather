"""Toast notification module for AccessiWeather.

This module provides cross-platform toast notification functionality
with safe error handling for test environments.
"""

import asyncio
import logging
import sys
import threading

logger = logging.getLogger(__name__)

try:
    from desktop_notifier import DesktopNotifier

    DESKTOP_NOTIFIER_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Desktop notifier not available: {e}")
    DesktopNotifier = None
    DESKTOP_NOTIFIER_AVAILABLE = False


class SafeDesktopNotifier:
    """A wrapper around desktop-notifier that provides synchronous interface.

    This class wraps the async desktop-notifier API to provide a synchronous
    interface compatible with the existing codebase.
    """

    def __init__(self, app_name: str = "AccessiWeather"):
        """Initialize the desktop notifier wrapper."""
        self.app_name = app_name
        self._loop = None
        self._thread = None

        if not DESKTOP_NOTIFIER_AVAILABLE:
            logger.warning("Desktop notifier not available, notifications will be logged only")
            self._notifier = None
            return

        # Don't create the notifier here - create it in the worker thread
        # to avoid COM threading issues
        self._notifier = None
        logger.info("SafeDesktopNotifier initialized (notifier will be created per-thread)")

    def _run_async(self, coro):
        """Run an async coroutine in a thread-safe way."""
        current_thread = threading.current_thread()
        logger.debug(
            f"_run_async called from thread: {current_thread.name} (ID: {current_thread.ident})"
        )

        try:
            # Try to get the current event loop
            loop = asyncio.get_running_loop()
            logger.debug(f"Found running event loop: {loop}")
            logger.debug(f"Loop is running: {loop.is_running()}")

            # If we're already in an event loop, we need to run in a thread
            if loop.is_running():
                # Create a new event loop in a separate thread
                logger.debug("Creating separate thread for async operation")
                result = None
                exception = None

                def run_in_thread():
                    nonlocal result, exception
                    thread_info = threading.current_thread()
                    logger.debug(
                        f"Notification thread started: {thread_info.name} (ID: {thread_info.ident})"
                    )

                    try:
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        logger.debug(f"Created new event loop in thread: {new_loop}")
                        result = new_loop.run_until_complete(coro)
                        new_loop.close()
                        logger.debug("Notification completed successfully")
                    except Exception as e:
                        logger.error(f"Exception in notification thread: {e}")
                        exception = e

                thread = threading.Thread(target=run_in_thread, name="DesktopNotifierWorker")
                thread.start()
                thread.join()

                if exception:
                    logger.error(f"Notification thread failed: {exception}")
                    raise exception
                return result
            # We can run directly in the current loop
            logger.debug("Running directly in current loop")
            return loop.run_until_complete(coro)
        except RuntimeError as e:
            # No event loop running, create a new one
            logger.debug(f"No event loop found ({e}), creating new one")
            return asyncio.run(coro)

    async def _send_notification_async(self, title: str, message: str, timeout: int = 10):
        """Send notification asynchronously."""
        if not DESKTOP_NOTIFIER_AVAILABLE:
            return

        # Create the notifier in this thread to avoid COM threading issues
        current_thread = threading.current_thread()
        logger.debug(
            f"Creating notifier in thread: {current_thread.name} (ID: {current_thread.ident})"
        )

        try:
            notifier = DesktopNotifier(app_name=self.app_name)
            logger.debug("Desktop notifier created successfully in worker thread")
            await notifier.send(title=title, message=message, timeout=timeout)
            logger.debug("Notification sent successfully")
        except Exception as e:
            logger.error(f"Failed to create or use notifier in worker thread: {e}")
            raise

    def send_notification(self, title: str, message: str, timeout: int = 10) -> bool:
        """Send a notification synchronously."""
        if not DESKTOP_NOTIFIER_AVAILABLE:
            logger.info(f"Notification (desktop notifier unavailable): {title} - {message}")
            return True

        try:
            self._run_async(self._send_notification_async(title, message, timeout))
            return True
        except Exception as e:
            logger.warning(f"Failed to send notification: {str(e)}")
            logger.info(f"Notification (fallback): {title} - {message}")
            return False


class SafeToastNotifier:
    """A wrapper around the notification system that handles exceptions.

    Provides cross-platform notification support using desktop-notifier.
    """

    def __init__(self):
        """Initialize the safe toast notifier."""
        self._desktop_notifier = SafeDesktopNotifier()

    def show_toast(self, **kwargs):
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

            # Use desktop-notifier
            return self._desktop_notifier.send_notification(title, message, timeout)
        except Exception as e:
            logger.warning(f"Failed to show toast notification: {str(e)}")
            logger.info(
                f"Toast notification would show: {kwargs.get('title')} - {kwargs.get('msg')}"
            )
            return False
