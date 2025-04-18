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
            
    def stop_all_threads(self, timeout=0.05):
        """Signal all registered threads to stop and attempt to join them.
        
        Args:
            timeout (float): Maximum time in seconds to wait for each thread to join.
                Default reduced to 0.2 seconds for faster application exit.
                
        Returns:
            list: Names of threads that did not stop cleanly within the timeout.
        """
        logger.info("[EXIT OPTIMIZATION] Beginning thread cleanup process")
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
                thread_name = thread_info.get('name') if thread_info else f"Thread-{thread_id}"
                logger.debug(f"[EXIT OPTIMIZATION] Signaling thread {thread_name} to stop")
                event.set()
            signal_time = time.time() - signal_start
            logger.debug(f"[EXIT OPTIMIZATION] Signal phase completed in {signal_time:.3f}s")

            # Join phase - Try to join threads with individual timeouts
            join_start = time.time()
            per_thread_timeout = min(timeout, 0.2)  # Cap per-thread timeout
            
            for thread_id in thread_ids:
                thread_info = self._threads.get(thread_id)
                if not thread_info:
                    continue
                    
                thread_obj = thread_info['thread']
                thread_name = thread_info.get('name', f'Thread-{thread_id}')
                
                if not thread_obj.is_alive():
                    logger.debug(f"Thread {thread_name} already stopped")
                    continue
                    
                # Quick join attempt with timeout
                thread_join_start = time.time()
                thread_obj.join(per_thread_timeout)
                join_elapsed = time.time() - thread_join_start
                
                if thread_obj.is_alive():
                    remaining_threads.append(thread_name)
                else:
                    logger.debug(f"Thread {thread_name} joined in {join_elapsed:.3f}s")
            
            join_time = time.time() - join_start
            logger.debug(f"[EXIT OPTIMIZATION] Join phase completed in {join_time:.3f}s, {len(remaining_threads)} threads remain")
            
            # Cleanup phase - Remove references to stopped threads
            cleanup_start = time.time()
            for thread_id in list(self._threads.keys()):
                thread_info = self._threads.get(thread_id)
                if not thread_info:
                    continue
                    
                thread_obj = thread_info['thread']
                if not thread_obj.is_alive() or thread_info.get('name') in remaining_threads:
                    # Either thread stopped or it's in our remaining list (we won't wait more)
                    if thread_id in self._threads:
                        del self._threads[thread_id]
                    if thread_id in self._stop_events:
                        del self._stop_events[thread_id]
        
            cleanup_time = time.time() - cleanup_start
            logger.debug(f"[EXIT OPTIMIZATION] Cleanup phase completed in {cleanup_time:.3f}s")

        # Final stats
        total_time = time.time() - overall_start_time
        if remaining_threads:
            logger.warning(f"[EXIT OPTIMIZATION] stop_all_threads finished in {total_time:.3f}s. {len(remaining_threads)} threads did not stop cleanly: {remaining_threads}")
        else:
            logger.info(f"[EXIT OPTIMIZATION] stop_all_threads finished in {total_time:.3f}s. All threads stopped successfully.")
            
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


def stop_all_threads(timeout=0.05):
    """Stop all registered threads.
    
    Args:
        timeout: Timeout for joining threads in seconds
        
    Returns:
        List of threads that could not be joined
    """
    return _thread_manager.stop_all_threads(timeout)
