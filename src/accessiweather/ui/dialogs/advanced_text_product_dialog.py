"""Advanced text product lookup dialog for Forecaster Notes."""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from typing import TYPE_CHECKING, Any

import wx

from .async_guard import guard_destroyed

if TYPE_CHECKING:
    from ...models import Location, TextProduct
    from ...services.forecast_product_service import ForecastProductService

logger = logging.getLogger(__name__)

_NWS_PRODUCT_TYPES = {"AFD", "HWO", "SPS", "CLI", "CF6", "RER", "LSR", "PNS"}
_SOURCE_PREFER_NWS = "Prefer NWS when available"
_SOURCE_IEM_ONLY = "IEM AFOS only"
_SOURCE_NWS_ONLY = "NWS history only"
_OFFICE_SELECTED = "Selected location office"
_OFFICE_NONE = "No office or national product"
_OFFICE_CUSTOM = "Custom office below"
_DATE_PRESETS = (
    "Latest or current",
    "Past 24 hours",
    "Past 7 days",
    "Past 30 days",
    "Past 90 days",
    "Past year",
    "Choose start and end dates",
)
_ARCHIVE_START_YEAR = 1983
_MONTH_CHOICES = (
    "01 - January",
    "02 - February",
    "03 - March",
    "04 - April",
    "05 - May",
    "06 - June",
    "07 - July",
    "08 - August",
    "09 - September",
    "10 - October",
    "11 - November",
    "12 - December",
)
_SPC_OUTLOOK_RE = re.compile(r"(?:SPC\s*)?DAY\s*([1-8])\s*(?:CONVECTIVE\s*)?OUTLOOK", re.I)
_WPC_OUTLOOK_RE = re.compile(
    r"(?:WPC\s*)?DAY\s*([1-8])\s*(?:EXCESSIVE\s*RAINFALL\s*)?OUTLOOK",
    re.I,
)
_PIL_RE = re.compile(r"^[A-Z0-9]{3,6}$")
_OFFICE_RE = re.compile(r"^[A-Z0-9]{3}$")
_CENTER_RE = re.compile(r"^[A-Z0-9]{4}$")
_WMO_RE = re.compile(r"^[A-Z]{4}[0-9]{2}$")


@dataclass(frozen=True)
class ProductPreset:
    """One user-facing lookup choice mapped to an API-safe product token."""

    category: str
    label: str
    value: str
    uses_local_office: bool = False
    iem_only: bool = False


_PRODUCT_PRESET_ITEMS: tuple[ProductPreset, ...] = (
    ProductPreset("Custom", "Custom AFOS product ID", ""),
    ProductPreset("Local office", "Local Area Forecast Discussion", "AFD", True),
    ProductPreset("Local office", "Local Hazardous Weather Outlook", "HWO", True),
    ProductPreset("Local office", "Local Special Weather Statement", "SPS", True),
    ProductPreset("Local office", "Local Storm Report", "LSR", True),
    ProductPreset("Local office", "Daily Climate Report", "CLI", True),
    ProductPreset("Local office", "Monthly Climate Report", "CF6", True),
    ProductPreset("Local office", "Record Event Report", "RER", True),
    ProductPreset("Local office", "Public Information Statement", "PNS", True),
    ProductPreset("Point-based SPC", "SPC Day 1 Outlook", "SPC Day 1 Outlook", iem_only=True),
    ProductPreset("Point-based SPC", "SPC Day 2 Outlook", "SPC Day 2 Outlook", iem_only=True),
    ProductPreset("Point-based SPC", "SPC Day 3 Outlook", "SPC Day 3 Outlook", iem_only=True),
    ProductPreset("Point-based SPC", "SPC Day 4 Outlook", "SPC Day 4 Outlook", iem_only=True),
    ProductPreset("Point-based SPC", "SPC Day 5 Outlook", "SPC Day 5 Outlook", iem_only=True),
    ProductPreset("Point-based SPC", "SPC Day 6 Outlook", "SPC Day 6 Outlook", iem_only=True),
    ProductPreset("Point-based SPC", "SPC Day 7 Outlook", "SPC Day 7 Outlook", iem_only=True),
    ProductPreset("Point-based SPC", "SPC Day 8 Outlook", "SPC Day 8 Outlook", iem_only=True),
    ProductPreset("Point-based SPC", "SPC MCD near location", "SPC MCD", iem_only=True),
    ProductPreset("Point-based SPC", "SPC Watches near location", "SPC Watches", iem_only=True),
    ProductPreset(
        "Point-based WPC",
        "WPC Day 1 ERO",
        "WPC Day 1 Excessive Rainfall Outlook",
        iem_only=True,
    ),
    ProductPreset(
        "Point-based WPC",
        "WPC Day 2 ERO",
        "WPC Day 2 Excessive Rainfall Outlook",
        iem_only=True,
    ),
    ProductPreset(
        "Point-based WPC",
        "WPC Day 3 ERO",
        "WPC Day 3 Excessive Rainfall Outlook",
        iem_only=True,
    ),
    ProductPreset("Point-based WPC", "WPC MPD near location", "WPC MPD", iem_only=True),
    ProductPreset("National AFOS", "WPC Short Range Discussion", "PMDSPD", iem_only=True),
    ProductPreset("National AFOS", "WPC Medium Range Discussion", "PMDEPD", iem_only=True),
    ProductPreset("National AFOS", "WPC Extended Discussion", "PMDET4", iem_only=True),
    ProductPreset("National AFOS", "WPC QPF Discussion", "QPFPFD", iem_only=True),
    ProductPreset("National AFOS", "CPC 6-10 and 8-14 Day Outlook", "PMDMRD", iem_only=True),
    ProductPreset("National AFOS", "NHC Atlantic Tropical Weather Outlook", "TWOAT", iem_only=True),
    ProductPreset(
        "National AFOS",
        "NHC East Pacific Tropical Weather Outlook",
        "TWOEP",
        iem_only=True,
    ),
    ProductPreset("National AFOS", "SPC Day 1 AFOS Outlook", "SWODY1", iem_only=True),
    ProductPreset("National AFOS", "SPC Day 2 AFOS Outlook", "SWODY2", iem_only=True),
    ProductPreset("National AFOS", "SPC Day 3 AFOS Outlook", "SWODY3", iem_only=True),
)
_PRODUCT_CATEGORIES = tuple(dict.fromkeys(item.category for item in _PRODUCT_PRESET_ITEMS))
_PRODUCT_PRESETS: dict[str, str] = {item.label: item.value for item in _PRODUCT_PRESET_ITEMS}
_PRODUCT_PRESETS.update(
    {
        "SPC MCD (Mesoscale Discussions) near location": "SPC MCD",
        "SPC Watches (Storm Prediction Center) near location": "SPC Watches",
        "WPC MPD (Mesoscale Precipitation Discussion) near location": "WPC MPD",
        "CPC 6-10 and 8-14 Day Outlook (Climate Prediction Center)": "PMDMRD",
    }
)
_LEFT = getattr(wx, "LEFT", wx.ALL)
_RIGHT = getattr(wx, "RIGHT", wx.ALL)
_TOP = getattr(wx, "TOP", wx.ALL)
_EVT_CHOICE = getattr(wx, "EVT_CHOICE", wx.EVT_BUTTON)
_COMBOBOX = getattr(wx, "ComboBox", wx.Choice)
_CB_READONLY = getattr(wx, "CB_READONLY", 0)
_SPINCTRL: Any = getattr(wx, "SpinCtrl", wx.TextCtrl)
_SCROLLED_WINDOW: Any = getattr(wx, "ScrolledWindow", wx.Panel)


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
        self.SetSize(wx.Size(760, 620))
        self.CenterOnParent()

    def _create_widgets(self, initial_product_type: str) -> None:
        """Build the dialog controls with adjacent labels for screen readers."""
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        self.form_panel = _SCROLLED_WINDOW(self)
        if hasattr(self.form_panel, "SetScrollRate"):
            self.form_panel.SetScrollRate(0, 20)
        form_sizer = wx.BoxSizer(wx.VERTICAL)

        self.product_preset_label = wx.StaticText(
            self.form_panel,
            label="Product group:",
        )
        form_sizer.Add(self.product_preset_label, 0, _LEFT | _RIGHT | _TOP | wx.EXPAND, 8)
        self.product_category_choice = wx.Choice(self.form_panel, choices=list(_PRODUCT_CATEGORIES))
        self.product_category_choice.SetSelection(0)
        form_sizer.Add(self.product_category_choice, 0, wx.ALL | wx.EXPAND, 8)

        self.product_choice_label = wx.StaticText(self.form_panel, label="Product:")
        form_sizer.Add(self.product_choice_label, 0, _LEFT | _RIGHT | _TOP | wx.EXPAND, 8)
        self.product_preset_choice = wx.Choice(
            self.form_panel, choices=self._preset_labels_for_category("Custom")
        )
        self.product_preset_choice.SetSelection(0)
        form_sizer.Add(self.product_preset_choice, 0, wx.ALL | wx.EXPAND, 8)

        self.product_label = wx.StaticText(
            self.form_panel,
            label=(
                "Custom AFOS product ID (3 to 6 letters/numbers). Only needed when "
                "the custom product choice is selected:"
            ),
        )
        form_sizer.Add(self.product_label, 0, _LEFT | _RIGHT | _TOP | wx.EXPAND, 8)
        self.product_input = wx.TextCtrl(self.form_panel, value=initial_product_type)
        form_sizer.Add(self.product_input, 0, wx.ALL | wx.EXPAND, 8)

        cwa_office = getattr(self._location, "cwa_office", "") or ""
        self.location_label = wx.StaticText(
            self.form_panel,
            label="Office selection for local AFOS products:",
        )
        form_sizer.Add(self.location_label, 0, _LEFT | _RIGHT | wx.EXPAND, 8)
        office_choices = [_OFFICE_NONE, _OFFICE_CUSTOM]
        if cwa_office:
            office_choices.insert(0, f"{_OFFICE_SELECTED} ({cwa_office.upper()})")
        self.office_choice = wx.Choice(self.form_panel, choices=office_choices)
        self.office_choice.SetSelection(0)
        form_sizer.Add(self.office_choice, 0, wx.ALL | wx.EXPAND, 8)

        self.custom_office_label = wx.StaticText(
            self.form_panel,
            label="Custom local office (3 letters, for example RAH):",
        )
        form_sizer.Add(self.custom_office_label, 0, _LEFT | _RIGHT | wx.EXPAND, 8)
        self.location_input = wx.TextCtrl(self.form_panel, value=cwa_office)
        form_sizer.Add(self.location_input, 0, wx.ALL | wx.EXPAND, 8)

        self.limit_label = wx.StaticText(self.form_panel, label="Maximum products to retrieve:")
        form_sizer.Add(self.limit_label, 0, _LEFT | _RIGHT | wx.EXPAND, 8)
        try:
            self.limit_input = _SPINCTRL(self.form_panel, min=1, max=25, initial=1)
        except TypeError:
            self.limit_input = _SPINCTRL(self.form_panel, value="1")
        form_sizer.Add(self.limit_input, 0, wx.ALL | wx.EXPAND, 8)

        self.date_preset_label = wx.StaticText(
            self.form_panel,
            label="Date lookup preset:",
        )
        form_sizer.Add(self.date_preset_label, 0, _LEFT | _RIGHT | wx.EXPAND, 8)
        self.date_preset_choice = _COMBOBOX(
            self.form_panel,
            choices=list(_DATE_PRESETS),
            style=_CB_READONLY,
        )
        self.date_preset_choice.SetSelection(0)
        form_sizer.Add(self.date_preset_choice, 0, wx.ALL | wx.EXPAND, 8)

        year_choices = [""] + [
            str(year) for year in range(datetime.now(UTC).year, _ARCHIVE_START_YEAR - 1, -1)
        ]
        day_choices = [""] + [f"{day:02d}" for day in range(1, 32)]

        self.start_date_label = wx.StaticText(
            self.form_panel,
            label=(
                "Start date for archive search (UTC). IEM text products are archive-backed, "
                "but specific products and offices may start later than 1983:"
            ),
        )
        form_sizer.Add(self.start_date_label, 0, _LEFT | _RIGHT | wx.EXPAND, 8)
        start_date_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.start_year_choice = wx.Choice(self.form_panel, choices=year_choices)
        self.start_month_choice = wx.Choice(self.form_panel, choices=[""] + list(_MONTH_CHOICES))
        self.start_day_choice = wx.Choice(self.form_panel, choices=day_choices)
        self.start_year_choice.SetSelection(0)
        self.start_month_choice.SetSelection(0)
        self.start_day_choice.SetSelection(0)
        start_date_sizer.Add(self.start_year_choice, 1, wx.RIGHT, 8)
        start_date_sizer.Add(self.start_month_choice, 1, wx.RIGHT, 8)
        start_date_sizer.Add(self.start_day_choice, 1)
        form_sizer.Add(start_date_sizer, 0, wx.ALL | wx.EXPAND, 8)

        self.end_date_label = wx.StaticText(
            self.form_panel,
            label="End date for archive search (UTC). Leave blank to search through now:",
        )
        form_sizer.Add(self.end_date_label, 0, _LEFT | _RIGHT | wx.EXPAND, 8)
        end_date_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.end_year_choice = wx.Choice(self.form_panel, choices=year_choices)
        self.end_month_choice = wx.Choice(self.form_panel, choices=[""] + list(_MONTH_CHOICES))
        self.end_day_choice = wx.Choice(self.form_panel, choices=day_choices)
        self.end_year_choice.SetSelection(0)
        self.end_month_choice.SetSelection(0)
        self.end_day_choice.SetSelection(0)
        end_date_sizer.Add(self.end_year_choice, 1, wx.RIGHT, 8)
        end_date_sizer.Add(self.end_month_choice, 1, wx.RIGHT, 8)
        end_date_sizer.Add(self.end_day_choice, 1)
        form_sizer.Add(end_date_sizer, 0, wx.ALL | wx.EXPAND, 8)

        self.start_label = wx.StaticText(
            self.form_panel,
            label=(
                "Resolved start or valid time in UTC. For SPC/WPC outlooks and SPC watches, "
                "this is the valid time:"
            ),
        )
        form_sizer.Add(self.start_label, 0, _LEFT | _RIGHT | wx.EXPAND, 8)
        self.start_input = wx.TextCtrl(self.form_panel, value="")
        form_sizer.Add(self.start_input, 0, wx.ALL | wx.EXPAND, 8)

        self.end_label = wx.StaticText(
            self.form_panel,
            label="Resolved end time for historical text products in UTC:",
        )
        form_sizer.Add(self.end_label, 0, _LEFT | _RIGHT | wx.EXPAND, 8)
        self.end_input = wx.TextCtrl(self.form_panel, value="")
        form_sizer.Add(self.end_input, 0, wx.ALL | wx.EXPAND, 8)

        self.order_label = wx.StaticText(self.form_panel, label="Result order:")
        form_sizer.Add(self.order_label, 0, _LEFT | _RIGHT | wx.EXPAND, 8)
        self.order_choice = wx.Choice(self.form_panel, choices=["Newest first", "Oldest first"])
        self.order_choice.SetSelection(0)
        form_sizer.Add(self.order_choice, 0, wx.ALL | wx.EXPAND, 8)

        self.afd_aviation_only = wx.CheckBox(self.form_panel, label="Aviation section only for AFD")
        form_sizer.Add(self.afd_aviation_only, 0, wx.ALL | wx.EXPAND, 8)

        self.center_label = wx.StaticText(
            self.form_panel,
            label="Issuing center filter (optional 4-character ID, for ambiguous AFOS IDs):",
        )
        form_sizer.Add(self.center_label, 0, _LEFT | _RIGHT | wx.EXPAND, 8)
        self.center_input = wx.TextCtrl(self.form_panel, value="")
        form_sizer.Add(self.center_input, 0, wx.ALL | wx.EXPAND, 8)

        self.wmo_label = wx.StaticText(
            self.form_panel,
            label="WMO header filter (optional 6-character TTAAII, for ambiguous AFOS IDs):",
        )
        form_sizer.Add(self.wmo_label, 0, _LEFT | _RIGHT | wx.EXPAND, 8)
        self.wmo_input = wx.TextCtrl(self.form_panel, value="")
        form_sizer.Add(self.wmo_input, 0, wx.ALL | wx.EXPAND, 8)

        self.source_label = wx.StaticText(self.form_panel, label="Lookup source:")
        form_sizer.Add(self.source_label, 0, _LEFT | _RIGHT | wx.EXPAND, 8)
        self.source_choice = wx.Choice(
            self.form_panel,
            choices=[_SOURCE_PREFER_NWS, _SOURCE_IEM_ONLY, _SOURCE_NWS_ONLY],
        )
        self.source_choice.SetSelection(0)
        form_sizer.Add(self.source_choice, 0, wx.ALL | wx.EXPAND, 8)

        self.result_label = wx.StaticText(self.form_panel, label="Lookup results:")
        form_sizer.Add(self.result_label, 0, _LEFT | _RIGHT | wx.EXPAND, 8)
        self.result_text = wx.TextCtrl(
            self.form_panel,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL,
            value="Choose a product and press Lookup.",
        )
        form_sizer.Add(self.result_text, 1, wx.ALL | wx.EXPAND, 8)

        self.form_panel.SetSizer(form_sizer)
        if hasattr(self.form_panel, "FitInside"):
            self.form_panel.FitInside()
        main_sizer.Add(self.form_panel, 1, wx.ALL | wx.EXPAND, 0)

        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.lookup_button = wx.Button(self, wx.ID_OK, label="Lookup")
        self.close_button = wx.Button(self, wx.ID_CLOSE, label="Close")
        button_sizer.AddStretchSpacer()
        button_sizer.Add(self.lookup_button, 0, wx.RIGHT, 8)
        button_sizer.Add(self.close_button, 0)
        main_sizer.Add(button_sizer, 0, wx.ALL | wx.EXPAND, 8)

        self.SetSizer(main_sizer)
        self._set_accessibility_metadata()

    def _bind_events(self) -> None:
        """Bind buttons and Escape handling."""
        self.product_category_choice.Bind(_EVT_CHOICE, self._on_product_category)
        self.product_preset_choice.Bind(_EVT_CHOICE, self._on_product_preset)
        self.date_preset_choice.Bind(_EVT_CHOICE, self._on_date_preset)
        for control in (
            self.start_year_choice,
            self.start_month_choice,
            self.start_day_choice,
            self.end_year_choice,
            self.end_month_choice,
            self.end_day_choice,
        ):
            control.Bind(_EVT_CHOICE, self._on_date_parts)
        self.lookup_button.Bind(wx.EVT_BUTTON, self._on_lookup)
        self.close_button.Bind(wx.EVT_BUTTON, self._on_close)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_key)
        for control in self._focusable_controls():
            control.Bind(wx.EVT_CHAR_HOOK, self._on_key)

    def _focusable_controls(self) -> tuple[Any, ...]:
        """Return controls that should consistently honor dialog-level Escape."""
        return (
            self.product_category_choice,
            self.product_preset_choice,
            self.product_input,
            self.office_choice,
            self.location_input,
            self.limit_input,
            self.date_preset_choice,
            self.start_year_choice,
            self.start_month_choice,
            self.start_day_choice,
            self.end_year_choice,
            self.end_month_choice,
            self.end_day_choice,
            self.start_input,
            self.end_input,
            self.order_choice,
            self.afd_aviation_only,
            self.center_input,
            self.wmo_input,
            self.source_choice,
            self.result_text,
            self.lookup_button,
            self.close_button,
        )

    def _set_accessibility_metadata(self) -> None:
        """Give focusable controls consistent names and helpful tooltips."""
        metadata = (
            (
                self.product_category_choice,
                "Product group",
                "Choose local, point-based, national, or custom text products",
            ),
            (
                self.product_preset_choice,
                "Product",
                "Choose a valid text product for the selected product group",
            ),
            (
                self.product_input,
                "Custom AFOS product ID",
                "Enter a 3 to 6 character AFOS product ID only when using a custom product",
            ),
            (
                self.office_choice,
                "Office selection",
                "Choose the selected location office, no office, or a custom local office",
            ),
            (
                self.location_input,
                "Custom local office",
                "Enter a 3-letter local NWS office such as RAH when custom office is selected",
            ),
            (
                self.limit_input,
                "Maximum products to retrieve",
                "Choose from 1 through 25 matching products",
            ),
            (
                self.date_preset_choice,
                "Date lookup preset",
                "Choose latest, recent archive ranges, or custom start and end dates",
            ),
            (self.start_year_choice, "Start year", "Choose the UTC start year for archive search"),
            (
                self.start_month_choice,
                "Start month",
                "Choose the UTC start month for archive search",
            ),
            (self.start_day_choice, "Start day", "Choose the UTC start day for archive search"),
            (self.end_year_choice, "End year", "Choose the UTC end year for archive search"),
            (self.end_month_choice, "End month", "Choose the UTC end month for archive search"),
            (self.end_day_choice, "End day", "Choose the UTC end day for archive search"),
            (
                self.start_input,
                "Resolved start or valid time",
                "Generated UTC start time; advanced users may enter a date or ISO timestamp",
            ),
            (
                self.end_input,
                "Resolved end time",
                "Generated UTC end time; advanced users may enter a date or ISO timestamp",
            ),
            (self.order_choice, "Result order", "Choose newest first or oldest first"),
            (
                self.afd_aviation_only,
                "Aviation section only for AFD",
                "Limit Area Forecast Discussion results to the aviation section",
            ),
            (
                self.center_input,
                "Issuing center filter",
                "Optional 4-character issuing center filter, such as KDMX",
            ),
            (
                self.wmo_input,
                "WMO header filter",
                "Optional 6-character WMO header filter, such as FXUS63",
            ),
            (self.source_choice, "Lookup source", "Choose NWS history, IEM AFOS, or prefer NWS"),
            (self.result_text, "Lookup results", "Read-only lookup result text"),
            (self.lookup_button, "Lookup", "Run the selected text product lookup"),
            (self.close_button, "Close", "Close the advanced text product lookup dialog"),
        )
        for control, name, tooltip in metadata:
            self._set_control_accessibility(control, name, tooltip)

    @staticmethod
    def _set_control_accessibility(control: Any, name: str, tooltip: str) -> None:
        set_name = getattr(control, "SetName", None)
        if set_name is not None:
            set_name(name)
        set_tooltip = getattr(control, "SetToolTip", None)
        if set_tooltip is not None:
            set_tooltip(tooltip)

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
        wx.CallAfter(self._apply_lookup_result, text)

    @guard_destroyed
    def _apply_lookup_result(self, text: str) -> None:
        """Apply the lookup result to the UI (guarded against dialog close)."""
        self.result_text.SetValue(text)

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
        location = self._selected_office()
        limit = self._parse_limit(self._control_value(self.limit_input))
        source = self.source_choice.GetStringSelection() or _SOURCE_PREFER_NWS
        order = self._selected_order()
        aviation_afd = bool(getattr(self.afd_aviation_only, "GetValue", lambda: False)())
        center = self._text_value(self.center_input).upper()
        wmo_id = self._text_value(self.wmo_input).upper()
        try:
            start = self._selected_datetime("start")
            end = self._selected_datetime("end")
        except ValueError as exc:
            return str(exc)

        if not product_id:
            return "Choose a product or enter a custom AFOS product ID."

        spc_outlook_day = self._spc_outlook_day(product_id)
        if spc_outlook_day is not None:
            return await self._lookup_spc_outlook(spc_outlook_day, start)
        if product_id in {"SPC MCD", "MCD", "SPC MESOSCALE DISCUSSION"}:
            return await self._lookup_spc_mcd(limit, start, end)
        if product_id in {"SPC WATCH", "SPC WATCHES", "WATCHES"}:
            return await self._lookup_spc_watches(start)
        wpc_outlook_day = self._wpc_outlook_day(product_id)
        if wpc_outlook_day is not None:
            return await self._lookup_wpc_outlook(wpc_outlook_day, start, limit)
        if product_id in {"WPC MPD", "MPD", "WPC MESOSCALE PRECIPITATION DISCUSSION"}:
            return await self._lookup_wpc_mpd(limit, start, end)

        if source != _SOURCE_IEM_ONLY and product_id in _NWS_PRODUCT_TYPES and location:
            products = await self._lookup_nws_history(product_id, location, limit, start, end)
            if products:
                return self._format_products("NWS", products)
            if source == _SOURCE_NWS_ONLY:
                return f"No NWS {product_id} history found for {location}."

        pil = self._iem_pil(product_id, location)
        validation_error = self._validate_iem_afos_lookup(
            product_id,
            pil,
            location,
            aviation_afd,
            center,
            wmo_id,
        )
        if validation_error:
            return validation_error

        afos_kwargs: dict[str, Any] = {
            "limit": limit,
            "start": start,
            "end": end,
            "order": order,
        }
        if aviation_afd:
            afos_kwargs["aviation_afd"] = True
            afos_kwargs["limit"] = 1
        if center:
            afos_kwargs["center"] = center
        if wmo_id:
            afos_kwargs["wmo_id"] = wmo_id
        product = await self._service.get_iem_afos(
            pil,
            **afos_kwargs,
        )
        return self._format_products("IEM", product)

    def _on_product_category(self, event) -> None:
        """Filter the product list when the user chooses a group."""
        del event
        category = self.product_category_choice.GetStringSelection() or "Custom"
        labels = self._preset_labels_for_category(category)
        if hasattr(self.product_preset_choice, "SetItems"):
            self.product_preset_choice.SetItems(labels)
        self.product_preset_choice.SetSelection(0)
        self._apply_product_preset(labels[0] if labels else "Custom AFOS product ID")

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

    async def _lookup_spc_outlook(self, day: int, valid_at: datetime | None) -> str:
        lat = getattr(self._location, "latitude", None)
        lon = getattr(self._location, "longitude", None)
        if lat is None or lon is None:
            return "SPC outlook lookup needs a location with latitude and longitude."
        product = await self._service.get_iem_spc_outlook(
            lat,
            lon,
            day=day,
            current=valid_at is None,
            valid_at=valid_at,
        )
        return self._format_products("IEM", product)

    async def _lookup_spc_mcd(
        self,
        limit: int,
        start: datetime | None,
        end: datetime | None,
    ) -> str:
        lat = getattr(self._location, "latitude", None)
        lon = getattr(self._location, "longitude", None)
        if lat is None or lon is None:
            return (
                "SPC MCD (Mesoscale Discussion) lookup needs a location with "
                "latitude and longitude."
            )
        product = await self._service.get_iem_spc_mcds(
            lat,
            lon,
            active_only=False,
            start=start,
            end=end,
            max_items=limit,
        )
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

    async def _lookup_wpc_mpd(
        self,
        limit: int,
        start: datetime | None,
        end: datetime | None,
    ) -> str:
        lat = getattr(self._location, "latitude", None)
        lon = getattr(self._location, "longitude", None)
        if lat is None or lon is None:
            return (
                "WPC MPD (Mesoscale Precipitation Discussion) lookup needs a location "
                "with latitude and longitude."
            )
        product = await self._service.get_iem_wpc_mpds(
            lat,
            lon,
            active_only=False,
            start=start,
            end=end,
            max_items=limit,
        )
        return self._format_products("IEM", product)

    def _on_product_preset(self, event) -> None:
        """Apply a selected product preset to the editable product field."""
        del event
        label = self.product_preset_choice.GetStringSelection()
        self._apply_product_preset(label)

    def _apply_product_preset(self, label: str) -> None:
        """Apply a selected product preset to form controls."""
        product_id = _PRODUCT_PRESETS.get(label, "")
        if product_id:
            self.product_input.SetValue(product_id)
            preset = self._preset_by_label(label)
            if preset and preset.uses_local_office:
                self.source_choice.SetSelection(0)
                self._select_office_choice(_OFFICE_SELECTED)
            if preset and preset.iem_only:
                self.source_choice.SetSelection(1)
                self._select_office_choice(_OFFICE_NONE)

    def _on_date_preset(self, event) -> None:
        """Apply a date preset to the custom date choices and resolved UTC fields."""
        del event
        preset = self.date_preset_choice.GetStringSelection()
        start, end = self._date_range_for_preset(preset)
        self._set_date_choices("start", start)
        self._set_date_choices("end", end)
        self.start_input.SetValue(self._format_form_datetime(start) if start is not None else "")
        self.end_input.SetValue(self._format_form_datetime(end) if end is not None else "")

    def _on_date_parts(self, event) -> None:
        """Resolve custom year/month/day choices into UTC fields."""
        del event
        try:
            start = self._date_from_choice_parts("start")
            end = self._date_from_choice_parts("end")
        except ValueError:
            return
        self.start_input.SetValue(self._format_form_datetime(start) if start is not None else "")
        self.end_input.SetValue(self._format_form_datetime(end) if end is not None else "")

    @staticmethod
    def _parse_limit(value: str) -> int:
        try:
            limit = int(value)
        except ValueError:
            return 1
        return max(1, min(limit, 25))

    @staticmethod
    def _control_value(control: Any) -> str:
        getter = getattr(control, "GetValue", None)
        if getter is None:
            return ""
        value = getter()
        return str(value)

    @staticmethod
    def _text_value(control: Any) -> str:
        getter = getattr(control, "GetValue", None)
        if getter is None:
            return ""
        value = getter()
        return value.strip() if isinstance(value, str) else ""

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

    def _selected_datetime(self, prefix: str) -> datetime | None:
        chosen = self._date_from_choice_parts(prefix)
        if chosen is not None:
            return chosen
        control = self.start_input if prefix == "start" else self.end_input
        return self._parse_optional_datetime(self._text_value(control))

    def _date_from_choice_parts(self, prefix: str) -> datetime | None:
        year_control = self.start_year_choice if prefix == "start" else self.end_year_choice
        month_control = self.start_month_choice if prefix == "start" else self.end_month_choice
        day_control = self.start_day_choice if prefix == "start" else self.end_day_choice
        year_text = year_control.GetStringSelection()
        month_text = month_control.GetStringSelection()
        day_text = day_control.GetStringSelection()
        if not all(isinstance(part, str) for part in (year_text, month_text, day_text)):
            return None
        if not year_text and not month_text and not day_text:
            return None
        if not year_text or not month_text or not day_text:
            raise ValueError("Choose year, month, and day for custom archive dates.")
        year = int(year_text)
        month = int(month_text.split(" ", 1)[0])
        day = int(day_text)
        try:
            return datetime(year, month, day, tzinfo=UTC)
        except ValueError as exc:
            raise ValueError("Choose a valid calendar date.") from exc

    def _set_date_choices(self, prefix: str, value: datetime | None) -> None:
        year_control = self.start_year_choice if prefix == "start" else self.end_year_choice
        month_control = self.start_month_choice if prefix == "start" else self.end_month_choice
        day_control = self.start_day_choice if prefix == "start" else self.end_day_choice
        if value is None:
            for control in (year_control, month_control, day_control):
                control.SetSelection(0)
            return
        self._set_choice_by_label(year_control, str(value.year))
        self._set_choice_by_label(month_control, f"{value.month:02d}", startswith=True)
        self._set_choice_by_label(day_control, f"{value.day:02d}")

    @staticmethod
    def _set_choice_by_label(control: Any, label: str, *, startswith: bool = False) -> None:
        count = getattr(control, "GetCount", lambda: 0)()
        for index in range(count):
            item = control.GetString(index)
            if item == label or (startswith and isinstance(item, str) and item.startswith(label)):
                control.SetSelection(index)
                return

    @staticmethod
    def _date_range_for_preset(preset: str) -> tuple[datetime | None, datetime | None]:
        if preset in {"", "Latest or current"}:
            return None, None
        now = datetime.now(UTC).replace(microsecond=0)
        if preset == "Choose start and end dates":
            return now - timedelta(days=1), now
        days_by_preset = {
            "Past 24 hours": 1,
            "Past 7 days": 7,
            "Past 30 days": 30,
            "Past 90 days": 90,
            "Past year": 365,
        }
        days = days_by_preset.get(preset)
        if days is None:
            return None, None
        return now - timedelta(days=days), now

    @staticmethod
    def _format_form_datetime(value: datetime) -> str:
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")

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

    def _selected_office(self) -> str:
        selection = self.office_choice.GetStringSelection()
        if not isinstance(selection, str):
            return self._text_value(self.location_input).upper()
        if selection.startswith(_OFFICE_SELECTED):
            cwa_office = getattr(self._location, "cwa_office", "") or ""
            return cwa_office.strip().upper()
        if selection == _OFFICE_CUSTOM:
            return self._text_value(self.location_input).upper()
        return ""

    def _select_office_choice(self, prefix_or_label: str) -> None:
        count = getattr(self.office_choice, "GetCount", lambda: 0)()
        for index in range(count):
            label = self.office_choice.GetString(index)
            if label == prefix_or_label or label.startswith(prefix_or_label):
                self.office_choice.SetSelection(index)
                return

    def _selected_order(self) -> str:
        return "asc" if self.order_choice.GetStringSelection() == "Oldest first" else "desc"

    @staticmethod
    def _preset_labels_for_category(category: str) -> list[str]:
        return [item.label for item in _PRODUCT_PRESET_ITEMS if item.category == category]

    @staticmethod
    def _preset_by_label(label: str) -> ProductPreset | None:
        for item in _PRODUCT_PRESET_ITEMS:
            if item.label == label:
                return item
        return None

    @staticmethod
    def _validate_iem_afos_lookup(
        product_id: str,
        pil: str,
        location: str,
        aviation_afd: bool,
        center: str,
        wmo_id: str,
    ) -> str | None:
        if product_id in _NWS_PRODUCT_TYPES and location and not _OFFICE_RE.fullmatch(location):
            return "Choose a valid 3-letter local NWS office, such as RAH."
        if not _PIL_RE.fullmatch(pil):
            return "Choose a preset or enter a 3-to-6 character AFOS product ID."
        if aviation_afd and not pil.startswith("AFD"):
            return "Aviation section lookup is only valid for Area Forecast Discussion products."
        if center and not _CENTER_RE.fullmatch(center):
            return "Issuing center must be a 4-character ID, such as KDMX."
        if wmo_id and not _WMO_RE.fullmatch(wmo_id):
            return "WMO header must be 6 characters like FXUS63."
        return None

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
            self.EndModal(wx.ID_CLOSE)
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
