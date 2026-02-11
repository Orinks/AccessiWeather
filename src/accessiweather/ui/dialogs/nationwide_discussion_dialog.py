"""Nationwide weather discussions dialog with tabbed layout."""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Any

import wx

if TYPE_CHECKING:
    from ...services.national_discussion_service import NationalDiscussionService

logger = logging.getLogger(__name__)


class NationwideDiscussionDialog(wx.Dialog):
    """
    Dialog displaying nationwide weather discussions in a tabbed interface.

    Tabs: WPC, SPC, NHC, CPC — each with labeled, read-only text controls
    for the relevant discussion products.
    """

    def __init__(
        self,
        parent: wx.Window | None = None,
        title: str = "Nationwide Weather Discussions",
        service: NationalDiscussionService | None = None,
    ):
        """
        Initialize the nationwide discussion dialog.

        Args:
            parent: Parent window
            title: Dialog title
            service: NationalDiscussionService instance for fetching data

        """
        super().__init__(
            parent,
            title=title,
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self._service = service
        self._is_loading = False

        self._create_widgets()
        self._bind_events()

        self.SetSize((800, 600))
        self.CenterOnParent()

        # Auto-load if service provided
        if self._service is not None:
            self._load_discussions()

    def _create_widgets(self) -> None:
        """Create all UI widgets."""
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Status label
        self.status_label = wx.StaticText(panel, label="")
        main_sizer.Add(self.status_label, 0, wx.ALL | wx.EXPAND, 5)

        # Notebook (tabs)
        self.notebook = wx.Notebook(panel, name="Discussion tabs")
        main_sizer.Add(self.notebook, 1, wx.ALL | wx.EXPAND, 5)

        # --- WPC tab ---
        self.wpc_panel = wx.Panel(self.notebook)
        wpc_sizer = wx.BoxSizer(wx.VERTICAL)

        wpc_sizer.Add(
            wx.StaticText(self.wpc_panel, label="Short Range Forecast:"), 0, wx.LEFT | wx.TOP, 5
        )
        self.wpc_short_range = wx.TextCtrl(
            self.wpc_panel,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
            name="WPC Short Range Forecast Discussion",
        )
        wpc_sizer.Add(self.wpc_short_range, 1, wx.ALL | wx.EXPAND, 5)

        wpc_sizer.Add(wx.StaticText(self.wpc_panel, label="Medium Range Forecast:"), 0, wx.LEFT, 5)
        self.wpc_medium_range = wx.TextCtrl(
            self.wpc_panel,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
            name="WPC Medium Range Forecast Discussion",
        )
        wpc_sizer.Add(self.wpc_medium_range, 1, wx.ALL | wx.EXPAND, 5)

        wpc_sizer.Add(wx.StaticText(self.wpc_panel, label="Extended Forecast:"), 0, wx.LEFT, 5)
        self.wpc_extended = wx.TextCtrl(
            self.wpc_panel,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
            name="WPC Extended Forecast Discussion",
        )
        wpc_sizer.Add(self.wpc_extended, 1, wx.ALL | wx.EXPAND, 5)

        wpc_sizer.Add(wx.StaticText(self.wpc_panel, label="QPF Discussion:"), 0, wx.LEFT, 5)
        self.wpc_qpf = wx.TextCtrl(
            self.wpc_panel,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
            name="WPC QPF Discussion",
        )
        wpc_sizer.Add(self.wpc_qpf, 1, wx.ALL | wx.EXPAND, 5)

        self.wpc_panel.SetSizer(wpc_sizer)
        self.notebook.AddPage(self.wpc_panel, "WPC")

        # --- SPC tab ---
        self.spc_panel = wx.Panel(self.notebook)
        spc_sizer = wx.BoxSizer(wx.VERTICAL)

        spc_sizer.Add(
            wx.StaticText(self.spc_panel, label="Day 1 Convective Outlook:"), 0, wx.LEFT | wx.TOP, 5
        )
        self.spc_day1 = wx.TextCtrl(
            self.spc_panel,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
            name="SPC Day 1 Convective Outlook",
        )
        spc_sizer.Add(self.spc_day1, 1, wx.ALL | wx.EXPAND, 5)

        spc_sizer.Add(
            wx.StaticText(self.spc_panel, label="Day 2 Convective Outlook:"), 0, wx.LEFT, 5
        )
        self.spc_day2 = wx.TextCtrl(
            self.spc_panel,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
            name="SPC Day 2 Convective Outlook",
        )
        spc_sizer.Add(self.spc_day2, 1, wx.ALL | wx.EXPAND, 5)

        spc_sizer.Add(
            wx.StaticText(self.spc_panel, label="Day 3 Convective Outlook:"), 0, wx.LEFT, 5
        )
        self.spc_day3 = wx.TextCtrl(
            self.spc_panel,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
            name="SPC Day 3 Convective Outlook",
        )
        spc_sizer.Add(self.spc_day3, 1, wx.ALL | wx.EXPAND, 5)

        self.spc_panel.SetSizer(spc_sizer)
        self.notebook.AddPage(self.spc_panel, "SPC")

        # --- NHC tab ---
        self.nhc_panel = wx.Panel(self.notebook)
        nhc_sizer = wx.BoxSizer(wx.VERTICAL)

        nhc_sizer.Add(
            wx.StaticText(self.nhc_panel, label="Atlantic Tropical Weather Outlook:"),
            0,
            wx.LEFT | wx.TOP,
            5,
        )
        self.nhc_atlantic = wx.TextCtrl(
            self.nhc_panel,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
            name="NHC Atlantic Tropical Weather Outlook",
        )
        nhc_sizer.Add(self.nhc_atlantic, 1, wx.ALL | wx.EXPAND, 5)

        nhc_sizer.Add(
            wx.StaticText(self.nhc_panel, label="East Pacific Tropical Weather Outlook:"),
            0,
            wx.LEFT,
            5,
        )
        self.nhc_east_pacific = wx.TextCtrl(
            self.nhc_panel,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
            name="NHC East Pacific Tropical Weather Outlook",
        )
        nhc_sizer.Add(self.nhc_east_pacific, 1, wx.ALL | wx.EXPAND, 5)

        self.nhc_panel.SetSizer(nhc_sizer)
        self.notebook.AddPage(self.nhc_panel, "NHC")

        # Store NHC page index for hiding
        self._nhc_page_index = self.notebook.GetPageCount() - 1

        # --- CPC tab ---
        self.cpc_panel = wx.Panel(self.notebook)
        cpc_sizer = wx.BoxSizer(wx.VERTICAL)

        cpc_sizer.Add(
            wx.StaticText(self.cpc_panel, label="6-10 Day Outlook:"), 0, wx.LEFT | wx.TOP, 5
        )
        self.cpc_6_10_day = wx.TextCtrl(
            self.cpc_panel,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
            name="CPC 6-10 Day Outlook",
        )
        cpc_sizer.Add(self.cpc_6_10_day, 1, wx.ALL | wx.EXPAND, 5)

        cpc_sizer.Add(wx.StaticText(self.cpc_panel, label="8-14 Day Outlook:"), 0, wx.LEFT, 5)
        self.cpc_8_14_day = wx.TextCtrl(
            self.cpc_panel,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
            name="CPC 8-14 Day Outlook",
        )
        cpc_sizer.Add(self.cpc_8_14_day, 1, wx.ALL | wx.EXPAND, 5)

        self.cpc_panel.SetSizer(cpc_sizer)
        self.notebook.AddPage(self.cpc_panel, "CPC")

        # Button sizer
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.refresh_button = wx.Button(panel, label="&Refresh")
        button_sizer.Add(self.refresh_button, 0, wx.RIGHT, 5)

        self.close_button = wx.Button(panel, wx.ID_CLOSE, label="&Close")
        button_sizer.Add(self.close_button, 0)

        main_sizer.Add(button_sizer, 0, wx.ALL | wx.ALIGN_RIGHT, 10)

        panel.SetSizer(main_sizer)

        dialog_sizer = wx.BoxSizer(wx.VERTICAL)
        dialog_sizer.Add(panel, 1, wx.EXPAND)
        self.SetSizer(dialog_sizer)

    def _bind_events(self) -> None:
        """Bind event handlers."""
        self.close_button.Bind(wx.EVT_BUTTON, self._on_close)
        self.refresh_button.Bind(wx.EVT_BUTTON, self._on_refresh)

    def _on_close(self, event) -> None:
        """Handle close button press."""
        self.EndModal(wx.ID_CLOSE)

    def _on_refresh(self, event) -> None:
        """Handle refresh button press."""
        self._load_discussions(force_refresh=True)

    def _set_status(self, message: str) -> None:
        """Update the status label."""
        self.status_label.SetLabel(message)

    def _set_all_loading(self) -> None:
        """Set all text controls to 'Loading...' state."""
        for ctrl in [
            self.wpc_short_range,
            self.wpc_medium_range,
            self.wpc_extended,
            self.wpc_qpf,
            self.spc_day1,
            self.spc_day2,
            self.spc_day3,
            self.nhc_atlantic,
            self.nhc_east_pacific,
            self.cpc_6_10_day,
            self.cpc_8_14_day,
        ]:
            ctrl.SetValue("Loading...")

    def _load_discussions(self, force_refresh: bool = False) -> None:
        """Load discussions in a background thread."""
        if self._is_loading or self._service is None:
            return

        self._is_loading = True
        self.refresh_button.Disable()
        self._set_status("Loading...")
        self._set_all_loading()

        thread = threading.Thread(
            target=self._fetch_discussions_thread,
            args=(force_refresh,),
            daemon=True,
        )
        thread.start()

    def _fetch_discussions_thread(self, force_refresh: bool) -> None:
        """Background thread to fetch discussions."""
        try:
            data = self._service.fetch_all_discussions(force_refresh=force_refresh)
            wx.CallAfter(self._on_discussions_loaded, data)
        except Exception as e:
            logger.error(f"Failed to fetch discussions: {e}")
            wx.CallAfter(self._on_discussions_error, str(e))

    def _on_discussions_loaded(self, data: dict[str, Any]) -> None:
        """Handle successful discussion loading (called via wx.CallAfter)."""
        self._is_loading = False
        self.refresh_button.Enable()
        self._set_status("Discussions loaded.")

        # WPC
        wpc = data.get("wpc", {})
        self.wpc_short_range.SetValue(wpc.get("short_range", {}).get("text", "Not available"))
        self.wpc_medium_range.SetValue(wpc.get("medium_range", {}).get("text", "Not available"))
        self.wpc_extended.SetValue(wpc.get("extended", {}).get("text", "Not available"))

        # QPF goes into WPC tab
        qpf = data.get("qpf", {})
        self.wpc_qpf.SetValue(qpf.get("qpf", {}).get("text", "Not available"))

        # SPC
        spc = data.get("spc", {})
        self.spc_day1.SetValue(spc.get("day1", {}).get("text", "Not available"))
        self.spc_day2.SetValue(spc.get("day2", {}).get("text", "Not available"))
        self.spc_day3.SetValue(spc.get("day3", {}).get("text", "Not available"))

        # NHC
        nhc = data.get("nhc", {})
        self.nhc_atlantic.SetValue(nhc.get("atlantic_outlook", {}).get("text", "Not available"))
        self.nhc_east_pacific.SetValue(
            nhc.get("east_pacific_outlook", {}).get("text", "Not available")
        )

        # Hide NHC tab if not hurricane season
        if self._service is not None and not self._service.is_hurricane_season():
            self._hide_nhc_tab()

        # CPC
        cpc = data.get("cpc", {})
        self.cpc_6_10_day.SetValue(cpc.get("outlook_6_10", {}).get("text", "Not available"))
        self.cpc_8_14_day.SetValue(cpc.get("outlook_8_14", {}).get("text", "Not available"))

    def _hide_nhc_tab(self) -> None:
        """Remove the NHC tab from the notebook if present."""
        for i in range(self.notebook.GetPageCount()):
            if self.notebook.GetPageText(i) == "NHC":
                self.notebook.RemovePage(i)
                self.nhc_panel.Hide()
                break

    def _on_discussions_error(self, error: str) -> None:
        """Handle discussion loading error (called via wx.CallAfter)."""
        self._is_loading = False
        self.refresh_button.Enable()
        self._set_status(f"Error loading discussions: {error}")

        error_msg = f"Failed to load discussions: {error}"
        for ctrl in [
            self.wpc_short_range,
            self.wpc_medium_range,
            self.wpc_extended,
            self.wpc_qpf,
            self.spc_day1,
            self.spc_day2,
            self.spc_day3,
            self.nhc_atlantic,
            self.nhc_east_pacific,
            self.cpc_6_10_day,
            self.cpc_8_14_day,
        ]:
            ctrl.SetValue(error_msg)

    def set_discussion_text(self, tab: str, field: str, text: str) -> None:
        """
        Set text for a specific discussion field.

        Args:
            tab: Tab name ('wpc', 'spc', 'nhc', 'cpc')
            field: Field name (e.g. 'short_range', 'day1', 'atlantic', '6_10_day')
            text: The discussion text to display

        """
        attr_name = f"{tab}_{field}"
        ctrl = getattr(self, attr_name, None)
        if ctrl and isinstance(ctrl, wx.TextCtrl):
            ctrl.SetValue(text)


def show_nationwide_discussion_dialog(
    parent: wx.Window | None = None,
    service: NationalDiscussionService | None = None,
) -> None:
    """
    Show the Nationwide Weather Discussions dialog.

    Args:
        parent: Parent window
        service: NationalDiscussionService instance

    """
    try:
        parent_ctrl = getattr(parent, "control", parent)
        dlg = NationwideDiscussionDialog(parent_ctrl, service=service)
        dlg.ShowModal()
        dlg.Destroy()
    except Exception as e:
        logger.error(f"Failed to show nationwide discussion dialog: {e}")
        wx.MessageBox(
            f"Failed to open nationwide discussions: {e}",
            "Error",
            wx.OK | wx.ICON_ERROR,
        )
