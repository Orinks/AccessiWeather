"""GUI testing fixtures and performance testing utilities."""

import time
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_wx_app():
    """Mock wx.App for GUI testing."""
    mock_app = MagicMock()
    mock_app.MainLoop = MagicMock()
    mock_app.ExitMainLoop = MagicMock()
    mock_app.Yield = MagicMock(return_value=True)
    return mock_app


@pytest.fixture
def mock_wx_frame():
    """Mock wx.Frame for GUI testing."""
    mock_frame = MagicMock()
    mock_frame.Show = MagicMock()
    mock_frame.Hide = MagicMock()
    mock_frame.Close = MagicMock()
    mock_frame.Destroy = MagicMock()
    mock_frame.SetTitle = MagicMock()
    mock_frame.SetSize = MagicMock()
    mock_frame.Center = MagicMock()
    mock_frame.Bind = MagicMock()
    return mock_frame


@pytest.fixture
def mock_wx_panel():
    """Mock wx.Panel for GUI testing."""
    mock_panel = MagicMock()
    mock_panel.SetSizer = MagicMock()
    mock_panel.Layout = MagicMock()
    mock_panel.Refresh = MagicMock()
    mock_panel.Update = MagicMock()
    return mock_panel


@pytest.fixture
def mock_wx_sizer():
    """Mock wx.Sizer for GUI testing."""
    mock_sizer = MagicMock()
    mock_sizer.Add = MagicMock()
    mock_sizer.AddSpacer = MagicMock()
    mock_sizer.Layout = MagicMock()
    mock_sizer.Fit = MagicMock()
    return mock_sizer


@pytest.fixture
def mock_wx_controls():
    """Mock wx controls for GUI testing."""
    controls = {}

    # Text controls
    mock_text_ctrl = MagicMock()
    mock_text_ctrl.GetValue = MagicMock(return_value="Test Value")
    mock_text_ctrl.SetValue = MagicMock()
    mock_text_ctrl.Clear = MagicMock()
    controls["TextCtrl"] = mock_text_ctrl

    # Button controls
    mock_button = MagicMock()
    mock_button.SetLabel = MagicMock()
    mock_button.GetLabel = MagicMock(return_value="Test Button")
    mock_button.Enable = MagicMock()
    mock_button.Disable = MagicMock()
    controls["Button"] = mock_button

    # Choice controls
    mock_choice = MagicMock()
    mock_choice.GetSelection = MagicMock(return_value=0)
    mock_choice.SetSelection = MagicMock()
    mock_choice.GetStringSelection = MagicMock(return_value="Option 1")
    mock_choice.SetStringSelection = MagicMock()
    mock_choice.Append = MagicMock()
    mock_choice.Clear = MagicMock()
    controls["Choice"] = mock_choice

    # CheckBox controls
    mock_checkbox = MagicMock()
    mock_checkbox.GetValue = MagicMock(return_value=True)
    mock_checkbox.SetValue = MagicMock()
    controls["CheckBox"] = mock_checkbox

    # StaticText controls
    mock_static_text = MagicMock()
    mock_static_text.SetLabel = MagicMock()
    mock_static_text.GetLabel = MagicMock(return_value="Static Text")
    controls["StaticText"] = mock_static_text

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
def headless_environment(monkeypatch):
    """Set up headless environment for GUI testing."""
    # Set environment variables for headless mode
    monkeypatch.setenv("DISPLAY", "")
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    monkeypatch.setenv("ACCESSIWEATHER_TEST_MODE", "1")

    # Return a simple object to indicate headless mode is active
    class HeadlessEnvironment:
        def __init__(self):
            self.headless = True
            self.display = ""

        def is_headless(self):
            return self.headless

    return HeadlessEnvironment()
