"""
Community Sound Packs browser dialog.

Provides a modal UI to browse, search, and install community sound packs
fetched via CommunitySoundPackService. Downloads are shown with a progress
indicator using the same UX pattern as UpdateProgressDialog.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from pathlib import Path

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW

from accessiweather.dialogs.update_progress_dialog import UpdateProgressDialog
from accessiweather.notifications.sound_pack_installer import SoundPackInstaller
from accessiweather.services.community_soundpack_service import (
    CommunityPack,
    CommunitySoundPackService,
)

logger = logging.getLogger(__name__)


class CommunityPacksBrowserDialog:
    """
    Modal dialog to browse community sound packs and install them.

    Args:
    ----
        app: The Toga app
        service: Service used to fetch and download packs
        installer: Installer used to install a downloaded ZIP
        on_installed: Optional callback fired with pack display name after install

    """

    def __init__(
        self,
        app: toga.App,
        service: CommunitySoundPackService,
        installer: SoundPackInstaller,
        on_installed: Callable[[str], None] | None = None,
    ) -> None:
        """Initialize the browser dialog."""
        self.app = app
        self.service = service
        self.installer = installer
        self.on_installed = on_installed

        self.window: toga.Window | None = None
        self.pack_list: toga.DetailedList | None = None
        self.search_input: toga.TextInput | None = None
        self.refresh_button: toga.Button | None = None

        self._packs: list[CommunityPack] = []
        self._pack_lookup: dict[str, CommunityPack] = {}

    def show(self) -> None:
        self.window = toga.Window(
            title="Browse Community Sound Packs", size=(760, 520), resizable=False
        )
        main = toga.Box(style=Pack(direction=COLUMN, padding=10))

        # Header with search and refresh
        header = toga.Box(style=Pack(direction=ROW, margin_bottom=8))
        hint_label = toga.Label(
            "Filter packs:", style=Pack(margin_right=6, alignment="center", baseline=True)
        )
        header.add(hint_label)
        self.search_input = toga.TextInput(
            placeholder="Search by name or author", style=Pack(flex=1, margin_right=8)
        )
        self.search_input.on_change = self._on_search
        with contextlib.suppress(AttributeError):
            self.search_input.aria_label = "Filter community sound packs"
        self.refresh_button = toga.Button(
            "Refresh", on_press=self._on_refresh, style=Pack(width=100)
        )
        header.add(self.search_input)
        header.add(self.refresh_button)
        main.add(header)

        # List of packs (detailed list provides better screen reader support)
        self.pack_list = toga.DetailedList(
            on_select=self._on_select_row,
            style=Pack(flex=1, margin_bottom=8),
        )
        with contextlib.suppress(AttributeError):
            self.pack_list.aria_label = "Community sound packs"
            self.pack_list.aria_description = (
                "Browse available community sound packs. Each entry announces name, version, author, size, "
                "and a short description. Use the arrow keys to explore and press Enter to select."
            )
        main.add(self.pack_list)

        # Button row
        buttons = toga.Box(style=Pack(direction=ROW))
        buttons.add(toga.Box(style=Pack(flex=1)))
        self.download_button = toga.Button(
            "Download & Install",
            on_press=self._on_download,
            enabled=False,
            style=Pack(margin_right=10),
        )
        self.preview_button = toga.Button(
            "Preview Details", on_press=self._on_preview, enabled=False, style=Pack(margin_right=10)
        )
        close_button = toga.Button("Close", on_press=lambda w: self.window.close())
        buttons.add(self.download_button)
        buttons.add(self.preview_button)
        buttons.add(close_button)
        main.add(buttons)

        self.window.content = main
        self.app.windows.add(self.window)
        self.window.show()
        # Focus search for accessibility
        asyncio.create_task(self._focus_search())
        # Load packs
        asyncio.create_task(self._load_packs())

    async def _focus_search(self):
        await asyncio.sleep(0.2)
        try:
            if self.search_input:
                self.search_input.focus()
        except Exception:
            pass

    async def _load_packs(self, force: bool = False):
        try:
            if self.pack_list:
                self.pack_list.data.clear()
            # Loading state
            if self.pack_list:
                self.pack_list.data.append(
                    {
                        "title": "Loading…",
                        "subtitle": "Fetching community packs",
                    }
                )
            packs = await self.service.fetch_available_packs(force_refresh=force)
            self._packs = packs
            await self._populate_list()
        except Exception as e:
            logger.error(f"Failed to load community packs: {e}")
            with contextlib.suppress(Exception):
                await self.app.main_window.error_dialog(
                    "Community Packs", f"Failed to load community packs: {e}"
                )

    async def _populate_list(self, filter_text: str = ""):
        if not self.pack_list:
            return
        self.pack_list.data.clear()
        self._pack_lookup.clear()
        ft = (filter_text or "").strip().lower()
        added = 0
        for p in self._packs:
            if ft and (ft not in p.name.lower()) and (ft not in p.author.lower()):
                continue
            size_str = f"{(p.file_size or 0) / (1024 * 1024):.1f} MB" if p.file_size else "?"
            pack_key = f"{p.name}::{p.author}::{p.version}"
            self._pack_lookup[pack_key] = p
            self.pack_list.data.append(
                {
                    "title": p.name,
                    "subtitle": self._format_accessible_summary(p, size_str),
                    "pack_key": pack_key,
                }
            )
            added += 1
        if added == 0:
            # Empty-state guidance when no packs are available or filtered out
            self.pack_list.data.append(
                {
                    "title": "No community packs found",
                    "subtitle": (
                        "You may be offline or rate-limited. Try Refresh or adjust search criteria."
                    ),
                }
            )
        if self.download_button:
            self.download_button.enabled = False

    def _on_search(self, widget):
        ft = widget.value or ""
        asyncio.create_task(self._populate_list(ft))

    def _on_refresh(self, widget):
        asyncio.create_task(self._load_packs(force=True))

    def _on_select_row(self, widget):
        has_sel = bool(widget.selection)
        self.preview_button.enabled = has_sel
        # Enable Download only if a pack is selected and has a valid download_url
        selected = self._get_selected_pack() if has_sel else None
        has_download_source = bool(
            selected and (selected.download_url or getattr(selected, "repo_path", None))
        )
        self.download_button.enabled = has_download_source

    def _get_selected_pack(self) -> CommunityPack | None:
        if not self.pack_list or not self.pack_list.selection:
            return None
        row = self.pack_list.selection
        key = getattr(row, "pack_key", None)
        if key and key in self._pack_lookup:
            return self._pack_lookup[key]
        title = getattr(row, "title", None)
        if title:
            for pack in self._packs:
                if pack.name == title:
                    return pack
        return None

    def _format_accessible_summary(self, p: CommunityPack, size: str) -> str:
        desc = (p.description or "").replace("\n", " ").strip()
        summary = f"Version {p.version} by {p.author}. Size {size}."
        if desc:
            summary = f"{summary} {desc}"
        if getattr(p, "repo_path", None) and not p.download_url:
            summary = f"{summary} Downloads directly from repository contents."
        return summary

    def _format_pack_details(self, p: CommunityPack) -> str:
        parts = [
            f"Name: {p.name}",
            f"Author: {p.author}",
            f"Version: {p.version}",
        ]
        if p.description:
            parts.append("")
            parts.append(p.description)
        if p.repository_url:
            parts.append("")
            parts.append(f"More info: {p.repository_url}")
        return "\n".join(parts)

    def _on_preview(self, widget):
        p = self._get_selected_pack()
        if not p:
            return
        asyncio.create_task(
            self.app.main_window.info_dialog("Pack Details", self._format_pack_details(p))
        )

    def _on_download(self, widget):
        p = self._get_selected_pack()
        if not p:
            return
        asyncio.create_task(self._download_and_install(p))

    async def _download_and_install(self, p: CommunityPack):
        try:
            progress = UpdateProgressDialog(self.app, title=f"Downloading {p.name}")
            progress.show_and_prepare()

            async def cb(pc: float, downloaded: int, total: int):
                await progress.update_progress(pc, downloaded, total)
                return not progress.is_cancelled

            # Download to a temp directory
            tmp_dir = Path(self.installer.soundpacks_dir) / "_downloads"
            zip_path = await self.service.download_pack(p, tmp_dir, cb)

            if progress.is_cancelled:
                await progress.complete_error("Download cancelled")
                return

            # Install from ZIP (offload to thread to avoid blocking UI)
            await progress.set_status("Installing...", f"Installing pack {p.name}")
            ok, msg = await asyncio.to_thread(self.installer.install_from_zip, zip_path, None)
            if ok:
                await progress.complete_success("Installed successfully")
                # Notify parent to refresh; pass the pack display name
                if self.on_installed:
                    with contextlib.suppress(Exception):
                        # If installer returned a quoted success message, still send p.name per contract
                        self.on_installed(p.name)
            else:
                await progress.complete_error(msg)
        except Exception as e:
            logger.error(f"Failed to download/install pack: {e}")
            with contextlib.suppress(Exception):
                await progress.complete_error(str(e))


# Local contextlib
import contextlib  # noqa: E402
