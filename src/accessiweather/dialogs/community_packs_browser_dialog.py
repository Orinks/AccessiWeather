"""Community Sound Packs browser dialog.

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
    """Modal dialog to browse community sound packs and install them.

    Args:
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
        self.table: toga.Table | None = None
        self.search_input: toga.TextInput | None = None
        self.refresh_button: toga.Button | None = None

        self._packs: list[CommunityPack] = []

    def show(self) -> None:
        self.window = toga.Window(
            title="Browse Community Sound Packs", size=(760, 520), resizable=False
        )
        main = toga.Box(style=Pack(direction=COLUMN, padding=10))

        # Header with search and refresh
        header = toga.Box(style=Pack(direction=ROW, margin_bottom=8))
        self.search_input = toga.TextInput(
            placeholder="Search by name or author", style=Pack(flex=1, margin_right=8)
        )
        self.search_input.on_change = self._on_search
        self.refresh_button = toga.Button(
            "Refresh", on_press=self._on_refresh, style=Pack(width=100)
        )
        header.add(self.search_input)
        header.add(self.refresh_button)
        main.add(header)

        # Table of packs
        self.table = toga.Table(
            headings=["Name", "Author", "Version", "Description", "Size"],
            style=Pack(flex=1, margin_bottom=8),
            multiple_select=False,
            on_select=self._on_select_row,
        )
        main.add(self.table)

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
            if self.table:
                self.table.data.clear()
            # Loading state
            if self.table:
                self.table.data.append(
                    {
                        "Name": "Loading...",
                        "Author": "",
                        "Version": "",
                        "Description": "",
                        "Size": "",
                    }
                )
            packs = await self.service.fetch_available_packs(force_refresh=force)
            self._packs = packs
            await self._populate_table()
        except Exception as e:
            logger.error(f"Failed to load community packs: {e}")
            with contextlib.suppress(Exception):  # type: ignore[name-defined]
                await self.app.main_window.error_dialog(
                    "Community Packs", f"Failed to load community packs: {e}"
                )

    async def _populate_table(self, filter_text: str = ""):
        if not self.table:
            return
        self.table.data.clear()
        ft = (filter_text or "").strip().lower()
        for p in self._packs:
            if ft and (ft not in p.name.lower()) and (ft not in p.author.lower()):
                continue
            size_str = f"{(p.file_size or 0) / (1024 * 1024):.1f} MB" if p.file_size else "?"
            self.table.data.append(
                {
                    "Name": p.name,
                    "Author": p.author,
                    "Version": p.version,
                    "Description": (p.description or "").replace("\n", " ")[:120],
                    "Size": size_str,
                    "_pack_ref": p,
                }
            )

    def _on_search(self, widget):
        ft = widget.value or ""
        asyncio.create_task(self._populate_table(ft))

    def _on_refresh(self, widget):
        asyncio.create_task(self._load_packs(force=True))

    def _on_select_row(self, widget):
        has_sel = bool(widget.selection)
        self.download_button.enabled = has_sel
        self.preview_button.enabled = has_sel

    def _get_selected_pack(self) -> CommunityPack | None:
        if not self.table or not self.table.selection:
            return None
        row = self.table.selection
        # Access hidden reference set in _populate_table
        return getattr(row, "_pack_ref", None)

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

            # Install from ZIP
            await progress.set_status("Installing...", f"Installing pack {p.name}")
            ok, msg = self.installer.install_from_zip(zip_path, pack_name=None)
            if ok:
                await progress.complete_success("Installed successfully")
                # Notify parent to refresh
                if self.on_installed:
                    with contextlib.suppress(Exception):
                        self.on_installed(msg if msg else p.name)
            else:
                await progress.complete_error(msg)
        except Exception as e:
            logger.error(f"Failed to download/install pack: {e}")
            with contextlib.suppress(Exception):
                await progress.complete_error(str(e))


# Local contextlib
import contextlib  # noqa: E402
