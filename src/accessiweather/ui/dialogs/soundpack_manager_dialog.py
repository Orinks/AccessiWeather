"""wxPython Sound Pack Manager dialog."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import wx

from ...notifications.sound_pack_installer import SoundPackInstaller
from ...services.community_soundpack_service import CommunitySoundPackService
from ...soundpack_paths import get_soundpacks_dir
from .soundpack_manager_community import SoundPackManagerCommunityMixin
from .soundpack_manager_mappings import SoundPackManagerMappingMixin
from .soundpack_manager_models import FRIENDLY_ALERT_CATEGORIES, SoundPackInfo  # noqa: F401
from .soundpack_manager_pack_actions import SoundPackManagerPackActionsMixin
from .soundpack_manager_ui import SoundPackManagerUiMixin

if TYPE_CHECKING:
    from ...app import AccessiWeatherApp

logger = logging.getLogger(__name__)


class SoundPackManagerDialog(
    SoundPackManagerCommunityMixin,
    SoundPackManagerPackActionsMixin,
    SoundPackManagerMappingMixin,
    SoundPackManagerUiMixin,
    wx.Dialog,
):
    """Dialog for managing sound packs."""

    def __init__(self, parent: wx.Window, app: AccessiWeatherApp) -> None:
        """Initialize the sound pack manager dialog."""
        super().__init__(
            parent,
            title="Sound Pack Manager",
            size=(850, 600),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self.app = app
        self.soundpacks_dir = get_soundpacks_dir()
        self.soundpacks_dir.mkdir(exist_ok=True)
        self.sound_packs: dict[str, SoundPackInfo] = {}
        self.selected_pack: str | None = None

        # External services
        self.installer = SoundPackInstaller(self.soundpacks_dir)
        self.community_service = self._create_community_service()

        # Preview player for sound previews (supports stop)
        from ...notifications.sound_player import get_preview_player

        self._preview_player = get_preview_player()
        self._current_preview_path: Path | None = None

        # Timer to check when preview playback finishes
        self._preview_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_preview_timer, self._preview_timer)

        self._load_sound_packs()
        self._create_ui()
        self._refresh_pack_list()
        self.Centre()
        if hasattr(self, "pack_listbox"):
            self.pack_listbox.SetFocus()

        # Bind close event to stop any playing preview
        self.Bind(wx.EVT_CLOSE, self._on_dialog_close)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)

    def _create_community_service(self) -> CommunitySoundPackService | None:
        """Create the community soundpack service."""
        try:
            return CommunitySoundPackService()
        except Exception as exc:
            logger.warning("Community packs disabled - failed to initialize service: %s", exc)
            return None

    def _load_sound_packs(self) -> None:
        """Load all available sound packs."""
        self.sound_packs.clear()
        if not self.soundpacks_dir.exists():
            return

        for pack_dir in self.soundpacks_dir.iterdir():
            if not pack_dir.is_dir():
                continue
            pack_json = pack_dir / "pack.json"
            if not pack_json.exists():
                continue
            try:
                with open(pack_json, encoding="utf-8") as f:
                    data = json.load(f)
                self.sound_packs[pack_dir.name] = SoundPackInfo(
                    pack_id=pack_dir.name,
                    name=data.get("name", pack_dir.name),
                    author=data.get("author", "Unknown"),
                    description=data.get("description", ""),
                    path=pack_dir,
                    sounds=data.get("sounds", {}),
                )
            except Exception as e:
                logger.error(f"Failed to load sound pack {pack_dir.name}: {e}")

    def _on_char_hook(self, event: wx.KeyEvent) -> None:
        """Handle keyboard shortcuts for the dialog."""
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self._on_close(event)
            return
        event.Skip()

    def _on_dialog_close(self, event) -> None:
        """Handle dialog close event (X button or escape)."""
        # Stop any playing preview and timer
        self._preview_timer.Stop()
        if self._preview_player:
            self._preview_player.stop()
        event.Skip()  # Allow normal close handling

    def _on_key(self, event: wx.KeyEvent) -> None:
        """Handle key events."""
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.Close()
        else:
            event.Skip()

    def _on_close(self, event) -> None:
        """Close the dialog."""
        # Stop any playing preview and timer
        self._preview_timer.Stop()
        if self._preview_player:
            self._preview_player.stop()

        # Clean up community service
        if self.community_service:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self.community_service.aclose())
                finally:
                    loop.close()
            except Exception:
                pass
        self.EndModal(wx.ID_CLOSE)


def show_soundpack_manager_dialog(parent: wx.Window, app: AccessiWeatherApp) -> None:
    """Show the sound pack manager dialog."""
    parent_ctrl = parent
    dialog = SoundPackManagerDialog(parent_ctrl, app)
    dialog.ShowModal()
    dialog.Destroy()
