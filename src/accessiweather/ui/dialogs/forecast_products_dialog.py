"""
Forecast Products dialog — tabbed host for AFD, HWO, and SPS panels.

A ``wx.Notebook`` with three :class:`ForecastProductPanel` pages. Focus lands
on the AFD TextCtrl when the dialog opens so the user sees content immediately.
Tab switches deliberately do NOT grab focus — the notebook tab strip stays
the active focus level until the user Tabs into content, matching the
accessible notebook contract.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

import wx

from .advanced_text_product_dialog import show_advanced_text_product_dialog
from .forecast_product_panel import ForecastProductPanel

ProductLoader = Callable[[], Awaitable[object]]

if TYPE_CHECKING:
    from ...ai_explainer import AIExplainer
    from ...models import Location
    from ...services.forecast_product_service import ForecastProductService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TextProductTab:
    """Configuration for a Forecaster Notes product tab."""

    product_type: str
    label: str
    loader_kind: str
    requires_cwa: bool = False


class ForecastProductsDialog(wx.Dialog):
    """Tabbed dialog showing available NWS AFD, HWO, and SPS products."""

    _TABS: tuple[TextProductTab, ...] = (
        TextProductTab("AFD", "Area Forecast Discussion", "current", requires_cwa=True),
        TextProductTab("HWO", "Hazardous Weather Outlook", "current", requires_cwa=True),
        TextProductTab("SPS", "Special Weather Statement", "current", requires_cwa=True),
        TextProductTab("LSR", "Local Storm Report", "nws_history", requires_cwa=True),
        TextProductTab("PNS", "Public Information Statement", "nws_history", requires_cwa=True),
        TextProductTab("CLI", "Daily Climate Report", "nws_history", requires_cwa=True),
        TextProductTab("SPC_OUTLOOK", "SPC Outlook (Storm Prediction Center)", "spc_outlook"),
        TextProductTab("SPC_MCD", "SPC MCD (Mesoscale Discussion)", "spc_mcd"),
        TextProductTab(
            "SPC_WATCHES",
            "SPC Watches (Storm Prediction Center)",
            "spc_watches_current",
        ),
        TextProductTab("WPC_ERO", "WPC ERO (Excessive Rainfall Outlook)", "wpc_ero"),
        TextProductTab(
            "WPC_MPD",
            "WPC MPD (Mesoscale Precipitation Discussion)",
            "wpc_mpd",
        ),
    )

    def __init__(
        self,
        parent: wx.Window,
        location: Location,
        forecast_product_service: ForecastProductService,
        ai_explainer: AIExplainer | None,
        app: object | None = None,
    ) -> None:
        """
        Build the dialog and its three panels.

        Args:
            parent: Parent window.
            location: Selected location (must have ``cwa_office`` for populated
                tabs; a null ``cwa_office`` is handled by the panel).
            forecast_product_service: Service used to fetch+cache each product.
            ai_explainer: Optional AI explainer wired through to each panel.
            app: Optional AccessiWeather app instance. Passed to each panel
                so async loaders can dispatch via ``app.run_async``.

        """
        super().__init__(
            parent,
            title="Forecaster Notes",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self._location = location
        self._service = forecast_product_service
        self._ai_explainer = ai_explainer
        self._app = app

        self._create_widgets()
        self._bind_events()

        self.SetSize(wx.Size(700, 600))
        self.CenterOnParent()

        # Land focus on the notebook's tab strip so the user hears which tab
        # is selected and can arrow through the others. Landing inside the
        # content forces screen readers to read the whole product text
        # before the user has indicated they want it.
        wx.CallAfter(self.notebook.SetFocus)

    def _create_widgets(self) -> None:
        """Construct the notebook with three product panels."""
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        self.notebook = wx.Notebook(self)

        self.panels: list[ForecastProductPanel] = []
        cwa_office = getattr(self._location, "cwa_office", None)
        location_name = getattr(self._location, "name", "")

        for tab in self._TABS:
            is_first_tab = len(self.panels) == 0
            loader = self._make_loader(tab)
            panel_cwa = cwa_office if tab.requires_cwa else "IEM"
            panel = ForecastProductPanel(
                parent=self.notebook,
                product_type=tab.product_type,
                product_loader=loader,
                ai_explainer=self._ai_explainer,
                cwa_office=panel_cwa,
                location_name=location_name,
                app=self._app,
                availability_callback=self._on_panel_availability_resolved,
                advanced_lookup_opener=self._make_advanced_lookup_opener(tab.product_type),
                autoload=is_first_tab,
            )
            self.notebook.AddPage(panel, tab.label)
            self.panels.append(panel)

        main_sizer.Add(self.notebook, 1, wx.ALL | wx.EXPAND, 8)

        # Close button row.
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.close_button = wx.Button(self, wx.ID_CLOSE, label="&Close")
        button_sizer.AddStretchSpacer()
        button_sizer.Add(self.close_button, 0)
        main_sizer.Add(button_sizer, 0, wx.ALL | wx.EXPAND, 8)

        self.SetSizer(main_sizer)

    def _bind_events(self) -> None:
        """
        Bind close and ESC events.

        We intentionally do NOT grab focus on page-change. Auto-moving focus
        into the content every time the user arrow-keys through tabs forces
        screen readers to re-read the full product text and breaks the
        standard "tab strip is a focus level, content is the next focus
        level" contract. The user moves into content themselves with Tab.
        """
        self.close_button.Bind(wx.EVT_BUTTON, self._on_close)
        self.notebook.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self._on_page_changed)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_key)

    # ------------------------------------------------------------------
    # Loader wiring
    # ------------------------------------------------------------------
    def _make_loader(self, tab: TextProductTab) -> ProductLoader:
        """Bind a zero-arg loader for a configured product tab."""
        cwa_office = getattr(self._location, "cwa_office", None)
        latitude = getattr(self._location, "latitude", None)
        longitude = getattr(self._location, "longitude", None)

        async def _loader():
            if tab.requires_cwa and cwa_office is None:
                return None
            if tab.loader_kind == "current":
                return await self._service.get(tab.product_type, cwa_office)
            if tab.loader_kind == "nws_history":
                return await self._service.get_history(tab.product_type, cwa_office, limit=1)
            if latitude is None or longitude is None:
                return None
            if tab.loader_kind == "spc_outlook":
                return await self._service.get_iem_afos(
                    "SWODY1",
                    timeout=4.0,
                )
            if tab.loader_kind == "spc_mcd":
                return await self._service.get_iem_spc_mcds(
                    latitude,
                    longitude,
                    max_items=3,
                    timeout=4.0,
                )
            if tab.loader_kind == "spc_watches_current":
                return await self._service.get_iem_spc_watches(
                    latitude,
                    longitude,
                    max_items=3,
                    timeout=4.0,
                )
            if tab.loader_kind == "wpc_ero":
                return await self._service.get_iem_wpc_outlook(
                    latitude,
                    longitude,
                    day=1,
                    limit=1,
                    max_items=3,
                    timeout=4.0,
                )
            if tab.loader_kind == "wpc_mpd":
                return await self._service.get_iem_wpc_mpds(
                    latitude,
                    longitude,
                    max_items=3,
                    timeout=4.0,
                )
            return None

        return _loader

    def _make_advanced_lookup_opener(self, product_type: str):
        """Bind an advanced lookup opener for ``product_type``."""

        def _open() -> None:
            show_advanced_text_product_dialog(
                self,
                self._location,
                self._service,
                initial_product_type=product_type,
                app=self._app,
            )

        return _open

    def _on_panel_availability_resolved(
        self,
        panel: ForecastProductPanel,
        has_product: bool,
    ) -> None:
        """
        Remove optional tabs whose product lookup completed with no content.

        AFD stays visible even when empty because it is the primary forecaster
        notes product and gives users a stable place to retry/read status.
        HWO and SPS are supplemental; when NWS confirms there is no product for
        the office, hiding those tabs avoids advertising unavailable content.
        Fetch errors report ``has_product=True`` so the tab remains available
        with its retry button.
        """
        if has_product or getattr(panel, "product_type", None) == "AFD":
            return

        try:
            index = self.panels.index(panel)
        except ValueError:
            return

        if len(self.panels) <= 1:
            return

        deleted = self.notebook.DeletePage(index)
        if deleted is False:
            logger.debug(
                "Notebook refused to remove empty %s page",
                getattr(panel, "product_type", "unknown"),
            )
            return

        del self.panels[index]

    # ------------------------------------------------------------------
    # Key events
    # ------------------------------------------------------------------
    def _on_page_changed(self, event) -> None:
        """Lazy-load supplemental tabs when the user selects them."""
        selection = self.notebook.GetSelection()
        if 0 <= selection < len(self.panels):
            self.panels[selection].ensure_loaded()
        event.Skip()

    def _on_key(self, event) -> None:
        """ESC closes the dialog."""
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.Close()
        else:
            event.Skip()

    def _on_close(self, event) -> None:
        """Close button handler."""
        del event
        self.EndModal(wx.ID_CLOSE)


def show_forecast_products_dialog(
    parent,
    location: Location,
    forecast_product_service: ForecastProductService,
    ai_explainer: AIExplainer | None,
    app: object | None = None,
) -> None:
    """Show the Forecast Products dialog modally and destroy on close."""
    try:
        parent_ctrl = getattr(parent, "control", parent)
        dlg = ForecastProductsDialog(
            parent_ctrl, location, forecast_product_service, ai_explainer, app=app
        )
        dlg.ShowModal()
        dlg.Destroy()
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Failed to show forecast products dialog: {exc}")
        wx.MessageBox(
            f"Failed to open Forecaster Notes: {exc}",
            "Error",
            wx.OK | wx.ICON_ERROR,
        )
