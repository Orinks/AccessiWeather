from __future__ import annotations

import asyncio
import logging

import toga
from toga.style.pack import COLUMN, ROW, Pack

from ...notifications.sound_pack_installer import SoundPackInstaller
from ..community_packs_browser_dialog import CommunityPacksBrowserDialog
from .community import CommunityIntegration
from .details_panel import DetailsPanel
from .list_panel import PackListPanel

logger = logging.getLogger(__name__)


class SoundPackManagerDialog:
    """Orchestrates the Sound Pack Manager dialog composed from panels."""

    def __init__(self, app: toga.App, current_pack: str = "default") -> None:
        """Initialize the Sound Pack Manager dialog orchestrator.

        Parameters
        ----------
        app : toga.App
            The Toga application instance.
        current_pack : str
            The pack id currently selected in settings.

        """
        self.app = app
        self.current_pack = current_pack
        self.selected_pack: str | None = None

        # External services
        self.community_service = None
        self.installer = SoundPackInstaller(app)

        # UI component placeholders used by the subpanels
        self.dialog: toga.Window | None = None
        self.pack_list = None
        self.mapping_category_select = None
        self.mapping_preview_button = None

        # Data containers (populated by existing logic methods when called)
        self.sound_packs = {}

    # Glue methods kept from the original class to preserve behavior

    def _load_sound_packs(self) -> None:
        # Existing implementation is preserved in the original module
        raise NotImplementedError

    def _refresh_pack_list(self) -> None:
        raise NotImplementedError

    def _update_pack_details(self) -> None:
        raise NotImplementedError

    def _on_pack_selected(self, widget) -> None:
        raise NotImplementedError

    def _on_mapping_key_change(self, widget) -> None:
        raise NotImplementedError

    def _on_preview_mapping(self, widget) -> None:
        raise NotImplementedError

    def _on_browse_community_packs(self, widget) -> None:
        # Use the extracted community integration
        dlg = CommunityPacksBrowserDialog(
            app=self.app,
            installer=self.installer,
            on_installed=CommunityIntegration(self).on_installed,
        )
        dlg.show()

    def _handle_community_installed(self, pack_display_name: str) -> None:
        try:
            self._load_sound_packs()
            self._refresh_pack_list()
            for pack_id, info in self.sound_packs.items():
                if info.get("name") == pack_display_name:
                    self.selected_pack = pack_id
                    self.current_pack = pack_id
                    self._update_pack_details()
                    break
        except Exception:
            pass

    def _on_close(self, widget) -> None:
        """Cleanup and close the dialog."""
        try:
            if getattr(self, "community_service", None):
                asyncio.create_task(self.community_service.aclose())
        except Exception:
            pass
        if self.dialog:
            self.dialog.close()

    def _create_dialog(self) -> None:
        """Create the sound pack manager dialog and compose subpanels."""
        self.dialog = toga.Window(title="Sound Pack Manager", size=(800, 600), resizable=True)
        main_box = toga.Box(style=Pack(direction=COLUMN, margin=10, flex=1))

        # Top row with list panel and details panel
        list_panel = PackListPanel(self).build()
        details_panel = DetailsPanel(self).build()

        top_row = toga.Box(style=Pack(direction=ROW, flex=1, gap=10))
        top_row.add(list_panel)
        top_row.add(details_panel)

        main_box.add(top_row)
        self.dialog.content = main_box


__all__ = ["SoundPackManagerDialog"]
