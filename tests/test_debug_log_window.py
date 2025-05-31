"""Tests for debug log window module."""

from unittest.mock import MagicMock, patch

import pytest
import wx

from accessiweather.gui.debug_log_window import DebugLogWindow


@pytest.fixture
def wx_app():
    """Create a wx.App for testing."""
    app = wx.App()
    yield app
    app.Destroy()


@pytest.mark.gui
def test_debug_log_window_init(wx_app):
    """Test DebugLogWindow initialization."""
    parent = wx.Frame(None)
    try:
        window = DebugLogWindow(parent)
        assert window is not None
        assert isinstance(window, wx.Dialog)
        assert window.GetParent() == parent
    finally:
        parent.Destroy()


@pytest.mark.gui
def test_debug_log_window_title(wx_app):
    """Test DebugLogWindow has correct title."""
    parent = wx.Frame(None)
    try:
        window = DebugLogWindow(parent)
        title = window.GetTitle()
        assert "Debug" in title or "Log" in title
    finally:
        parent.Destroy()


@pytest.mark.gui
def test_debug_log_window_has_text_control(wx_app):
    """Test DebugLogWindow has a text control for logs."""
    parent = wx.Frame(None)
    try:
        window = DebugLogWindow(parent)
        # Look for text control in children
        text_controls = []
        for child in window.GetChildren():
            if isinstance(child, wx.TextCtrl):
                text_controls.append(child)

        assert len(text_controls) > 0, "Should have at least one text control"
    finally:
        parent.Destroy()


@pytest.mark.gui
def test_debug_log_window_has_buttons(wx_app):
    """Test DebugLogWindow has control buttons."""
    parent = wx.Frame(None)
    try:
        window = DebugLogWindow(parent)
        # Look for buttons in children
        buttons = []
        for child in window.GetChildren():
            if isinstance(child, wx.Button):
                buttons.append(child)

        # Should have at least a close button
        assert len(buttons) > 0, "Should have at least one button"
    finally:
        parent.Destroy()


@pytest.mark.gui
def test_debug_log_window_modal(wx_app):
    """Test DebugLogWindow can be shown as modal."""
    parent = wx.Frame(None)
    try:
        window = DebugLogWindow(parent)
        # Test that ShowModal method exists and can be called
        assert hasattr(window, "ShowModal")
        # Don't actually show modal in tests as it would block
    finally:
        parent.Destroy()


@pytest.mark.gui
def test_debug_log_window_close(wx_app):
    """Test DebugLogWindow can be closed."""
    parent = wx.Frame(None)
    try:
        window = DebugLogWindow(parent)
        # Test that Close method exists and can be called
        assert hasattr(window, "Close")
        window.Close()
    finally:
        parent.Destroy()


@pytest.mark.gui
def test_debug_log_window_destroy(wx_app):
    """Test DebugLogWindow can be destroyed."""
    parent = wx.Frame(None)
    try:
        window = DebugLogWindow(parent)
        # Test that Destroy method exists and can be called
        assert hasattr(window, "Destroy")
        window.Destroy()
    finally:
        parent.Destroy()


@pytest.mark.unit
@patch("wx.Dialog")
def test_debug_log_window_mock_init(mock_dialog):
    """Test DebugLogWindow initialization with mocked wx.Dialog."""
    mock_parent = MagicMock()  # noqa: F841
    mock_dialog_instance = MagicMock()
    mock_dialog.return_value = mock_dialog_instance

    # Import and create instance
    from accessiweather.gui.debug_log_window import DebugLogWindow

    # This will test the import and basic structure
    # without requiring actual wx components
    assert DebugLogWindow is not None


@pytest.mark.unit
def test_debug_log_window_module_import():
    """Test that debug_log_window module can be imported."""
    try:
        import accessiweather.gui.debug_log_window

        assert hasattr(accessiweather.gui.debug_log_window, "DebugLogWindow")
    except ImportError:
        pytest.fail("Failed to import debug_log_window module")


@pytest.mark.unit
def test_debug_log_window_class_exists():
    """Test that DebugLogWindow class exists."""
    from accessiweather.gui.debug_log_window import DebugLogWindow

    assert DebugLogWindow is not None
    assert callable(DebugLogWindow)


@pytest.mark.gui
def test_debug_log_window_size(wx_app):
    """Test DebugLogWindow has reasonable size."""
    parent = wx.Frame(None)
    try:
        window = DebugLogWindow(parent)
        size = window.GetSize()
        # Should have reasonable minimum size
        assert size.width > 200
        assert size.height > 150
    finally:
        parent.Destroy()


@pytest.mark.gui
def test_debug_log_window_sizer(wx_app):
    """Test DebugLogWindow uses sizers for layout."""
    parent = wx.Frame(None)
    try:
        window = DebugLogWindow(parent)
        sizer = window.GetSizer()
        # Should have a sizer for proper layout
        assert sizer is not None
    finally:
        parent.Destroy()
