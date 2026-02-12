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
        self.notebook.AddPage(self.wpc_panel, "WPC (Weather Prediction Center)")

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
        self.notebook.AddPage(self.spc_panel, "SPC (Storm Prediction Center)")

        # --- NHC tab (June-November only) ---
        self._nhc_available = self._service is not None and self._service.is_hurricane_season()
        if self._nhc_available:
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
            self.notebook.AddPage(self.nhc_panel, "NHC (National Hurricane Center)")

        # Store NHC page index for hiding
        self._nhc_page_index = self.notebook.GetPageCount() - 1

        # --- CPC tab ---
        self.cpc_panel = wx.Panel(self.notebook)
        cpc_sizer = wx.BoxSizer(wx.VERTICAL)

        cpc_sizer.Add(
            wx.StaticText(self.cpc_panel, label="6-10 & 8-14 Day Outlook:"),
            0,
            wx.LEFT | wx.TOP,
            5,
        )
        self.cpc_outlook = wx.TextCtrl(
            self.cpc_panel,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
            name="CPC 6-10 and 8-14 Day Outlook",
        )
        cpc_sizer.Add(self.cpc_outlook, 1, wx.ALL | wx.EXPAND, 5)

        self.cpc_panel.SetSizer(cpc_sizer)
        self.notebook.AddPage(self.cpc_panel, "CPC (Climate Prediction Center)")

        # AI Explanation section
        main_sizer.Add(wx.StaticText(panel, label="AI Summary:"), 0, wx.LEFT | wx.TOP, 10)
        self.explanation_display = wx.TextCtrl(
            panel,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
            size=(-1, 120),
            name="AI-generated plain language summary",
        )
        self.explanation_display.SetValue(
            "Click 'Summarize with AI' to generate a plain language summary "
            "of the currently selected tab's discussions."
        )
        main_sizer.Add(self.explanation_display, 0, wx.ALL | wx.EXPAND, 10)

        # Button sizer
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.explain_button = wx.Button(panel, label="&Summarize with AI")
        button_sizer.Add(self.explain_button, 0, wx.RIGHT, 5)

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
        self.explain_button.Bind(wx.EVT_BUTTON, self._on_explain)
        self._is_explaining = False
        self._update_explain_button_state()

    def _on_close(self, event) -> None:
        """Handle close button press."""
        self.EndModal(wx.ID_CLOSE)

    def _on_refresh(self, event) -> None:
        """Handle refresh button press."""
        self._load_discussions(force_refresh=True)

    def _update_explain_button_state(self) -> None:
        """Enable or disable the explain button based on AI availability."""
        try:
            from ...config.secure_storage import SecureStorage

            api_key = SecureStorage.get_password("openrouter_api_key")
            if api_key:
                self.explain_button.Enable()
            else:
                self.explain_button.Disable()
        except Exception:
            self.explain_button.Disable()

    def _get_current_tab_text(self) -> tuple[str, str]:
        """Get the discussion text from the currently selected tab."""
        page_idx = self.notebook.GetSelection()
        page_label = self.notebook.GetPageText(page_idx)

        # Collect all non-empty text from the current tab's text controls
        page = self.notebook.GetPage(page_idx)
        texts = []
        for child in page.GetChildren():
            if isinstance(child, wx.TextCtrl):
                text = child.GetValue().strip()
                if text and text not in ("Loading...", "Not available", "Discussion not available"):
                    texts.append(text)

        return page_label, "\n\n".join(texts)

    def _on_explain(self, event) -> None:
        """Handle explain button press."""
        if self._is_explaining:
            return

        tab_name, tab_text = self._get_current_tab_text()
        if not tab_text:
            self.explanation_display.SetValue("No discussion text available to summarize.")
            return

        self._is_explaining = True
        self.explain_button.Disable()
        self.explanation_display.SetValue(f"Generating summary of {tab_name} discussions...")
        self._set_status("Generating AI summary...")

        thread = threading.Thread(
            target=self._do_explain_thread,
            args=(tab_name, tab_text),
            daemon=True,
        )
        thread.start()

    def _do_explain_thread(self, tab_name: str, text: str) -> None:
        """Run AI explanation in background thread."""
        try:
            from ...ai_explainer import AIExplainer, ExplanationStyle
            from ...config.secure_storage import SecureStorage

            api_key = SecureStorage.get_password("openrouter_api_key")
            if not api_key:
                wx.CallAfter(
                    self._on_explain_complete,
                    "OpenRouter API key not configured. Set it in Settings > AI.",
                )
                return

            # Get app reference for settings
            app = wx.GetApp()
            settings = app.config_manager.get_settings() if app else None
            model_pref = getattr(settings, "ai_model_preference", None) if settings else None
            model = "openrouter/auto" if model_pref == "auto" else model_pref

            explainer = AIExplainer(
                api_key=api_key,
                model=model if model else None,
                custom_system_prompt=getattr(settings, "custom_system_prompt", None)
                if settings
                else None,
                custom_instructions=getattr(settings, "custom_instructions", None)
                if settings
                else None,
            )

            result = explainer.explain_discussion(
                discussion_text=text,
                location_name="the United States",
                style=ExplanationStyle.STANDARD,
            )

            wx.CallAfter(self._on_explain_complete, result)

        except Exception as e:
            logger.error(f"AI explanation failed: {e}")
            wx.CallAfter(self._on_explain_complete, f"Error generating summary: {e}")

    def _on_explain_complete(self, text: str) -> None:
        """Handle AI explanation result."""
        self.explanation_display.SetValue(text)
        self._is_explaining = False
        self.explain_button.Enable()
        self._set_status("AI summary generated.")

    def _set_status(self, message: str) -> None:
        """Update the status label."""
        self.status_label.SetLabel(message)

    def _set_all_loading(self) -> None:
        """Set all text controls to 'Loading...' state."""
        controls = [
            self.wpc_short_range,
            self.wpc_medium_range,
            self.wpc_extended,
            self.wpc_qpf,
            self.spc_day1,
            self.spc_day2,
            self.spc_day3,
            self.cpc_outlook,
        ]
        if self._nhc_available:
            controls.extend([self.nhc_atlantic, self.nhc_east_pacific])
        for ctrl in controls:
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

        # NHC (only populated during hurricane season)
        if self._nhc_available:
            nhc = data.get("nhc", {})
            self.nhc_atlantic.SetValue(nhc.get("atlantic_outlook", {}).get("text", "Not available"))
            self.nhc_east_pacific.SetValue(
                nhc.get("east_pacific_outlook", {}).get("text", "Not available")
            )

        # Hide tabs where no data is available
        self._hide_empty_tabs(data)

        # CPC
        cpc = data.get("cpc", {})
        self.cpc_outlook.SetValue(cpc.get("outlook", {}).get("text", "Not available"))

    def _hide_empty_tabs(self, data: dict[str, Any]) -> None:
        """Hide tabs where all discussions have no useful content."""
        unavailable = {"", "Not available", "Discussion not available"}

        def _has_data(section: dict, keys: list[str]) -> bool:
            return any(
                section.get(k, {}).get("text", "") not in unavailable
                and not section.get(k, {}).get("text", "").startswith("Error")
                for k in keys
            )

        tab_checks = {
            "WPC (Weather Prediction Center)": _has_data(
                data.get("wpc", {}), ["short_range", "medium_range", "extended"]
            )
            or _has_data(data.get("qpf", {}), ["qpf"]),
            "SPC (Storm Prediction Center)": _has_data(
                data.get("spc", {}), ["day1", "day2", "day3"]
            ),
            "NHC (National Hurricane Center)": _has_data(
                data.get("nhc", {}), ["atlantic_outlook", "east_pacific_outlook"]
            ),
            "CPC (Climate Prediction Center)": _has_data(data.get("cpc", {}), ["outlook"]),
        }

        # Remove tabs with no data (iterate in reverse to preserve indices)
        for i in range(self.notebook.GetPageCount() - 1, -1, -1):
            label = self.notebook.GetPageText(i)
            if label in tab_checks and not tab_checks[label]:
                self.notebook.GetPage(i).Hide()
                self.notebook.RemovePage(i)

    def _on_discussions_error(self, error: str) -> None:
        """Handle discussion loading error (called via wx.CallAfter)."""
        self._is_loading = False
        self.refresh_button.Enable()
        self._set_status(f"Error loading discussions: {error}")

        error_msg = f"Failed to load discussions: {error}"
        controls = [
            self.wpc_short_range,
            self.wpc_medium_range,
            self.wpc_extended,
            self.wpc_qpf,
            self.spc_day1,
            self.spc_day2,
            self.spc_day3,
            self.cpc_outlook,
        ]
        if self._nhc_available:
            controls.extend([self.nhc_atlantic, self.nhc_east_pacific])
        for ctrl in controls:
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
