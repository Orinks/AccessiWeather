"""
Tests for :class:`ForecastProductsDialog` and main-window wiring.

Covers Unit 8 of the Forecast Products PR 1 plan — dialog construction with
three tabs, focus handling on tab switch, main-window routing (Nationwide
still goes to NationwideDiscussionDialog, US locations go to the new
dialog), QUICK_ACTION_LABELS rename, and the non-US adjacent-StaticText
pattern.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

# This file's fixtures monkey-patch wx.Panel.__init__ and wx.Dialog.__init__
# to neutralize real-widget construction so we can pass MagicMock parents.
# That's safe when the wx module is the in-repo stub (no real C-extension),
# but destructive when real wxPython is installed — the patches leak across
# test files and break later alert-dialog tests that need a real Panel init.
# Skip the whole module when real wx is detected (CI under xvfb).
pytestmark = pytest.mark.skipif(
    hasattr(sys.modules.get("wx"), "_core"),
    reason="Real wxPython detected; this test module patches wx globals and "
    "is only safe against the stub wx in tests/conftest.py.",
)

# ---------------------------------------------------------------------------
# Stub augmentation (see test_forecast_product_panel.py for shape).
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

_StubDialog = _wx.Dialog
for _meth in (
    "SetSize",
    "SetSizer",
    "Bind",
    "EndModal",
    "Show",
    "Hide",
    "Close",
    "CenterOnParent",
):
    if not hasattr(_StubDialog, _meth):
        setattr(_StubDialog, _meth, lambda self, *a, **kw: None)

_StubPanel = _wx.Panel
for _meth in ("SetSizer", "GetSizer", "Bind", "Layout", "Show", "Hide"):
    if not hasattr(_StubPanel, _meth):
        setattr(_StubPanel, _meth, lambda self, *a, **kw: None)


# ---------------------------------------------------------------------------
# Imports under test
# ---------------------------------------------------------------------------
from accessiweather.iem_client import IemProductFetchError  # noqa: E402
from accessiweather.models import Location, TextProduct  # noqa: E402
from accessiweather.ui.dialogs.forecast_products_dialog import (  # noqa: E402
    ForecastProductsDialog,
)


# ---------------------------------------------------------------------------
# Autouse: neutralize wx.Dialog.__init__ and wx.Panel.__init__ so MagicMock
# parents don't crash when real wxPython is installed on the test host.
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _neutralize_wx_bases():
    saved: dict = {}
    saved["Dialog.__init__"] = _wx.Dialog.__init__
    saved["Panel.__init__"] = _wx.Panel.__init__

    def _noop(self, *a, **kw):
        return None

    _wx.Dialog.__init__ = _noop
    _wx.Panel.__init__ = _noop

    patched_methods = {}

    def _set_sizer(self, sizer):
        self._main_sizer = sizer

    def _get_sizer(self):
        return getattr(self, "_main_sizer", None)

    def _noop_meth(self, *a, **kw):
        return None

    for cls in (_wx.Dialog, _wx.Panel):
        for meth_name, impl in (
            ("SetSizer", _set_sizer),
            ("GetSizer", _get_sizer),
            ("Bind", _noop_meth),
            ("Show", _noop_meth),
            ("Hide", _noop_meth),
            ("Layout", _noop_meth),
            ("SetSize", _noop_meth),
            ("CenterOnParent", _noop_meth),
            ("EndModal", _noop_meth),
            ("Close", _noop_meth),
        ):
            patched_methods[(id(cls), meth_name)] = (cls, getattr(cls, meth_name, None))
            setattr(cls, meth_name, impl)
    saved["patched_methods"] = patched_methods

    for name in ("StaticText", "TextCtrl", "Button", "Choice", "CheckBox"):
        saved[name] = getattr(_wx, name)
        setattr(
            _wx,
            name,
            MagicMock(name=name, side_effect=lambda *a, **kw: MagicMock(name="widget")),
        )

    # wx.CallAfter asserts a wx.App exists on real wxPython; swap for MagicMock.
    saved["CallAfter"] = _wx.CallAfter
    _wx.CallAfter = MagicMock(name="CallAfter")

    yield

    _wx.Dialog.__init__ = saved["Dialog.__init__"]
    _wx.Panel.__init__ = saved["Panel.__init__"]
    import contextlib

    for (_cls_id, meth_name), (cls, orig) in saved["patched_methods"].items():
        if orig is None:
            with contextlib.suppress(AttributeError):
                delattr(cls, meth_name)
        else:
            setattr(cls, meth_name, orig)
    for name in ("StaticText", "TextCtrl", "Button", "Choice", "CheckBox"):
        setattr(_wx, name, saved[name])
    _wx.CallAfter = saved["CallAfter"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _stub_notebook():
    """Build a wx.Notebook stub that tracks AddPage and selection."""
    nb = MagicMock(name="Notebook")
    nb.pages = []

    def _add_page(panel, label, *a, **kw):
        nb.pages.append((panel, label))
        return True

    nb.AddPage.side_effect = _add_page
    nb.GetSelection.return_value = 0
    return nb


@pytest.fixture
def notebook_factory():
    """Patch wx.Notebook to our tracking stub for the duration of the test."""
    original = _wx.Notebook
    nb_holder = {}

    def _factory(*a, **kw):
        nb = _stub_notebook()
        nb_holder["instance"] = nb
        return nb

    _wx.Notebook = MagicMock(side_effect=_factory)
    yield nb_holder
    _wx.Notebook = original


@pytest.fixture
def panel_factory():
    """Patch ForecastProductPanel to a lightweight mock recording its ctor args."""
    created: list[dict] = []

    class _FakePanel:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.product_type = kwargs.get("product_type")
            self.product_textctrl = MagicMock(name="TextCtrl")
            self.ensure_loaded = MagicMock(name=f"ensure_loaded_{self.product_type}")
            created.append({"product_type": self.product_type, "instance": self, **kwargs})

    # The dialog imports ForecastProductPanel directly from the module;
    # patch the symbol it bound at import time.
    from accessiweather.ui.dialogs import forecast_products_dialog

    original_sym = forecast_products_dialog.ForecastProductPanel
    forecast_products_dialog.ForecastProductPanel = _FakePanel  # type: ignore[assignment]
    yield created
    forecast_products_dialog.ForecastProductPanel = original_sym  # type: ignore[assignment]


@pytest.fixture
def sample_us_location():
    return Location(
        name="Raleigh, NC",
        latitude=35.78,
        longitude=-78.64,
        country_code="US",
        cwa_office="RAH",
        forecast_zone_id="NCZ027",
    )


# ---------------------------------------------------------------------------
# Dialog-level tests
# ---------------------------------------------------------------------------
class TestForecastProductsDialog:
    def test_inactive_iem_summary_counts_as_unavailable_for_active_tabs(self):
        product = TextProduct(
            product_type="WPC_ERO",
            product_id="WPC_ERO_DAY1",
            cwa_office="WPC",
            issuance_time=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
            product_text=(
                "WPC Day 1 Excessive Rainfall Outlook\n\n"
                "Generated: 2026-05-01T12:00:00Z\n\n"
                "No active outlooks were returned."
            ),
            headline="WPC Day 1 Excessive Rainfall Outlook",
        )

        result = ForecastProductsDialog._active_iem_tab_product_or_none(product)

        assert result is None

    def test_active_iem_summary_remains_available_for_active_tabs(self):
        product = TextProduct(
            product_type="SPC_WATCHES",
            product_id="SPC_WATCHES",
            cwa_office="SPC",
            issuance_time=None,
            product_text=("SPC Watches\n\nWatch 1:\nSEL: SEL8\nType: SVR\n"),
            headline="SPC Watches",
        )

        result = ForecastProductsDialog._active_iem_tab_product_or_none(product)

        assert result is product

    def test_dialog_builds_location_relevant_text_product_tabs(
        self, notebook_factory, panel_factory, sample_us_location
    ):
        service = MagicMock(name="ForecastProductService")
        ai = MagicMock(name="AIExplainer")

        dlg = ForecastProductsDialog(
            parent=MagicMock(),
            location=sample_us_location,
            forecast_product_service=service,
            ai_explainer=ai,
        )

        types = [entry["product_type"] for entry in panel_factory]
        assert types == ["AFD", "HWO", "SPS"]
        assert len(dlg.panels) == 3

        # Each panel got wired to the same service + explainer.
        for entry in panel_factory:
            assert entry["ai_explainer"] is ai
            assert entry["cwa_office"] == "RAH"
            assert entry["location_name"] == "Raleigh, NC"
        assert panel_factory[0]["autoload"] is True
        assert all(entry["autoload"] is False for entry in panel_factory[1:])

    def test_loader_invokes_service_get(self, notebook_factory, panel_factory, sample_us_location):
        """Each panel's bound loader calls service.get(product_type, cwa_office)."""
        import asyncio

        service = MagicMock(name="ForecastProductService")

        async def _fake_get(product_type, cwa_office):
            return SimpleNamespace(product_type=product_type, cwa=cwa_office)

        service.get = _fake_get

        ForecastProductsDialog(
            parent=MagicMock(),
            location=sample_us_location,
            forecast_product_service=service,
            ai_explainer=None,
        )

        loaders = [entry["product_loader"] for entry in panel_factory[:3]]
        assert len(loaders) == 3
        # Each loader resolves to the correct product type.
        loop = asyncio.new_event_loop()
        try:
            for expected_type, loader in zip(["AFD", "HWO", "SPS"], loaders, strict=True):
                result = loop.run_until_complete(loader())
                assert result.product_type == expected_type
                assert result.cwa == "RAH"
        finally:
            loop.close()

    def test_loader_invokes_iem_for_point_based_tabs(
        self, notebook_factory, panel_factory, sample_us_location
    ):
        """Point-based tabs use IEM structured service helpers."""
        import asyncio

        service = MagicMock(name="ForecastProductService")

        async def _fake_spc_outlook(latitude, longitude, **kwargs):
            return SimpleNamespace(
                product_type="SPC_OUTLOOK",
                latitude=latitude,
                longitude=longitude,
                kwargs=kwargs,
            )

        service.get_iem_spc_outlook.side_effect = _fake_spc_outlook

        dlg = ForecastProductsDialog(
            parent=MagicMock(),
            location=sample_us_location,
            forecast_product_service=service,
            ai_explainer=None,
        )

        spc_tab = next(
            tab for tab in ForecastProductsDialog._TABS if tab.product_type == "SPC_OUTLOOK"
        )
        result = asyncio.run(dlg._make_loader(spc_tab)())

        assert result.product_type == "SPC_OUTLOOK"
        assert result.latitude == 35.7796
        assert result.longitude == -78.6382
        assert result.kwargs == {"day": 1, "current": True, "max_items": 3, "timeout": 10.0}
        service.get_iem_afos.assert_not_called()

    def test_point_based_loader_returns_none_for_inactive_iem_summary(
        self, notebook_factory, panel_factory, sample_us_location
    ):
        """No-active IEM summaries disappear from the active tab strip."""
        import asyncio

        service = MagicMock(name="ForecastProductService")

        async def _fake_wpc_outlook(latitude, longitude, **kwargs):
            return TextProduct(
                product_type="WPC_ERO",
                product_id="WPC_ERO_DAY1",
                cwa_office="WPC",
                issuance_time=None,
                product_text="WPC Day 1 Excessive Rainfall Outlook\n\nNo active outlooks were returned.",
                headline="WPC Day 1 Excessive Rainfall Outlook",
            )

        service.get_iem_wpc_outlook.side_effect = _fake_wpc_outlook

        dlg = ForecastProductsDialog(
            parent=MagicMock(),
            location=sample_us_location,
            forecast_product_service=service,
            ai_explainer=None,
        )

        wpc_tab = next(tab for tab in ForecastProductsDialog._TABS if tab.product_type == "WPC_ERO")
        result = asyncio.run(dlg._make_loader(wpc_tab)())

        assert result is None

    def test_point_based_loader_returns_none_for_iem_fetch_error(
        self, notebook_factory, panel_factory, sample_us_location
    ):
        """Optional active IEM tabs disappear when IEM is too slow or unavailable."""
        import asyncio

        service = MagicMock(name="ForecastProductService")

        async def _fake_spc_outlook(latitude, longitude, **kwargs):
            raise IemProductFetchError("IEM SPC outlook request failed: TimeoutException")

        service.get_iem_spc_outlook.side_effect = _fake_spc_outlook

        dlg = ForecastProductsDialog(
            parent=MagicMock(),
            location=sample_us_location,
            forecast_product_service=service,
            ai_explainer=None,
        )

        spc_tab = next(
            tab for tab in ForecastProductsDialog._TABS if tab.product_type == "SPC_OUTLOOK"
        )
        result = asyncio.run(dlg._make_loader(spc_tab)())

        assert result is None

    def test_dialog_passes_advanced_lookup_opener_to_panels(
        self, notebook_factory, panel_factory, sample_us_location
    ):
        service = MagicMock(name="ForecastProductService")

        dlg = ForecastProductsDialog(
            parent=MagicMock(),
            location=sample_us_location,
            forecast_product_service=service,
            ai_explainer=None,
        )

        openers = [entry["advanced_lookup_opener"] for entry in panel_factory]
        assert len(openers) == 3
        for opener in openers:
            assert callable(opener)

        with patch(
            "accessiweather.ui.dialogs.forecast_products_dialog.show_advanced_text_product_dialog"
        ) as show_dialog:
            openers[0]()

        show_dialog.assert_called_once_with(
            dlg,
            sample_us_location,
            service,
            initial_product_type="AFD",
            app=None,
        )

    def test_page_change_lazy_loads_selected_tab(
        self, notebook_factory, panel_factory, sample_us_location
    ):
        service = MagicMock(name="ForecastProductService")
        dlg = ForecastProductsDialog(
            parent=MagicMock(),
            location=sample_us_location,
            forecast_product_service=service,
            ai_explainer=None,
        )
        notebook_factory["instance"].GetSelection.return_value = 2
        event = MagicMock()

        dlg._on_page_changed(event)

        panel_factory[2]["instance"].ensure_loaded.assert_called_once()
        event.Skip.assert_called_once()

    def test_page_change_does_not_steal_focus(
        self, notebook_factory, panel_factory, sample_us_location
    ):
        """
        Tab switching must NOT auto-grab focus into the content.

        Accessibility contract: the notebook tab strip is one focus level,
        the selected tab's content is the next. Auto-focusing the TextCtrl
        on every arrow-through-tabs forces the screen reader to re-read
        the full product text. The user moves into content with Tab.
        """
        service = MagicMock()
        dlg = ForecastProductsDialog(
            parent=MagicMock(),
            location=sample_us_location,
            forecast_product_service=service,
            ai_explainer=None,
        )
        notebook_factory["instance"].GetSelection.return_value = 1
        event = MagicMock()

        dlg._on_page_changed(event)

        panel_factory[1]["instance"].ensure_loaded.assert_called_once()
        panel_factory[1]["instance"].product_textctrl.SetFocus.assert_not_called()
        event.Skip.assert_called_once()


# ---------------------------------------------------------------------------
# Main-window wiring tests
# ---------------------------------------------------------------------------
class TestMainWindowWiring:
    def test_quick_action_label_renamed(self):
        from accessiweather.ui.main_window import QUICK_ACTION_LABELS

        assert QUICK_ACTION_LABELS["discussion"] == "Forecaster &Notes"

    def test_nationwide_branch_still_routes_to_nationwide_dialog(self):
        """Nationwide selection opens NationwideDiscussionDialog, not the new one."""
        from accessiweather.ui import main_window

        mw = MagicMock(spec=main_window.MainWindow)
        mw._get_discussion_service = MagicMock(return_value=MagicMock())
        mw._on_forecast_products = MagicMock()

        current = Location(
            name="Nationwide",
            latitude=39.0,
            longitude=-98.0,
            country_code="US",
        )
        mw.app = MagicMock()
        mw.app.config_manager.get_current_location.return_value = current

        # Patch the nationwide dialog module to capture construction.
        with patch(
            "accessiweather.ui.dialogs.nationwide_discussion_dialog.NationwideDiscussionDialog"
        ) as nat_dlg_cls:
            nat_instance = MagicMock()
            nat_dlg_cls.return_value = nat_instance
            main_window.MainWindow._on_discussion(mw)

        nat_dlg_cls.assert_called_once()
        mw._on_forecast_products.assert_not_called()

    def test_non_nationwide_routes_to_forecast_products(self):
        """Any non-Nationwide location dispatches to _on_forecast_products."""
        from accessiweather.ui import main_window

        mw = MagicMock(spec=main_window.MainWindow)
        mw._on_forecast_products = MagicMock()
        current = Location(
            name="Raleigh, NC",
            latitude=35.78,
            longitude=-78.64,
            country_code="US",
        )
        mw.app = MagicMock()
        mw.app.config_manager.get_current_location.return_value = current

        main_window.MainWindow._on_discussion(mw)
        mw._on_forecast_products.assert_called_once()

    def test_update_button_state_us_enables(self):
        """US location: button enabled, US-only label hidden."""
        from accessiweather.ui import main_window

        mw = MagicMock(spec=main_window.MainWindow)
        mw.app = MagicMock()
        mw.app.config_manager.get_current_location.return_value = Location(
            name="Raleigh, NC",
            latitude=35.78,
            longitude=-78.64,
            country_code="US",
        )
        mw.discussion_button = MagicMock()
        mw.forecast_products_us_only_label = MagicMock()

        main_window.MainWindow._update_forecast_products_button_state(mw)
        mw.discussion_button.Enable.assert_called()
        mw.forecast_products_us_only_label.Hide.assert_called()

    def test_update_button_state_non_us_disables(self):
        """Non-US location: button disabled, US-only label shown (adjacent StaticText)."""
        from accessiweather.ui import main_window

        mw = MagicMock(spec=main_window.MainWindow)
        mw.app = MagicMock()
        mw.app.config_manager.get_current_location.return_value = Location(
            name="London, UK",
            latitude=51.5,
            longitude=-0.1,
            country_code="GB",
        )
        mw.discussion_button = MagicMock()
        mw.forecast_products_us_only_label = MagicMock()

        main_window.MainWindow._update_forecast_products_button_state(mw)
        mw.discussion_button.Disable.assert_called()
        mw.forecast_products_us_only_label.Show.assert_called()
