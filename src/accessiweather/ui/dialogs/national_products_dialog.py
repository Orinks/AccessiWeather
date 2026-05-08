"""Dialog for latest national forecaster text products."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

import wx

from ...models import TextProduct
from .forecast_product_panel import ForecastProductPanel

if TYPE_CHECKING:
    from ...ai_explainer import AIExplainer
    from ...services.forecast_product_service import ForecastProductService

logger = logging.getLogger(__name__)

ProductResult = TextProduct | list[TextProduct] | None
ProductLoader = Callable[[], Awaitable[ProductResult]]


@dataclass(frozen=True)
class NationalProductTab:
    """Configuration for one national AFOS product tab."""

    product_id: str
    label: str


class NationalProductsDialog(wx.Dialog):
    """Tabbed dialog for national WPC, SPC, NHC, and CPC text products."""

    _TABS: tuple[NationalProductTab, ...] = (
        NationalProductTab("PMDSPD", "WPC Short Range"),
        NationalProductTab("PMDEPD", "WPC Medium Range"),
        NationalProductTab("PMDET4", "WPC Extended"),
        NationalProductTab("QPFPFD", "WPC QPF Discussion"),
        NationalProductTab("PMDMRD", "CPC Outlook"),
        NationalProductTab("TWOAT", "NHC Atlantic Outlook"),
        NationalProductTab("TWOEP", "NHC East Pacific Outlook"),
        NationalProductTab("SWODY1", "SPC Day 1 Outlook"),
        NationalProductTab("SWODY2", "SPC Day 2 Outlook"),
        NationalProductTab("SWODY3", "SPC Day 3 Outlook"),
    )

    def __init__(
        self,
        parent: wx.Window,
        forecast_product_service: ForecastProductService,
        ai_explainer: AIExplainer | None,
        app: object | None = None,
    ) -> None:
        """Build the national products dialog."""
        super().__init__(
            parent,
            title="National Products",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self._service = forecast_product_service
        self._ai_explainer = ai_explainer
        self._app = app
        self.panels: list[ForecastProductPanel] = []

        self._create_widgets()
        self._bind_events()

        self.SetSize(wx.Size(760, 620))
        self.CenterOnParent()
        wx.CallAfter(self.notebook.SetFocus)

    def _create_widgets(self) -> None:
        """Construct the product notebook and close button."""
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        self.notebook = wx.Notebook(self)

        for index, tab in enumerate(self._TABS):
            panel = ForecastProductPanel(
                parent=self.notebook,
                product_type=tab.product_id,
                product_loader=self._make_loader(tab.product_id),
                ai_explainer=self._ai_explainer,
                cwa_office="IEM",
                location_name="National",
                app=self._app,
                autoload=index == 0,
            )
            self.notebook.AddPage(panel, tab.label)
            self.panels.append(panel)

        main_sizer.Add(self.notebook, 1, wx.ALL | wx.EXPAND, 8)

        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.close_button = wx.Button(self, wx.ID_CLOSE, label="&Close")
        button_sizer.AddStretchSpacer()
        button_sizer.Add(self.close_button, 0)
        main_sizer.Add(button_sizer, 0, wx.ALL | wx.EXPAND, 8)

        self.SetSizer(main_sizer)

    def _bind_events(self) -> None:
        """Bind close, page-change, and ESC handlers."""
        self.close_button.Bind(wx.EVT_BUTTON, self._on_close)
        self.notebook.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self._on_page_changed)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_key)

    def _make_loader(self, product_id: str) -> ProductLoader:
        """Return a loader for the latest IEM AFOS text product."""

        async def _loader():
            return await self._service.get_iem_afos(product_id, timeout=10.0)

        return _loader

    def _on_page_changed(self, event) -> None:
        """Lazy-load national tabs as the user selects them."""
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


def show_national_products_dialog(
    parent,
    forecast_product_service: ForecastProductService,
    ai_explainer: AIExplainer | None,
    app: object | None = None,
) -> None:
    """Show the National Products dialog modally and destroy it afterward."""
    try:
        parent_ctrl = getattr(parent, "control", parent)
        dlg = NationalProductsDialog(parent_ctrl, forecast_product_service, ai_explainer, app=app)
        dlg.ShowModal()
        dlg.Destroy()
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to show national products dialog: %s", exc)
        wx.MessageBox(
            f"Failed to open National Products: {exc}",
            "Error",
            wx.OK | wx.ICON_ERROR,
        )
