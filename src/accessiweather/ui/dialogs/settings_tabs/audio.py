"""Audio settings tab."""

from __future__ import annotations

import logging

import wx

logger = logging.getLogger(__name__)


class AudioTab:
    """Audio tab: sound playback, sound pack selection, event sounds configuration."""

    def __init__(self, dialog):
        """Store reference to the parent settings dialog."""
        self.dialog = dialog

    # ------------------------------------------------------------------
    # Static helpers (also used by SettingsDialogSimple for backward compat)
    # ------------------------------------------------------------------

    @staticmethod
    def _get_event_sound_sections() -> tuple[tuple[str, str, tuple[str, ...]], ...]:
        """Return grouped event-sound sections used by the settings UI."""
        try:
            from ....sound_events import SOUND_EVENT_SECTIONS
        except ImportError:
            from accessiweather.sound_events import SOUND_EVENT_SECTIONS

        return tuple(
            (title, description, tuple(event_key for event_key, _label in section_events))
            for title, description, section_events in SOUND_EVENT_SECTIONS
        )

    @staticmethod
    def _get_mutable_sound_events() -> tuple[tuple[str, str], ...]:
        """Return user-configurable event sound labels."""
        try:
            from ....sound_events import USER_MUTABLE_SOUND_EVENTS
        except ImportError:
            from accessiweather.sound_events import USER_MUTABLE_SOUND_EVENTS

        return tuple(USER_MUTABLE_SOUND_EVENTS)

    @classmethod
    def _build_default_event_sound_states(cls) -> dict[str, bool]:
        """Return the default enabled state for each mutable sound event."""
        return {event_key: True for event_key, _label in cls._get_mutable_sound_events()}

    # ------------------------------------------------------------------
    # Instance helpers (read/write dialog state)
    # ------------------------------------------------------------------

    def _get_muted_sound_events(self) -> list[str]:
        """Return muted event keys in the configured display order."""
        state_map = (
            getattr(self.dialog, "_event_sound_states", {})
            or self._build_default_event_sound_states()
        )
        return [
            event_key
            for event_key, _label in self._get_mutable_sound_events()
            if not state_map.get(event_key, True)
        ]

    def _get_event_sound_summary_text(self) -> str:
        """Build summary text shown on the audio tab."""
        total_events = len(self._get_mutable_sound_events())
        muted_events = self._get_muted_sound_events()
        enabled_count = total_events - len(muted_events)

        if not muted_events:
            return f"All {total_events} sound events are enabled."
        if enabled_count == 0:
            return "All event sounds are turned off."
        return f"{enabled_count} of {total_events} sound events are enabled."

    def _refresh_event_sound_summary(self) -> None:
        """Refresh the event sound summary shown on the audio tab."""
        summary_control = self.dialog._controls.get("event_sounds_summary")
        if summary_control is not None:
            summary_control.SetLabel(self._get_event_sound_summary_text())

    def set_event_sound_states(self, muted_sound_events: list[str] | tuple[str, ...]) -> None:
        """Apply muted event settings to the in-memory audio state."""
        muted_event_set = set(muted_sound_events)
        self.dialog._event_sound_states = {
            event_key: event_key not in muted_event_set
            for event_key, _label in self._get_mutable_sound_events()
        }
        self._refresh_event_sound_summary()

    # ------------------------------------------------------------------
    # Tab interface
    # ------------------------------------------------------------------

    def create(self):
        """Build the Audio tab panel and add it to the notebook."""
        panel = wx.Panel(self.dialog.notebook)
        sizer = wx.BoxSizer(wx.VERTICAL)
        controls = self.dialog._controls

        sizer.Add(wx.StaticText(panel, label="Audio"), 0, wx.ALL, 5)
        sizer.Add(
            wx.StaticText(
                panel,
                label=(
                    "Choose whether sounds are enabled, which sound pack is active, "
                    "and which events should play audio."
                ),
            ),
            0,
            wx.LEFT | wx.RIGHT | wx.BOTTOM,
            5,
        )

        playback_section = wx.StaticBoxSizer(wx.VERTICAL, panel, "Playback")

        controls["sound_enabled"] = wx.CheckBox(panel, label="Play notification sounds")
        playback_section.Add(controls["sound_enabled"], 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)

        row1 = wx.BoxSizer(wx.HORIZONTAL)
        row1.Add(
            wx.StaticText(panel, label="Sound pack:"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )

        # Load available sound packs
        self.dialog._sound_pack_ids = ["default"]
        pack_names = ["Default"]
        try:
            from ....notifications.sound_player import get_available_sound_packs

            packs = get_available_sound_packs()
            self.dialog._sound_pack_ids = list(packs.keys())
            pack_names = [packs[pid].get("name", pid) for pid in self.dialog._sound_pack_ids]
        except Exception as e:
            logger.warning(f"Failed to load sound packs: {e}")

        controls["sound_pack"] = wx.Choice(panel, choices=pack_names)
        row1.Add(controls["sound_pack"], 0)
        playback_section.Add(row1, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)

        test_btn = wx.Button(panel, label="Test Sound")
        test_btn.Bind(wx.EVT_BUTTON, self.dialog._on_test_sound)
        action_row = wx.BoxSizer(wx.HORIZONTAL)
        action_row.Add(test_btn, 0, wx.RIGHT, 10)

        manage_btn = wx.Button(panel, label="Manage Sound Packs...")
        manage_btn.Bind(wx.EVT_BUTTON, self.dialog._on_manage_soundpacks)
        action_row.Add(manage_btn, 0)
        playback_section.Add(action_row, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
        sizer.Add(playback_section, 0, wx.EXPAND | wx.ALL, 5)

        event_sounds_section = wx.StaticBoxSizer(wx.VERTICAL, panel, "Event sounds")
        event_sounds_section.Add(
            wx.StaticText(panel, label="Choose which events can play sounds."),
            0,
            wx.LEFT | wx.RIGHT | wx.BOTTOM,
            5,
        )
        controls["event_sounds_summary"] = wx.StaticText(panel, label="")
        event_sounds_section.Add(
            controls["event_sounds_summary"], 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 5
        )
        controls["configure_event_sounds"] = wx.Button(panel, label="Configure Event Sounds...")
        controls["configure_event_sounds"].Bind(
            wx.EVT_BUTTON, self.dialog._on_configure_event_sounds
        )
        event_sounds_section.Add(
            controls["configure_event_sounds"], 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 5
        )
        sizer.Add(event_sounds_section, 0, wx.EXPAND | wx.ALL, 5)

        panel.SetSizer(sizer)
        self.dialog.notebook.AddPage(panel, "Audio")
        return panel

    def load(self, settings):
        """Populate Audio tab controls from settings."""
        controls = self.dialog._controls

        controls["sound_enabled"].SetValue(getattr(settings, "sound_enabled", True))

        current_pack = getattr(settings, "sound_pack", "default")
        pack_ids = getattr(self.dialog, "_sound_pack_ids", ["default"])
        try:
            pack_idx = pack_ids.index(current_pack)
            controls["sound_pack"].SetSelection(pack_idx)
        except (ValueError, AttributeError):
            controls["sound_pack"].SetSelection(0)

        self.set_event_sound_states(getattr(settings, "muted_sound_events", ["data_updated"]))

    def save(self) -> dict:
        """Return Audio tab settings as a dict."""
        controls = self.dialog._controls
        pack_ids = getattr(self.dialog, "_sound_pack_ids", ["default"])
        pack_idx = controls["sound_pack"].GetSelection()
        sound_pack = pack_ids[pack_idx] if pack_idx < len(pack_ids) else "default"

        return {
            "sound_enabled": controls["sound_enabled"].GetValue(),
            "sound_pack": sound_pack,
            "muted_sound_events": self._get_muted_sound_events(),
        }

    def setup_accessibility(self):
        """Set accessibility names for Audio tab controls."""
        controls = self.dialog._controls
        names = {
            "sound_enabled": "Enable Sounds",
            "sound_pack": "Active sound pack",
            "event_sounds_summary": "Event sound summary",
            "configure_event_sounds": "Configure event sounds",
        }
        for key, name in names.items():
            controls[key].SetName(name)
