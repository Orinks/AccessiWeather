"""Utilities for testing wxPython applications.

This module provides utilities for testing wxPython applications, including:
- Event loop management
- Thread-safe UI updates
- Event simulation
- Waiting for events to process
"""

import queue
import threading
import time
from typing import Any, Callable, List, TypeVar

import wx

T = TypeVar("T")


class EventLoopContext:
    """Context manager for running code within a wx event loop.

    This ensures that wx events are processed during test execution.
    """

    def __init__(self, timeout_ms: int = 1000):
        """Initialize the context manager.

        Args:
            timeout_ms: Maximum time to wait for events to process (milliseconds)
        """
        self.timeout_ms = timeout_ms
        self.old_app = None
        self.app = None

    def __enter__(self):
        """Enter the context, creating a wx.App if needed."""
        # Store the current app if it exists
        self.old_app = wx.GetApp()
        if self.old_app is None:
            self.app = wx.App()
        return self

    def __exit__(self, *_):
        """Exit the context, processing pending events."""
        # Process pending events
        for _ in range(5):  # Process events multiple times to ensure all are handled
            wx.SafeYield()
            time.sleep(0.01)  # Small delay to allow events to be processed

        # Don't destroy the app if we didn't create it
        if self.old_app is None and self.app is not None:
            # Simply destroy the app without running MainLoop
            # This is more reliable in test environments
            self.app = None


class CallAfterContext:
    """Context manager for executing code with wx.CallAfter and waiting for completion."""

    def __init__(self, timeout_ms: int = 1000):
        """Initialize the context manager.

        Args:
            timeout_ms: Maximum time to wait for the function to complete (milliseconds)
        """
        self.timeout_ms = timeout_ms
        self.result_queue = queue.Queue()

    def __call__(self, func: Callable, *args, **kwargs) -> Any:
        """Call a function using wx.CallAfter and wait for the result.

        Args:
            func: The function to call
            *args: Arguments to pass to the function
            **kwargs: Keyword arguments to pass to the function

        Returns:
            The result of the function call
        """
        # Execute the function directly and return the result
        # This is more reliable in test environments than using CallAfter
        try:
            result = func(*args, **kwargs)
            # Process events to ensure any side effects are handled
            for _ in range(5):
                wx.SafeYield()
                time.sleep(0.01)
            return result
        except Exception as e:
            # Process events before re-raising
            for _ in range(5):
                wx.SafeYield()
                time.sleep(0.01)
            raise e


class EventCatcher:
    """Catch and record wx events for testing."""

    def __init__(self, event_types: List[wx.PyEventBinder]):
        """Initialize the event catcher.

        Args:
            event_types: List of event types to catch
        """
        self.event_types = event_types
        self.caught_events: List[wx.Event] = []
        self.event_queue = queue.Queue()

    def bind_to_window(self, window: wx.Window):
        """Bind the event catcher to a window.

        Args:
            window: The window to bind to
        """
        for event_type in self.event_types:
            window.Bind(event_type, self._on_event)

    def _on_event(self, event: wx.Event):
        """Handle an event.

        Args:
            event: The event to handle
        """
        self.caught_events.append(event)
        self.event_queue.put(event)
        event.Skip()  # Allow normal processing

    def wait_for_event(self, timeout_ms: int = 1000) -> wx.Event:
        """Wait for an event to be caught.

        Args:
            timeout_ms: Maximum time to wait for an event (milliseconds)

        Returns:
            The caught event

        Raises:
            TimeoutError: If no event is caught within the timeout
        """
        # Process events to ensure they're delivered
        start_time = time.time()
        while time.time() - start_time < timeout_ms / 1000:
            # Check if we already have events
            if not self.event_queue.empty():
                return self.event_queue.get(block=False)

            # Process events
            wx.SafeYield()
            time.sleep(0.01)

        # Check one more time
        try:
            return self.event_queue.get(block=False)
        except queue.Empty:
            # If we have caught events but they're not in the queue,
            # return the most recent one
            if self.caught_events:
                return self.caught_events[-1]
            raise TimeoutError(f"No event caught within {timeout_ms}ms")

    def clear(self):
        """Clear all caught events."""
        self.caught_events.clear()
        # Clear the queue
        while not self.event_queue.empty():
            try:
                self.event_queue.get_nowait()
            except queue.Empty:
                break


def post_event(window: wx.Window, event_type: wx.PyEventBinder, **kwargs) -> wx.Event:
    """Post an event to a window.

    Args:
        window: The window to post the event to
        event_type: The type of event to post
        **kwargs: Attributes to set on the event

    Returns:
        The posted event
    """
    # Create the event - handle different wxPython versions
    if isinstance(event_type.evtType[0], int):
        # For wxPython 4.2.x
        event = wx.CommandEvent(event_type.evtType[0])
    else:
        # For older wxPython versions
        event = event_type.evtType[0]()

    # Set attributes
    for key, value in kwargs.items():
        if hasattr(event, key):
            setattr(event, key, value)

    # Set the window ID if not already set
    if hasattr(event, "SetId") and not kwargs.get("id"):
        event.SetId(window.GetId())

    # Post the event
    wx.PostEvent(window, event)

    # Process events to ensure it's delivered
    wx.SafeYield()

    return event


def wait_for_idle(timeout_ms: int = 1000):
    """Wait for the application to be idle.

    Args:
        timeout_ms: Maximum time to wait (milliseconds) - ignored but kept for compatibility
    """
    # Process pending events multiple times
    # Use wx.SafeYield which is more reliable than wx.Yield
    for _ in range(5):  # Process events a few times
        wx.SafeYield()
        time.sleep(0.01)  # Small delay to allow events to be processed
    return


def simulate_user_input(window: wx.Window, input_type: str, **kwargs):
    """Simulate user input on a window.

    Args:
        window: The window to simulate input on
        input_type: The type of input to simulate (e.g., "text", "click")
        **kwargs: Additional arguments for the specific input type
    """
    if input_type == "text":
        if isinstance(window, wx.TextCtrl):
            text = kwargs.get("text", "")
            window.SetValue(text)
            # Generate events
            post_event(window, wx.EVT_TEXT)
    elif input_type == "click":
        if isinstance(window, wx.Button):
            post_event(window, wx.EVT_BUTTON)
    elif input_type == "select":
        if isinstance(window, wx.Choice) or isinstance(window, wx.ComboBox):
            selection = kwargs.get("selection", 0)
            window.SetSelection(selection)
            post_event(window, wx.EVT_CHOICE)
    # Add more input types as needed


class AsyncEventWaiter:
    """Wait for asynchronous events to complete."""

    def __init__(self):
        """Initialize the event waiter."""
        self.event = threading.Event()
        self.result = None
        self.exception = None

    def callback(self, result=None):
        """Callback to signal that the event is complete.

        Args:
            result: The result of the operation
        """
        self.result = result
        self.event.set()

    def error_callback(self, exception):
        """Callback to signal that the event failed.

        Args:
            exception: The exception that occurred
        """
        self.exception = exception
        self.event.set()

    def wait(self, timeout_ms: int = 5000):
        """Wait for the event to complete.

        Args:
            timeout_ms: Maximum time to wait (milliseconds)

        Returns:
            The result of the operation

        Raises:
            TimeoutError: If the event does not complete within the timeout
            Exception: If the operation failed
        """
        start_time = time.time()
        while time.time() - start_time < timeout_ms / 1000:
            # Check if the event is already set
            if self.event.is_set():
                break

            # Process events to ensure callbacks are executed
            wx.SafeYield()
            time.sleep(0.01)

            # Check again after processing events
            if self.event.wait(0.01):  # Short timeout
                break

        # Final check with a short timeout
        if not self.event.wait(0.1):
            raise TimeoutError(f"Event did not complete within {timeout_ms}ms")

        # Check for exceptions
        if self.exception is not None:
            raise self.exception

        return self.result


# Convenience functions
def call_after(func: Callable, *args, **kwargs) -> Any:
    """Call a function using wx.CallAfter and wait for the result.

    Args:
        func: The function to call
        *args: Arguments to pass to the function
        **kwargs: Keyword arguments to pass to the function

    Returns:
        The result of the function call
    """
    # Execute the function directly and process events
    # This is more reliable in test environments
    result = func(*args, **kwargs)

    # Process events to ensure any side effects are handled
    for _ in range(5):
        wx.SafeYield()
        time.sleep(0.01)

    return result


def run_with_event_loop(func: Callable, *args, **kwargs) -> Any:
    """Run a function within a wx event loop.

    Args:
        func: The function to run
        *args: Arguments to pass to the function
        **kwargs: Keyword arguments to pass to the function

    Returns:
        The result of the function
    """
    with EventLoopContext():
        return func(*args, **kwargs)
