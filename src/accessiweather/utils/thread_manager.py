"""Thread manager for AccessiWeather.

This module provides a thread manager that helps track and manage threads
in the application.
"""

import logging
import threading
import time
import weakref

logger = logging.getLogger(__name__)


class ThreadManager:
    """Thread manager for AccessiWeather.
    
    This class provides methods for tracking and managing threads in the
    application, making it easier to ensure all threads are properly
    cleaned up when the application exits.
    """
    
    def __init__(self):
        """Initialize the thread manager."""
        self._threads = {}
        self._stop_events = {}
        self._lock = threading.RLock()
        logger.debug(f"ThreadManager {id(self)} initialized.")

    def register_thread(self, thread, stop_event=None, name=None):
        """Register a thread with the manager.
        
        Args:
            thread: The thread to register
            stop_event: An event that can be set to stop the thread (optional)
            name: A name for the thread (optional)
            
        Returns:
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
            self._threads[thread_id] = {'thread': thread, 'name': thread_name}
            
            # Store the stop event if provided
            if stop_event is not None:
                self._stop_events[thread_id] = stop_event
                
            logger.debug(f"Registered thread: {thread_name} (id: {thread_id})")
            
        return thread
        
    def unregister_thread(self, thread_id):
        """Unregister a thread using its ID.

        Args:
            thread_id: The identifier of the thread to unregister.
        """
        with self._lock:
            # Check if thread exists before trying to delete
            if thread_id in self._threads:
                thread_name = self._threads[thread_id].get('name', f'Thread-{thread_id}')
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
                logger.debug(f"No stop event found for thread ID: {thread_id} during unregistration (this might be normal).")

    def get_threads(self):
        """Get all registered threads.
        
        Returns:
            List of registered threads
        """
        with self._lock:
            return [thread['thread'] for thread in self._threads.values()]
            
    def get_stop_events(self):
        """Get all registered stop events.
        
        Returns:
            List of registered stop events
        """
        with self._lock:
            return list(self._stop_events.values())
            
    def stop_all_threads(self, timeout=0.5):
        """Signal all registered threads to stop and attempt to join them."""
        remaining_threads = []
        with self._lock:
            if not self._threads:
                logger.debug("stop_all_threads called, but no threads are registered.")
                return []
            
            logger.info(f"Stopping {len(self._threads)} registered threads...")
            thread_ids = list(self._threads.keys()) # Copy keys to avoid runtime error
            
            # First, signal all threads to stop
            for thread_id in thread_ids:
                if thread_id in self._stop_events:
                    logger.debug(f"Signaling thread {thread_id} ({self._threads.get(thread_id, {}).get('name', 'Unknown')}) to stop.")
                    self._stop_events[thread_id].set()
                else:
                    logger.warning(f"Stop event not found for thread {thread_id}. Cannot signal stop.")

            # Then, attempt to join all threads
            start_time = time.time()
            for thread_id in thread_ids:
                thread_info = self._threads.get(thread_id)
                if thread_info:
                    thread_obj = thread_info['thread']
                    thread_name = thread_info.get('name', f'Thread-{thread_id}')
                    if thread_obj.is_alive():
                        adjusted_timeout = max(0, timeout - (time.time() - start_time))
                        logger.debug(f"Attempting to join thread {thread_name} (ID: {thread_id}) with timeout {adjusted_timeout:.2f}s.")
                        thread_obj.join(adjusted_timeout)
                        if thread_obj.is_alive():
                            logger.warning(f"Thread {thread_name} (ID: {thread_id}) did not join within the timeout.")
                            remaining_threads.append(thread_name)
                        else:
                            logger.debug(f"Thread {thread_name} (ID: {thread_id}) joined successfully.")
                    else:
                        logger.debug(f"Thread {thread_name} (ID: {thread_id}) was already stopped.")
            
            # Clean up references for joined threads (or threads that weren't alive)
            # We do this separately to avoid modifying the dictionary while iterating
            successfully_stopped_ids = [tid for tid in thread_ids if tid not in [t.get('thread').ident for t in self._threads.values() if t.get('thread').is_alive()] ]
            for thread_id in successfully_stopped_ids:
                 if thread_id in self._threads: # Check if still present
                    logger.debug(f"Removing references for stopped thread {thread_id}.")
                    del self._threads[thread_id]
                    if thread_id in self._stop_events:
                        del self._stop_events[thread_id]

        if remaining_threads:
            logger.warning(f"stop_all_threads finished. {len(remaining_threads)} threads did not stop cleanly: {remaining_threads}")
        else:
            logger.info("stop_all_threads finished. All registered threads stopped.")
        return remaining_threads

    def get_active_threads(self):
        """Get all active threads.
        
        Returns:
            List of active threads
        """
        with self._lock:
            return [thread['thread'] for thread in self._threads.values() if thread['thread'].is_alive()]
            
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


# Global thread manager instance
_thread_manager = ThreadManager()


def get_thread_manager():
    """Get the global thread manager instance.
    
    Returns:
        The global thread manager instance
    """
    return _thread_manager


def register_thread(thread, stop_event=None, name=None):
    """Register a thread with the global thread manager.
    
    Args:
        thread: The thread to register
        stop_event: An event that can be set to stop the thread (optional)
        name: A name for the thread (optional)
        
    Returns:
        The registered thread
    """
    return _thread_manager.register_thread(thread, stop_event, name)


def unregister_thread(thread_id):
    """Unregister a thread from the global thread manager.
    
    Args:
        thread_id: The identifier of the thread to unregister.
    """
    return _thread_manager.unregister_thread(thread_id)


def stop_all_threads(timeout=0.5):
    """Stop all registered threads.
    
    Args:
        timeout: Timeout for joining threads in seconds
        
    Returns:
        List of threads that could not be joined
    """
    return _thread_manager.stop_all_threads(timeout)
