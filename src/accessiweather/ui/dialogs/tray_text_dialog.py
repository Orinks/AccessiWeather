"""
Tray text format customization dialog for AccessiWeather.

Provides a dedicated dialog for configuring the tray icon text format string,
with a list of available placeholders, a format input field, and a live preview.
Placeholders are displayed and accepted in [placeholder] bracket notation.
"""

from __future__ import annotations

import wx

from ...format_string_parser import FormatStringParser

# Sample weather data used for the live preview
_SAMPLE_WEATHER = {
    "temp": "72F",
    "temp_f": "72F",
    "temp_c": "22C",
    "condition": "Partly Cloudy",
    "humidity": "55%",
    "wind": "NW at 10 mph",
    "wind_speed": "10 mph",
    "wind_dir": "NW",
    "pressure": "30.1 inHg",
    "location": "Sample City",
    "feels_like": "70F",
    "uv": "5",
    "visibility": "10 mi",
    "high": "78F",
    "low": "60F",
    "precip": "0 in",
    "precip_chance": "20%",
}


class TrayTextCustomizationDialog(wx.Dialog):
    """
    Dialog for configuring the tray icon text format string.

    Shows available placeholders in [placeholder] notation, a format input
    field (accepting both [x] and {x} styles), and a live preview.
    """

    def __init__(
        self,
        parent: wx.Window,
        current_format: str = "{temp} {condition}",
    ):
        """
        Initialize the dialog.

        Args:
            parent: Parent window
            current_format: Currently configured format string

        """
        super().__init__(
            parent,
            title="Customize Tray Text Format",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self._parser = FormatStringParser()
        self._current_format = current_format or "{temp} {condition}"
        self._build_ui()
        self.SetSize(560, 480)
        self.CenterOnParent()
        self._update_preview()

    def _build_ui(self) -> None:
        """Build the dialog UI."""
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Instruction label
        intro = wx.StaticText(
            self,
            label=(
                "Use [placeholder] in your format string. Click a placeholder below to insert it."
            ),
        )
        intro.Wrap(520)
        main_sizer.Add(intro, 0, wx.ALL, 10)

        # Placeholder list
        list_label = wx.StaticText(self, label="Available Placeholders:")
        main_sizer.Add(list_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)

        self._placeholder_list = wx.ListCtrl(
            self,
            style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_SUNKEN,
        )
        self._placeholder_list.InsertColumn(0, "Placeholder", width=140)
        self._placeholder_list.InsertColumn(1, "Description", width=360)

        for name, desc in FormatStringParser.SUPPORTED_PLACEHOLDERS.items():
            idx = self._placeholder_list.InsertItem(
                self._placeholder_list.GetItemCount(), f"[{name}]"
            )
            self._placeholder_list.SetItem(idx, 1, desc)

        self._placeholder_list.SetMinSize((-1, 140))
        main_sizer.Add(self._placeholder_list, 1, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 10)

        # Insert button
        self._insert_btn = wx.Button(self, label="Insert Placeholder")
        self._insert_btn.Bind(wx.EVT_BUTTON, self._on_insert)
        main_sizer.Add(self._insert_btn, 0, wx.LEFT | wx.TOP, 10)

        # Format string input
        format_label = wx.StaticText(self, label="Format string:")
        main_sizer.Add(format_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)

        self._format_ctrl = wx.TextCtrl(self, value=self._current_format)
        self._format_ctrl.Bind(wx.EVT_TEXT, self._on_format_changed)
        main_sizer.Add(self._format_ctrl, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 10)

        # Validation message
        self._validation_label = wx.StaticText(self, label="")
        self._validation_label.SetForegroundColour(wx.RED)
        main_sizer.Add(self._validation_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)

        # Preview
        preview_label = wx.StaticText(self, label="Preview (sample data):")
        main_sizer.Add(preview_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)

        self._preview_label = wx.StaticText(self, label="")
        self._preview_label.SetFont(self._preview_label.GetFont().MakeBold())
        main_sizer.Add(self._preview_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)

        # Buttons
        btn_sizer = wx.StdDialogButtonSizer()
        ok_btn = wx.Button(self, wx.ID_OK)
        ok_btn.SetDefault()
        btn_sizer.AddButton(ok_btn)
        cancel_btn = wx.Button(self, wx.ID_CANCEL)
        btn_sizer.AddButton(cancel_btn)
        btn_sizer.Realize()
        main_sizer.Add(btn_sizer, 0, wx.ALL | wx.EXPAND, 10)

        self.SetSizer(main_sizer)

        ok_btn.Bind(wx.EVT_BUTTON, self._on_ok)

    def _on_insert(self, event) -> None:
        """Insert the selected placeholder into the format string field."""
        idx = self._placeholder_list.GetFirstSelected()
        if idx == -1:
            return
        name_with_brackets = self._placeholder_list.GetItemText(idx, 0)
        # Insert at current cursor position
        pos = self._format_ctrl.GetInsertionPoint()
        current = self._format_ctrl.GetValue()
        new_value = current[:pos] + name_with_brackets + current[pos:]
        self._format_ctrl.SetValue(new_value)
        self._format_ctrl.SetInsertionPoint(pos + len(name_with_brackets))
        self._format_ctrl.SetFocus()

    def _on_format_changed(self, event) -> None:
        """Update the preview when the format string changes."""
        self._update_preview()

    def _update_preview(self) -> None:
        """Re-render the preview label with sample weather data."""
        fmt = (
            self._format_ctrl.GetValue() if hasattr(self, "_format_ctrl") else self._current_format
        )
        if not fmt:
            fmt = "{temp} {condition}"

        is_valid, error = self._parser.validate_format_string(fmt)
        if not is_valid:
            self._validation_label.SetLabel(f"Invalid: {error}")
            self._preview_label.SetLabel("")
            return

        self._validation_label.SetLabel("")
        result = self._parser.format_string(fmt, _SAMPLE_WEATHER)
        # Add sample location prefix like the real formatter does
        preview = f"Sample City: {result}" if result else "Sample City: 72F Partly Cloudy"
        self._preview_label.SetLabel(preview)

    def _on_ok(self, event) -> None:
        """Validate before accepting."""
        fmt = self._format_ctrl.GetValue()
        is_valid, error = self._parser.validate_format_string(fmt)
        if not is_valid:
            wx.MessageBox(
                f"Invalid format string:\n{error}",
                "Format Error",
                wx.OK | wx.ICON_ERROR,
                self,
            )
            return
        self.EndModal(wx.ID_OK)

    def get_format_string(self) -> str:
        """
        Return the format string as entered by the user.

        The string may use either [placeholder] or {placeholder} notation.
        Both are accepted by the parser at runtime.
        """
        return self._format_ctrl.GetValue()
