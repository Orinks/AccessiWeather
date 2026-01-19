"""Community Sound Packs Browser Dialog using gui_builder."""

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

import wx
from gui_builder import fields, forms

from ...notifications.sound_pack_installer import SoundPackInstaller
from ...services.community_soundpack_service import (
    CommunityPack,
    CommunitySoundPackService,
)
from .progress_dialog import ProgressDialog

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class CommunityPacksBrowserDialog(forms.Dialog):
    """Dialog for browsing and installing community sound packs using gui_builder."""

    # Header with search
    filter_label = fields.StaticText(label="Filter packs:")
    search_input = fields.Text(label="Search by name or author")
    refresh_button = fields.Button(label="&Refresh")

    # Pack list section
    list_header = fields.StaticText(label="Available Packs:")
    pack_list = fields.ListBox(label="Available community sound packs")

    # Details section
    name_label = fields.StaticText(label="Select a pack to view details")
    author_label = fields.StaticText(label="")
    version_label = fields.StaticText(label="")
    size_label = fields.StaticText(label="")

    # Description
    description_header = fields.StaticText(label="Description:")
    description_text = fields.Text(
        label="Pack description",
        multiline=True,
        readonly=True,
    )

    # Status
    status_label = fields.StaticText(label="")

    # Buttons
    install_button = fields.Button(label="&Download && Install")
    close_button = fields.Button(label="&Close")

    def __init__(
        self,
        soundpacks_dir: Path,
        on_installed: Callable[[str], None] | None = None,
        **kwargs,
    ):
        """Initialize the community packs browser dialog."""
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

        kwargs.setdefault("title", "Browse Community Sound Packs")
        super().__init__(**kwargs)

    def render(self, **kwargs):
        """Render the dialog and set up components."""
        super().render(**kwargs)
        self._setup_initial_state()
        self._setup_accessibility()
        # Load packs after dialog is shown
        wx.CallAfter(self._start_loading)

    def _setup_initial_state(self) -> None:
        """Set up initial state."""
        self.install_button.disable()

    def _setup_accessibility(self) -> None:
        """Set up accessibility labels."""
        self.search_input.set_accessible_label("Search for sound packs by name or author")
        self.pack_list.set_accessible_label("Available community sound packs")
        self.description_text.set_accessible_label("Selected pack description")

    def _pack_key(self, pack: CommunityPack) -> str:
        """Create a stable key for a pack."""
        return f"{pack.name}|{pack.author}|{pack.version}"

    def _start_loading(self, force: bool = False) -> None:
        """Start loading packs in background."""
        if not self.service:
            self.status_label.set_label("Community packs unavailable")
            return

        self.status_label.set_label("Loading community packs...")
        self.refresh_button.disable()
        self.pack_list.set_items(["Loading..."])

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
        self.refresh_button.enable()
        self.status_label.set_label(f"Found {len(packs)} community packs")

    def _on_load_error(self, error: str) -> None:
        """Handle load error."""
        self.pack_list.set_items(["Failed to load packs"])
        self.status_label.set_label(f"Error: {error}")
        self.refresh_button.enable()

    def _populate_list(self, filter_text: str = "") -> None:
        """Populate the pack list."""
        self._selected_key = None
        self.install_button.disable()

        ft = filter_text.strip().lower()
        items = []

        for pack in self._packs:
            if ft and ft not in pack.name.lower() and ft not in pack.author.lower():
                continue

            key = self._pack_key(pack)
            size_str = f"{(pack.file_size or 0) / (1024 * 1024):.1f} MB" if pack.file_size else "?"
            display = f"{pack.name} v{pack.version} by {pack.author} ({size_str})"
            items.append((display, key))

        if items:
            self.pack_list.set_items([item[0] for item in items])
            # Store keys for lookup
            self._list_keys = [item[1] for item in items]
        else:
            self.pack_list.set_items(["No packs found"])
            self._list_keys = []
            self._update_details(None)

    @search_input.add_callback
    def on_search(self):
        """Handle search input."""
        self._populate_list(self.search_input.get_value())

    @refresh_button.add_callback
    def on_refresh(self):
        """Handle refresh button."""
        self._start_loading(force=True)

    @pack_list.add_callback
    def on_pack_selected(self):
        """Handle pack selection."""
        index = self.pack_list.get_index()
        if index is None or not hasattr(self, "_list_keys") or index >= len(self._list_keys):
            self._selected_key = None
            self._update_details(None)
            self.install_button.disable()
            return

        key = self._list_keys[index]
        if not key or key not in self._pack_index:
            self._selected_key = None
            self._update_details(None)
            self.install_button.disable()
            return

        self._selected_key = key
        pack = self._pack_index[key]
        self._update_details(pack)
        self.install_button.enable(bool(pack.download_url or getattr(pack, "repo_path", None)))

    def _update_details(self, pack: CommunityPack | None) -> None:
        """Update the details panel."""
        if not pack:
            self.name_label.set_label("Select a pack to view details")
            self.author_label.set_label("")
            self.version_label.set_label("")
            self.size_label.set_label("")
            self.description_text.set_value("")
            return

        self.name_label.set_label(pack.name)
        self.author_label.set_label(f"Author: {pack.author}")
        self.version_label.set_label(f"Version: {pack.version}")
        if pack.file_size:
            mb = pack.file_size / (1024 * 1024)
            self.size_label.set_label(f"Size: {mb:.1f} MB")
        else:
            self.size_label.set_label("Size: Unknown")
        self.description_text.set_value(pack.description or "No description provided.")

    @install_button.add_callback
    def on_install(self):
        """Handle install button."""
        if not self._selected_key or not self.service:
            return

        pack = self._pack_index.get(self._selected_key)
        if not pack:
            return

        # Get parent control for progress dialog
        parent_ctrl = self.widget.control

        # Show progress dialog
        progress = ProgressDialog(
            title=f"Downloading {pack.name}",
            message="Preparing download...",
            parent=parent_ctrl,
        )
        progress.render()
        progress.widget.control.Show()

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
        wx.CallLater(1500, progress.widget.control.Destroy)

    def _on_install_success(self, progress: ProgressDialog, pack_name: str) -> None:
        """Handle install success."""
        progress.widget.control.Destroy()
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
        wx.CallLater(3000, progress.widget.control.Destroy)

    @close_button.add_callback
    def on_close(self):
        """Handle close button."""
        self.widget.control.EndModal(wx.ID_CLOSE)

    def destroy(self) -> None:
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


def show_community_packs_dialog(
    parent,
    soundpacks_dir: Path,
    on_installed: Callable[[str], None] | None = None,
) -> None:
    """Show the community packs browser dialog."""
    parent_ctrl = getattr(parent, "control", parent)
    dialog = CommunityPacksBrowserDialog(soundpacks_dir, on_installed, parent=parent_ctrl)
    dialog.render()
    dialog.widget.control.ShowModal()
    dialog.destroy()
    dialog.widget.control.Destroy()
