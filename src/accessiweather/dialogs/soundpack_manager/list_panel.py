from __future__ import annotations

from typing import TYPE_CHECKING

import toga
from toga.style.pack import COLUMN, Pack

if TYPE_CHECKING:  # pragma: no cover - import only for type checking
    from .main import SoundPackManagerDialog


class PackListPanel:
    """Encapsulates the list panel UI and related logic."""

    def __init__(self, dialog: SoundPackManagerDialog) -> None:
        """Create the list panel bound to a dialog."""
        self.dlg = dialog
        self.panel = toga.Box(style=Pack(direction=COLUMN, flex=1, margin_right=10))

    def build(self) -> toga.Box:
        # Panel title
        title_label = toga.Label(
            "Available Sound Packs", style=Pack(font_weight="bold", margin_bottom=5)
        )
        self.panel.add(title_label)

        # List box
        self.dlg.pack_list = toga.Selection(
            on_select=self.dlg._on_pack_selected, style=Pack(flex=1)
        )
        self.panel.add(self.dlg.pack_list)

        # Button row (list actions)
        button_row = self.dlg._create_button_panel()
        self.panel.add(button_row)

        return self.panel

    # These were methods on the dialog; keep the underlying implementations in dialog


__all__ = ["PackListPanel"]
