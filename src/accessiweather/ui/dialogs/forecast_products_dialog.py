"""
Forecast Products dialog — tabbed host for forecaster-note and surf-condition panels.

A ``wx.Notebook`` with :class:`ForecastProductPanel` pages for official NWS
text products and clearly labelled source-derived conditions.
Tab switches deliberately do NOT grab focus — the notebook tab strip stays
the active focus level until the user Tabs into content, matching the
accessible notebook contract.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

import wx

from ...iem_client import IemProductFetchError
from ...models import TextProduct
from .advanced_text_product_dialog import show_advanced_text_product_dialog
from .forecast_product_panel import ForecastProductPanel
from .national_products_dialog import show_national_products_dialog

_ACTIVE_IEM_LOADER_KINDS = {
    "spc_outlook",
    "spc_mcd",
    "spc_watches_current",
    "wpc_ero",
    "wpc_mpd",
}
_INACTIVE_IEM_SUMMARY_PREFIXES = (
    "No active ",
    "No matching ",
    "No structured data returned.",
)

if TYPE_CHECKING:
    from ...ai_explainer import AIExplainer
    from ...models import Location
    from ...services.forecast_product_service import ForecastProductService

logger = logging.getLogger(__name__)

ProductResult = TextProduct | list[TextProduct] | None
ProductLoader = Callable[[], Awaitable[ProductResult]]


@dataclass(frozen=True)
class TextProductTab:
    """Configuration for a Forecaster Notes product tab."""

    product_type: str
    label: str
    loader_kind: str
    requires_cwa: bool = False


class ForecastProductsDialog(wx.Dialog):
    """Tabbed dialog showing available text products and surf/beach conditions."""

    _TABS: tuple[TextProductTab, ...] = (
        TextProductTab("AFD", "Area Forecast Discussion", "current", requires_cwa=True),
        TextProductTab("HWO", "Hazardous Weather Outlook", "current", requires_cwa=True),
        TextProductTab("SPS", "Special Weather Statement", "current", requires_cwa=True),
        TextProductTab("SURF", "Surf/Beach Conditions", "surf_conditions"),
        TextProductTab("CLI", "Daily Climate Report", "daily_climate"),
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
        self._pending_iem_tabs: tuple[TextProductTab, ...] = ()

        self._create_widgets()
        self._bind_events()
        self._schedule_active_iem_tab_check()

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

        pending_iem_tabs: list[TextProductTab] = []
        cwa_office = getattr(self._location, "cwa_office", None)
        for tab in self._TABS:
            if tab.requires_cwa and not cwa_office:
                continue
            if tab.loader_kind in _ACTIVE_IEM_LOADER_KINDS:
                pending_iem_tabs.append(tab)
                continue
            is_first_tab = len(self.panels) == 0
            self._add_tab_panel(tab, autoload=self._should_autoload_tab(tab, is_first_tab))
        self._pending_iem_tabs = tuple(pending_iem_tabs)

        main_sizer.Add(self.notebook, 1, wx.ALL | wx.EXPAND, 8)

        self.active_iem_status = wx.StaticText(
            self,
            label="Checking active SPC and WPC products...",
        )
        main_sizer.Add(self.active_iem_status, 0, wx.LEFT | wx.RIGHT | wx.EXPAND, 8)

        # Close button row.
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.national_products_button = wx.Button(self, label="&National Products")
        button_sizer.Add(self.national_products_button, 0)
        self.close_button = wx.Button(self, wx.ID_CLOSE, label="&Close")
        button_sizer.AddStretchSpacer()
        button_sizer.Add(self.close_button, 0)
        main_sizer.Add(button_sizer, 0, wx.ALL | wx.EXPAND, 8)

        self.SetSizer(main_sizer)

    @staticmethod
    def _should_autoload_tab(tab: TextProductTab, is_first_tab: bool) -> bool:
        """Return whether a tab should begin loading when the dialog opens."""
        return is_first_tab or tab.loader_kind == "daily_climate"

    def _add_tab_panel(
        self,
        tab: TextProductTab,
        *,
        autoload: bool,
        product_override: object | None = None,
    ) -> ForecastProductPanel:
        """Add a notebook page for a resolved tab."""
        cwa_office = getattr(self._location, "cwa_office", None)
        location_name = getattr(self._location, "name", "")
        loader: ProductLoader
        if product_override is None:
            loader = self._make_loader(tab)
        else:

            async def _override_loader() -> ProductResult:
                return cast(ProductResult, product_override)

            loader = _override_loader

        panel_cwa = (
            cwa_office
            if tab.requires_cwa or tab.loader_kind in {"daily_climate", "surf_conditions"}
            else "IEM"
        )
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
            autoload=autoload,
        )
        self.notebook.AddPage(panel, tab.label)
        self.panels.append(panel)
        return panel

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
        self.national_products_button.Bind(wx.EVT_BUTTON, self._on_national_products)
        self.notebook.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self._on_page_changed)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_key)

    def _schedule_active_iem_tab_check(self) -> None:
        """Check optional IEM tabs in the background and add only active ones."""
        if not self._pending_iem_tabs:
            self._finish_active_iem_tab_check()
            return
        coro = self._resolve_active_iem_tabs()
        runner = getattr(self._app, "run_async", None) if self._app is not None else None
        if runner is not None:
            runner(coro)
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            coro.close()
            self._finish_active_iem_tab_check()
            return
        loop.create_task(coro)

    async def _resolve_active_iem_tabs(self) -> None:
        """Resolve active IEM products without touching wx objects off-thread."""
        resolved: list[object] = list(
            await asyncio.gather(
                *(self._resolve_active_iem_tab(tab) for tab in self._pending_iem_tabs),
                return_exceptions=True,
            )
        )
        wx.CallAfter(self._add_resolved_active_iem_tabs, resolved)

    async def _resolve_active_iem_tab(
        self, tab: TextProductTab
    ) -> tuple[TextProductTab, object] | None:
        product = await self._make_loader(tab)()
        if product is None:
            return None
        return tab, product

    def _add_resolved_active_iem_tabs(self, resolved: list[object]) -> None:
        for item in resolved:
            if isinstance(item, Exception):
                logger.info("Optional active IEM tab check failed: %s", item)
                continue
            if item is None:
                continue
            if not isinstance(item, tuple) or len(item) != 2:
                continue
            tab, product = item
            self._add_tab_panel(tab, autoload=False, product_override=product)
        self._finish_active_iem_tab_check()

    def _finish_active_iem_tab_check(self) -> None:
        status = getattr(self, "active_iem_status", None)
        if status is not None:
            status.SetLabel("")
            status.Hide()
            self.Layout()

    # ------------------------------------------------------------------
    # Loader wiring
    # ------------------------------------------------------------------
    @staticmethod
    def _active_iem_tab_product_or_none(product):
        """Return ``None`` when an active-tab IEM summary has no current product."""
        text = getattr(product, "product_text", "")
        if not isinstance(text, str):
            return product
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith(("Generated:",)):
                continue
            if any(stripped.startswith(prefix) for prefix in _INACTIVE_IEM_SUMMARY_PREFIXES):
                return None
        return product

    async def _load_active_iem_tab_product(self, product_awaitable: Awaitable[object]):
        """Load an optional active IEM tab, hiding it when IEM is slow or empty."""
        try:
            product = await product_awaitable
        except IemProductFetchError as exc:
            logger.info("Optional active IEM tab lookup failed: %s", exc)
            return None
        return self._active_iem_tab_product_or_none(product)

    def _make_loader(self, tab: TextProductTab) -> ProductLoader:
        """Bind a zero-arg loader for a configured product tab."""
        cwa_office = getattr(self._location, "cwa_office", None)
        latitude = getattr(self._location, "latitude", None)
        longitude = getattr(self._location, "longitude", None)

        async def _loader():
            if tab.requires_cwa and cwa_office is None:
                return None
            if tab.loader_kind == "current":
                return await self._service.get(cast(Any, tab.product_type), str(cwa_office))
            if tab.loader_kind == "surf_conditions":
                return await self._service.get_surf_conditions_for_location(
                    self._location,
                    weather_client=getattr(self._app, "weather_client", None),
                )
            if tab.loader_kind == "nws_history":
                return await self._service.get_history(tab.product_type, str(cwa_office), limit=1)
            if tab.loader_kind == "daily_climate":
                product = await self._service.get_daily_climate_report_for_location(self._location)
                self._check_daily_climate_notification(product)
                return product
            if latitude is None or longitude is None:
                return None
            if tab.loader_kind == "spc_outlook":
                return await self._load_active_iem_tab_product(
                    self._service.get_iem_spc_outlook(
                        latitude,
                        longitude,
                        day=1,
                        current=True,
                        max_items=3,
                        timeout=10.0,
                    )
                )
            if tab.loader_kind == "spc_mcd":
                return await self._load_active_iem_tab_product(
                    self._service.get_iem_spc_mcds(
                        latitude,
                        longitude,
                        max_items=3,
                        timeout=10.0,
                    )
                )
            if tab.loader_kind == "spc_watches_current":
                return await self._load_active_iem_tab_product(
                    self._service.get_iem_spc_watches(
                        latitude,
                        longitude,
                        max_items=3,
                        timeout=10.0,
                    )
                )
            if tab.loader_kind == "wpc_ero":
                return await self._load_active_iem_tab_product(
                    self._service.get_iem_wpc_outlook(
                        latitude,
                        longitude,
                        day=1,
                        limit=1,
                        max_items=3,
                        timeout=10.0,
                    )
                )
            if tab.loader_kind == "wpc_mpd":
                return await self._load_active_iem_tab_product(
                    self._service.get_iem_wpc_mpds(
                        latitude,
                        longitude,
                        max_items=3,
                        timeout=10.0,
                    )
                )
            return None

        return _loader

    def _check_daily_climate_notification(self, product: TextProduct | None) -> None:
        """Pipe loaded CLI reports through the opt-in event notification path."""
        if product is None or self._app is None:
            return
        try:
            app = cast(Any, self._app)
            settings = app.config_manager.get_settings()
            if not getattr(settings, "notify_daily_climate_report_update", False):
                return
            manager_getter = getattr(self.GetParent(), "_get_notification_event_manager", None)
            manager = manager_getter() if callable(manager_getter) else None
            if manager is None:
                return
            event = cast(Any, manager).check_daily_climate_report(
                product,
                settings,
                self._location.name,
            )
            if event is None:
                return
            notifier = getattr(app, "notifier", None)
            if notifier is None:
                return
            notifier.send_notification(
                title=event.title,
                message=event.message,
                timeout=10,
                sound_event=event.sound_event,
                play_sound=bool(getattr(settings, "sound_enabled", False)),
            )
        except Exception:  # noqa: BLE001
            logger.debug("Daily climate report notification check skipped", exc_info=True)

    def _make_advanced_lookup_opener(self, product_type: str):
        """Bind an advanced lookup opener for ``product_type``."""
        initial_product_type = "SRF" if product_type == "SURF" else product_type

        def _open() -> None:
            show_advanced_text_product_dialog(
                self,
                self._location,
                self._service,
                initial_product_type=initial_product_type,
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
        HWO, SPS, and surf/beach conditions are supplemental; when lookup
        confirms there is no content, hiding those tabs avoids advertising
        unavailable content.
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

    def _on_national_products(self, event) -> None:
        """Open the national text products dialog."""
        del event
        show_national_products_dialog(
            self,
            self._service,
            self._ai_explainer,
            app=self._app,
        )


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
