"""wxPython Community Sound Packs Browser Dialog."""

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

import wx

from ...notifications.sound_pack_installer import SoundPackInstaller
from ...services.community_soundpack_service import (
    CommunityPack,
    CommunitySoundPackService,
)
from .progress_dialog import ProgressDialog

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class CommunityPacksBrowserDialog(wx.Dialog):
    """Dialog for browsing and installing community sound packs."""

    def __init__(
        self,
        parent: wx.Window,
        soundpacks_dir: Path,
        on_installed: Callable[[str], None] | None = None,
    ) -> None:
        """Initialize the community packs browser dialog."""
        super().__init__(
            parent,
            title="Browse Community Sound Packs",
            size=(850, 550),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self.soundpacks_dir = soundpacks_dir
        self.on_installed = on_installed
        self.installer = SoundPackInstaller(soundpacks_dir)

        # Initialize service
        try:
            self.service = CommunitySoundPackService()
        except Exception as e:
            logger.error(f"Failed to initialize community service: {e}")
            self.service = None

        # Data
        self._packs: list[CommunityPack] = []
        self._pack_index: dict[str, CommunityPack] = {}
        self._selected_key: str | None = None

        self._create_ui()
        self.Centre()

        # Load packs after dialog is shown
        wx.CallAfter(self._start_loading)

    def _create_ui(self) -> None:
        """Create the dialog UI."""
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Header with search
        header_sizer = wx.BoxSizer(wx.HORIZONTAL)
        header_sizer.Add(
            wx.StaticText(panel, label="Filter packs:"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            5,
        )
        self.search_input = wx.TextCtrl(panel, size=(250, -1))
        self.search_input.SetName("Filter community packs")
        self.search_input.SetHint("Search by name or author")
        self.search_input.Bind(wx.EVT_TEXT, self._on_search)
        header_sizer.Add(self.search_input, 1, wx.RIGHT, 10)

        self.refresh_btn = wx.Button(panel, label="Refresh")
        self.refresh_btn.SetName("Refresh community packs")
        self.refresh_btn.Bind(wx.EVT_BUTTON, self._on_refresh)
        header_sizer.Add(self.refresh_btn, 0)

        main_sizer.Add(header_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # Main content - horizontal split
        content_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Left panel - Pack list
        left_panel = self._create_pack_list_panel(panel)
        content_sizer.Add(left_panel, 1, wx.EXPAND | wx.RIGHT, 10)

        # Right panel - Pack details
        right_panel = self._create_details_panel(panel)
        content_sizer.Add(right_panel, 1, wx.EXPAND)

        main_sizer.Add(content_sizer, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        # Status label
        self.status_label = wx.StaticText(panel, label="")
        main_sizer.Add(self.status_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)

        # Bottom buttons
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_sizer.AddStretchSpacer()

        self.install_btn = wx.Button(panel, label="Download && Install")
        self.install_btn.SetName("Download and install selected pack")
        self.install_btn.Bind(wx.EVT_BUTTON, self._on_install)
        self.install_btn.Enable(False)
        button_sizer.Add(self.install_btn, 0, wx.RIGHT, 5)

        close_btn = wx.Button(panel, wx.ID_CLOSE, label="Close")
        close_btn.SetName("Close community packs dialog")
        close_btn.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CLOSE))
        button_sizer.Add(close_btn, 0)

        main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.ALL, 10)

        panel.SetSizer(main_sizer)

    def _create_pack_list_panel(self, parent: wx.Window) -> wx.BoxSizer:
        """Create the pack list panel."""
        sizer = wx.BoxSizer(wx.VERTICAL)

        label = wx.StaticText(parent, label="Available Packs:")
        label_font = label.GetFont()
        label_font.SetWeight(wx.FONTWEIGHT_BOLD)
        label.SetFont(label_font)
        sizer.Add(label, 0, wx.BOTTOM, 5)

        self.pack_listbox = wx.ListBox(parent, style=wx.LB_SINGLE)
        self.pack_listbox.SetName("Available community packs list")
        self.pack_listbox.Bind(wx.EVT_LISTBOX, self._on_pack_selected)
        sizer.Add(self.pack_listbox, 1, wx.EXPAND)

        return sizer

    def _create_details_panel(self, parent: wx.Window) -> wx.BoxSizer:
        """Create the details panel."""
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Details box
        details_box = wx.StaticBox(parent, label="Pack Details")
        details_sizer = wx.StaticBoxSizer(details_box, wx.VERTICAL)

        self.name_label = wx.StaticText(parent, label="Select a pack to view details")
        name_font = self.name_label.GetFont()
        name_font.SetPointSize(12)
        name_font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.name_label.SetFont(name_font)
        details_sizer.Add(self.name_label, 0, wx.ALL, 5)

        self.author_label = wx.StaticText(parent, label="")
        details_sizer.Add(self.author_label, 0, wx.LEFT | wx.BOTTOM, 5)

        self.version_label = wx.StaticText(parent, label="")
        details_sizer.Add(self.version_label, 0, wx.LEFT | wx.BOTTOM, 5)

        self.size_label = wx.StaticText(parent, label="")
        details_sizer.Add(self.size_label, 0, wx.LEFT | wx.BOTTOM, 5)

        sizer.Add(details_sizer, 0, wx.EXPAND | wx.BOTTOM, 10)

        # Description
        desc_label = wx.StaticText(parent, label="Description:")
        desc_font = desc_label.GetFont()
        desc_font.SetWeight(wx.FONTWEIGHT_BOLD)
        desc_label.SetFont(desc_font)
        sizer.Add(desc_label, 0, wx.BOTTOM, 5)

        self.description_text = wx.TextCtrl(
            parent,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_WORDWRAP,
            size=(-1, 150),
        )
        self.description_text.SetName("Selected pack description")
        sizer.Add(self.description_text, 1, wx.EXPAND)

        return sizer

    def _pack_key(self, pack: CommunityPack) -> str:
        """Create a stable key for a pack."""
        return f"{pack.name}|{pack.author}|{pack.version}"

    def _start_loading(self, force: bool = False) -> None:
        """Start loading packs in background."""
        if not self.service:
            self.status_label.SetLabel("Community packs unavailable")
            return

        self.status_label.SetLabel("Loading community packs...")
        self.refresh_btn.Enable(False)
        self.pack_listbox.Clear()
        self.pack_listbox.Append("Loading...")

        # Run async operation in thread
        def load_thread():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    packs = loop.run_until_complete(
                        self.service.fetch_available_packs(force_refresh=force)
                    )
                    wx.CallAfter(self._on_packs_loaded, packs)
                finally:
                    loop.close()
            except Exception as e:
                logger.error(f"Failed to load community packs: {e}")
                wx.CallAfter(self._on_load_error, str(e))

        thread = threading.Thread(target=load_thread, daemon=True)
        thread.start()

    def _on_packs_loaded(self, packs: list[CommunityPack]) -> None:
        """Handle packs loaded."""
        self._packs = packs
        self._pack_index = {self._pack_key(p): p for p in packs}
        self._populate_list()
        self.refresh_btn.Enable(True)
        self.status_label.SetLabel(f"Found {len(packs)} community packs")

    def _on_load_error(self, error: str) -> None:
        """Handle load error."""
        self.pack_listbox.Clear()
        self.pack_listbox.Append("Failed to load packs")
        self.status_label.SetLabel(f"Error: {error}")
        self.refresh_btn.Enable(True)

    def _populate_list(self, filter_text: str = "") -> None:
        """Populate the pack list."""
        self.pack_listbox.Clear()
        self._selected_key = None
        self.install_btn.Enable(False)

        ft = filter_text.strip().lower()

        for pack in self._packs:
            if ft and ft not in pack.name.lower() and ft not in pack.author.lower():
                continue

            key = self._pack_key(pack)
            size_str = f"{(pack.file_size or 0) / (1024 * 1024):.1f} MB" if pack.file_size else "?"
            display = f"{pack.name} v{pack.version} by {pack.author} ({size_str})"
            self.pack_listbox.Append(display, key)

        if self.pack_listbox.GetCount() == 0:
            self.pack_listbox.Append("No packs found")
            self._update_details(None)

    def _on_search(self, event) -> None:
        """Handle search input."""
        self._populate_list(self.search_input.GetValue())

    def _on_refresh(self, event) -> None:
        """Handle refresh button."""
        self._start_loading(force=True)

    def _on_pack_selected(self, event) -> None:
        """Handle pack selection."""
        sel = self.pack_listbox.GetSelection()
        if sel == wx.NOT_FOUND:
            self._selected_key = None
            self._update_details(None)
            self.install_btn.Enable(False)
            return

        key = self.pack_listbox.GetClientData(sel)
        if not key or key not in self._pack_index:
            self._selected_key = None
            self._update_details(None)
            self.install_btn.Enable(False)
            return

        self._selected_key = key
        pack = self._pack_index[key]
        self._update_details(pack)
        self.install_btn.Enable(bool(pack.download_url or getattr(pack, "repo_path", None)))

    def _update_details(self, pack: CommunityPack | None) -> None:
        """Update the details panel."""
        if not pack:
            self.name_label.SetLabel("Select a pack to view details")
            self.author_label.SetLabel("")
            self.version_label.SetLabel("")
            self.size_label.SetLabel("")
            self.description_text.SetValue("")
            return

        self.name_label.SetLabel(pack.name)
        self.author_label.SetLabel(f"Author: {pack.author}")
        self.version_label.SetLabel(f"Version: {pack.version}")
        if pack.file_size:
            mb = pack.file_size / (1024 * 1024)
            self.size_label.SetLabel(f"Size: {mb:.1f} MB")
        else:
            self.size_label.SetLabel("Size: Unknown")
        self.description_text.SetValue(pack.description or "No description provided.")

    def _on_install(self, event) -> None:
        """Handle install button."""
        if not self._selected_key or not self.service:
            return

        pack = self._pack_index.get(self._selected_key)
        if not pack:
            return

        # Show progress dialog
        progress = ProgressDialog(self, f"Downloading {pack.name}", "Preparing download...")
        progress.Show()

        def download_thread():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    tmp_dir = self.soundpacks_dir / "_downloads"
                    tmp_dir.mkdir(exist_ok=True)

                    def on_progress(pct: float, downloaded: int, total: int) -> bool:
                        if total > 0:
                            detail = f"{downloaded / (1024 * 1024):.1f} MB of {total / (1024 * 1024):.1f} MB"
                        else:
                            detail = f"{downloaded / (1024 * 1024):.1f} MB downloaded"
                        return progress.update_progress(pct, f"Downloading {pack.name}...", detail)

                    zip_path = loop.run_until_complete(
                        self.service.download_pack(pack, tmp_dir, on_progress)
                    )

                    if progress.is_cancelled:
                        wx.CallAfter(self._on_download_cancelled, progress)
                        return

                    progress.set_status("Installing...", f"Installing {pack.name}")
                    ok, msg = self.installer.install_from_zip(zip_path, None)

                    if ok:
                        wx.CallAfter(self._on_install_success, progress, pack.name)
                    else:
                        wx.CallAfter(self._on_install_error, progress, msg)

                finally:
                    loop.close()
            except Exception as e:
                logger.error(f"Download/install failed: {e}")
                wx.CallAfter(self._on_install_error, progress, str(e))

        thread = threading.Thread(target=download_thread, daemon=True)
        thread.start()

    def _on_download_cancelled(self, progress: ProgressDialog) -> None:
        """Handle download cancelled."""
        progress.complete_error("Download cancelled")
        wx.CallLater(1500, progress.Destroy)

    def _on_install_success(self, progress: ProgressDialog, pack_name: str) -> None:
        """Handle install success."""
        progress.Destroy()
        wx.MessageBox(
            f'"{pack_name}" has been installed.\n\n'
            "Switch to the Sound Pack Manager or Settings > Audio to activate it.",
            "Sound Pack Installed",
            wx.OK | wx.ICON_INFORMATION,
        )
        if self.on_installed:
            self.on_installed(pack_name)

    def _on_install_error(self, progress: ProgressDialog, error: str) -> None:
        """Handle install error."""
        progress.complete_error(error)
        wx.CallLater(3000, progress.Destroy)

    def Destroy(self) -> bool:
        """Clean up resources before destroying."""
        # Clean up community service
        if self.service:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self.service.aclose())
                finally:
                    loop.close()
            except Exception:
                pass
        return super().Destroy()


def show_community_packs_dialog(
    parent: wx.Window,
    soundpacks_dir: Path,
    on_installed: Callable[[str], None] | None = None,
) -> None:
    """Show the community packs browser dialog."""
    parent_ctrl = getattr(parent, "control", parent)
    dialog = CommunityPacksBrowserDialog(parent_ctrl, soundpacks_dir, on_installed)
    dialog.ShowModal()
    dialog.Destroy()
