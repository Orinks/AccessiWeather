"""Widget construction helpers for the nationwide discussion dialog."""

from __future__ import annotations

from typing import Any

import wx


def create_nationwide_discussion_widgets(dialog: Any) -> None:
    """Create all widgets for the nationwide discussion dialog."""
    panel = wx.Panel(dialog)
    main_sizer = wx.BoxSizer(wx.VERTICAL)

    dialog.status_label = wx.StaticText(panel, label="")
    main_sizer.Add(dialog.status_label, 0, wx.ALL | wx.EXPAND, 5)

    dialog.notebook = wx.Notebook(panel, name="Discussion tabs")
    main_sizer.Add(dialog.notebook, 1, wx.ALL | wx.EXPAND, 5)

    _add_wpc_tab(dialog)
    _add_spc_tab(dialog)
    _add_nhc_tab(dialog)
    _add_cpc_tab(dialog)
    _add_ai_summary_section(dialog, panel, main_sizer)
    _add_buttons(dialog, panel, main_sizer)

    panel.SetSizer(main_sizer)

    dialog_sizer = wx.BoxSizer(wx.VERTICAL)
    dialog_sizer.Add(panel, 1, wx.EXPAND)
    dialog.SetSizer(dialog_sizer)


def _add_labeled_text(parent: wx.Window, sizer: wx.BoxSizer, label: str, name: str) -> wx.TextCtrl:
    sizer.Add(wx.StaticText(parent, label=label), 0, wx.LEFT | wx.TOP, 5)
    text = wx.TextCtrl(
        parent,
        style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
        name=name,
    )
    sizer.Add(text, 1, wx.ALL | wx.EXPAND, 5)
    return text


def _add_wpc_tab(dialog: Any) -> None:
    dialog.wpc_panel = wx.Panel(dialog.notebook)
    wpc_sizer = wx.BoxSizer(wx.VERTICAL)
    dialog.wpc_short_range = _add_labeled_text(
        dialog.wpc_panel,
        wpc_sizer,
        "Short Range Forecast:",
        "WPC Short Range Forecast Discussion",
    )
    dialog.wpc_medium_range = _add_labeled_text(
        dialog.wpc_panel,
        wpc_sizer,
        "Medium Range Forecast:",
        "WPC Medium Range Forecast Discussion",
    )
    dialog.wpc_extended = _add_labeled_text(
        dialog.wpc_panel,
        wpc_sizer,
        "Extended Forecast:",
        "WPC Extended Forecast Discussion",
    )
    dialog.wpc_qpf = _add_labeled_text(
        dialog.wpc_panel,
        wpc_sizer,
        "QPF Discussion:",
        "WPC QPF Discussion",
    )
    dialog.wpc_panel.SetSizer(wpc_sizer)
    dialog.notebook.AddPage(dialog.wpc_panel, "WPC (Weather Prediction Center)")


def _add_spc_tab(dialog: Any) -> None:
    dialog.spc_panel = wx.Panel(dialog.notebook)
    spc_sizer = wx.BoxSizer(wx.VERTICAL)
    dialog.spc_day1 = _add_labeled_text(
        dialog.spc_panel,
        spc_sizer,
        "Day 1 Convective Outlook:",
        "SPC Day 1 Convective Outlook",
    )
    dialog.spc_day2 = _add_labeled_text(
        dialog.spc_panel,
        spc_sizer,
        "Day 2 Convective Outlook:",
        "SPC Day 2 Convective Outlook",
    )
    dialog.spc_day3 = _add_labeled_text(
        dialog.spc_panel,
        spc_sizer,
        "Day 3 Convective Outlook:",
        "SPC Day 3 Convective Outlook",
    )
    dialog.spc_panel.SetSizer(spc_sizer)
    dialog.notebook.AddPage(dialog.spc_panel, "SPC (Storm Prediction Center)")


def _add_nhc_tab(dialog: Any) -> None:
    dialog._nhc_available = dialog._service is not None and dialog._service.is_hurricane_season()
    if dialog._nhc_available:
        dialog.nhc_panel = wx.Panel(dialog.notebook)
        nhc_sizer = wx.BoxSizer(wx.VERTICAL)
        dialog.nhc_atlantic = _add_labeled_text(
            dialog.nhc_panel,
            nhc_sizer,
            "Atlantic Tropical Weather Outlook:",
            "NHC Atlantic Tropical Weather Outlook",
        )
        dialog.nhc_east_pacific = _add_labeled_text(
            dialog.nhc_panel,
            nhc_sizer,
            "East Pacific Tropical Weather Outlook:",
            "NHC East Pacific Tropical Weather Outlook",
        )
        dialog.nhc_panel.SetSizer(nhc_sizer)
        dialog.notebook.AddPage(dialog.nhc_panel, "NHC (National Hurricane Center)")

    dialog._nhc_page_index = dialog.notebook.GetPageCount() - 1


def _add_cpc_tab(dialog: Any) -> None:
    dialog.cpc_panel = wx.Panel(dialog.notebook)
    cpc_sizer = wx.BoxSizer(wx.VERTICAL)
    dialog.cpc_outlook = _add_labeled_text(
        dialog.cpc_panel,
        cpc_sizer,
        "6-10 & 8-14 Day Outlook:",
        "CPC 6-10 and 8-14 Day Outlook",
    )
    dialog.cpc_panel.SetSizer(cpc_sizer)
    dialog.notebook.AddPage(dialog.cpc_panel, "CPC (Climate Prediction Center)")


def _add_ai_summary_section(dialog: Any, panel: wx.Panel, main_sizer: wx.BoxSizer) -> None:
    main_sizer.Add(wx.StaticText(panel, label="AI Summary:"), 0, wx.LEFT | wx.TOP, 10)
    dialog.explanation_display = wx.TextCtrl(
        panel,
        style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
        size=(-1, 120),
        name="AI-generated plain language summary",
    )
    dialog.explanation_display.SetValue(
        "Click 'Summarize with AI' to generate a plain language summary "
        "of the currently selected tab's discussions."
    )
    main_sizer.Add(dialog.explanation_display, 0, wx.ALL | wx.EXPAND, 10)


def _add_buttons(dialog: Any, panel: wx.Panel, main_sizer: wx.BoxSizer) -> None:
    button_sizer = wx.BoxSizer(wx.HORIZONTAL)

    dialog.explain_button = wx.Button(panel, label="&Summarize with AI")
    button_sizer.Add(dialog.explain_button, 0, wx.RIGHT, 5)

    dialog.refresh_button = wx.Button(panel, label="&Refresh")
    button_sizer.Add(dialog.refresh_button, 0, wx.RIGHT, 5)

    dialog.close_button = wx.Button(panel, wx.ID_CLOSE, label="&Close")
    button_sizer.Add(dialog.close_button, 0)

    main_sizer.Add(button_sizer, 0, wx.ALL | wx.ALIGN_RIGHT, 10)
