"""
Tests for the NWS Zone Information section in EditLocationDialog.

Covers Unit 5 of the Forecast Products PR 1 plan (A-R8, A-R9):
- "Forecast Zone" and "NWS Office" rows under a StaticBox
- Hidden for non-US locations (country_code != "US")
- "Not yet resolved" fallback for US locations with null zone fields
- Sizing switches from fixed (420, 200) to Fit()-based with 420 min width
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

# This file's fixtures monkey-patch wx.Dialog.__init__. Safe against the
# in-repo stub (no C-extension), destructive against real wxPython where the
# patches can leak across test files. Skip when real wx is detected.
pytestmark = pytest.mark.skipif(
    hasattr(sys.modules.get("wx"), "_core"),
    reason="Real wxPython detected; this test module patches wx globals and "
    "is only safe against the stub wx in tests/conftest.py.",
)

# ---------------------------------------------------------------------------
# Extend the wx stub with the constants/classes EditLocationDialog needs.
# ---------------------------------------------------------------------------
_wx = sys.modules["wx"]

for _attr, _val in {
    "DEFAULT_DIALOG_STYLE": 0,
    "ALIGN_RIGHT": 0x0200,
    "LEFT": 0x0010,
    "RIGHT": 0x0020,
    "TOP": 0x0040,
    "BOTTOM": 0x0080,
    "RESIZE_BORDER": 0x0040,
    "TE_PROCESS_ENTER": 0x0400,
    "LC_REPORT": 0x4000,
    "LC_SINGLE_SEL": 0x2000,
    "BORDER_SUNKEN": 0x0800,
}.items():
    if not hasattr(_wx, _attr):
        setattr(_wx, _attr, _val)

for _attr in ("EVT_TEXT_ENTER", "EVT_LIST_ITEM_SELECTED"):
    if not hasattr(_wx, _attr):
        setattr(_wx, _attr, MagicMock(name=_attr))

# StaticBox / StaticBoxSizer / StdDialogButtonSizer / Size are not in the root stub.
for _attr in ("ListCtrl", "StaticBoxSizer", "StdDialogButtonSizer", "Size"):
    if not hasattr(_wx, _attr):
        setattr(_wx, _attr, MagicMock(name=_attr))


class _StaticBoxStub(_wx.Control):
    """Class-like StaticBox stub so MagicMock(spec=wx.StaticBox) stays valid."""


def _ensure_static_box_stub():
    if not hasattr(_wx, "StaticBox") or isinstance(_wx.StaticBox, MagicMock):
        _wx.StaticBox = _StaticBoxStub


_ensure_static_box_stub()


class _ListCtrlStub(_wx.Control):
    """Class-like ListCtrl stub so full-suite wx mock leaks cannot affect this module."""


def _ensure_list_ctrl_stub():
    if not hasattr(_wx, "ListCtrl") or isinstance(_wx.ListCtrl, MagicMock):
        _wx.ListCtrl = _ListCtrlStub


_ensure_list_ctrl_stub()


class _TextCtrlStub(_wx.Control):
    """Class-like TextCtrl stub for stable dialog construction in the wx stub."""


def _ensure_text_ctrl_stub():
    if not hasattr(_wx, "TextCtrl") or isinstance(_wx.TextCtrl, MagicMock):
        _wx.TextCtrl = _TextCtrlStub


_ensure_text_ctrl_stub()

_USING_STUB = (
    not hasattr(sys.modules.get("wx", None), "App") or _wx.Dialog.__name__ == "_WxStubBase"
)

# Ensure Dialog base class has the instance methods the dialog invokes on self.
_StubBase = _wx.Dialog
for _meth in ("SetSize", "SetMinSize", "Fit", "Show", "Hide", "Bind", "EndModal"):
    if not hasattr(_StubBase, _meth):
        setattr(_StubBase, _meth, lambda self, *a, **kw: None)


from accessiweather.models import Location  # noqa: E402
from accessiweather.ui.dialogs.location_dialog import EditLocationDialog  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
class _DialogRecorder:
    """Captures constructor args and tracks widgets created during init."""

    def __init__(self):
        self.dialog_kwargs: dict = {}
        self.static_boxes: list[MagicMock] = []
        self.static_texts: list[MagicMock] = []
        self.min_size_calls: list = []
        self.fit_calls: int = 0


@pytest.fixture
def recorder():
    """Patch wx classes to capture widgets and dialog init kwargs."""
    _ensure_static_box_stub()
    _ensure_list_ctrl_stub()
    _ensure_text_ctrl_stub()

    rec = _DialogRecorder()
    saved: dict = {}
    active_patches: list = []

    if not _USING_STUB:
        # Real wx installed — patch Dialog.__init__ and instance methods.
        for method in ("__init__", "SetSize", "Bind", "EndModal", "Show", "Hide"):
            if method == "__init__":
                p = patch.object(_wx.Dialog, "__init__", lambda self, *a, **kw: None)
            else:
                p = patch.object(_wx.Dialog, method, lambda self, *a, **kw: None)
            active_patches.append(p)
            p.start()

    # Track Dialog __init__ kwargs via a wrapper around the base class.
    _orig_dialog_init = _wx.Dialog.__init__

    def _dialog_init(self, *a, **kw):
        rec.dialog_kwargs = dict(kw)
        # For tests, do NOT forward to super() (stub) to keep behaviour trivial.
        return

    saved["Dialog.__init__"] = _orig_dialog_init
    _wx.Dialog.__init__ = _dialog_init

    # Track SetMinSize and Fit on the Dialog base class
    def _set_min_size(self, *a, **kw):
        rec.min_size_calls.append(a[0] if a else kw)

    def _fit(self, *a, **kw):
        rec.fit_calls += 1

    _StubBase.SetMinSize = _set_min_size
    _StubBase.Fit = _fit

    # Track StaticText creations — return real MagicMocks that retain the label
    # so GetLabel() returns what was passed in.
    def _make_static_text(*args, **kwargs):
        st = MagicMock(name="StaticText")
        label = kwargs.get("label", args[1] if len(args) > 1 else "")
        st.GetLabel.return_value = label
        st._test_label = label  # convenience for assertions
        rec.static_texts.append(st)
        return st

    saved["StaticText"] = _wx.StaticText
    _wx.StaticText = _make_static_text

    saved["TextCtrl"] = _wx.TextCtrl
    _wx.TextCtrl = MagicMock(
        name="TextCtrl", side_effect=lambda *a, **kw: MagicMock(name="TextCtrlInst")
    )

    # Track StaticBox creations — record Show() calls for visibility assertions.
    def _make_static_box(*args, **kwargs):
        box = MagicMock(name="StaticBox")
        box._test_label = kwargs.get("label", args[1] if len(args) > 1 else "")
        box.IsShown.return_value = True

        def _box_show(visible=True):
            box.IsShown.return_value = bool(visible)

        box.Show.side_effect = _box_show
        rec.static_boxes.append(box)
        return box

    saved["StaticBox"] = _wx.StaticBox
    _wx.StaticBox = _make_static_box

    # StaticBoxSizer is called with (box, orient) — return a MagicMock sizer.
    saved["StaticBoxSizer"] = _wx.StaticBoxSizer
    _wx.StaticBoxSizer = MagicMock(
        name="StaticBoxSizer", side_effect=lambda *a, **kw: MagicMock(name="StaticBoxSizerInst")
    )

    saved["StdDialogButtonSizer"] = _wx.StdDialogButtonSizer
    _wx.StdDialogButtonSizer = MagicMock(
        name="StdDialogButtonSizer",
        side_effect=lambda *a, **kw: MagicMock(name="StdDialogButtonSizerInst"),
    )

    # BoxSizer likewise — return a MagicMock so Add() is tracked.
    saved["BoxSizer"] = _wx.BoxSizer
    _wx.BoxSizer = MagicMock(
        name="BoxSizer", side_effect=lambda *a, **kw: MagicMock(name="BoxSizerInst")
    )

    saved["ListCtrl"] = _wx.ListCtrl
    _wx.ListCtrl = MagicMock(
        name="ListCtrl", side_effect=lambda *a, **kw: MagicMock(name="ListCtrlInst")
    )

    saved["Panel"] = _wx.Panel
    _wx.Panel = MagicMock(name="Panel", side_effect=lambda *a, **kw: MagicMock(name="PanelInst"))

    saved["Button"] = _wx.Button
    _wx.Button = MagicMock(name="Button", side_effect=lambda *a, **kw: MagicMock(name="ButtonInst"))

    saved["CheckBox"] = _wx.CheckBox
    _wx.CheckBox = MagicMock(
        name="CheckBox", side_effect=lambda *a, **kw: MagicMock(name="CheckBoxInst")
    )

    # Patch wx.Size with a MagicMock so ctor calls are tracked even when
    # real wxPython is installed on the host.
    saved["Size"] = _wx.Size
    _wx.Size = MagicMock(name="Size", side_effect=lambda *a, **kw: (a, kw))

    yield rec

    # Restore
    _wx.Dialog.__init__ = saved["Dialog.__init__"]
    for name in (
        "StaticText",
        "StaticBox",
        "StaticBoxSizer",
        "StdDialogButtonSizer",
        "BoxSizer",
        "ListCtrl",
        "Panel",
        "TextCtrl",
        "Button",
        "CheckBox",
        "Size",
    ):
        setattr(_wx, name, saved[name])

    for p in active_patches:
        p.stop()


def _find_text_with_prefix(texts, prefix: str):
    """Return the first StaticText mock whose label starts with prefix."""
    for t in texts:
        if t._test_label.startswith(prefix):
            return t
    return None


def _find_static_box_with_label(boxes, label: str):
    """Return the first StaticBox mock whose label matches."""
    for box in boxes:
        if box._test_label == label:
            return box
    return None


def _open_edit_dialog(location: Location):
    """Open the edit dialog with the app argument required by current UI wiring."""
    return EditLocationDialog(parent=MagicMock(), app=MagicMock(), location=location)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestEditLocationDialogZoneInfo:
    """Covers the NWS Zone Information StaticBox in EditLocationDialog."""

    def test_happy_path_us_populated(self, recorder):
        """US location with populated zone fields renders both rows."""
        loc = Location(
            name="Raleigh, NC",
            latitude=35.78,
            longitude=-78.64,
            country_code="US",
            forecast_zone_id="NCZ027",
            cwa_office="RAH",
        )

        _open_edit_dialog(loc)

        zone_row = _find_text_with_prefix(recorder.static_texts, "Forecast Zone:")
        office_row = _find_text_with_prefix(recorder.static_texts, "NWS Office:")
        assert zone_row is not None
        assert office_row is not None
        assert zone_row._test_label == "Forecast Zone: NCZ027"
        assert office_row._test_label == "NWS Office: RAH"

        # StaticBox exists and was NOT hidden.
        zone_box = _find_static_box_with_label(recorder.static_boxes, "NWS Zone Information")
        assert zone_box is not None
        assert zone_box.IsShown() is True

    def test_non_us_location_hides_staticbox(self, recorder):
        """Non-US location hides the entire NWS Zone Information StaticBox."""
        loc = Location(
            name="London, UK",
            latitude=51.5074,
            longitude=-0.1278,
            country_code="GB",
            forecast_zone_id=None,
            cwa_office=None,
        )

        _open_edit_dialog(loc)

        box = _find_static_box_with_label(recorder.static_boxes, "NWS Zone Information")
        assert box is not None
        # Show(False) was called on the box.
        box.Show.assert_called_once_with(False)
        assert box.IsShown() is False

    def test_us_both_null_shows_not_yet_resolved(self, recorder):
        """US location with both fields null shows the 'Not yet resolved' message."""
        loc = Location(
            name="Phoenix, AZ",
            latitude=33.45,
            longitude=-112.07,
            country_code="US",
            forecast_zone_id=None,
            cwa_office=None,
        )

        _open_edit_dialog(loc)

        zone_row = _find_text_with_prefix(recorder.static_texts, "Forecast Zone:")
        office_row = _find_text_with_prefix(recorder.static_texts, "NWS Office:")
        assert zone_row is not None
        assert office_row is not None
        assert "Not yet resolved" in zone_row._test_label
        assert "Not yet resolved" in office_row._test_label

        # StaticBox is still shown (US location).
        zone_box = _find_static_box_with_label(recorder.static_boxes, "NWS Zone Information")
        assert zone_box is not None
        assert zone_box.IsShown() is True
        zone_box.Show.assert_not_called()

    def test_us_partial_mixed_values(self, recorder):
        """US location with one field populated and the other null."""
        loc = Location(
            name="Somewhere, US",
            latitude=40.0,
            longitude=-100.0,
            country_code="US",
            forecast_zone_id="ABZ001",
            cwa_office=None,
        )

        _open_edit_dialog(loc)

        zone_row = _find_text_with_prefix(recorder.static_texts, "Forecast Zone:")
        office_row = _find_text_with_prefix(recorder.static_texts, "NWS Office:")
        assert zone_row is not None and office_row is not None
        assert zone_row._test_label == "Forecast Zone: ABZ001"
        assert "Not yet resolved" in office_row._test_label

    def test_sizing_uses_fit_and_min_size(self, recorder):
        """Dialog calls SetMinSize((420, -1)) + Fit(), not the old fixed size."""
        loc = Location(
            name="Raleigh, NC",
            latitude=35.78,
            longitude=-78.64,
            country_code="US",
            forecast_zone_id="NCZ027",
            cwa_office="RAH",
        )

        _open_edit_dialog(loc)

        # Fit() was called at least once
        assert recorder.fit_calls >= 1
        # SetMinSize was called (with a wx.Size built from 640, -1).
        assert len(recorder.min_size_calls) >= 1
        # wx.Size was constructed with (640, -1) during dialog init.
        size_ctor_calls = [(c.args, c.kwargs) for c in getattr(_wx.Size, "call_args_list", [])]
        assert ((640, -1), {}) in size_ctor_calls

        # And the fixed size=(420, 200) is no longer passed to Dialog.__init__.
        assert "size" not in recorder.dialog_kwargs or recorder.dialog_kwargs.get("size") != (
            420,
            200,
        )

    def test_accessibility_labels_via_getlabel(self, recorder):
        """
        Each StaticText row's GetLabel() returns the label-prefixed string.

        Screen readers announce adjacent wx.StaticText content — this is the
        accessibility affordance, not SetName() or tooltips.
        """
        loc = Location(
            name="Raleigh, NC",
            latitude=35.78,
            longitude=-78.64,
            country_code="US",
            forecast_zone_id="NCZ027",
            cwa_office="RAH",
        )

        _open_edit_dialog(loc)

        zone_row = _find_text_with_prefix(recorder.static_texts, "Forecast Zone:")
        office_row = _find_text_with_prefix(recorder.static_texts, "NWS Office:")

        assert zone_row is not None and office_row is not None
        assert zone_row.GetLabel() == "Forecast Zone: NCZ027"
        assert office_row.GetLabel() == "NWS Office: RAH"
