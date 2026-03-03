"""
Tests for initial focus in AirQuality, UVIndex, and Discussion dialogs.

Covers the SetFocus calls added for screen reader accessibility (issue #409).
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Extend the wx stub (created by root conftest.py) with constants and methods
# that the dialog modules need at instantiation time.
# ---------------------------------------------------------------------------
_wx = sys.modules["wx"]

# Style / ID constants used inside dialog constructors and _create_ui
for _attr, _val in {
    "DEFAULT_DIALOG_STYLE": 0,
    "RESIZE_BORDER": 0x0040,
    "ID_CLOSE": 5104,
    "TE_MULTILINE": 0x0020,
    "TE_READONLY": 0x0010,
    "TE_RICH2": 0x8000,
    "LEFT": 0x0010,
    "RIGHT": 0x0020,
    "TOP": 0x0040,
    "BOTTOM": 0x0080,
    "ALIGN_RIGHT": 0x0200,
}.items():
    if not hasattr(_wx, _attr):
        setattr(_wx, _attr, _val)

if not hasattr(_wx, "Colour"):
    _wx.Colour = lambda *a, **kw: MagicMock(name="Colour")

if not hasattr(_wx, "MessageBox"):
    _wx.MessageBox = MagicMock(name="MessageBox")

if not hasattr(_wx, "SystemSettings"):
    _wx.SystemSettings = MagicMock(name="SystemSettings")
    _wx.SYS_COLOUR_GRAYTEXT = 0

# Stub wx.lib.scrolledpanel (needed by soundpack_wizard_dialog via __init__.py)
if "wx.lib.scrolledpanel" not in sys.modules:
    import types

    _scrolled = types.ModuleType("wx.lib.scrolledpanel")
    _scrolled.ScrolledPanel = _wx.Dialog  # reuse _WxStubBase
    sys.modules["wx.lib.scrolledpanel"] = _scrolled

# Methods that dialogs invoke on *self* (inherits _WxStubBase via wx.Dialog).
_StubBase = _wx.Dialog
for _meth in ("SetSize", "CenterOnParent", "SetSizer", "EndModal", "Layout", "Hide", "Show"):
    if not hasattr(_StubBase, _meth):
        setattr(_StubBase, _meth, lambda self, *a, **kw: None)
if not hasattr(_StubBase, "GetSizer"):
    _StubBase.GetSizer = lambda self: MagicMock()

# ---------------------------------------------------------------------------
# Now safe to import the dialog classes under test
# ---------------------------------------------------------------------------
from accessiweather.ui.dialogs.air_quality_dialog import AirQualityDialog  # noqa: E402
from accessiweather.ui.dialogs.discussion_dialog import DiscussionDialog  # noqa: E402
from accessiweather.ui.dialogs.uv_index_dialog import UVIndexDialog  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers & Fixtures
# ---------------------------------------------------------------------------
class _WidgetTracker:
    """Collects wx widget instances created during a test."""

    def __init__(self):
        self.buttons: list[MagicMock] = []
        self.textctrls: list[MagicMock] = []

    def _make_button(self, *a, **kw):
        btn = MagicMock(name="Button")
        self.buttons.append(btn)
        return btn

    def _make_textctrl(self, *a, **kw):
        ctrl = MagicMock(name="TextCtrl")
        self.textctrls.append(ctrl)
        return ctrl


@pytest.fixture(autouse=True)
def widget_tracker():
    """
    Replace wx widget constructors with factories returning unique MagicMocks.

    The conftest.py stub sets classes like ``_wx.BoxSizer = MagicMock`` (the
    CLASS, not an instance).  Calling ``MagicMock(panel, label=...)`` would
    pass the first arg as ``spec``, restricting attribute access.  Replacing
    them with plain factory functions avoids this.
    """
    tracker = _WidgetTracker()
    saved = {}

    # Save originals and replace with spec-free factories
    for name in ("StaticText", "BoxSizer", "Panel"):
        saved[name] = getattr(_wx, name)
        setattr(_wx, name, lambda *a, **kw: MagicMock())

    saved["Button"] = _wx.Button
    _wx.Button = tracker._make_button

    saved["TextCtrl"] = _wx.TextCtrl
    _wx.TextCtrl = tracker._make_textctrl

    yield tracker

    # Restore originals
    for name, orig in saved.items():
        setattr(_wx, name, orig)


def _make_environmental(*, has_data_val: bool = True, has_hourly: bool = True):
    """Build a mock environmental data object for AQ / UV dialogs."""
    env = MagicMock()
    env.has_data.return_value = has_data_val

    # Real numbers needed because the dialogs format them (int(round(...)))
    env.air_quality_index = 42
    env.air_quality_category = "Good"
    env.air_quality_pollutant = "PM2_5"
    env.uv_index = 3
    env.uv_category = "Moderate"
    env.updated_at = None  # skip timestamp formatting branch

    if has_hourly:
        hour = MagicMock()
        hour.time = "10 AM"
        hour.aqi = 42
        hour.uv_index = 3
        hour.pm2_5 = 12.0
        hour.pm10 = 20.0
        hour.ozone = None
        hour.nitrogen_dioxide = None
        hour.sulphur_dioxide = None
        hour.carbon_monoxide = None
        env.hourly_air_quality = [hour]
        env.hourly_uv_index = [hour]
    else:
        env.hourly_air_quality = None
        env.hourly_uv_index = None

    return env


# ===========================================================================
# AirQualityDialog
# ===========================================================================
class TestAirQualityDialogFocus:
    """Initial-focus tests for AirQualityDialog."""

    def test_focus_hourly_display_with_data(self, widget_tracker):
        """When data and hourly forecast exist, focus goes to _hourly_display."""
        env = _make_environmental(has_data_val=True, has_hourly=True)

        dlg = AirQualityDialog(
            parent=MagicMock(), location_name="Test", environmental=env, app=MagicMock()
        )

        assert dlg._hourly_display is not None
        dlg._hourly_display.SetFocus.assert_called_once()

    def test_focus_close_button_without_data(self, widget_tracker):
        """When no data is available, focus goes to the close button."""
        AirQualityDialog(
            parent=MagicMock(), location_name="Test", environmental=None, app=MagicMock()
        )

        # Only one button is created (Close)
        assert len(widget_tracker.buttons) == 1
        widget_tracker.buttons[0].SetFocus.assert_called_once()


# ===========================================================================
# UVIndexDialog
# ===========================================================================
class TestUVIndexDialogFocus:
    """Initial-focus tests for UVIndexDialog."""

    def test_focus_hourly_display_with_data(self, widget_tracker):
        """When data and hourly forecast exist, focus goes to _hourly_display."""
        env = _make_environmental(has_data_val=True, has_hourly=True)

        dlg = UVIndexDialog(
            parent=MagicMock(), location_name="Test", environmental=env, app=MagicMock()
        )

        assert dlg._hourly_display is not None
        dlg._hourly_display.SetFocus.assert_called_once()

    def test_focus_close_button_without_data(self, widget_tracker):
        """When no data is available, focus goes to the close button."""
        UVIndexDialog(parent=MagicMock(), location_name="Test", environmental=None, app=MagicMock())

        # Only one button is created (Close)
        assert len(widget_tracker.buttons) == 1
        widget_tracker.buttons[0].SetFocus.assert_called_once()


# ===========================================================================
# DiscussionDialog
# ===========================================================================
class TestDiscussionDialogFocus:
    """Initial-focus tests for DiscussionDialog."""

    def test_focus_discussion_display(self, widget_tracker):
        """Focus goes to discussion_display when the dialog opens."""
        app = MagicMock()
        app.current_weather_data = None
        app.config_manager.get_current_location.return_value = None

        dlg = DiscussionDialog(parent=MagicMock(), app=app)

        dlg.discussion_display.SetFocus.assert_called_once()
