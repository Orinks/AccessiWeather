"""Update dialog for AccessiWeather.

This module provides dialogs for notifying users about available updates
and handling update installation.
"""

import logging
import threading
import webbrowser

import wx

from accessiweather.services.update_service import UpdateInfo, UpdateService
from accessiweather.version import __version__

logger = logging.getLogger(__name__)


class UpdateNotificationDialog(wx.Dialog):
    """Dialog to notify users about available updates."""

    def __init__(self, parent, update_info: UpdateInfo, update_service: UpdateService):
        """Initialize the update notification dialog.

        Args:
            parent: Parent window
            update_info: Information about the available update
            update_service: Update service instance
        """
        super().__init__(
            parent,
            title=f"Update Available - AccessiWeather v{update_info.version}",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self.update_info = update_info
        self.update_service = update_service
        self.download_thread = None

        self._init_ui()
        self.SetSizerAndFit(self.main_sizer)
        self.CenterOnParent()

        # Set minimum size
        self.SetMinSize((500, 400))

    def _init_ui(self):
        """Initialize the user interface."""
        self.main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Header
        header_text = f"A new version of AccessiWeather is available!"
        header_label = wx.StaticText(self, label=header_text)
        header_font = header_label.GetFont()
        header_font.SetWeight(wx.FONTWEIGHT_BOLD)
        header_font.SetPointSize(header_font.GetPointSize() + 2)
        header_label.SetFont(header_font)
        self.main_sizer.Add(header_label, 0, wx.ALL | wx.CENTER, 10)

        # Version info
        version_text = f"Current version: {__version__}\n"
        version_text += f"Available version: {self.update_info.version}"
        if self.update_info.is_prerelease:
            version_text += " (Development Build)"

        version_label = wx.StaticText(self, label=version_text)
        self.main_sizer.Add(version_label, 0, wx.ALL | wx.EXPAND, 10)

        # Release notes
        notes_label = wx.StaticText(self, label="Release Notes:")
        notes_font = notes_label.GetFont()
        notes_font.SetWeight(wx.FONTWEIGHT_BOLD)
        notes_label.SetFont(notes_font)
        self.main_sizer.Add(notes_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)

        # Release notes text control
        self.notes_ctrl = wx.TextCtrl(
            self,
            value=self.update_info.release_notes,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_WORDWRAP,
            name="Release Notes",
        )
        self.notes_ctrl.SetMinSize((450, 200))
        self.main_sizer.Add(self.notes_ctrl, 1, wx.ALL | wx.EXPAND, 10)

        # Installation options
        options_box = wx.StaticBoxSizer(wx.VERTICAL, self, "Installation Options")

        # Auto-install option (if available)
        settings = self.update_service.get_settings()
        auto_install_enabled = settings.get("auto_install_enabled", False)

        if auto_install_enabled and self.update_info.installer_asset:
            self.auto_install_radio = wx.RadioButton(
                self,
                label="Download and install automatically",
                style=wx.RB_GROUP,
                name="Auto Install Option",
            )
            options_box.Add(self.auto_install_radio, 0, wx.ALL, 5)

            auto_install_note = wx.StaticText(
                self,
                label="The installer will be downloaded and run automatically. You may need to confirm UAC prompts.",
            )
            auto_install_note.SetFont(auto_install_note.GetFont().Smaller())
            options_box.Add(auto_install_note, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)
        else:
            self.auto_install_radio = None

        # Manual download option
        manual_label = "Download manually" if self.auto_install_radio else "Download update"
        self.manual_download_radio = wx.RadioButton(
            self,
            label=manual_label,
            style=wx.RB_GROUP if not self.auto_install_radio else 0,
            name="Manual Download Option",
        )
        options_box.Add(self.manual_download_radio, 0, wx.ALL, 5)

        manual_note = wx.StaticText(
            self,
            label="Open the download page in your web browser to manually download and install the update.",
        )
        manual_note.SetFont(manual_note.GetFont().Smaller())
        options_box.Add(manual_note, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        # Set default selection
        if self.auto_install_radio:
            self.auto_install_radio.SetValue(True)
        else:
            self.manual_download_radio.SetValue(True)

        self.main_sizer.Add(options_box, 0, wx.ALL | wx.EXPAND, 10)

        # Progress bar (initially hidden)
        self.progress_gauge = wx.Gauge(self, range=100, name="Download Progress")
        self.progress_label = wx.StaticText(self, label="")
        self.progress_gauge.Hide()
        self.progress_label.Hide()
        self.main_sizer.Add(self.progress_label, 0, wx.LEFT | wx.RIGHT, 10)
        self.main_sizer.Add(self.progress_gauge, 0, wx.ALL | wx.EXPAND, 10)

        # Buttons
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Skip this version button
        self.skip_button = wx.Button(self, label="Skip This Version", name="Skip Version")
        button_sizer.Add(self.skip_button, 0, wx.ALL, 5)

        # Remind later button
        self.remind_button = wx.Button(self, label="Remind Me Later", name="Remind Later")
        button_sizer.Add(self.remind_button, 0, wx.ALL, 5)

        button_sizer.AddStretchSpacer()

        # Install/Download button
        self.install_button = wx.Button(self, label="Install Update", name="Install Update")
        self.install_button.SetDefault()
        button_sizer.Add(self.install_button, 0, wx.ALL, 5)

        # Cancel button
        self.cancel_button = wx.Button(self, wx.ID_CANCEL, "Cancel")
        button_sizer.Add(self.cancel_button, 0, wx.ALL, 5)

        self.main_sizer.Add(button_sizer, 0, wx.ALL | wx.EXPAND, 10)

        # Bind events
        self.Bind(wx.EVT_BUTTON, self.OnSkipVersion, self.skip_button)
        self.Bind(wx.EVT_BUTTON, self.OnRemindLater, self.remind_button)
        self.Bind(wx.EVT_BUTTON, self.OnInstallUpdate, self.install_button)
        self.Bind(wx.EVT_BUTTON, self.OnCancel, self.cancel_button)

        # Update button label based on selection
        if self.auto_install_radio:
            self.Bind(wx.EVT_RADIOBUTTON, self.OnInstallOptionChanged, self.auto_install_radio)
        self.Bind(wx.EVT_RADIOBUTTON, self.OnInstallOptionChanged, self.manual_download_radio)

    def OnInstallOptionChanged(self, event):
        """Handle installation option change."""
        if self.auto_install_radio and self.auto_install_radio.GetValue():
            self.install_button.SetLabel("Install Update")
        else:
            self.install_button.SetLabel("Download Update")

    def OnSkipVersion(self, event):
        """Handle skip version button."""
        # Mark this version as skipped
        self.update_service.update_state["last_notified_version"] = self.update_info.version
        self.update_service._save_update_state()

        self.EndModal(wx.ID_IGNORE)

    def OnRemindLater(self, event):
        """Handle remind later button."""
        # Don't update last_notified_version so we'll be reminded again
        self.EndModal(wx.ID_CANCEL)

    def OnCancel(self, event):
        """Handle cancel button."""
        self.EndModal(wx.ID_CANCEL)

    def OnInstallUpdate(self, event):
        """Handle install/download update button."""
        if self.auto_install_radio and self.auto_install_radio.GetValue():
            # Auto install
            self._start_auto_install()
        else:
            # Manual download - open browser
            webbrowser.open(self.update_info.release_url)
            self.EndModal(wx.ID_OK)

    def _start_auto_install(self):
        """Start automatic installation process."""
        # Disable buttons and show progress
        self.install_button.Enable(False)
        self.skip_button.Enable(False)
        self.remind_button.Enable(False)

        self.progress_label.SetLabel("Downloading update...")
        self.progress_label.Show()
        self.progress_gauge.Show()
        self.Layout()

        # Start download in background thread
        self.download_thread = threading.Thread(target=self._download_and_install, daemon=True)
        self.download_thread.start()

    def _download_and_install(self):
        """Download and install update in background thread."""
        try:
            # Set up progress callback for this download
            original_callback = self.update_service.progress_callback
            self.update_service.progress_callback = self._on_progress_update

            success = self.update_service.download_and_install_update(
                self.update_info, install_type="installer"
            )

            # Restore original callback
            self.update_service.progress_callback = original_callback

            # Update UI on main thread
            wx.CallAfter(self._on_download_complete, success)

        except Exception as e:
            logger.error(f"Error during auto-install: {e}")
            # Restore original callback
            if "original_callback" in locals():
                self.update_service.progress_callback = original_callback
            wx.CallAfter(self._on_download_complete, False)

    def _on_download_complete(self, success: bool):
        """Handle download completion on main thread."""
        if success:
            self.progress_label.SetLabel("Download complete! Installer is starting...")
            self.progress_gauge.SetValue(100)

            # Show completion message
            wx.MessageBox(
                "The update installer has been started. AccessiWeather will close to allow the update to complete.",
                "Update Started",
                wx.OK | wx.ICON_INFORMATION,
                self,
            )

            # Close the application to allow update
            self.EndModal(wx.ID_YES)  # Special return code to indicate app should exit

        else:
            self.progress_label.SetLabel("Download failed. Please try manual download.")

            # Re-enable buttons
            self.install_button.Enable(True)
            self.skip_button.Enable(True)
            self.remind_button.Enable(True)

            # Switch to manual download option
            self.manual_download_radio.SetValue(True)
            self.install_button.SetLabel("Download Update")

    def _on_progress_update(self, progress: float):
        """Handle progress updates from download."""
        wx.CallAfter(self._update_progress, progress)

    def _update_progress(self, progress: float):
        """Update progress bar on main thread."""
        self.progress_gauge.SetValue(int(progress))
        self.progress_label.SetLabel(f"Downloading update... {progress:.1f}%")


class UpdateProgressDialog(wx.ProgressDialog):
    """Simple progress dialog for update operations."""

    def __init__(self, parent, title="Checking for Updates"):
        super().__init__(
            title=title,
            message="Please wait...",
            maximum=100,
            parent=parent,
            style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE,
        )

        self.SetSize((400, 150))
        self.CenterOnParent()
