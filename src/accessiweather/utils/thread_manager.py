"""
Thread manager for AccessiWeather.

This module provides a centralized thread manager that tracks and manages
all background threads in the application.
"""

import logging
import threading
import time
from typing import Any, ClassVar, Optional

logger = logging.getLogger(__name__)


class ThreadManager:
    """
    Thread manager singleton for AccessiWeather.

    This class provides methods for tracking and managing threads in the
    application, making it easier to ensure all threads are properly
    cleaned up when the application exits.

    Attributes
    ----------
        _instance: Class variable to store the singleton instance
        _instance_lock: Class lock to ensure thread-safe singleton creation

    """

    _instance: Optional["ThreadManager"] = None
    _instance_lock: ClassVar[threading.Lock] = threading.Lock()

    @classmethod
    def instance(cls) -> "ThreadManager":
        """
        Get the singleton instance of ThreadManager.

        Returns
        -------
            The singleton ThreadManager instance

        """
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = ThreadManager()
            return cls._instance

    def __init__(self):
        """
        Initialize the thread manager.

        Note:
        ----
            This should not be called directly. Use ThreadManager.instance() instead.

        """
        self._threads: dict[int, dict[str, Any]] = {}
        self._stop_events: dict[int, threading.Event] = {}
        self._lock = threading.RLock()
        logger.debug("ThreadManager initialized")

    def register_thread(self, thread, stop_event=None, name=None):
        """
        Register a thread with the manager.

        Args:
        ----
            thread: The thread to register
            stop_event: An event that can be set to stop the thread (optional)
            name: A name for the thread (optional)

        Returns:
        -------
            The registered thread

        """
        if thread is None:
            return None

        with self._lock:
            # Use thread ident as key
            thread_id = thread.ident
            if thread_id is None:
                # Thread hasn't started yet, use object id
                thread_id = id(thread)

            # Use provided name or thread name
            thread_name = name or thread.name

            # Store the thread
            self._threads[thread_id] = {"thread": thread, "name": thread_name}

            # Store the stop event if provided
            if stop_event is not None:
                self._stop_events[thread_id] = stop_event

            logger.debug(f"Registered thread: {thread_name} (id: {thread_id})")

        return thread

    def unregister_thread(self, thread_id):
        """
        Unregister a thread using its ID.

        Args:
        ----
            thread_id: The identifier of the thread to unregister.

        """
        with self._lock:
            # Check if thread exists before trying to delete
            if thread_id in self._threads:
                thread_name = self._threads[thread_id].get("name", f"Thread-{thread_id}")
                logger.debug(f"Unregistering thread {thread_name} (ID: {thread_id}).")
                del self._threads[thread_id]
            else:
                logger.warning(f"Attempted to unregister non-existent thread ID: {thread_id}")

            # Also remove the corresponding stop event if it exists
            if thread_id in self._stop_events:
                logger.debug(f"Removing stop event for thread ID: {thread_id}")
                del self._stop_events[thread_id]
            else:
                # This might happen if the thread was registered without a stop event
                # or if it was already unregistered.
                logger.debug(
                    f"No stop event found for thread ID: {thread_id} during unregistration (this might be normal)."
                )

    def get_threads(self):
        """
        Get all registered threads.

        Returns
        -------
            List of registered threads

        """
        with self._lock:
            return [thread["thread"] for thread in self._threads.values()]

    def get_stop_events(self):
        """
        Get all registered stop events.

        Returns
        -------
            List of registered stop events

        """
        with self._lock:
            return list(self._stop_events.values())

    def stop_all_threads(self, timeout=3.0):
        """
        Signal all registered threads to stop and attempt to join them.

        Args:
        ----
            timeout (float): Maximum time in seconds to wait for all threads to join.
                Default is 3.0 seconds for a balance of responsiveness and thoroughness.

        Returns:
        -------
            list: Names of threads that did not stop cleanly within the timeout.

        """
        logger.info("Beginning thread cleanup process")
        overall_start_time = time.time()
        remaining_threads = []

        with self._lock:
            if not self._threads:
                logger.debug("stop_all_threads called, but no threads are registered.")
                return []

            thread_count = len(self._threads)
            logger.info(f"Stopping {thread_count} registered threads...")
            thread_ids = list(self._threads.keys())  # Copy keys to avoid runtime error

            # Signal phase - Set all stop events at once to maximize parallel stopping
            signal_start = time.time()
            for thread_id, event in self._stop_events.items():
                thread_info = self._threads.get(thread_id)
                thread_name = thread_info.get("name") if thread_info else f"Thread-{thread_id}"
                logger.debug(f"Signaling thread {thread_name} to stop")
                event.set()
            signal_time = time.time() - signal_start
            logger.debug(f"Signal phase completed in {signal_time:.3f}s")

            # Join phase - Try to join threads with individual timeouts
            join_start = time.time()

            # Calculate per-thread timeout based on total timeout and thread count
            # Ensure each thread gets a fair share of the total timeout
            per_thread_timeout = min(1.0, timeout / max(1, len(thread_ids)))
            logger.debug(f"Using per-thread timeout of {per_thread_timeout:.3f}s")

            # Track elapsed time to ensure we don't exceed total timeout
            elapsed: float = 0.0

            for thread_id in thread_ids:
                # Check if we're approaching the total timeout
                if elapsed >= timeout * 0.9:  # Leave 10% for cleanup
                    logger.warning(
                        f"Approaching total timeout ({elapsed:.3f}s/{timeout:.3f}s), skipping remaining threads"
                    )
                    break

                thread_info = self._threads.get(thread_id)
                if not thread_info:
                    continue

                thread_obj = thread_info["thread"]
                thread_name = thread_info.get("name", f"Thread-{thread_id}")

                if not thread_obj.is_alive():
                    logger.debug(f"Thread {thread_name} already stopped")
                    continue

                # Join attempt with timeout
                thread_join_start = time.time()
                thread_obj.join(per_thread_timeout)
                join_elapsed = time.time() - thread_join_start
                elapsed += join_elapsed

                if thread_obj.is_alive():
                    remaining_threads.append(thread_name)
                    logger.warning(
                        f"Thread {thread_name} did not stop within {per_thread_timeout:.3f}s"
                    )
                else:
                    logger.debug(f"Thread {thread_name} joined in {join_elapsed:.3f}s")

            join_time = time.time() - join_start
            logger.debug(
                f"Join phase completed in {join_time:.3f}s, {len(remaining_threads)} threads remain"
            )

            # Cleanup phase - Remove references to stopped threads
            cleanup_start = time.time()
            for thread_id in list(self._threads.keys()):
                thread_info = self._threads.get(thread_id)
                if not thread_info:
                    continue

                thread_obj = thread_info["thread"]
                if not thread_obj.is_alive():
                    # Thread has stopped, remove it
                    if thread_id in self._threads:
                        del self._threads[thread_id]
                    if thread_id in self._stop_events:
                        del self._stop_events[thread_id]
                elif thread_info.get("name") in remaining_threads:
                    # Thread is in our remaining list (we won't wait more)
                    # but keep it in the registry for potential future cleanup
                    logger.debug(
                        f"Keeping thread {thread_info.get('name')} in registry for future cleanup"
                    )

            cleanup_time = time.time() - cleanup_start
            logger.debug(f"Cleanup phase completed in {cleanup_time:.3f}s")

        # Final stats
        total_time = time.time() - overall_start_time
        if remaining_threads:
            logger.warning(
                f"stop_all_threads finished in {total_time:.3f}s. {len(remaining_threads)} threads did not stop cleanly: {remaining_threads}"
            )
        else:
            logger.info(
                f"stop_all_threads finished in {total_time:.3f}s. All threads stopped successfully."
            )

        return remaining_threads

    def is_thread_running(self, thread_id):
        """
        Check if a thread is running.

        Args:
        ----
            thread_id: The ID of the thread to check

        Returns:
        -------
            True if the thread is running, False otherwise

        """
        with self._lock:
            if thread_id in self._threads:
                thread = self._threads[thread_id]["thread"]
                return thread.is_alive()
            return False

    def get_active_threads(self):
        """
        Get a list of all active threads.

        Returns
        -------
            A list of thread objects that are currently active

        """
        active_threads = []
        with self._lock:
            for _thread_id, thread_info in self._threads.items():
                thread = thread_info["thread"]
                if thread.is_alive():
                    active_threads.append(thread)
        return active_threads

    def get_active_thread_info(self):
        """
        Get detailed information about all active threads.

        Returns
        -------
            A list of dictionaries containing thread information

        """
        active_threads = []
        with self._lock:
            for thread_id, thread_info in self._threads.items():
                thread = thread_info["thread"]
                if thread.is_alive():
                    active_threads.append(
                        {
                            "id": thread_id,
                            "name": thread_info["name"],
                            "daemon": thread.daemon,
                            "has_stop_event": thread_id in self._stop_events,
                        }
                    )
        return active_threads

    def clear(self):
        """Clear all registered threads and stop events."""
        with self._lock:
            self._threads.clear()
            self._stop_events.clear()

    def __len__(self):
        """Get the number of registered threads."""
        with self._lock:
            return len(self._threads)

    def __bool__(self):
        """Check if there are any registered threads."""
        with self._lock:
            return bool(self._threads)


# Module-level functions that use the singleton instance


def get_thread_manager():
    """
    Get the global thread manager instance.

    Returns
    -------
        The global thread manager instance

    """
    return ThreadManager.instance()


def register_thread(thread, stop_event=None, name=None):
    """
    Register a thread with the global thread manager.

    Args:
    ----
        thread: The thread to register
        stop_event: An event that can be set to stop the thread (optional)
        name: A name for the thread (optional)

    Returns:
    -------
        The registered thread

    """
    return ThreadManager.instance().register_thread(thread, stop_event, name)


def unregister_thread(thread_id):
    """
    Unregister a thread from the global thread manager.

    Args:
    ----
        thread_id: The identifier of the thread to unregister.

    """
    return ThreadManager.instance().unregister_thread(thread_id)


def stop_all_threads(timeout=3.0):
    """
    Stop all registered threads.

    Args:
    ----
        timeout: Timeout for joining threads in seconds (default: 3.0)

    Returns:
    -------
        List of threads that could not be joined

    """
    return ThreadManager.instance().stop_all_threads(timeout)
