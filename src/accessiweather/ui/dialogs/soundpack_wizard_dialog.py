"""wxPython Sound Pack Creation Wizard dialog."""

from __future__ import annotations

import contextlib
import json
import logging
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import wx
import wx.lib.scrolledpanel as scrolled

from .soundpack_manager_dialog import FRIENDLY_ALERT_CATEGORIES

logger = logging.getLogger(__name__)


@dataclass
class WizardState:
    """State container for the wizard."""

    pack_name: str = ""
    author: str = ""
    description: str = ""
    selected_alert_keys: list[str] = field(default_factory=list)
    sound_mappings: dict[str, str] = field(default_factory=dict)


class SoundPackWizardDialog(wx.Dialog):
    """Wizard dialog for creating a new sound pack."""

    def __init__(self, parent: wx.Window, soundpacks_dir: Path) -> None:
        """Initialize the sound pack creation wizard."""
        super().__init__(
            parent,
            title="Create Sound Pack",
            size=(650, 550),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self.soundpacks_dir = soundpacks_dir
        self.current_step = 1
        self.total_steps = 4
        self.state = WizardState()
        self.created_pack_id: str | None = None

        # Create staging directory for temporary files
        self.staging_dir = Path(tempfile.mkdtemp(prefix="aw_soundpack_wizard_"))

        self._create_ui()
        self._render_step()
        self.Centre()

    def _create_ui(self) -> None:
        """Create the wizard UI."""
        self.panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Header
        self.header_label = wx.StaticText(self.panel, label="")
        header_font = self.header_label.GetFont()
        header_font.SetPointSize(12)
        header_font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.header_label.SetFont(header_font)
        main_sizer.Add(self.header_label, 0, wx.ALL, 10)

        # Content area (will be replaced for each step)
        self.content_panel = wx.Panel(self.panel)
        self.content_sizer = wx.BoxSizer(wx.VERTICAL)
        self.content_panel.SetSizer(self.content_sizer)
        main_sizer.Add(self.content_panel, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        # Navigation buttons
        nav_sizer = wx.BoxSizer(wx.HORIZONTAL)
        nav_sizer.AddStretchSpacer()

        self.prev_btn = wx.Button(self.panel, label="< Previous")
        self.prev_btn.SetName("Previous step")
        self.prev_btn.Bind(wx.EVT_BUTTON, self._go_previous)
        nav_sizer.Add(self.prev_btn, 0, wx.RIGHT, 5)

        self.next_btn = wx.Button(self.panel, label="Next >")
        self.next_btn.SetName("Next step or create pack")
        self.next_btn.Bind(wx.EVT_BUTTON, self._go_next)
        nav_sizer.Add(self.next_btn, 0, wx.RIGHT, 5)

        self.cancel_btn = wx.Button(self.panel, wx.ID_CANCEL, label="Cancel")
        self.cancel_btn.SetName("Cancel sound pack wizard")
        self.cancel_btn.Bind(wx.EVT_BUTTON, self._on_cancel)
        nav_sizer.Add(self.cancel_btn, 0)

        main_sizer.Add(nav_sizer, 0, wx.EXPAND | wx.ALL, 10)

        self.panel.SetSizer(main_sizer)

    def _render_step(self) -> None:
        """Render the current step."""
        titles = {
            1: "Pack Details",
            2: "Select Alert Types",
            3: "Assign Sounds",
            4: "Preview & Finalize",
        }
        self.header_label.SetLabel(
            f"Step {self.current_step} of {self.total_steps}: {titles.get(self.current_step, '')}"
        )

        self.prev_btn.Enable(self.current_step > 1)
        self.next_btn.SetLabel("Create Pack" if self.current_step == self.total_steps else "Next >")

        # Clear content panel
        self.content_sizer.Clear(True)

        # Build step content
        if self.current_step == 1:
            self._build_step1()
        elif self.current_step == 2:
            self._build_step2()
        elif self.current_step == 3:
            self._build_step3()
        else:
            self._build_step4()

        self.content_panel.Layout()
        self.panel.Layout()

    def _build_step1(self) -> None:
        """Step 1: Pack details."""
        # Name
        self.content_sizer.Add(
            wx.StaticText(self.content_panel, label="Pack name (required):"),
            0,
            wx.BOTTOM,
            3,
        )
        self.name_input = wx.TextCtrl(self.content_panel, value=self.state.pack_name)
        self.name_input.SetName("Sound pack name")
        self.name_input.SetHint("e.g., My Weather Sounds")
        self.content_sizer.Add(self.name_input, 0, wx.EXPAND | wx.BOTTOM, 10)

        # Author
        self.content_sizer.Add(
            wx.StaticText(self.content_panel, label="Author (optional):"),
            0,
            wx.BOTTOM,
            3,
        )
        self.author_input = wx.TextCtrl(self.content_panel, value=self.state.author)
        self.author_input.SetName("Sound pack author")
        self.content_sizer.Add(self.author_input, 0, wx.EXPAND | wx.BOTTOM, 10)

        # Description
        self.content_sizer.Add(
            wx.StaticText(self.content_panel, label="Description (optional):"),
            0,
            wx.BOTTOM,
            3,
        )
        self.desc_input = wx.TextCtrl(
            self.content_panel,
            value=self.state.description,
            style=wx.TE_MULTILINE,
            size=(-1, 100),
        )
        self.desc_input.SetName("Sound pack description")
        self.content_sizer.Add(self.desc_input, 1, wx.EXPAND | wx.BOTTOM, 10)

        # Hint
        hint = wx.StaticText(
            self.content_panel,
            label="A folder name will be generated from your pack name.",
        )
        hint.SetForegroundColour(wx.Colour(100, 100, 100))
        self.content_sizer.Add(hint, 0)

        # Set focus
        self.name_input.SetFocus()

    def _build_step2(self) -> None:
        """Step 2: Select alert types."""
        help_text = wx.StaticText(
            self.content_panel,
            label="Choose the alert categories you want sounds for:",
        )
        self.content_sizer.Add(help_text, 0, wx.BOTTOM, 10)

        # Scrolled panel for checkboxes
        scroll = scrolled.ScrolledPanel(self.content_panel, size=(-1, 300))
        scroll_sizer = wx.BoxSizer(wx.VERTICAL)

        self.category_checks: list[tuple[str, wx.CheckBox]] = []
        for display_name, tech_key in FRIENDLY_ALERT_CATEGORIES:
            cb = wx.CheckBox(scroll, label=display_name)
            cb.SetName(f"Alert category {display_name}")
            cb.SetValue(tech_key in self.state.selected_alert_keys)
            scroll_sizer.Add(cb, 0, wx.BOTTOM, 5)
            self.category_checks.append((tech_key, cb))

        scroll.SetSizer(scroll_sizer)
        scroll.SetupScrolling()
        self.content_sizer.Add(scroll, 1, wx.EXPAND | wx.BOTTOM, 10)

        # Action buttons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

        select_common_btn = wx.Button(self.content_panel, label="Select Common")
        select_common_btn.SetName("Select common alert categories")
        select_common_btn.Bind(wx.EVT_BUTTON, self._select_common_alerts)
        btn_sizer.Add(select_common_btn, 0, wx.RIGHT, 5)

        clear_btn = wx.Button(self.content_panel, label="Clear All")
        clear_btn.SetName("Clear all alert categories")
        clear_btn.Bind(wx.EVT_BUTTON, self._clear_all_alerts)
        btn_sizer.Add(clear_btn, 0)

        self.content_sizer.Add(btn_sizer, 0)

    def _select_common_alerts(self, event) -> None:
        """Select common alert types."""
        common = {
            "alert",
            "notify",
            "error",
            "success",
            "startup",
            "exit",
            "tornado_warning",
            "thunderstorm_warning",
            "flood_warning",
        }
        for key, cb in self.category_checks:
            cb.SetValue(key in common)

    def _clear_all_alerts(self, event) -> None:
        """Clear all alert selections."""
        for _, cb in self.category_checks:
            cb.SetValue(False)

    def _build_step3(self) -> None:
        """Step 3: Assign sounds."""
        help_text = wx.StaticText(
            self.content_panel,
            label="Assign a sound file to each selected alert. You can leave some blank.",
        )
        self.content_sizer.Add(help_text, 0, wx.BOTTOM, 10)

        # Scrolled panel for sound assignments
        scroll = scrolled.ScrolledPanel(self.content_panel, size=(-1, 350))
        scroll_sizer = wx.FlexGridSizer(cols=3, hgap=5, vgap=5)
        scroll_sizer.AddGrowableCol(1, 1)

        self.mapping_controls: list[tuple[str, wx.TextCtrl]] = []

        for key in self.state.selected_alert_keys:
            # Get friendly name
            friendly = key.replace("_", " ").title()
            for display_name, tech_key in FRIENDLY_ALERT_CATEGORIES:
                if tech_key == key:
                    friendly = display_name
                    break

            # Label
            label = wx.StaticText(scroll, label=f"{friendly}:")
            scroll_sizer.Add(label, 0, wx.ALIGN_CENTER_VERTICAL)

            # File display
            file_ctrl = wx.TextCtrl(scroll, style=wx.TE_READONLY)
            file_ctrl.SetName(f"Sound file for {friendly}")
            existing = self.state.sound_mappings.get(key)
            if existing:
                file_ctrl.SetValue(Path(existing).name)
            scroll_sizer.Add(file_ctrl, 1, wx.EXPAND)

            # Choose button
            choose_btn = wx.Button(scroll, label="Choose...", size=(80, -1))
            choose_btn.SetName(f"Choose sound file for {friendly}")
            choose_btn.Bind(
                wx.EVT_BUTTON,
                lambda evt, k=key, fc=file_ctrl: self._choose_sound_file(k, fc),
            )
            scroll_sizer.Add(choose_btn, 0)

            self.mapping_controls.append((key, file_ctrl))

        scroll.SetSizer(scroll_sizer)
        scroll.SetupScrolling()
        self.content_sizer.Add(scroll, 1, wx.EXPAND)

    def _choose_sound_file(self, key: str, file_ctrl: wx.TextCtrl) -> None:
        """Choose a sound file for the given key."""
        wildcard = "Audio files (*.wav;*.mp3;*.ogg;*.flac)|*.wav;*.mp3;*.ogg;*.flac"
        with wx.FileDialog(
            self,
            f"Choose sound for {key}",
            wildcard=wildcard,
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return

            src = Path(dialog.GetPath())
            if not src.exists():
                return

            # Copy to staging directory
            dest = self.staging_dir / src.name
            if src.resolve() != dest.resolve():
                shutil.copy2(src, dest)

            self.state.sound_mappings[key] = str(dest)
            file_ctrl.SetValue(dest.name)

    def _build_step4(self) -> None:
        """Step 4: Preview and finalize."""
        # Summary
        summary = wx.StaticText(
            self.content_panel,
            label=f"Pack: {self.state.pack_name}  |  Author: {self.state.author or 'Unknown'}",
        )
        self.content_sizer.Add(summary, 0, wx.BOTTOM, 5)

        if self.state.description:
            desc = wx.StaticText(self.content_panel, label=self.state.description)
            desc.Wrap(500)
            self.content_sizer.Add(desc, 0, wx.BOTTOM, 5)

        count = len([k for k in self.state.selected_alert_keys if k in self.state.sound_mappings])
        sounds_text = wx.StaticText(
            self.content_panel,
            label=f"Sounds assigned: {count} of {len(self.state.selected_alert_keys)}",
        )
        self.content_sizer.Add(sounds_text, 0, wx.BOTTOM, 10)

        # Sounds list
        scroll = scrolled.ScrolledPanel(self.content_panel, size=(-1, 250))
        scroll_sizer = wx.FlexGridSizer(cols=3, hgap=5, vgap=5)
        scroll_sizer.AddGrowableCol(1, 1)

        for key in self.state.selected_alert_keys:
            friendly = key.replace("_", " ").title()
            for display_name, tech_key in FRIENDLY_ALERT_CATEGORIES:
                if tech_key == key:
                    friendly = display_name
                    break

            label = wx.StaticText(scroll, label=f"{friendly}:")
            scroll_sizer.Add(label, 0, wx.ALIGN_CENTER_VERTICAL)

            file_name = "(default)"
            if key in self.state.sound_mappings:
                file_name = Path(self.state.sound_mappings[key]).name
            file_label = wx.StaticText(scroll, label=file_name)
            scroll_sizer.Add(file_label, 1, wx.EXPAND)

            # Preview button
            preview_btn = wx.Button(scroll, label="Preview", size=(70, -1))
            preview_btn.SetName(f"Preview sound for {friendly}")
            preview_btn.Bind(
                wx.EVT_BUTTON,
                lambda evt, k=key: self._preview_sound(k),
            )
            preview_btn.Enable(key in self.state.sound_mappings)
            scroll_sizer.Add(preview_btn, 0)

        scroll.SetSizer(scroll_sizer)
        scroll.SetupScrolling()
        self.content_sizer.Add(scroll, 1, wx.EXPAND | wx.BOTTOM, 10)

        # Test button
        test_btn = wx.Button(self.content_panel, label="Test All Sounds")
        test_btn.SetName("Test all sounds")
        test_btn.Bind(wx.EVT_BUTTON, self._test_all_sounds)
        self.content_sizer.Add(test_btn, 0)

    def _preview_sound(self, key: str) -> None:
        """Preview a sound for the given key."""
        src = self.state.sound_mappings.get(key)
        if not src:
            return

        from ...notifications.sound_player import play_sound_file

        play_sound_file(Path(src))

    def _test_all_sounds(self, event) -> None:
        """Test all assigned sounds."""
        import time

        from ...notifications.sound_player import play_sound_file

        for key in list(self.state.selected_alert_keys)[:5]:  # Limit to 5
            src = self.state.sound_mappings.get(key)
            if src:
                play_sound_file(Path(src))
                time.sleep(0.5)  # Brief delay

    def _validate_current_step(self) -> bool:
        """Validate the current step before proceeding."""
        if self.current_step == 1:
            self.state.pack_name = self.name_input.GetValue().strip()
            self.state.author = self.author_input.GetValue().strip()
            self.state.description = self.desc_input.GetValue().strip()

            if not self.state.pack_name:
                wx.MessageBox(
                    "Please enter a pack name to continue.",
                    "Missing Name",
                    wx.OK | wx.ICON_WARNING,
                )
                return False
            return True

        if self.current_step == 2:
            self.state.selected_alert_keys = [
                key for key, cb in self.category_checks if cb.GetValue()
            ]
            if not self.state.selected_alert_keys:
                wx.MessageBox(
                    "Please select at least one alert type.",
                    "No Selection",
                    wx.OK | wx.ICON_WARNING,
                )
                return False
            return True

        return True

    def _go_previous(self, event) -> None:
        """Go to previous step."""
        if self.current_step > 1:
            self.current_step -= 1
            self._render_step()

    def _go_next(self, event) -> None:
        """Go to next step or create pack."""
        if not self._validate_current_step():
            return

        if self.current_step < self.total_steps:
            self.current_step += 1
            self._render_step()
        else:
            # Create the pack
            self._create_pack()

    def _create_pack(self) -> None:
        """Create the sound pack."""
        # Generate unique pack ID
        slug = self.state.pack_name.strip().lower().replace(" ", "_").replace("-", "_")
        # Remove non-alphanumeric chars
        slug = "".join(c for c in slug if c.isalnum() or c == "_")

        pack_id = slug
        suffix = 2
        while (self.soundpacks_dir / pack_id).exists():
            pack_id = f"{slug}_{suffix}"
            suffix += 1

        pack_dir = self.soundpacks_dir / pack_id
        pack_dir.mkdir(parents=True)

        # Copy sound files
        sounds_mapping = {}
        for key, src_path_str in self.state.sound_mappings.items():
            if not src_path_str:
                continue
            src_path = Path(src_path_str)
            if src_path.exists():
                dest = pack_dir / src_path.name
                shutil.copy2(src_path, dest)
                sounds_mapping[key] = src_path.name

        # Create pack.json
        pack_data = {
            "name": self.state.pack_name,
            "author": self.state.author or "Unknown",
            "description": self.state.description,
            "version": "1.0.0",
            "sounds": sounds_mapping,
        }

        pack_json = pack_dir / "pack.json"
        with open(pack_json, "w", encoding="utf-8") as f:
            json.dump(pack_data, f, indent=2)

        self.created_pack_id = pack_id

        # Clean up staging directory
        with contextlib.suppress(Exception):
            shutil.rmtree(self.staging_dir)

        wx.MessageBox(
            f"Sound pack '{self.state.pack_name}' created successfully!",
            "Pack Created",
            wx.OK | wx.ICON_INFORMATION,
        )

        self.EndModal(wx.ID_OK)

    def _on_cancel(self, event) -> None:
        """Cancel the wizard."""
        # Check if there are any changes
        has_changes = bool(
            self.state.pack_name
            or self.state.author
            or self.state.description
            or self.state.selected_alert_keys
            or self.state.sound_mappings
        )

        if has_changes:
            result = wx.MessageBox(
                "Discard changes and close the wizard?",
                "Cancel Wizard",
                wx.YES_NO | wx.ICON_QUESTION,
            )
            if result != wx.YES:
                return

        # Clean up staging directory
        with contextlib.suppress(Exception):
            shutil.rmtree(self.staging_dir)

        self.EndModal(wx.ID_CANCEL)
