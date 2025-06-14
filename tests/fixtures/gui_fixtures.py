"""GUI testing fixtures."""

import os
from unittest.mock import patch

import pytest


@pytest.fixture
def headless_environment():
    """Set up headless environment for GUI testing."""
    original_display = os.environ.get("DISPLAY")
    os.environ["DISPLAY"] = ""
    yield
    if original_display is not None:
        os.environ["DISPLAY"] = original_display
    elif "DISPLAY" in os.environ:
        del os.environ["DISPLAY"]


@pytest.fixture
def mock_wx_app():
    """Mock wxPython App for GUI testing."""
    with patch("wx.App") as mock_app:
        yield mock_app
