"""GUI testing fixtures and performance testing utilities for Toga app."""

import time
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_toga_app():
    """Mock Toga App for GUI testing."""
    mock_app = MagicMock()
    mock_app.main_loop = MagicMock()
    mock_app.exit = MagicMock()
    mock_app.paths = MagicMock()
    mock_app.paths.config = MagicMock()
    return mock_app


@pytest.fixture
def mock_toga_main_window():
    """Mock Toga MainWindow for GUI testing."""
    mock_window = MagicMock()
    mock_window.show = MagicMock()
    mock_window.hide = MagicMock()
    mock_window.close = MagicMock()
    mock_window.title = "Test Window"
    mock_window.size = (800, 600)
    return mock_window


@pytest.fixture
def mock_toga_box():
    """Mock Toga Box for layout testing."""
    mock_box = MagicMock()
    mock_box.add = MagicMock()
    mock_box.insert = MagicMock()
    mock_box.remove = MagicMock()
    mock_box.clear = MagicMock()
    return mock_box


@pytest.fixture
def mock_toga_controls():
    """Mock Toga controls for GUI testing."""
    controls = {}

    # Text input controls
    mock_text_input = MagicMock()
    mock_text_input.value = "Test Value"
    mock_text_input.placeholder = "Enter text"
    mock_text_input.readonly = False
    controls["TextInput"] = mock_text_input

    # Multiline text input
    mock_multiline_text = MagicMock()
    mock_multiline_text.value = "Test multiline text"
    mock_multiline_text.readonly = False
    controls["MultilineTextInput"] = mock_multiline_text

    # Button controls
    mock_button = MagicMock()
    mock_button.text = "Test Button"
    mock_button.enabled = True
    mock_button.on_press = MagicMock()
    controls["Button"] = mock_button

    # Selection controls
    mock_selection = MagicMock()
    mock_selection.items = ["Option 1", "Option 2", "Option 3"]
    mock_selection.value = "Option 1"
    mock_selection.on_change = MagicMock()
    controls["Selection"] = mock_selection

    # Switch controls
    mock_switch = MagicMock()
    mock_switch.value = True
    mock_switch.text = "Enable feature"
    mock_switch.on_change = MagicMock()
    controls["Switch"] = mock_switch

    # Label controls
    mock_label = MagicMock()
    mock_label.text = "Test Label"
    controls["Label"] = mock_label

    return controls


@pytest.fixture
def performance_timer():
    """Performance timing utility for tests."""

    class PerformanceTimer:
        def __init__(self):
            self.start_time = None
            self.end_time = None

        def start(self):
            self.start_time = time.perf_counter()

        def stop(self):
            self.end_time = time.perf_counter()

        def elapsed(self):
            if self.start_time is None or self.end_time is None:
                return None
            return self.end_time - self.start_time

        def __enter__(self):
            self.start()
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.stop()

    return PerformanceTimer()


@pytest.fixture
def memory_profiler():
    """Memory profiling utility for tests."""

    class MemoryProfiler:
        def __init__(self):
            self.initial_memory = None
            self.final_memory = None

        def start(self):
            # In a real implementation, this would use psutil or similar
            # For testing purposes, we'll just mock it
            self.initial_memory = 100  # MB

        def stop(self):
            self.final_memory = 105  # MB

        def memory_used(self):
            if self.initial_memory is None or self.final_memory is None:
                return None
            return self.final_memory - self.initial_memory

        def __enter__(self):
            self.start()
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.stop()

    return MemoryProfiler()


@pytest.fixture
def api_call_counter():
    """Counter for tracking API calls in performance tests."""

    class APICallCounter:
        def __init__(self):
            self.count = 0
            self.calls = []

        def increment(self, endpoint=None):
            self.count += 1
            if endpoint:
                self.calls.append(endpoint)

        def reset(self):
            self.count = 0
            self.calls.clear()

        def get_count(self):
            return self.count

        def get_calls(self):
            return self.calls.copy()

    return APICallCounter()


@pytest.fixture
def toga_test_environment(monkeypatch):
    """Set up test environment for Toga app testing."""
    # Set environment variables for test mode
    monkeypatch.setenv("ACCESSIWEATHER_TEST_MODE", "1")
    monkeypatch.setenv("TOGA_BACKEND", "dummy")  # Use dummy backend for testing

    # Return a simple object to indicate test mode is active
    class TogaTestEnvironment:
        def __init__(self):
            self.test_mode = True
            self.backend = "dummy"

        def is_test_mode(self):
            return self.test_mode

    return TogaTestEnvironment()
