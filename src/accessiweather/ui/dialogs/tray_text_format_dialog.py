"""Dialog for editing tray text format strings."""

from __future__ import annotations

import wx

from ...taskbar_icon_updater import DEFAULT_TOOLTIP_FORMAT, TaskbarIconUpdater


class TrayTextFormatDialog(wx.Dialog):
    """Small dialog for editing tray text placeholders with a live preview."""

    def __init__(
        self,
        parent,
        *,
        updater: TaskbarIconUpdater,
        weather_data=None,
        location_name: str | None = None,
        initial_format: str = DEFAULT_TOOLTIP_FORMAT,
    ):
        super().__init__(
            parent,
            title="Tray Text Format",
            size=(520, 500),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self._updater = updater
        self._weather_data = weather_data
        self._location_name = location_name
        self._format_ctrl: wx.TextCtrl
        self._preview_ctrl: wx.TextCtrl

        self._create_ui(initial_format)
        self._update_preview()

    def _create_ui(self, initial_format: str) -> None:
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        main_sizer.Add(
            wx.StaticText(self, label="Tray text format:"),
            0,
            wx.LEFT | wx.RIGHT | wx.TOP,
            10,
        )

        self._format_ctrl = wx.TextCtrl(self, value=initial_format)
        self._format_ctrl.Bind(wx.EVT_TEXT, self._on_format_changed)
        main_sizer.Add(self._format_ctrl, 0, wx.EXPAND | wx.ALL, 10)

        main_sizer.Add(
            wx.StaticText(self, label="Supported placeholders:"),
            0,
            wx.LEFT | wx.RIGHT,
            10,
        )

        placeholders_ctrl = wx.TextCtrl(
            self,
            value=self._updater.parser.get_supported_placeholders_help().strip(),
            style=wx.TE_MULTILINE | wx.TE_READONLY,
        )
        main_sizer.Add(placeholders_ctrl, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        main_sizer.Add(
            wx.StaticText(self, label="Preview:"),
            0,
            wx.LEFT | wx.RIGHT,
            10,
        )

        self._preview_ctrl = wx.TextCtrl(
            self,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_NO_VSCROLL,
        )
        main_sizer.Add(self._preview_ctrl, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        button_sizer = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
        if button_sizer:
            main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.ALL, 10)

        self.SetSizer(main_sizer)

    def _on_format_changed(self, event: wx.CommandEvent) -> None:
        self._update_preview()
        event.Skip()

    def _update_preview(self) -> None:
        self._preview_ctrl.SetValue(
            self._updater.build_preview(
                self._format_ctrl.GetValue(),
                weather_data=self._weather_data,
                location_name=self._location_name,
            )
        )

    def get_format_string(self) -> str:
        """Return the edited format string."""
        value = self._format_ctrl.GetValue().strip()
        return value or DEFAULT_TOOLTIP_FORMAT
