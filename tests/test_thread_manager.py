"""Tests for thread manager."""

import threading
import time
from _thread import RLock as _RLock
from unittest.mock import MagicMock, patch

import pytest

from accessiweather.utils.thread_manager import (
    ThreadManager,
    get_thread_manager,
    register_thread,
    stop_all_threads,
    unregister_thread,
)

# --- Test Data ---


class SimpleThread(threading.Thread):
    """A simple thread that runs until its stop event is set."""

    def __init__(self, stop_event=None):
        super().__init__()
        self.stop_event = stop_event or threading.Event()

    def run(self):
        while not self.stop_event.is_set():
            time.sleep(0.01)  # Small sleep to prevent busy waiting


# --- Fixtures ---


@pytest.fixture
def thread_manager():
    """Create a fresh ThreadManager instance."""
    return ThreadManager()


@pytest.fixture
def mock_thread():
    """Create a mock thread."""
    thread = MagicMock(spec=threading.Thread)
    thread.name = "MockThread"
    thread.ident = 12345
    thread.is_alive.return_value = True
    return thread


@pytest.fixture
def mock_stop_event():
    """Create a mock stop event."""
    event = MagicMock(spec=threading.Event)
    return event


# --- ThreadManager Tests ---


def test_init(thread_manager):
    """Test ThreadManager initialization."""
    assert not thread_manager._threads
    assert not thread_manager._stop_events
    assert isinstance(thread_manager._lock, _RLock)


def test_register_thread_no_event(thread_manager, mock_thread):
    """Test registering a thread without a stop event."""
    result = thread_manager.register_thread(mock_thread)

    assert result is mock_thread
    assert mock_thread.ident in thread_manager._threads
    assert thread_manager._threads[mock_thread.ident]["thread"] is mock_thread
    assert thread_manager._threads[mock_thread.ident]["name"] == "MockThread"
    assert mock_thread.ident not in thread_manager._stop_events


def test_register_thread_with_event(thread_manager, mock_thread, mock_stop_event):
    """Test registering a thread with a stop event."""
    result = thread_manager.register_thread(mock_thread, mock_stop_event)

    assert result is mock_thread
    assert mock_thread.ident in thread_manager._threads
    assert thread_manager._threads[mock_thread.ident]["thread"] is mock_thread
    assert mock_thread.ident in thread_manager._stop_events
    assert thread_manager._stop_events[mock_thread.ident] is mock_stop_event


def test_register_thread_with_name(thread_manager, mock_thread):
    """Test registering a thread with a custom name."""
    custom_name = "CustomThreadName"
    result = thread_manager.register_thread(mock_thread, name=custom_name)

    assert result is mock_thread
    assert thread_manager._threads[mock_thread.ident]["name"] == custom_name


def test_register_thread_none(thread_manager):
    """Test registering None as a thread."""
    result = thread_manager.register_thread(None)

    assert result is None
    assert not thread_manager._threads
    assert not thread_manager._stop_events


def test_unregister_thread(thread_manager, mock_thread, mock_stop_event):
    """Test unregistering a thread."""
    thread_manager.register_thread(mock_thread, mock_stop_event)
    thread_manager.unregister_thread(mock_thread.ident)

    assert mock_thread.ident not in thread_manager._threads
    assert mock_thread.ident not in thread_manager._stop_events


def test_unregister_nonexistent(thread_manager):
    """Test unregistering a non-existent thread."""
    thread_manager.unregister_thread(99999)  # Should not raise


def test_get_threads(thread_manager, mock_thread):
    """Test getting all registered threads."""
    thread_manager.register_thread(mock_thread)

    threads = thread_manager.get_threads()

    assert threads == [mock_thread]


def test_get_stop_events(thread_manager, mock_thread, mock_stop_event):
    """Test getting all registered stop events."""
    thread_manager.register_thread(mock_thread, mock_stop_event)

    events = thread_manager.get_stop_events()

    assert events == [mock_stop_event]


def test_stop_all_threads_clean_stop(thread_manager):
    """Test stopping threads that respond to stop events."""
    # Create a real thread that will stop when the event is set
    stop_event = threading.Event()
    thread = SimpleThread(stop_event)
    thread.start()

    thread_manager.register_thread(thread, stop_event)
    remaining = thread_manager.stop_all_threads(timeout=0.1)

    assert not remaining  # No threads should remain
    assert not thread.is_alive()  # Thread should have stopped
    assert stop_event.is_set()  # Event should be set
    assert not thread_manager._threads  # Thread should be unregistered
    assert not thread_manager._stop_events  # Event should be unregistered


def test_stop_all_threads_timeout(thread_manager, mock_thread, mock_stop_event):
    """Test stopping threads that don't respond within timeout."""
    mock_thread.is_alive.return_value = True  # Thread never dies
    thread_manager.register_thread(mock_thread, mock_stop_event, name="StuckThread")

    remaining = thread_manager.stop_all_threads(timeout=0.01)

    assert remaining == ["StuckThread"]
    mock_stop_event.set.assert_called_once()
    mock_thread.join.assert_called_once_with(0.01)


def test_stop_all_threads_no_threads(thread_manager):
    """Test stopping when no threads are registered."""
    remaining = thread_manager.stop_all_threads()

    assert not remaining


def test_get_active_threads(thread_manager):
    """Test getting active threads."""
    # Create one active and one inactive thread
    active_thread = MagicMock(spec=threading.Thread)
    active_thread.ident = 1
    active_thread.is_alive.return_value = True

    inactive_thread = MagicMock(spec=threading.Thread)
    inactive_thread.ident = 2
    inactive_thread.is_alive.return_value = False

    thread_manager.register_thread(active_thread)
    thread_manager.register_thread(inactive_thread)

    active_threads = thread_manager.get_active_threads()

    assert active_threads == [active_thread]


def test_clear(thread_manager, mock_thread, mock_stop_event):
    """Test clearing all registered threads and events."""
    thread_manager.register_thread(mock_thread, mock_stop_event)
    thread_manager.clear()

    assert not thread_manager._threads
    assert not thread_manager._stop_events


def test_len(thread_manager, mock_thread):
    """Test len() operator."""
    assert len(thread_manager) == 0

    thread_manager.register_thread(mock_thread)
    assert len(thread_manager) == 1


def test_bool(thread_manager, mock_thread):
    """Test bool() operator."""
    assert not bool(thread_manager)

    thread_manager.register_thread(mock_thread)
    assert bool(thread_manager)


# --- Global Function Tests ---


def test_get_thread_manager():
    """Test getting the global thread manager instance."""
    manager1 = get_thread_manager()
    manager2 = get_thread_manager()

    assert manager1 is manager2  # Should return the same instance


def test_register_thread_global(mock_thread, mock_stop_event):
    """Test registering a thread using the global function."""
    with patch("accessiweather.utils.thread_manager._thread_manager") as mock_manager:
        register_thread(mock_thread, mock_stop_event, "TestThread")
        mock_manager.register_thread.assert_called_once_with(
            mock_thread, mock_stop_event, "TestThread"
        )


def test_unregister_thread_global(mock_thread):
    """Test unregistering a thread using the global function."""
    with patch("accessiweather.utils.thread_manager._thread_manager") as mock_manager:
        unregister_thread(mock_thread.ident)
        mock_manager.unregister_thread.assert_called_once_with(mock_thread.ident)


def test_stop_all_threads_global():
    """Test stopping all threads using the global function."""
    with patch("accessiweather.utils.thread_manager._thread_manager") as mock_manager:
        mock_manager.stop_all_threads.return_value = []
        remaining = stop_all_threads(timeout=0.1)
        mock_manager.stop_all_threads.assert_called_once_with(0.1)
        assert remaining == []
