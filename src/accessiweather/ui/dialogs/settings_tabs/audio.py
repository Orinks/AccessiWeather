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

    @classmethod
    def build_event_sound_summary_text(cls, state_map: dict[str, bool]) -> str:
        """Build plain-language event sound summary text."""
        total_events = len(cls._get_mutable_sound_events())
        enabled_count = sum(1 for enabled in state_map.values() if enabled)
        if enabled_count == total_events:
            return f"Sounds will play for all {total_events} selectable event types."
        if enabled_count == 0:
            return "Sounds are turned off for every selectable event type."
        return f"Sounds will play for {enabled_count} of {total_events} selectable event types."

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
        state_map = (
            getattr(self.dialog, "_event_sound_states", {})
            or self._build_default_event_sound_states()
        )
        return self.build_event_sound_summary_text(state_map)

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

    def create(self, page_label: str = "Audio"):
        """Build the Audio tab panel and add it to the notebook."""
        panel = wx.ScrolledWindow(self.dialog.notebook)
        panel.SetScrollRate(0, 20)
        sizer = wx.BoxSizer(wx.VERTICAL)
        controls = self.dialog._controls

        self.dialog.add_help_text(
            panel,
            sizer,
            "Choose whether AccessiWeather plays sounds, which sound pack it uses, and which events are allowed to make noise.",
            left=5,
        )

        playback_section = self.dialog.create_section(
            panel,
            sizer,
            "Playback",
            "Turn sound on or off, then choose the sound pack you want to hear.",
        )
        controls["sound_enabled"] = wx.CheckBox(panel, label="Play notification sounds")
        playback_section.Add(
            controls["sound_enabled"],
            0,
            wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND,
            10,
        )

        self.dialog._sound_pack_ids = ["default"]
        pack_names = ["Default"]
        try:
            from ....notifications.sound_player import get_available_sound_packs

            packs = get_available_sound_packs()
            self.dialog._sound_pack_ids = list(packs.keys())
            pack_names = [packs[pid].get("name", pid) for pid in self.dialog._sound_pack_ids]
        except Exception as e:
            logger.warning(f"Failed to load sound packs: {e}")

        controls["sound_pack"] = self.dialog.add_labeled_control_row(
            panel,
            playback_section,
            "Sound pack:",
            lambda parent: wx.Choice(parent, choices=pack_names),
        )
        action_row = wx.BoxSizer(wx.HORIZONTAL)
        test_btn = wx.Button(panel, label="Play sample sound")
        test_btn.Bind(wx.EVT_BUTTON, self.dialog._on_test_sound)
        action_row.Add(test_btn, 0, wx.RIGHT, 10)
        manage_btn = wx.Button(panel, label="Manage sound packs...")
        manage_btn.Bind(wx.EVT_BUTTON, self.dialog._on_manage_soundpacks)
        action_row.Add(manage_btn, 0)
        playback_section.Add(action_row, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        event_sounds_section = self.dialog.create_section(
            panel,
            sizer,
            "When sounds play",
            "Choose which event types can make sound. This gives you finer control without turning all audio off.",
        )
        controls["event_sounds_summary"] = wx.StaticText(panel, label="")
        event_sounds_section.Add(
            controls["event_sounds_summary"],
            0,
            wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND,
            10,
        )
        controls["configure_event_sounds"] = wx.Button(
            panel,
            label="Choose event sounds...",
        )
        controls["configure_event_sounds"].Bind(
            wx.EVT_BUTTON,
            self.dialog._on_configure_event_sounds,
        )
        event_sounds_section.Add(
            controls["configure_event_sounds"],
            0,
            wx.LEFT | wx.RIGHT | wx.BOTTOM,
            10,
        )

        panel.SetSizer(sizer)
        self.dialog.notebook.AddPage(panel, page_label)
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
            "sound_enabled": "Play notification sounds",
            "sound_pack": "Sound pack",
            "event_sounds_summary": "Event sound summary",
            "configure_event_sounds": "Choose event sounds",
        }
        for key, name in names.items():
            controls[key].SetName(name)
