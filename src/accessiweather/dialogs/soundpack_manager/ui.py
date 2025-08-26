from __future__ import annotations

import contextlib
import logging

import toga
from toga.style import Pack
from travertino.constants import COLUMN, ROW

from .constants import FRIENDLY_ALERT_CATEGORIES, AlertCategoryItem

logger = logging.getLogger(__name__)


def create_dialog_ui(dlg) -> None:
    dlg.dialog = toga.Window(
        title="Sound Pack Manager",
        size=(800, 600),
        resizable=True,
    )

    main_box = toga.Box(style=Pack(direction=COLUMN, margin=10, flex=1))

    # Title
    title_label = toga.Label(
        "Sound Pack Manager", style=Pack(font_size=16, font_weight="bold", margin_bottom=10)
    )
    main_box.add(title_label)

    # Content area
    content_box = toga.Box(style=Pack(direction=ROW, flex=1, margin_bottom=10))

    # Left panel - Sound pack list
    left_panel = create_pack_list_panel(dlg)
    content_box.add(left_panel)

    # Right panel - Pack details and sounds
    right_panel = create_pack_details_panel(dlg)
    content_box.add(right_panel)

    main_box.add(content_box)

    # Bottom buttons
    button_box = create_button_panel(dlg)
    main_box.add(button_box)

    dlg.dialog.content = main_box

    # Populate the pack list with loaded sound packs
    dlg._refresh_pack_list()

    # Select current pack if available (for focus), but do not change app setting here
    if dlg.current_pack in dlg.sound_packs:
        dlg.selected_pack = dlg.current_pack
        for item in dlg.pack_list.data:
            if item.pack_id == dlg.current_pack:
                break
        dlg._update_pack_details()


def create_pack_list_panel(dlg) -> toga.Box:
    panel = toga.Box(style=Pack(direction=COLUMN, flex=1, margin_right=10))

    title_label = toga.Label(
        "Available Sound Packs", style=Pack(font_weight="bold", margin_bottom=5)
    )
    panel.add(title_label)

    dlg.pack_list = toga.DetailedList(
        on_select=dlg._on_pack_selected, style=Pack(flex=1, margin_bottom=10)
    )
    panel.add(dlg.pack_list)

    dlg.import_button = toga.Button(
        "Import Sound Pack", on_press=dlg._on_import_pack, style=Pack(width=150)
    )
    panel.add(dlg.import_button)

    panel.add(
        toga.Label(
            "Hint: Select your active pack in Settings > General.",
            style=Pack(margin_top=8, font_style="italic"),
        )
    )

    return panel


def create_pack_details_panel(dlg) -> toga.Box:
    panel = toga.Box(style=Pack(direction=COLUMN, flex=2, margin_left=10))

    title_label = toga.Label("Sound Pack Details", style=Pack(font_weight="bold", margin_bottom=5))
    panel.add(title_label)

    dlg.pack_info_box = toga.Box(
        style=Pack(direction=COLUMN, margin=10, background_color="#f0f0f0")
    )
    dlg.pack_name_label = toga.Label(
        "No pack selected", style=Pack(font_size=14, font_weight="bold", margin_bottom=5)
    )
    dlg.pack_info_box.add(dlg.pack_name_label)
    dlg.pack_author_label = toga.Label("", style=Pack(margin_bottom=5))
    dlg.pack_info_box.add(dlg.pack_author_label)
    dlg.pack_description_label = toga.Label("", style=Pack(margin_bottom=10))
    dlg.pack_info_box.add(dlg.pack_description_label)
    panel.add(dlg.pack_info_box)

    sounds_label = toga.Label(
        "Sounds in this pack:", style=Pack(font_weight="bold", margin=(10, 0, 5, 0))
    )
    panel.add(sounds_label)

    dlg.sound_selection = toga.Selection(
        items=[],
        accessor="display_name",
        on_change=dlg._on_sound_selected,
        style=Pack(flex=1, margin_bottom=10),
    )
    panel.add(dlg.sound_selection)

    mapping_header = toga.Box(style=Pack(direction=ROW, margin_bottom=5))
    mapping_label = toga.Label("Alert category:", style=Pack(font_weight="bold", margin_right=5))
    mapping_header.add(mapping_label)
    panel.add(mapping_header)

    mapping_row = toga.Box(style=Pack(direction=ROW, margin_bottom=10))
    dlg.mapping_key_selection = toga.Selection(
        items=[
            AlertCategoryItem(display_name=name, technical_key=key)
            for name, key in FRIENDLY_ALERT_CATEGORIES
        ],
        accessor="display_name",
        on_change=dlg._on_mapping_key_change,
        style=Pack(width=260, margin_right=10),
    )
    with contextlib.suppress(Exception):
        dlg.mapping_key_selection.aria_label = "Alert category"
        dlg.mapping_key_selection.aria_description = (
            "Select from common weather alert categories. Each category maps to technical keys used by weather services. "
            "Use the custom mapping field below for specific alert types not listed."
        )
    dlg.mapping_file_input = toga.TextInput(
        readonly=True, placeholder="Select audio file...", style=Pack(flex=1, margin_right=10)
    )
    dlg.mapping_browse_button = toga.Button(
        "Browse...", on_press=dlg._on_browse_mapping_file, style=Pack(margin_right=10)
    )
    dlg.mapping_preview_button = toga.Button(
        "Preview", on_press=dlg._on_preview_mapping, enabled=False
    )
    mapping_row.add(dlg.mapping_key_selection)
    mapping_row.add(dlg.mapping_file_input)
    mapping_row.add(dlg.mapping_browse_button)
    mapping_row.add(dlg.mapping_preview_button)
    panel.add(mapping_row)

    simple_map_box = toga.Box(style=Pack(direction=ROW, margin_bottom=10))
    simple_label = toga.Label("Add or change a mapping:", style=Pack(margin_right=10))
    dlg.simple_key_input = toga.TextInput(
        placeholder="e.g., excessive_heat_warning or tornado_warning",
        style=Pack(width=260, margin_right=10),
    )
    dlg.simple_file_button = toga.Button(
        "Choose Sound...", on_press=dlg._on_simple_choose_file, style=Pack(margin_right=10)
    )
    dlg.simple_remove_button = toga.Button("Remove Mapping", on_press=dlg._on_simple_remove_mapping)
    simple_map_box.add(simple_label)
    simple_map_box.add(dlg.simple_key_input)
    simple_map_box.add(dlg.simple_file_button)
    simple_map_box.add(dlg.simple_remove_button)
    panel.add(simple_map_box)

    return panel


def create_button_panel(dlg) -> toga.Box:
    button_box = toga.Box(style=Pack(direction=ROW))

    button_box.add(toga.Box(style=Pack(flex=1)))

    dlg.create_button = toga.Button(
        "Create New", on_press=dlg._on_create_pack, style=Pack(margin_right=10)
    )
    button_box.add(dlg.create_button)

    dlg.create_wizard_button = toga.Button(
        "Create with Wizard", on_press=dlg._on_create_pack_wizard, style=Pack(margin_right=10)
    )
    button_box.add(dlg.create_wizard_button)

    dlg.browse_community_button = toga.Button(
        "Browse Community",
        on_press=dlg._on_browse_community_packs,
        style=Pack(margin_right=10),
        enabled=dlg.community_service is not None,
    )
    button_box.add(dlg.browse_community_button)

    # New: Share Pack button
    dlg.share_button = toga.Button(
        "Share Pack",
        on_press=dlg._on_share_pack,
        style=Pack(margin_right=10),
        enabled=False,
    )
    button_box.add(dlg.share_button)

    # Add accessibility description for share button
    with contextlib.suppress(Exception):
        dlg.share_button.aria_description = "Share your sound pack with the community. No GitHub account required - just complete pack metadata (name, author) and at least one mapped sound."
    dlg.duplicate_button = toga.Button(
        "Duplicate", on_press=dlg._on_duplicate_pack, enabled=False, style=Pack(margin_right=10)
    )
    button_box.add(dlg.duplicate_button)

    dlg.edit_button = toga.Button(
        "Edit", on_press=dlg._on_edit_pack, enabled=False, style=Pack(margin_right=10)
    )
    button_box.add(dlg.edit_button)

    dlg.select_button = toga.Button(
        "Open",
        on_press=dlg._on_open_pack,
        enabled=False,
        style=Pack(margin_right=10, background_color="#4CAF50", color="#ffffff"),
    )
    button_box.add(dlg.select_button)

    dlg.delete_button = toga.Button(
        "Delete Pack",
        on_press=dlg._on_delete_pack,
        enabled=False,
        style=Pack(margin_right=10, background_color="#ff4444", color="#ffffff"),
    )
    button_box.add(dlg.delete_button)

    dlg.close_button = toga.Button("Close", on_press=dlg._on_close, style=Pack(margin_right=0))
    button_box.add(dlg.close_button)

    return button_box
