"""
Tests for :class:`ForecastProductPanel`.

Covers Unit 8 of the Forecast Products PR 1 plan — per-tab rendering of AFD,
HWO, and SPS products; empty / error / loading / no-CWA states; SPS
multi-product chooser; and the AI button visibility contract mirrored from
:mod:`discussion_dialog`.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

# This file's fixtures monkey-patch wx.Panel.__init__ to neutralize real-widget
# construction so we can pass MagicMock parents. Safe against the in-repo stub
# (no C-extension), destructive against real wxPython where the patches leak
# across test files. Skip the whole module when real wx is detected.
pytestmark = pytest.mark.skipif(
    hasattr(sys.modules.get("wx"), "_core"),
    reason="Real wxPython detected; this test module patches wx globals and "
    "is only safe against the stub wx in tests/conftest.py.",
)

# ---------------------------------------------------------------------------
# Extend the wx stub with the classes and constants this dialog needs. The
# stub lives in tests/conftest.py; we augment per-test-file as needed so new
# work never breaks unrelated tests.
# ---------------------------------------------------------------------------
_wx = sys.modules["wx"]

for _attr, _val in {
    "DEFAULT_DIALOG_STYLE": 0,
    "ALIGN_RIGHT": 0x0200,
    "LEFT": 0x0010,
    "RIGHT": 0x0020,
    "TOP": 0x0040,
    "BOTTOM": 0x0080,
    "RESIZE_BORDER": 0x40,
    "TE_MULTILINE": 0x0020,
    "TE_READONLY": 0x0010,
    "HSCROLL": 0x8000,
    "WXK_ESCAPE": 27,
    "ID_CLOSE": 5107,
}.items():
    if not hasattr(_wx, _attr):
        setattr(_wx, _attr, _val)

for _attr in ("Notebook", "EVT_NOTEBOOK_PAGE_CHANGED"):
    if not hasattr(_wx, _attr):
        setattr(_wx, _attr, MagicMock(name=_attr))

# Ensure the Panel base class responds to the methods the panel uses on self.
_StubPanel = _wx.Panel
for _meth in ("SetSizer", "GetSizer", "Bind", "Layout", "Show", "Hide"):
    if not hasattr(_StubPanel, _meth):
        setattr(_StubPanel, _meth, lambda self, *a, **kw: None)

# GetSizer needs to return the _main_sizer instance the panel stored.
if getattr(_StubPanel, "_patched_getsizer", False) is False:

    def _get_sizer(self):
        return getattr(self, "_main_sizer", None)

    _StubPanel.GetSizer = _get_sizer
    _StubPanel._patched_getsizer = True  # type: ignore[attr-defined]

# Likewise the Dialog base class for downstream dialog tests.
_StubDialog = _wx.Dialog
for _meth in ("SetSize", "SetSizer", "Bind", "EndModal", "Show", "Hide", "Close", "CenterOnParent"):
    if not hasattr(_StubDialog, _meth):
        setattr(_StubDialog, _meth, lambda self, *a, **kw: None)


# ---------------------------------------------------------------------------
# Imports under test (after stub setup).
# ---------------------------------------------------------------------------
from accessiweather.models import TextProduct  # noqa: E402
from accessiweather.ui.dialogs.forecast_product_panel import (  # noqa: E402
    ForecastProductPanel,
    _format_issuance,
    _format_sps_choice_entry,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _neutralize_wx_widgets():
    """
    Swap real wx widget classes for MagicMock factories for these tests.

    When real wxPython is installed, the widget constructors validate their
    parent; we don't want real widgets anyway. We swap them here and restore
    on teardown. Matches the pattern in test_location_dialog_zone_info.py.
    """
    saved: dict = {}
    saved["Panel.__init__"] = _wx.Panel.__init__

    def _noop_init(self, *a, **kw):
        return None

    _wx.Panel.__init__ = _noop_init

    # Install no-op methods on Panel so self.SetSizer / self.Bind / self.GetSizer
    # do not hit real wx validation.
    patched_methods = {}

    def _set_sizer(self, sizer):
        self._main_sizer = sizer

    def _get_sizer(self):
        return getattr(self, "_main_sizer", None)

    def _noop(self, *a, **kw):
        return None

    for meth_name, impl in (
        ("SetSizer", _set_sizer),
        ("GetSizer", _get_sizer),
        ("Bind", _noop),
        ("Show", _noop),
        ("Hide", _noop),
        ("Layout", _noop),
    ):
        patched_methods[meth_name] = getattr(_wx.Panel, meth_name, None)
        setattr(_wx.Panel, meth_name, impl)
    saved["patched_methods"] = patched_methods

    for name in ("StaticText", "TextCtrl", "Button", "Choice", "CheckBox"):
        saved[name] = getattr(_wx, name)
        setattr(
            _wx,
            name,
            MagicMock(
                name=name,
                side_effect=lambda *a, **kw: MagicMock(name=f"{kw.get('label', 'widget')}"),
            ),
        )

    yield

    import contextlib

    _wx.Panel.__init__ = saved["Panel.__init__"]
    for meth_name, orig in saved["patched_methods"].items():
        if orig is None:
            with contextlib.suppress(AttributeError):
                delattr(_wx.Panel, meth_name)
        else:
            setattr(_wx.Panel, meth_name, orig)
    for name in ("StaticText", "TextCtrl", "Button", "Choice", "CheckBox"):
        setattr(_wx, name, saved[name])


@pytest.fixture
def captured_sizer():
    """
    Instrument wx.BoxSizer so Show(widget, bool) calls are recorded.

    Returns a dict ``{widget_id: is_shown}`` that tests can inspect. Each
    sizer tracks both its Show() calls and an Add()-order list of widgets.
    """
    original = _wx.BoxSizer

    class _FakeSizer:
        instances: list = []

        def __init__(self, *_a, **_kw):
            self.show_calls: list = []
            self.added: list = []
            _FakeSizer.instances.append(self)

        def Add(self, widget, *_a, **_kw):
            self.added.append(widget)

        def Show(self, widget, visible=True):
            self.show_calls.append((widget, bool(visible)))
            # Also reflect visibility on the widget when it's a MagicMock so
            # tests can check .Show / .Hide call counts elsewhere.
            import contextlib

            with contextlib.suppress(Exception):
                widget._sizer_visible = bool(visible)

        def Layout(self):
            pass

    _wx.BoxSizer = _FakeSizer
    _FakeSizer.instances.clear()
    yield _FakeSizer
    _wx.BoxSizer = original


@pytest.fixture
def explainer_stub():
    """Minimal AIExplainer-shaped stub with a clearable cache."""

    class _Stub:
        def __init__(self):
            self.cache = MagicMock()

        async def explain_text_product(self, *args, **kwargs):
            return SimpleNamespace(
                text="Plain summary", model_used="m", token_count=1, estimated_cost=0.0
            )

    return _Stub()


def _build_panel(
    product_type: str,
    *,
    loader_result=None,
    loader_error: Exception | None = None,
    cwa_office: str | None = "RAH",
    ai_explainer=None,
    location_name: str = "Raleigh, NC",
) -> ForecastProductPanel:
    """
    Construct a panel whose loader returns ``loader_result`` (or raises).

    ``_schedule_load`` is monkey-patched to run the coroutine synchronously
    via ``_on_load_complete`` / ``_on_load_error``, side-stepping the event
    loop entirely for deterministic GUI tests.
    """
    if loader_error is not None:

        async def _loader():
            raise loader_error
    else:

        async def _loader():
            return loader_result

    # Patch _schedule_load BEFORE __init__ triggers its first load.
    orig_schedule = ForecastProductPanel._schedule_load

    def _sync_schedule(self, coro):
        # Drive the coroutine manually — no asyncio loop needed.
        try:
            try:
                coro.send(None)
            except StopIteration as stop:
                result = stop.value
                self._on_load_complete(result)
                return
            except Exception as exc:  # noqa: BLE001
                self._on_load_error(exc)
                return
            # If the coroutine actually awaited something, we won't pump
            # further — tests stick to plain return/raise loaders.
        except Exception as exc:  # noqa: BLE001
            self._on_load_error(exc)

    ForecastProductPanel._schedule_load = _sync_schedule
    try:
        panel = ForecastProductPanel(
            parent=MagicMock(),
            product_type=product_type,
            product_loader=_loader,
            ai_explainer=ai_explainer,
            cwa_office=cwa_office,
            location_name=location_name,
        )
    finally:
        ForecastProductPanel._schedule_load = orig_schedule
    return panel


def _make_product(
    product_type: str = "AFD",
    *,
    text: str = "Sample product text",
    headline: str | None = None,
    product_id: str = "ID-1",
    issuance: datetime | None = None,
) -> TextProduct:
    return TextProduct(
        product_type=product_type,  # type: ignore[arg-type]
        product_id=product_id,
        cwa_office="RAH",
        issuance_time=issuance or datetime(2026, 4, 20, 14, 30, tzinfo=UTC),
        product_text=text,
        headline=headline,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestForecastProductPanelRendering:
    """Happy-path rendering for each product type."""

    def test_afd_populated(self, captured_sizer):
        afd = _make_product("AFD", text="Full AFD raw text")
        panel = _build_panel("AFD", loader_result=afd)

        panel.product_textctrl.SetValue.assert_any_call("Full AFD raw text")
        # Issuance label got a non-empty label starting with "Issued:"
        issuance_calls = [c.args[0] for c in panel.issuance_label.SetLabel.call_args_list if c.args]
        assert any(lbl.startswith("Issued:") for lbl in issuance_calls)

    def test_hwo_empty_graph_renders_empty_copy(self, captured_sizer):
        # Empty result — simulates 200 with empty @graph.
        panel = _build_panel("HWO", loader_result=[])
        panel.product_textctrl.SetValue.assert_any_call(
            "Hazardous Weather Outlook not currently available for RAH."
        )
        panel.explain_button.Disable.assert_called()

    def test_sps_empty_renders_no_statements_copy(self, captured_sizer):
        panel = _build_panel("SPS", loader_result=None)
        panel.product_textctrl.SetValue.assert_any_call(
            "No recent Special Weather Statements for RAH."
        )

    def test_afd_rare_empty_returns_afd_copy(self, captured_sizer):
        panel = _build_panel("AFD", loader_result=None)
        panel.product_textctrl.SetValue.assert_any_call(
            "Area Forecast Discussion not currently available for RAH."
        )


class TestForecastProductPanelSPS:
    """SPS multi-product selection behaviour."""

    def test_multi_sps_shows_choice(self, captured_sizer):
        p1 = _make_product("SPS", text="First", headline="Dense fog", product_id="sps-1")
        p2 = _make_product("SPS", text="Second", headline="Fire weather", product_id="sps-2")
        p3 = _make_product("SPS", text="Third", headline="Pollen", product_id="sps-3")

        panel = _build_panel("SPS", loader_result=[p1, p2, p3])

        # Choice repopulated with three entries.
        append_calls = [c.args[0] for c in panel.sps_choice.Append.call_args_list if c.args]
        assert len(append_calls) == 3
        assert any("Dense fog" in entry for entry in append_calls)
        assert any("Fire weather" in entry for entry in append_calls)
        assert any("Pollen" in entry for entry in append_calls)

        # Chooser was Show(True)'d via the main sizer.
        sizer = panel._main_sizer
        assert (panel.sps_choice, True) in sizer.show_calls
        # First product is rendered in the TextCtrl.
        panel.product_textctrl.SetValue.assert_any_call("First")

    def test_single_sps_hides_choice(self, captured_sizer):
        p1 = _make_product("SPS", text="Only one", product_id="sps-1")
        panel = _build_panel("SPS", loader_result=[p1])

        sizer = panel._main_sizer
        # The chooser was never Show(True)'d — all Show calls on the choice
        # widget kept visibility False.
        choice_calls = [visible for (w, visible) in sizer.show_calls if w is panel.sps_choice]
        assert choice_calls  # at least one Show call occurred
        assert not any(choice_calls)  # none of them were True

    def test_swap_sps_via_choice_event(self, captured_sizer):
        p1 = _make_product("SPS", text="Red flag", headline="Fire", product_id="sps-1")
        p2 = _make_product("SPS", text="Dense fog advisory", headline="Fog", product_id="sps-2")
        panel = _build_panel("SPS", loader_result=[p1, p2])

        # Switch to index 1.
        panel.sps_choice.GetSelection = MagicMock(return_value=1)
        panel._on_sps_choice_changed(MagicMock())
        panel.product_textctrl.SetValue.assert_any_call("Dense fog advisory")


class TestForecastProductPanelErrorState:
    """Fetch-failure path renders retry button + try-again message."""

    def test_fetch_error_renders_retry(self, captured_sizer):
        from accessiweather.weather_client_nws import TextProductFetchError

        panel = _build_panel("HWO", loader_error=TextProductFetchError("boom"))

        panel.product_textctrl.SetValue.assert_any_call(
            "Failed to fetch Hazardous Weather Outlook — try again."
        )
        panel.retry_button.Show.assert_called()
        panel.explain_button.Disable.assert_called()

    def test_retry_triggers_reload(self, captured_sizer):
        """Retry button click re-invokes the loader."""
        from accessiweather.weather_client_nws import TextProductFetchError

        panel = _build_panel("HWO", loader_error=TextProductFetchError("boom"))

        # Swap in a fresh loader so retry reports success.
        afd = _make_product("HWO", text="Retry worked")

        async def _fresh_loader():
            return afd

        panel._product_loader = _fresh_loader

        # Patch scheduler synchronously for this call too.
        def _sync_schedule(self, coro):
            try:
                try:
                    coro.send(None)
                except StopIteration as stop:
                    self._on_load_complete(stop.value)
            except Exception as exc:  # noqa: BLE001
                self._on_load_error(exc)

        orig = ForecastProductPanel._schedule_load
        ForecastProductPanel._schedule_load = _sync_schedule
        try:
            panel._on_retry(MagicMock())
        finally:
            ForecastProductPanel._schedule_load = orig

        panel.product_textctrl.SetValue.assert_any_call("Retry worked")


class TestForecastProductPanelNoCwa:
    """cwa_office is None — all three product types share a fallback message."""

    @pytest.mark.parametrize("product_type", ["AFD", "HWO", "SPS"])
    def test_no_cwa_office_message(self, captured_sizer, product_type):
        panel = _build_panel(product_type, cwa_office=None, loader_result=None)
        panel.product_textctrl.SetValue.assert_any_call(
            "NWS text products will populate after the next weather refresh."
        )
        panel.explain_button.Disable.assert_called()


class TestForecastProductPanelAIVisibility:
    """AI summary widgets stay hidden until Plain Language Summary is clicked."""

    def test_ai_widgets_hidden_on_initial_render(self, captured_sizer, explainer_stub):
        afd = _make_product("AFD", text="Full AFD")
        panel = _build_panel("AFD", loader_result=afd, ai_explainer=explainer_stub)

        sizer = panel._main_sizer
        # Both AI widgets were explicitly hidden via the sizer.
        header_calls = [
            visible for (w, visible) in sizer.show_calls if w is panel.ai_summary_header
        ]
        display_calls = [
            visible for (w, visible) in sizer.show_calls if w is panel.ai_summary_display
        ]
        assert header_calls and not any(header_calls)
        assert display_calls and not any(display_calls)

    def test_explain_button_enabled_when_ai_and_text_present(self, captured_sizer, explainer_stub):
        afd = _make_product("AFD", text="Full AFD")
        panel = _build_panel("AFD", loader_result=afd, ai_explainer=explainer_stub)
        # Explain button was Enable()'d after load.
        panel.explain_button.Enable.assert_called()

    def test_explain_button_disabled_without_ai_explainer(self, captured_sizer):
        afd = _make_product("AFD", text="Full AFD")
        panel = _build_panel("AFD", loader_result=afd, ai_explainer=None)
        # With no explainer, Disable() was called (Enable is never reached).
        panel.explain_button.Disable.assert_called()


class TestFormattingHelpers:
    def test_format_issuance_none(self):
        assert _format_issuance(None) == "Issued: unknown"

    def test_format_issuance_includes_issued_prefix(self):
        out = _format_issuance(datetime(2026, 4, 20, 14, 30, tzinfo=UTC))
        assert out.startswith("Issued:")

    def test_sps_entry_uses_headline(self):
        p = _make_product("SPS", text="body", headline="Fire weather watch")
        entry = _format_sps_choice_entry(p)
        assert "Fire weather watch" in entry
        assert entry.startswith("Issued ")

    def test_sps_entry_falls_back_to_first_line(self):
        p = _make_product("SPS", text="First line\nsecond line\n", headline=None)
        entry = _format_sps_choice_entry(p)
        assert "First line" in entry
