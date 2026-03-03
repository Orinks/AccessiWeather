"""
Tests verifying dialogs use system colors instead of hardcoded foreground colors.

Covers the replacements made for high-contrast / theme compatibility (issue #408).
Two layers of verification:
1. Static scan: no wx.Colour() inside SetForegroundColour calls across dialog files.
2. Runtime: wx.SystemSettings.GetColour is called during dialog construction.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Extend the wx stub for dialog instantiation
# ---------------------------------------------------------------------------
_wx = sys.modules["wx"]

for _attr, _val in {
    "DEFAULT_DIALOG_STYLE": 0,
    "RESIZE_BORDER": 0x0040,
    "ID_CLOSE": 5104,
    "ID_CANCEL": 5101,
    "TE_MULTILINE": 0x0020,
    "TE_READONLY": 0x0010,
    "TE_RICH2": 0x8000,
    "TE_PROCESS_ENTER": 0x0400,
    "LEFT": 0x0010,
    "RIGHT": 0x0020,
    "TOP": 0x0040,
    "BOTTOM": 0x0080,
    "ALIGN_RIGHT": 0x0200,
    "ALIGN_CENTER_VERTICAL": 0x0800,
    "LC_REPORT": 0x0001,
    "LC_SINGLE_SEL": 0x0004,
    "BORDER_SUNKEN": 0x0200,
    "FD_OPEN": 0x0001,
    "FD_FILE_MUST_EXIST": 0x0002,
    "YES_NO": 0x000A,
    "YES": 0x0002,
    "ICON_QUESTION": 0,
    "ICON_INFORMATION": 0,
    "ICON_WARNING": 0,
    "FONTWEIGHT_BOLD": 92,
    "FONTWEIGHT_NORMAL": 90,
    "FONTFAMILY_TELETYPE": 75,
    "FONTSTYLE_NORMAL": 90,
}.items():
    if not hasattr(_wx, _attr):
        setattr(_wx, _attr, _val)

if not hasattr(_wx, "Colour"):
    _wx.Colour = lambda *a, **kw: MagicMock(name="Colour")

if not hasattr(_wx, "Font"):
    _wx.Font = lambda *a, **kw: MagicMock(name="Font")

if not hasattr(_wx, "MessageBox"):
    _wx.MessageBox = MagicMock(name="MessageBox")

if not hasattr(_wx, "FileDialog"):
    _wx.FileDialog = MagicMock(name="FileDialog")

if not hasattr(_wx, "ListCtrl"):
    _wx.ListCtrl = MagicMock

if not hasattr(_wx, "FlexGridSizer"):
    _wx.FlexGridSizer = MagicMock

if not hasattr(_wx, "EVT_TEXT_ENTER"):
    _wx.EVT_TEXT_ENTER = MagicMock()

if not hasattr(_wx, "EVT_LIST_ITEM_SELECTED"):
    _wx.EVT_LIST_ITEM_SELECTED = MagicMock()

if not hasattr(_wx, "EVT_LIST_ITEM_ACTIVATED"):
    _wx.EVT_LIST_ITEM_ACTIVATED = MagicMock()

if not hasattr(_wx, "EVT_CHAR_HOOK"):
    _wx.EVT_CHAR_HOOK = MagicMock()

# Stub wx.lib.scrolledpanel
if "wx.lib.scrolledpanel" not in sys.modules:
    import types

    _scrolled = types.ModuleType("wx.lib.scrolledpanel")
    _scrolled.ScrolledPanel = _wx.Dialog  # reuse _WxStubBase
    sys.modules["wx.lib.scrolledpanel"] = _scrolled

# Methods on _WxStubBase
_StubBase = _wx.Dialog
for _meth in (
    "SetSize",
    "CenterOnParent",
    "Centre",
    "SetSizer",
    "EndModal",
    "Layout",
    "Hide",
    "Show",
    "Bind",
    "SetName",
):
    if not hasattr(_StubBase, _meth):
        setattr(_StubBase, _meth, lambda self, *a, **kw: None)
if not hasattr(_StubBase, "GetSizer"):
    _StubBase.GetSizer = lambda self: MagicMock()


# ===========================================================================
# 1. Static Analysis: no hardcoded wx.Colour in SetForegroundColour
# ===========================================================================
DIALOG_DIR = Path(__file__).resolve().parents[2] / "src" / "accessiweather" / "ui" / "dialogs"

# Pattern matches: SetForegroundColour(wx.Colour(...))
_HARDCODED_PATTERN = re.compile(r"SetForegroundColour\(\s*wx\.Colour\(")


def _scan_for_hardcoded_colors() -> list[tuple[str, int, str]]:
    """
    Scan dialog files for hardcoded wx.Colour in SetForegroundColour calls.

    Returns list of (filename, line_number, line_text) tuples.
    """
    hits: list[tuple[str, int, str]] = []
    for py_file in sorted(DIALOG_DIR.glob("*.py")):
        for lineno, line in enumerate(py_file.read_text().splitlines(), start=1):
            if _HARDCODED_PATTERN.search(line):
                hits.append((py_file.name, lineno, line.strip()))
    return hits


class TestNoHardcodedColors:
    """Verify no dialog uses hardcoded wx.Colour() for foreground text."""

    def test_no_hardcoded_foreground_colors_in_dialogs(self):
        """All SetForegroundColour calls must use wx.SystemSettings.GetColour."""
        hits = _scan_for_hardcoded_colors()
        if hits:
            report = "\n".join(f"  {f}:{ln}: {text}" for f, ln, text in hits)
            pytest.fail(
                f"Found {len(hits)} hardcoded foreground color(s):\n{report}\n"
                "Use wx.SystemSettings.GetColour(wx.SYS_COLOUR_*) instead."
            )


# ===========================================================================
# 2. Runtime: SystemSettings.GetColour is called during dialog init
# ===========================================================================


@pytest.fixture(autouse=True)
def _widget_factories():
    """Replace wx widget constructors with spec-free factories."""
    saved = {}

    for name in ("StaticText", "BoxSizer", "Panel", "ListCtrl", "FlexGridSizer"):
        saved[name] = getattr(_wx, name, None)
        setattr(_wx, name, lambda *a, **kw: MagicMock())

    for name in ("Button", "TextCtrl", "CheckBox"):
        saved[name] = getattr(_wx, name, None)
        setattr(_wx, name, lambda *a, **kw: MagicMock())

    yield

    for name, orig in saved.items():
        if orig is not None:
            setattr(_wx, name, orig)


def _make_environmental(*, has_data_val=True, has_hourly=True):
    """Build a mock environmental data object."""
    env = MagicMock()
    env.has_data.return_value = has_data_val
    env.air_quality_index = 42
    env.air_quality_category = "Good"
    env.air_quality_pollutant = "PM2_5"
    env.uv_index = 3
    env.uv_category = "Moderate"
    env.updated_at = None
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


class TestSystemColorsUsedAtRuntime:
    """Verify wx.SystemSettings.GetColour is called during dialog init."""

    def test_air_quality_dialog_uses_system_colors(self):
        """AirQualityDialog calls SystemSettings.GetColour for hint text."""
        from accessiweather.ui.dialogs.air_quality_dialog import AirQualityDialog

        _wx.SystemSettings.GetColour.reset_mock()
        env = _make_environmental(has_data_val=True)

        AirQualityDialog(
            parent=MagicMock(), location_name="Test", environmental=env, app=MagicMock()
        )

        assert _wx.SystemSettings.GetColour.call_count > 0

    def test_uv_index_dialog_uses_system_colors(self):
        """UVIndexDialog calls SystemSettings.GetColour for hint text."""
        from accessiweather.ui.dialogs.uv_index_dialog import UVIndexDialog

        _wx.SystemSettings.GetColour.reset_mock()
        env = _make_environmental(has_data_val=True)

        UVIndexDialog(parent=MagicMock(), location_name="Test", environmental=env, app=MagicMock())

        assert _wx.SystemSettings.GetColour.call_count > 0

    def test_weather_history_dialog_uses_system_colors(self):
        """WeatherHistoryDialog calls SystemSettings.GetColour."""
        from accessiweather.ui.dialogs.weather_history_dialog import WeatherHistoryDialog

        _wx.SystemSettings.GetColour.reset_mock()

        WeatherHistoryDialog(
            parent=MagicMock(),
            location_name="Test",
            sections=[("Test", "Some content")],
        )

        assert _wx.SystemSettings.GetColour.call_count > 0

    def test_aviation_dialog_uses_system_colors(self):
        """AviationDialog calls SystemSettings.GetColour for hint text."""
        from accessiweather.ui.dialogs.aviation_dialog import AviationDialog

        _wx.SystemSettings.GetColour.reset_mock()

        app = MagicMock()
        app.config_manager.get_current_location.return_value = MagicMock(name="TestCity")

        AviationDialog(parent=MagicMock(), app=app)

        assert _wx.SystemSettings.GetColour.call_count > 0
