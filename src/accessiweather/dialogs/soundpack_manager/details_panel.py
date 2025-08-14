from __future__ import annotations

from typing import TYPE_CHECKING

import toga
from toga.style.pack import COLUMN, Pack

from .constants import FRIENDLY_ALERT_CATEGORIES, AlertCategoryItem

if TYPE_CHECKING:  # pragma: no cover - import only for type checking
    from .main import SoundPackManagerDialog


class DetailsPanel:
    """Encapsulates the details panel UI and related logic.

    This class only constructs the panel; event handlers remain on the main dialog to
    preserve behavior without deep refactors.
    """

    def __init__(self, dialog: SoundPackManagerDialog) -> None:
        """Create the details panel bound to a dialog."""
        self.dlg = dialog
        self.panel = toga.Box(style=Pack(direction=COLUMN, flex=2, margin_left=10))

    def build(self) -> toga.Box:
        # Panel title
        title_label = toga.Label(
            "Sound Pack Details", style=Pack(font_weight="bold", margin_bottom=5)
        )
        self.panel.add(title_label)

        # Mapping selector
        self.dlg.mapping_category_select = toga.Selection(
            items=[AlertCategoryItem(name, key) for name, key in FRIENDLY_ALERT_CATEGORIES],
            on_select=self.dlg._on_mapping_key_change,
            style=Pack(margin_bottom=10),
        )
        self.panel.add(self.dlg.mapping_category_select)

        # Mapping preview and action buttons (wired to dialog handlers)
        self.dlg.mapping_preview_button = toga.Button(
            "Preview Mapping", on_press=self.dlg._on_preview_mapping
        )
        self.panel.add(self.dlg.mapping_preview_button)

        return self.panel


__all__ = ["DetailsPanel"]
