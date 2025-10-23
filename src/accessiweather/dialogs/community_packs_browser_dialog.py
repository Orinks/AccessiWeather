"""
Community Sound Packs browser dialog.

Provides a modal UI to browse, search, and install community sound packs
fetched via CommunitySoundPackService. Downloads are shown with a progress
indicator using the same UX pattern as UpdateProgressDialog.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable
from pathlib import Path

import toga
from toga.style import Pack
from travertino.constants import COLUMN, ROW

from ..notifications.sound_pack_installer import SoundPackInstaller
from ..services.community_soundpack_service import (
    CommunityPack,
    CommunitySoundPackService,
)
from .update_progress_dialog import UpdateProgressDialog

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
        service: CommunitySoundPackService | None,
        installer: SoundPackInstaller,
        on_installed: Callable[[str], None] | None = None,
    ) -> None:
        """Initialize the browser dialog."""
        self.app = app
        self.service = service
        self.installer = installer
        self.on_installed = on_installed

        # Window + UI controls
        self.window: toga.Window | None = None
        self.search_input: toga.TextInput | None = None
        self.refresh_button: toga.Button | None = None
        self.pack_list: toga.DetailedList | None = None
        self.pack_table: toga.Table | None = None
        self._use_detailed_list: bool = True
        self.details_name_label: toga.Label | None = None
        self.details_author_label: toga.Label | None = None
        self.details_version_label: toga.Label | None = None
        self.details_size_label: toga.Label | None = None
        self.details_repo_label: toga.Label | None = None
        self.details_description_label: toga.Label | None = None
        self.install_button: toga.Button | None = None
        self.preview_button: toga.Button | None = None
        self.status_label: toga.Label | None = None

        # Data/state
        self._packs: list[CommunityPack] = []
        self._pack_index: dict[str, CommunityPack] = {}
        self._selected_key: str | None = None
        self._loading_task: asyncio.Task | None = None

    # Public API -----------------------------------------------------
    def show(self) -> None:
        """Show the dialog window."""
        if self.window is None:
            self._build_window()

        if not self.window:
            return

        self._reset_ui()

        # Add to app window list if needed
        try:
            if self.window not in getattr(self.app, "windows", []):
                self.app.windows.add(self.window)
        except Exception:
            with contextlib.suppress(Exception):
                self.app.windows.add(self.window)

        self.window.show()
        asyncio.create_task(self._focus_search())

        if self.service is None:
            asyncio.create_task(
                self._show_error(
                    "Community sound packs are currently unavailable. Please try again later."
                )
            )
            return

        self._start_loading()

    # UI construction ------------------------------------------------
    def _build_window(self) -> None:
        """Construct window and UI controls once."""
        self.window = toga.Window(
            title="Browse Community Sound Packs",
            size=(820, 560),
            resizable=True,
        )

        root = toga.Box(style=Pack(direction=COLUMN, padding=12, flex=1))

        # Header with search + refresh
        header = toga.Box(style=Pack(direction=ROW, margin_bottom=8))
        hint_label = toga.Label("Filter packs:", style=Pack(margin_right=6, alignment="center"))
        header.add(hint_label)
        self.search_input = toga.TextInput(
            placeholder="Search by name or author",
            style=Pack(flex=1, margin_right=8),
            on_change=self._on_search,
        )
        with contextlib.suppress(AttributeError):
            self.search_input.aria_label = "Filter community sound packs"
        self.refresh_button = toga.Button(
            "Refresh",
            on_press=self._on_refresh,
            style=Pack(width=110),
        )
        header.add(self.search_input)
        header.add(self.refresh_button)
        root.add(header)

        # Main content split: list + details
        content = toga.Box(style=Pack(direction=ROW, flex=1, margin_bottom=8))

        # Pack list panel
        list_panel = toga.Box(style=Pack(direction=COLUMN, flex=1, margin_right=10))
        list_panel.add(
            toga.Label("Available Packs", style=Pack(font_weight="bold", margin_bottom=6))
        )
        self._use_detailed_list = True
        try:
            self.pack_list = toga.DetailedList(
                on_select=self._on_select_row,
                style=Pack(flex=1),
            )
            with contextlib.suppress(AttributeError):
                self.pack_list.aria_label = "Community sound packs"
                self.pack_list.aria_description = (
                    "Browse available community sound packs. Each entry announces name, version, author, "
                    "size, and a short description. Use the arrow keys to explore and press Enter to select."
                )
            list_panel.add(self.pack_list)
            self.pack_table = None
        except Exception as exc:
            logger.warning("DetailedList unavailable, falling back to Table: %s", exc)
            self._use_detailed_list = False
            self.pack_list = None
            self.pack_table = toga.Table(
                headings=["Name", "Author", "Version", "Description", "Size"],
                style=Pack(flex=1),
                multiple_select=False,
                on_select=self._on_select_row,
            )
            with contextlib.suppress(AttributeError):
                self.pack_table.aria_label = "Community sound packs"
                self.pack_table.aria_description = (
                    "Browse available community sound packs. Columns include name, author, version, "
                    "description, and size. Use the arrow keys to explore and press Enter to select."
                )
            list_panel.add(self.pack_table)
        content.add(list_panel)

        # Details panel
        details_panel = toga.Box(style=Pack(direction=COLUMN, flex=1.4, padding=10))
        details_panel.add(
            toga.Label("Pack Details", style=Pack(font_weight="bold", margin_bottom=6))
        )
        self.details_name_label = toga.Label("Select a pack to view details.")
        self.details_author_label = toga.Label("")
        self.details_version_label = toga.Label("")
        self.details_size_label = toga.Label("")
        self.details_repo_label = toga.Label("", style=Pack(margin_bottom=6))
        self.details_description_label = toga.Label(
            "",
            style=Pack(flex=1, padding_top=6),
        )
        details_panel.add(self.details_name_label)
        details_panel.add(self.details_author_label)
        details_panel.add(self.details_version_label)
        details_panel.add(self.details_size_label)
        details_panel.add(self.details_repo_label)
        details_panel.add(toga.Label("Description:", style=Pack(font_weight="bold", margin_top=10)))
        details_panel.add(self.details_description_label)
        content.add(details_panel)

        root.add(content)

        # Status label
        self.status_label = toga.Label("", style=Pack(margin_bottom=6))
        root.add(self.status_label)

        # Footer buttons
        button_row = toga.Box(style=Pack(direction=ROW))
        button_row.add(toga.Box(style=Pack(flex=1)))
        self.install_button = toga.Button(
            "Download & Install",
            on_press=self._on_download,
            enabled=False,
            style=Pack(margin_right=10),
        )
        self.preview_button = toga.Button(
            "Preview Details",
            on_press=self._on_preview,
            enabled=False,
            style=Pack(margin_right=10),
        )
        close_button = toga.Button("Close", on_press=lambda _: self._request_close())
        button_row.add(self.install_button)
        button_row.add(self.preview_button)
        button_row.add(close_button)
        root.add(button_row)

        self.window.content = root
        with contextlib.suppress(Exception):
            self.window.on_close = self._on_close

    # Helpers --------------------------------------------------------
    def _reset_ui(self) -> None:
        """Reset UI to initial state before loading data."""
        self._selected_key = None
        self._packs.clear()
        self._pack_index.clear()

        if self.pack_list is not None:
            with contextlib.suppress(Exception):
                self.pack_list.data.clear()
        if self.pack_table is not None:
            with contextlib.suppress(Exception):
                self.pack_table.data.clear()

        self._update_details(None)
        self._set_status("")
        self._set_buttons_enabled(False)

    def _start_loading(self, force: bool = False) -> None:
        """Kick off async load of community packs."""
        if self.service is None:
            return
        if self._loading_task and not self._loading_task.done():
            self._loading_task.cancel()
        self._loading_task = asyncio.create_task(self._load_packs(force=force))

    async def _focus_search(self) -> None:
        await asyncio.sleep(0.25)
        try:
            if self.search_input:
                self.search_input.focus()
        except Exception:
            pass

    async def _load_packs(self, force: bool = False) -> None:
        """Fetch packs and populate the list."""
        if self.service is None:
            return

        self._set_status("Loading community packs...")
        self._set_buttons_enabled(False)
        if self.refresh_button:
            self.refresh_button.enabled = False

        self._show_loading_state()

        try:
            packs = await self.service.fetch_available_packs(force_refresh=force)
            self._packs = list(packs)
            self._pack_index = {self._pack_key(pack): pack for pack in self._packs}
            filter_text = self.search_input.value if self.search_input else ""
            self._populate_list(filter_text)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("Failed to load community packs: %s", exc)
            await self._show_error(f"Failed to load community packs: {exc}")
        finally:
            if self.refresh_button:
                self.refresh_button.enabled = True
            self._set_status("")

    def _show_loading_state(self) -> None:
        """Display a temporary loading row."""
        if self._use_detailed_list and self.pack_list:
            with contextlib.suppress(Exception):
                self.pack_list.data.clear()
                self.pack_list.data.append(
                    {
                        "title": "Loading...",
                        "subtitle": "Fetching community packs",
                        "pack_key": None,
                    }
                )
        elif self.pack_table:
            with contextlib.suppress(Exception):
                self.pack_table.data.clear()
                self.pack_table.data.append(
                    {
                        "Name": "Loading...",
                        "Author": "",
                        "Version": "",
                        "Description": "Fetching community packs",
                        "Size": "",
                        "pack_key": None,
                    }
                )

    def _populate_list(self, filter_text: str = "") -> None:
        """Populate the list/table with packs matching the filter."""
        view = None
        if self._use_detailed_list and self.pack_list:
            view = self.pack_list.data
        elif self.pack_table:
            view = self.pack_table.data
        if view is None:
            return

        with contextlib.suppress(Exception):
            view.clear()

        self._selected_key = None
        self._set_buttons_enabled(False)

        ft = (filter_text or "").strip().lower()
        first_key: str | None = None

        for pack in self._packs:
            if ft and ft not in pack.name.lower() and ft not in pack.author.lower():
                continue

            key = self._pack_key(pack)
            size_str = f"{(pack.file_size or 0) / (1024 * 1024):.1f} MB" if pack.file_size else "?"
            summary = self._format_accessible_summary(pack, size_str)

            if self._use_detailed_list and self.pack_list:
                self.pack_list.data.append(
                    {
                        "title": pack.name,
                        "subtitle": summary,
                        "pack_key": key,
                    }
                )
            elif self.pack_table:
                self.pack_table.data.append(
                    {
                        "Name": pack.name,
                        "Author": pack.author,
                        "Version": pack.version,
                        "Description": (pack.description or "").replace("\n", " ")[:120],
                        "Size": size_str,
                        "pack_key": key,
                    }
                )

            if first_key is None:
                first_key = key

        if first_key:
            self._apply_initial_selection(first_key)
        else:
            self._update_details(None)
            message = "You may be offline or rate-limited. Try Refresh or adjust search criteria."
            if self._use_detailed_list and self.pack_list:
                self.pack_list.data.append(
                    {
                        "title": "No community packs found",
                        "subtitle": message,
                        "pack_key": None,
                    }
                )
            elif self.pack_table:
                self.pack_table.data.append(
                    {
                        "Name": "No community packs found",
                        "Author": "",
                        "Version": "",
                        "Description": message,
                        "Size": "",
                        "pack_key": None,
                    }
                )

    def _on_search(self, widget) -> None:
        self._populate_list(widget.value or "")

    def _on_refresh(self, widget) -> None:
        if self.service is None:
            asyncio.create_task(
                self._show_error(
                    "Community sound packs are currently unavailable. Please try again later."
                )
            )
            return
        self._start_loading(force=True)

    def _on_select_row(self, widget) -> None:
        row = getattr(widget, "selection", None)
        key = getattr(row, "pack_key", None)
        if not key:
            self._selected_key = None
            self._update_details(None)
            self._set_buttons_enabled(False)
            return

        self._selected_key = key
        pack = self._pack_index.get(key)
        if pack is None:
            self._update_details(None)
            self._set_buttons_enabled(False)
            return

        self._update_details(pack)
        self._set_buttons_enabled(self._pack_has_download_source(pack))

    def _apply_initial_selection(self, key: str) -> None:
        """Initialize selection state without modifying widget selection directly."""
        pack = self._pack_index.get(key)
        if pack is None:
            return
        self._selected_key = key
        self._update_details(pack)
        self._set_buttons_enabled(self._pack_has_download_source(pack))

    def _update_details(self, pack: CommunityPack | None) -> None:
        """Update the right-hand details panel based on selection."""
        if not self.details_name_label:
            return

        if pack is None:
            self.details_name_label.text = "Select a community sound pack to view details."
            if self.details_author_label:
                self.details_author_label.text = ""
            if self.details_version_label:
                self.details_version_label.text = ""
            if self.details_size_label:
                self.details_size_label.text = ""
            if self.details_repo_label:
                self.details_repo_label.text = ""
            if self.details_description_label:
                self.details_description_label.text = ""
            return

        self.details_name_label.text = pack.name
        if self.details_author_label:
            self.details_author_label.text = f"Author: {pack.author}"
        if self.details_version_label:
            self.details_version_label.text = f"Version: {pack.version}"
        if self.details_size_label:
            if pack.file_size:
                mb = pack.file_size / (1024 * 1024)
                self.details_size_label.text = f"Size: {mb:.1f} MB"
            else:
                self.details_size_label.text = "Size: Unknown"
        if self.details_repo_label:
            if pack.repository_url:
                self.details_repo_label.text = f"Repository: {pack.repository_url}"
            else:
                self.details_repo_label.text = ""
        if self.details_description_label:
            desc = pack.description or "No description provided."
            self.details_description_label.text = desc.replace("\r\n", "\n")

    def _pack_has_download_source(self, pack: CommunityPack) -> bool:
        return bool(pack.download_url or getattr(pack, "repo_path", None))

    def _set_buttons_enabled(self, enabled: bool) -> None:
        if self.install_button:
            self.install_button.enabled = enabled
        if self.preview_button:
            self.preview_button.enabled = enabled

    def _set_status(self, message: str) -> None:
        if self.status_label is not None:
            self.status_label.text = message

    def _pack_key(self, pack: CommunityPack) -> str:
        """Create a stable key for list items."""
        return "|".join(
            filter(
                None,
                [
                    pack.name,
                    pack.author,
                    pack.version,
                    pack.release_tag or "",
                ],
            )
        )

    def _format_accessible_summary(self, pack: CommunityPack, size: str) -> str:
        desc = (pack.description or "").replace("\n", " ").strip()
        summary = f"Version {pack.version} by {pack.author}. Size {size}."
        if desc:
            summary = f"{summary} {desc}"
        if getattr(pack, "repo_path", None) and not pack.download_url:
            summary = f"{summary} Downloads directly from repository contents."
        return summary

    def _get_selected_pack(self) -> CommunityPack | None:
        if self._selected_key:
            return self._pack_index.get(self._selected_key)
        return None

    def _on_preview(self, widget) -> None:
        pack = self._get_selected_pack()
        if not pack:
            return

        details = [
            f"Name: {pack.name}",
            f"Author: {pack.author}",
            f"Version: {pack.version}",
        ]
        if pack.description:
            details.append("")
            details.append(pack.description)
        if pack.repository_url:
            details.append("")
            details.append(f"More info: {pack.repository_url}")

        asyncio.create_task(self.app.main_window.info_dialog("Pack Details", "\n".join(details)))

    def _on_download(self, widget) -> None:
        pack = self._get_selected_pack()
        if not pack:
            return
        asyncio.create_task(self._download_and_install(pack))

    async def _download_and_install(self, pack: CommunityPack) -> None:
        """Download the selected pack and install it."""
        progress = UpdateProgressDialog(self.app, title=f"Downloading {pack.name}")
        progress.show_and_prepare()

        try:

            async def on_progress(pct: float, downloaded: int, total: int) -> bool:
                await progress.update_progress(pct, downloaded, total)
                return not progress.is_cancelled

            tmp_dir = Path(self.installer.soundpacks_dir) / "_downloads"
            zip_path = await self.service.download_pack(pack, tmp_dir, on_progress)  # type: ignore[union-attr]

            if progress.is_cancelled:
                await progress.complete_error("Download cancelled")
                return

            await progress.set_status("Installing...", f"Installing pack {pack.name}")
            ok, msg = await asyncio.to_thread(self.installer.install_from_zip, zip_path, None)
            if ok:
                await progress.complete_success("Installed successfully")
                if self.on_installed:
                    with contextlib.suppress(Exception):
                        self.on_installed(pack.name)
                self._set_status(f"Installed {pack.name}")
            else:
                await progress.complete_error(msg)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("Failed to download/install pack: %s", exc)
            with contextlib.suppress(Exception):
                await progress.complete_error(str(exc))
        finally:
            with contextlib.suppress(Exception):
                progress.window.close()

    async def _show_error(self, message: str) -> None:
        """Show an error dialog if the main window is available."""
        with contextlib.suppress(Exception):
            await self.app.main_window.error_dialog("Community Packs", message)
        self._set_status(message)

    def _request_close(self) -> None:
        """Close the window from a button press."""
        if self.window is not None:
            with contextlib.suppress(Exception):
                self.window.close()

    def _on_close(self, widget=None) -> None:
        """Handle window close by cancelling pending work."""
        if self._loading_task and not self._loading_task.done():
            self._loading_task.cancel()
        self._loading_task = None


__all__ = ["CommunityPacksBrowserDialog"]
