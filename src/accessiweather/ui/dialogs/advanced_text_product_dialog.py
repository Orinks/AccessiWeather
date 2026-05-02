"""Advanced text product lookup dialog for Forecaster Notes."""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import UTC, datetime, time
from typing import TYPE_CHECKING, Any

import wx

if TYPE_CHECKING:
    from ...models import Location, TextProduct
    from ...services.forecast_product_service import ForecastProductService

logger = logging.getLogger(__name__)

_NWS_PRODUCT_TYPES = {"AFD", "HWO", "SPS", "CLI", "CF6", "RER", "LSR", "PNS"}
_SOURCE_PREFER_NWS = "Prefer NWS when available"
_SOURCE_IEM_ONLY = "IEM AFOS only"
_SOURCE_NWS_ONLY = "NWS history only"
_SPC_OUTLOOK_RE = re.compile(r"(?:SPC\s*)?DAY\s*([1-8])\s*(?:CONVECTIVE\s*)?OUTLOOK", re.I)
_WPC_OUTLOOK_RE = re.compile(
    r"(?:WPC\s*)?DAY\s*([1-8])\s*(?:EXCESSIVE\s*RAINFALL\s*)?OUTLOOK",
    re.I,
)
_PRODUCT_PRESETS: dict[str, str] = {
    "Custom product ID": "",
    "Local Area Forecast Discussion": "AFD",
    "Local Hazardous Weather Outlook": "HWO",
    "Local Special Weather Statement": "SPS",
    "Local Storm Report": "LSR",
    "Daily Climate Report": "CLI",
    "Monthly Climate Report": "CF6",
    "Record Event Report": "RER",
    "Public Information Statement": "PNS",
    "SPC Day 1 Outlook (Storm Prediction Center)": "SPC Day 1 Outlook",
    "SPC Day 2 Outlook (Storm Prediction Center)": "SPC Day 2 Outlook",
    "SPC Day 3 Outlook (Storm Prediction Center)": "SPC Day 3 Outlook",
    "SPC Day 4 Outlook (Storm Prediction Center)": "SPC Day 4 Outlook",
    "SPC Day 5 Outlook (Storm Prediction Center)": "SPC Day 5 Outlook",
    "SPC Day 6 Outlook (Storm Prediction Center)": "SPC Day 6 Outlook",
    "SPC Day 7 Outlook (Storm Prediction Center)": "SPC Day 7 Outlook",
    "SPC Day 8 Outlook (Storm Prediction Center)": "SPC Day 8 Outlook",
    "SPC MCD (Mesoscale Discussions) near location": "SPC MCD",
    "SPC Watches (Storm Prediction Center) near location": "SPC Watches",
    "WPC Day 1 ERO (Excessive Rainfall Outlook)": "WPC Day 1 Excessive Rainfall Outlook",
    "WPC Day 2 ERO (Excessive Rainfall Outlook)": "WPC Day 2 Excessive Rainfall Outlook",
    "WPC Day 3 ERO (Excessive Rainfall Outlook)": "WPC Day 3 Excessive Rainfall Outlook",
    "WPC MPD (Mesoscale Precipitation Discussion) near location": "WPC MPD",
    "WPC Short Range Discussion (Weather Prediction Center)": "PMDSPD",
    "WPC Extended Discussion (Weather Prediction Center)": "PMDEPD",
    "WPC Quantitative Precipitation Discussion (Weather Prediction Center)": "QPFPFD",
    "SPC Day 1 AFOS Outlook (Storm Prediction Center)": "SWODY1",
    "SPC Day 2 AFOS Outlook (Storm Prediction Center)": "SWODY2",
    "SPC Day 3 AFOS Outlook (Storm Prediction Center)": "SWODY3",
}
_LEFT = getattr(wx, "LEFT", wx.ALL)
_RIGHT = getattr(wx, "RIGHT", wx.ALL)
_TOP = getattr(wx, "TOP", wx.ALL)
_EVT_CHOICE = getattr(wx, "EVT_CHOICE", wx.EVT_BUTTON)


class AdvancedTextProductDialog(wx.Dialog):
    """Dialog for looking up NWS/IEM text products beyond the default tabs."""

    def __init__(
        self,
        parent: wx.Window,
        location: Location,
        forecast_product_service: ForecastProductService,
        initial_product_type: str = "AFD",
        app: object | None = None,
    ) -> None:
        """Initialize the dialog for the selected location and default product."""
        super().__init__(
            parent,
            title="Advanced Text Product Lookup",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self._location = location
        self._service = forecast_product_service
        self._app = app

        self._create_widgets(initial_product_type)
        self._bind_events()
        self.SetSize((760, 620))
        self.CenterOnParent()

    def _create_widgets(self, initial_product_type: str) -> None:
        """Build the dialog controls with adjacent labels for screen readers."""
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        self.product_preset_label = wx.StaticText(
            self,
            label="Product preset:",
        )
        main_sizer.Add(self.product_preset_label, 0, _LEFT | _RIGHT | _TOP | wx.EXPAND, 8)
        self.product_preset_choice = wx.Choice(self, choices=list(_PRODUCT_PRESETS))
        self.product_preset_choice.SetSelection(0)
        main_sizer.Add(self.product_preset_choice, 0, wx.ALL | wx.EXPAND, 8)

        self.product_label = wx.StaticText(
            self,
            label=(
                "Product ID or structured product (examples: AFD, HWO, SWODY1, "
                "SPC MCD (Mesoscale Discussion), "
                "WPC MPD (Mesoscale Precipitation Discussion)):"
            ),
        )
        main_sizer.Add(self.product_label, 0, _LEFT | _RIGHT | _TOP | wx.EXPAND, 8)
        self.product_input = wx.TextCtrl(self, value=initial_product_type)
        main_sizer.Add(self.product_input, 0, wx.ALL | wx.EXPAND, 8)

        cwa_office = getattr(self._location, "cwa_office", "") or ""
        self.location_label = wx.StaticText(
            self,
            label="NWS office for local products (optional, for example RAH):",
        )
        main_sizer.Add(self.location_label, 0, _LEFT | _RIGHT | wx.EXPAND, 8)
        self.location_input = wx.TextCtrl(self, value=cwa_office)
        main_sizer.Add(self.location_input, 0, wx.ALL | wx.EXPAND, 8)

        self.limit_label = wx.StaticText(self, label="Maximum products to retrieve:")
        main_sizer.Add(self.limit_label, 0, _LEFT | _RIGHT | wx.EXPAND, 8)
        self.limit_input = wx.TextCtrl(self, value="1")
        main_sizer.Add(self.limit_input, 0, wx.ALL | wx.EXPAND, 8)

        self.start_label = wx.StaticText(
            self,
            label="Start or valid time (optional, YYYY-MM-DD or ISO UTC):",
        )
        main_sizer.Add(self.start_label, 0, _LEFT | _RIGHT | wx.EXPAND, 8)
        self.start_input = wx.TextCtrl(self, value="")
        main_sizer.Add(self.start_input, 0, wx.ALL | wx.EXPAND, 8)

        self.end_label = wx.StaticText(
            self,
            label="End time for historical text products (optional, YYYY-MM-DD or ISO UTC):",
        )
        main_sizer.Add(self.end_label, 0, _LEFT | _RIGHT | wx.EXPAND, 8)
        self.end_input = wx.TextCtrl(self, value="")
        main_sizer.Add(self.end_input, 0, wx.ALL | wx.EXPAND, 8)

        self.source_label = wx.StaticText(self, label="Lookup source:")
        main_sizer.Add(self.source_label, 0, _LEFT | _RIGHT | wx.EXPAND, 8)
        self.source_choice = wx.Choice(
            self,
            choices=[_SOURCE_PREFER_NWS, _SOURCE_IEM_ONLY, _SOURCE_NWS_ONLY],
        )
        self.source_choice.SetSelection(0)
        main_sizer.Add(self.source_choice, 0, wx.ALL | wx.EXPAND, 8)

        self.result_label = wx.StaticText(self, label="Lookup results:")
        main_sizer.Add(self.result_label, 0, _LEFT | _RIGHT | wx.EXPAND, 8)
        self.result_text = wx.TextCtrl(
            self,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL,
            value="Choose a product and press Lookup.",
        )
        main_sizer.Add(self.result_text, 1, wx.ALL | wx.EXPAND, 8)

        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.lookup_button = wx.Button(self, wx.ID_OK, label="Lookup")
        self.close_button = wx.Button(self, wx.ID_CLOSE, label="Close")
        button_sizer.AddStretchSpacer()
        button_sizer.Add(self.lookup_button, 0, wx.RIGHT, 8)
        button_sizer.Add(self.close_button, 0)
        main_sizer.Add(button_sizer, 0, wx.ALL | wx.EXPAND, 8)

        self.SetSizer(main_sizer)

    def _bind_events(self) -> None:
        """Bind buttons and Escape handling."""
        self.product_preset_choice.Bind(_EVT_CHOICE, self._on_product_preset)
        self.lookup_button.Bind(wx.EVT_BUTTON, self._on_lookup)
        self.close_button.Bind(wx.EVT_BUTTON, self._on_close)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_key)

    def _on_lookup(self, event) -> None:
        """Start a lookup from the current form values."""
        del event
        self.result_text.SetValue("Looking up product...")
        self._schedule_lookup(self._lookup())

    def _schedule_lookup(self, coro) -> None:
        """Dispatch a lookup coroutine through the app loop when available."""
        runner = getattr(self._app, "run_async", None) if self._app is not None else None
        if runner is not None:
            runner(self._run_lookup(coro))
            return

        try:
            asyncio.ensure_future(self._run_lookup(coro))
        except RuntimeError:
            try:
                text = self._run_lookup_sync()
            except Exception as exc:  # noqa: BLE001
                text = f"Lookup failed: {exc}"
            self.result_text.SetValue(text)
            coro.close()

    async def _run_lookup(self, coro) -> None:
        """Await a lookup and marshal the result back to the UI thread."""
        try:
            text = await coro
        except Exception as exc:  # noqa: BLE001
            logger.warning("Advanced text product lookup failed: %s", exc)
            text = f"Lookup failed: {exc}"
        wx.CallAfter(self.result_text.SetValue, text)

    def _run_lookup_sync(self) -> str:
        """Run a lookup synchronously for stub GUI tests."""
        loop = asyncio.new_event_loop()
        try:
            text = loop.run_until_complete(self._lookup())
        finally:
            loop.close()
        self.result_text.SetValue(text)
        return text

    async def _lookup(self) -> str:
        product_id = self.product_input.GetValue().strip().upper()
        location = self.location_input.GetValue().strip().upper()
        limit = self._parse_limit(self.limit_input.GetValue())
        source = self.source_choice.GetStringSelection() or _SOURCE_PREFER_NWS
        try:
            start = self._parse_optional_datetime(self.start_input.GetValue())
            end = self._parse_optional_datetime(self.end_input.GetValue())
        except ValueError as exc:
            return str(exc)

        if not product_id:
            return "Enter a product ID or SPC product name."

        spc_outlook_day = self._spc_outlook_day(product_id)
        if spc_outlook_day is not None:
            return await self._lookup_spc_outlook(spc_outlook_day)
        if product_id in {"SPC MCD", "MCD", "SPC MESOSCALE DISCUSSION"}:
            return await self._lookup_spc_mcd()
        if product_id in {"SPC WATCH", "SPC WATCHES", "WATCHES"}:
            return await self._lookup_spc_watches(start)
        wpc_outlook_day = self._wpc_outlook_day(product_id)
        if wpc_outlook_day is not None:
            return await self._lookup_wpc_outlook(wpc_outlook_day, start, limit)
        if product_id in {"WPC MPD", "MPD", "WPC MESOSCALE PRECIPITATION DISCUSSION"}:
            return await self._lookup_wpc_mpd()

        if source != _SOURCE_IEM_ONLY and product_id in _NWS_PRODUCT_TYPES and location:
            products = await self._lookup_nws_history(product_id, location, limit, start, end)
            if products:
                return self._format_products("NWS", products)
            if source == _SOURCE_NWS_ONLY:
                return f"No NWS {product_id} history found for {location}."

        product = await self._service.get_iem_afos(
            self._iem_pil(product_id, location),
            limit=limit,
            start=start,
            end=end,
        )
        return self._format_products("IEM", product)

    async def _lookup_nws_history(
        self,
        product_id: str,
        location: str,
        limit: int,
        start: datetime | None,
        end: datetime | None,
    ) -> list[TextProduct]:
        history = await self._service.get_history(
            product_id,
            location,
            limit=limit,
            start=start,
            end=end,
        )
        if history is None:
            return []
        if isinstance(history, list):
            return history
        return [history]

    async def _lookup_spc_outlook(self, day: int) -> str:
        lat = getattr(self._location, "latitude", None)
        lon = getattr(self._location, "longitude", None)
        if lat is None or lon is None:
            return "SPC outlook lookup needs a location with latitude and longitude."
        product = await self._service.get_iem_spc_outlook(lat, lon, day=day, current=True)
        return self._format_products("IEM", product)

    async def _lookup_spc_mcd(self) -> str:
        lat = getattr(self._location, "latitude", None)
        lon = getattr(self._location, "longitude", None)
        if lat is None or lon is None:
            return (
                "SPC MCD (Mesoscale Discussion) lookup needs a location with "
                "latitude and longitude."
            )
        product = await self._service.get_iem_spc_mcds(lat, lon)
        return self._format_products("IEM", product)

    async def _lookup_spc_watches(self, valid_at: datetime | None) -> str:
        lat = getattr(self._location, "latitude", None)
        lon = getattr(self._location, "longitude", None)
        if lat is None or lon is None:
            return "SPC watch lookup needs a location with latitude and longitude."
        product = await self._service.get_iem_spc_watches(lat, lon, valid_at=valid_at)
        return self._format_products("IEM", product)

    async def _lookup_wpc_outlook(
        self,
        day: int,
        valid_at: datetime | None,
        limit: int,
    ) -> str:
        lat = getattr(self._location, "latitude", None)
        lon = getattr(self._location, "longitude", None)
        if lat is None or lon is None:
            return "WPC outlook lookup needs a location with latitude and longitude."
        product = await self._service.get_iem_wpc_outlook(
            lat,
            lon,
            day=day,
            valid_at=valid_at,
            limit=limit,
        )
        return self._format_products("IEM", product)

    async def _lookup_wpc_mpd(self) -> str:
        lat = getattr(self._location, "latitude", None)
        lon = getattr(self._location, "longitude", None)
        if lat is None or lon is None:
            return (
                "WPC MPD (Mesoscale Precipitation Discussion) lookup needs a location "
                "with latitude and longitude."
            )
        product = await self._service.get_iem_wpc_mpds(lat, lon)
        return self._format_products("IEM", product)

    def _on_product_preset(self, event) -> None:
        """Apply a selected product preset to the editable product field."""
        del event
        label = self.product_preset_choice.GetStringSelection()
        product_id = _PRODUCT_PRESETS.get(label, "")
        if product_id:
            self.product_input.SetValue(product_id)
            if product_id not in _NWS_PRODUCT_TYPES:
                self.source_choice.SetSelection(1)

    @staticmethod
    def _parse_limit(value: str) -> int:
        try:
            limit = int(value)
        except ValueError:
            return 1
        return max(1, min(limit, 25))

    @staticmethod
    def _parse_optional_datetime(value: str) -> datetime | None:
        text = value.strip()
        if not text:
            return None
        try:
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
                parsed = datetime.combine(datetime.fromisoformat(text).date(), time(), tzinfo=UTC)
            else:
                normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
                parsed = datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise ValueError("Enter dates as YYYY-MM-DD or ISO timestamps.") from exc
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed

    @staticmethod
    def _spc_outlook_day(product_id: str) -> int | None:
        match = _SPC_OUTLOOK_RE.fullmatch(product_id)
        if match is None:
            return None
        return int(match.group(1))

    @staticmethod
    def _wpc_outlook_day(product_id: str) -> int | None:
        match = _WPC_OUTLOOK_RE.fullmatch(product_id)
        if match is None:
            return None
        return int(match.group(1))

    @staticmethod
    def _iem_pil(product_id: str, location: str) -> str:
        if product_id in _NWS_PRODUCT_TYPES and location:
            return f"{product_id}{location}"
        return product_id

    @staticmethod
    def _format_products(source: str, products: Any) -> str:
        if products is None:
            return f"Source: {source}\n\nNo product found."
        if not isinstance(products, list):
            products = [products]
        if not products:
            return f"Source: {source}\n\nNo product found."

        chunks = [f"Source: {source}"]
        for product in products:
            headline = getattr(product, "headline", None)
            issuance = getattr(product, "issuance_time", None)
            issued = issuance.isoformat() if isinstance(issuance, datetime) else "unknown"
            chunks.append(
                "\n".join(
                    part
                    for part in (
                        "",
                        f"Product: {getattr(product, 'product_type', 'unknown')}",
                        f"Issued: {issued}",
                        f"Headline: {headline}" if headline else "",
                        getattr(product, "product_text", ""),
                    )
                    if part
                )
            )
        return "\n\n".join(chunks)

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


def show_advanced_text_product_dialog(
    parent,
    location: Location,
    forecast_product_service: ForecastProductService,
    *,
    initial_product_type: str = "AFD",
    app: object | None = None,
) -> None:
    """Show the advanced text product lookup dialog modally."""
    try:
        parent_ctrl = getattr(parent, "control", parent)
        dlg = AdvancedTextProductDialog(
            parent_ctrl,
            location,
            forecast_product_service,
            initial_product_type=initial_product_type,
            app=app,
        )
        dlg.ShowModal()
        dlg.Destroy()
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to show advanced text product dialog: %s", exc)
        wx.MessageBox(
            f"Failed to open Advanced Text Product Lookup: {exc}",
            "Error",
            wx.OK | wx.ICON_ERROR,
        )
