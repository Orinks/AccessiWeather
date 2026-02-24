"""
Update available dialog for AccessiWeather.

Shows the changelog for a new version and lets the user decide
whether to download it.
"""

import wx


class UpdateAvailableDialog(wx.Dialog):
    """Dialog showing update details with changelog."""

    def __init__(
        self,
        parent: wx.Window,
        current_version: str,
        new_version: str,
        channel_label: str,
        release_notes: str,
    ):
        """
        Initialize the update dialog.

        Args:
            parent: Parent window
            current_version: Currently installed version string
            new_version: Available version string
            channel_label: "Stable" or "Nightly"
            release_notes: Release notes / changelog text

        """
        super().__init__(
            parent,
            title=f"{channel_label} Update Available",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self._build_ui(current_version, new_version, channel_label, release_notes)
        self.SetSize(500, 420)
        self.CenterOnParent()

    def _build_ui(
        self,
        current_version: str,
        new_version: str,
        channel_label: str,
        release_notes: str,
    ) -> None:
        """Build the dialog UI."""
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Header
        header = wx.StaticText(
            self,
            label=(
                f"A new {channel_label} update is available!\n"
                f"Current: {current_version}  \u2192  Latest: {new_version}"
            ),
        )
        sizer.Add(header, 0, wx.ALL | wx.EXPAND, 10)

        # Changelog label
        changelog_label = wx.StaticText(self, label="What's new:")
        sizer.Add(changelog_label, 0, wx.LEFT | wx.RIGHT, 10)

        # Changelog text (read-only, multi-line)
        notes = release_notes.strip() if release_notes else "No release notes available."
        self.changelog_text = wx.TextCtrl(
            self,
            value=notes,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2 | wx.HSCROLL,
        )
        sizer.Add(self.changelog_text, 1, wx.ALL | wx.EXPAND, 10)

        # Buttons
        btn_sizer = wx.StdDialogButtonSizer()
        download_btn = wx.Button(self, wx.ID_OK, "&Download Update")
        download_btn.SetDefault()
        cancel_btn = wx.Button(self, wx.ID_CANCEL, "&Cancel")
        btn_sizer.AddButton(download_btn)
        btn_sizer.AddButton(cancel_btn)
        btn_sizer.Realize()
        sizer.Add(btn_sizer, 0, wx.ALL | wx.EXPAND, 10)

        self.SetSizer(sizer)

        # Focus the changelog so the user can read it immediately
        self.changelog_text.SetFocus()
        # Move cursor to start so screen readers begin at the top
        self.changelog_text.SetInsertionPoint(0)
