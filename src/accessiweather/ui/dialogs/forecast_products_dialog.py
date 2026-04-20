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
from typing import TYPE_CHECKING, Literal, cast

import wx

from .forecast_product_panel import ForecastProductPanel

ProductType = Literal["AFD", "HWO", "SPS"]

if TYPE_CHECKING:
    from ...ai_explainer import AIExplainer
    from ...models import Location
    from ...services.forecast_product_service import ForecastProductService

logger = logging.getLogger(__name__)


class ForecastProductsDialog(wx.Dialog):
    """Tabbed dialog showing NWS AFD, HWO, and SPS for a US location."""

    _TABS: tuple[tuple[str, str], ...] = (
        ("AFD", "AFD"),
        ("HWO", "HWO"),
        ("SPS", "SPS"),
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
            title="Forecast Products",
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

        # Focus the AFD tab's TextCtrl once the dialog has laid out.
        wx.CallAfter(self._focus_active_tab)

    def _create_widgets(self) -> None:
        """Construct the notebook with three product panels."""
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        self.notebook = wx.Notebook(self)

        self.panels: list[ForecastProductPanel] = []
        cwa_office = getattr(self._location, "cwa_office", None)
        location_name = getattr(self._location, "name", "")

        for product_type, tab_label in self._TABS:
            typed_product_type = cast("ProductType", product_type)
            loader = self._make_loader(typed_product_type)
            panel = ForecastProductPanel(
                parent=self.notebook,
                product_type=typed_product_type,
                product_loader=loader,
                ai_explainer=self._ai_explainer,
                cwa_office=cwa_office,
                location_name=location_name,
                app=self._app,
            )
            self.notebook.AddPage(panel, tab_label)
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
        self.Bind(wx.EVT_CHAR_HOOK, self._on_key)

    # ------------------------------------------------------------------
    # Loader wiring
    # ------------------------------------------------------------------
    def _make_loader(self, product_type: ProductType):
        """Bind a zero-arg loader for ``product_type`` against the service."""
        cwa_office = getattr(self._location, "cwa_office", None)

        async def _loader():
            if cwa_office is None:
                return None
            return await self._service.get(product_type, cwa_office)

        return _loader

    # ------------------------------------------------------------------
    # Focus + key events
    # ------------------------------------------------------------------
    def _focus_active_tab(self) -> None:
        """Move focus to the currently-active tab's product TextCtrl."""
        try:
            idx = self.notebook.GetSelection()
        except Exception:  # noqa: BLE001
            idx = 0
        if idx is None or idx < 0:
            idx = 0
        if 0 <= idx < len(self.panels):
            try:
                self.panels[idx].product_textctrl.SetFocus()
            except Exception:  # noqa: BLE001
                logger.debug("Unable to move focus to product TextCtrl", exc_info=True)

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
            f"Failed to open Forecast Products: {exc}",
            "Error",
            wx.OK | wx.ICON_ERROR,
        )
