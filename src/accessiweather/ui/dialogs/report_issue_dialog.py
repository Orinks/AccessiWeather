"""Dialog for reporting issues to GitHub."""

from __future__ import annotations

import platform
import sys
import urllib.parse
import webbrowser

import wx

from accessiweather import __version__

GITHUB_REPO = "Orinks/AccessiWeather"
ISSUE_URL = f"https://github.com/{GITHUB_REPO}/issues/new"


class ReportIssueDialog(wx.Dialog):
    """Dialog for reporting issues to GitHub."""

    def __init__(self, parent: wx.Window | None = None):
        """Initialize the report issue dialog."""
        super().__init__(
            parent,
            title="Report Issue",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self._create_controls()
        self._do_layout()
        self._bind_events()

        self.SetSize((500, 400))
        self.CenterOnParent()

    def _create_controls(self) -> None:
        """Create dialog controls."""
        # Issue type
        self.type_label = wx.StaticText(self, label="Issue Type:")
        self.type_choice = wx.Choice(
            self,
            choices=["Bug Report", "Feature Request"],
        )
        self.type_choice.SetSelection(0)

        # Title
        self.title_label = wx.StaticText(self, label="Title:")
        self.title_input = wx.TextCtrl(self)
        self.title_input.SetHint("Brief summary of the issue")

        # Description
        self.desc_label = wx.StaticText(self, label="Description:")
        self.desc_input = wx.TextCtrl(
            self,
            style=wx.TE_MULTILINE,
        )
        self.desc_input.SetHint(
            "Describe the issue or feature request.\n"
            "For bugs: What happened? What did you expect?"
        )

        # System info preview
        self.info_label = wx.StaticText(self, label="System info (auto-collected):")
        self.info_text = wx.TextCtrl(
            self,
            style=wx.TE_MULTILINE | wx.TE_READONLY,
        )
        self.info_text.SetValue(self._get_system_info())

        # Buttons
        self.submit_btn = wx.Button(self, wx.ID_OK, label="Open in Browser")
        self.cancel_btn = wx.Button(self, wx.ID_CANCEL, label="Cancel")

    def _do_layout(self) -> None:
        """Layout dialog controls."""
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Type row
        type_sizer = wx.BoxSizer(wx.HORIZONTAL)
        type_sizer.Add(self.type_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        type_sizer.Add(self.type_choice, 1)
        main_sizer.Add(type_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # Title
        main_sizer.Add(self.title_label, 0, wx.LEFT | wx.RIGHT, 10)
        main_sizer.Add(self.title_input, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # Description
        main_sizer.Add(self.desc_label, 0, wx.LEFT | wx.RIGHT, 10)
        main_sizer.Add(self.desc_input, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # System info
        main_sizer.Add(self.info_label, 0, wx.LEFT | wx.RIGHT, 10)
        main_sizer.Add(
            self.info_text, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10
        )
        self.info_text.SetMinSize((-1, 60))

        # Buttons
        btn_sizer = wx.StdDialogButtonSizer()
        btn_sizer.AddButton(self.submit_btn)
        btn_sizer.AddButton(self.cancel_btn)
        btn_sizer.Realize()
        main_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 10)

        self.SetSizer(main_sizer)

    def _bind_events(self) -> None:
        """Bind event handlers."""
        self.submit_btn.Bind(wx.EVT_BUTTON, self._on_submit)

    def _get_system_info(self) -> str:
        """Collect system information."""
        return (
            f"- App Version: {__version__}\n"
            f"- OS: {platform.system()} {platform.release()}\n"
            f"- Python: {sys.version.split()[0]}"
        )

    def _on_submit(self, event: wx.CommandEvent) -> None:
        """Handle submit button click."""
        title = self.title_input.GetValue().strip()
        if not title:
            wx.MessageBox(
                "Please enter a title for the issue.",
                "Title Required",
                wx.OK | wx.ICON_WARNING,
            )
            self.title_input.SetFocus()
            return

        # Build issue body
        description = self.desc_input.GetValue().strip()
        system_info = self.info_text.GetValue()

        body_parts = []
        if description:
            body_parts.append(description)
        body_parts.append("\n---\n**System Information:**\n```")
        body_parts.append(system_info)
        body_parts.append("```")

        body = "\n".join(body_parts)

        # Determine label
        issue_type = self.type_choice.GetSelection()
        label = "bug" if issue_type == 0 else "enhancement"

        # Build URL with query parameters
        params = {
            "title": title,
            "body": body,
            "labels": label,
        }
        url = f"{ISSUE_URL}?{urllib.parse.urlencode(params)}"

        # Open in browser
        webbrowser.open(url)

        self.EndModal(wx.ID_OK)
