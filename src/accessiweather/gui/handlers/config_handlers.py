"""Configuration handlers for the WeatherApp class

This module contains the configuration-related handlers for the WeatherApp class.
"""

import json
import logging
import os
import time

import wx

from .common import WeatherAppHandlerBase

logger = logging.getLogger(__name__)


class WeatherAppConfigHandlers(WeatherAppHandlerBase):
    """Configuration handlers for the WeatherApp class

    This class is meant to be inherited by WeatherApp, not used directly.
    It provides configuration-related event handlers for the WeatherApp class.
    """

    def _save_config(self, show_errors=True):
        """Save configuration to file

        Args:
            show_errors: Whether to show error message boxes (default: True)

        Returns:
            bool: True if save was successful, False otherwise
        """
        start_time = time.time()
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self._config_path), exist_ok=True)

            # Save config
            with open(self._config_path, "w") as f:
                json.dump(self.config, f, indent=2)

            elapsed = time.time() - start_time
            logger.debug(f"[EXIT OPTIMIZATION] Configuration saved in {elapsed:.3f}s")
            return True
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(
                f"[EXIT OPTIMIZATION] Failed to save config after {elapsed:.3f}s: {str(e)}"
            )
            if show_errors:
                wx.MessageBox(
                    f"Failed to save configuration: {str(e)}",
                    "Configuration Error",
                    wx.OK | wx.ICON_ERROR,
                )
            return False

    def _save_config_async(self):
        """Save configuration in a separate thread to avoid blocking the UI

        Returns:
            thread: The started thread object, which can be joined if needed
        """
        import threading

        logger.debug("[EXIT OPTIMIZATION] Starting async config save thread")
        # Create a unique thread name with timestamp for easier tracking
        thread_name = f"ConfigSaveThread-{int(time.time())}"
        thread = threading.Thread(target=self._save_config_thread, daemon=True, name=thread_name)
        thread.start()

        # Register with thread manager for proper cleanup
        from accessiweather.utils.thread_manager import register_thread

        stop_event = threading.Event()
        register_thread(thread, stop_event, name=thread_name)
        return thread

    def _save_config_thread(self):
        """Thread function to save configuration without blocking the UI
        This is called by _save_config_async.
        """
        import threading

        thread_id = threading.get_ident()
        thread_name = threading.current_thread().name

        try:
            start_time = time.time()
            logger.debug(f"[EXIT OPTIMIZATION] Config save thread {thread_name} started")

            # Quick check if we should abort (app might be closing)
            from accessiweather.utils.thread_manager import get_thread_manager

            manager = get_thread_manager()
            thread_info = next(
                (
                    t
                    for t in manager._threads.values()
                    if t.get("thread") == threading.current_thread()
                ),
                None,
            )

            if (
                thread_info
                and hasattr(thread_info.get("stop_event", None), "is_set")
                and thread_info.get("stop_event").is_set()
            ):
                logger.debug(
                    f"[EXIT OPTIMIZATION] Config save thread {thread_name} aborting due to stop event"
                )
                return

            # Do the actual config save
            success = self._save_config(show_errors=False)
            elapsed = time.time() - start_time

            if success:
                logger.debug(f"[EXIT OPTIMIZATION] Async config save completed in {elapsed:.3f}s")
            else:
                logger.error(f"[EXIT OPTIMIZATION] Async config save failed after {elapsed:.3f}s")
        except Exception as e:
            logger.error(
                f"[EXIT OPTIMIZATION] Unexpected error in config save thread: {e}", exc_info=True
            )
        finally:
            # Always unregister thread when done for proper cleanup
            try:
                from accessiweather.utils.thread_manager import unregister_thread

                logger.debug(f"[EXIT OPTIMIZATION] Unregistering config save thread {thread_name}")
                unregister_thread(thread_id)
            except Exception as e:
                logger.warning(f"[EXIT OPTIMIZATION] Error unregistering config thread: {e}")
