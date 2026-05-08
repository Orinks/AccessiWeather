"""Widget construction helpers for forecast product panels."""

from __future__ import annotations

from typing import Any

import wx

from .forecast_product_formatting import PRODUCT_FULL_NAMES


def create_product_panel_widgets(panel: Any) -> None:
    """Construct and attach the widgets used by a ForecastProductPanel."""
    main_sizer = wx.BoxSizer(wx.VERTICAL)

    full_name = PRODUCT_FULL_NAMES.get(panel.product_type, panel.product_type)
    panel.header_label = wx.StaticText(panel, label=full_name)
    main_sizer.Add(panel.header_label, 0, wx.ALL | wx.EXPAND, 8)

    panel.sps_choice_label = None
    panel.sps_choice = None
    if panel.product_type == "SPS":
        panel.sps_choice_label = wx.StaticText(panel, label="Recent Special Weather Statements:")
        main_sizer.Add(panel.sps_choice_label, 0, wx.LEFT | wx.RIGHT, 8)
        panel.sps_choice = wx.Choice(panel)
        main_sizer.Add(panel.sps_choice, 0, wx.ALL | wx.EXPAND, 8)
        main_sizer.Show(panel.sps_choice_label, False)
        main_sizer.Show(panel.sps_choice, False)

    panel.product_textctrl = wx.TextCtrl(
        panel,
        style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL,
        value="Loading...",
    )
    main_sizer.Add(panel.product_textctrl, 1, wx.ALL | wx.EXPAND, 8)

    panel.issuance_label = wx.StaticText(panel, label="")
    main_sizer.Add(panel.issuance_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

    panel.ai_summary_header = wx.StaticText(panel, label="Plain Language Summary:")
    main_sizer.Add(panel.ai_summary_header, 0, wx.LEFT | wx.RIGHT, 8)
    panel.ai_summary_display = wx.TextCtrl(
        panel,
        style=wx.TE_MULTILINE | wx.TE_READONLY,
    )
    main_sizer.Add(panel.ai_summary_display, 0, wx.ALL | wx.EXPAND, 8)
    main_sizer.Show(panel.ai_summary_header, False)
    main_sizer.Show(panel.ai_summary_display, False)

    panel.model_info_label = wx.StaticText(panel, label="Model Information:")
    main_sizer.Add(panel.model_info_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
    panel.model_info = wx.TextCtrl(
        panel,
        value="",
        style=wx.TE_MULTILINE | wx.TE_READONLY,
        size=wx.Size(-1, 80),
    )
    main_sizer.Add(panel.model_info, 0, wx.LEFT | wx.RIGHT | wx.EXPAND, 8)
    main_sizer.Show(panel.model_info_label, False)
    main_sizer.Show(panel.model_info, False)

    button_sizer = wx.BoxSizer(wx.HORIZONTAL)
    panel.explain_button = wx.Button(panel, label="Plain Language Summary")
    panel.regenerate_button = wx.Button(panel, label="Regenerate Summary")
    panel.advanced_lookup_button = wx.Button(panel, label="Advanced Lookup")
    panel.retry_button = wx.Button(panel, label="Try again")
    button_sizer.Add(panel.explain_button, 0, wx.RIGHT, 5)
    button_sizer.Add(panel.regenerate_button, 0, wx.RIGHT, 5)
    button_sizer.Add(panel.advanced_lookup_button, 0, wx.RIGHT, 5)
    button_sizer.Add(panel.retry_button, 0)
    main_sizer.Add(button_sizer, 0, wx.ALL, 8)

    panel.regenerate_button.Hide()
    panel.retry_button.Hide()
    panel.explain_button.Disable()

    panel.SetSizer(main_sizer)
    panel._main_sizer = main_sizer
