from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - import only for type checking
    from .main import SoundPackManagerDialog


class CommunityIntegration:
    """Community packs integration helpers (browse, install callbacks, cleanup)."""

    def __init__(self, dialog: SoundPackManagerDialog) -> None:
        """Create the community integration bound to a dialog."""
        self.dlg = dialog

    def on_installed(self, pack_display_name: str) -> None:
        # Delegate to dialog for refresh and auto-select
        self.dlg._handle_community_installed(pack_display_name)

    def on_close(self) -> None:
        try:
            if getattr(self.dlg, "community_service", None):
                asyncio.create_task(self.dlg.community_service.aclose())
        except Exception:
            pass


__all__ = ["CommunityIntegration"]
