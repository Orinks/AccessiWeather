"""Debug dialog for testing alert notifications with different types and severities."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import NamedTuple

import wx

from ...models import WeatherAlert

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Preset alert definitions
# Each entry becomes one row in the listbox.
# ---------------------------------------------------------------------------


class AlertPreset(NamedTuple):
    label: str
    event: str
    severity: str
    urgency: str
    headline: str
    description: str


ALERT_PRESETS: list[AlertPreset] = [
    AlertPreset(
        label="Tornado Warning (Extreme)",
        event="Tornado Warning",
        severity="Extreme",
        urgency="Immediate",
        headline="Tornado Warning in effect until 9:15 PM EDT.",
        description="A tornado warning has been issued for your area. "
        "Take cover now in a sturdy building.",
    ),
    AlertPreset(
        label="Severe Thunderstorm Warning (Severe)",
        event="Severe Thunderstorm Warning",
        severity="Severe",
        urgency="Immediate",
        headline="Severe Thunderstorm Warning until 7:45 PM EDT.",
        description="A severe thunderstorm capable of producing golf ball sized hail "
        "and damaging winds is approaching.",
    ),
    AlertPreset(
        label="Flash Flood Warning (Severe)",
        event="Flash Flood Warning",
        severity="Severe",
        urgency="Immediate",
        headline="Flash Flood Warning until midnight EDT.",
        description="Flash flooding is occurring or imminent. Do not attempt to travel "
        "in flooded areas.",
    ),
    AlertPreset(
        label="Flash Flood Watch (Moderate)",
        event="Flash Flood Watch",
        severity="Moderate",
        urgency="Expected",
        headline="Flash Flood Watch in effect through Wednesday morning.",
        description="Conditions are favorable for flash flooding.",
    ),
    AlertPreset(
        label="Hurricane Warning (Extreme)",
        event="Hurricane Warning",
        severity="Extreme",
        urgency="Immediate",
        headline="Hurricane Warning in effect.",
        description="Hurricane conditions expected within 36 hours. "
        "Complete preparations immediately.",
    ),
    AlertPreset(
        label="Winter Storm Watch (Moderate)",
        event="Winter Storm Watch",
        severity="Moderate",
        urgency="Expected",
        headline="Winter Storm Watch from late tonight through Thursday morning.",
        description="Heavy snow possible. Total snowfall accumulations of 8 to 14 inches possible.",
    ),
    AlertPreset(
        label="Winter Storm Warning (Severe)",
        event="Winter Storm Warning",
        severity="Severe",
        urgency="Expected",
        headline="Winter Storm Warning until 6 AM EST Thursday.",
        description="Heavy snow expected. Total snowfall accumulations of 10 to 16 inches.",
    ),
    AlertPreset(
        label="Dense Fog Advisory (Minor)",
        event="Dense Fog Advisory",
        severity="Minor",
        urgency="Expected",
        headline="Dense Fog Advisory until 10 AM EDT.",
        description="Visibility of one quarter mile or less expected.",
    ),
    AlertPreset(
        label="Frost Advisory (Minor)",
        event="Frost Advisory",
        severity="Minor",
        urgency="Expected",
        headline="Frost Advisory from 2 AM to 8 AM EDT.",
        description="Temperatures in the upper 20s to low 30s with light winds will "
        "result in frost formation.",
    ),
    AlertPreset(
        label="Heat Advisory (Moderate)",
        event="Heat Advisory",
        severity="Moderate",
        urgency="Expected",
        headline="Heat Advisory until 8 PM EDT this evening.",
        description="Heat index values up to 105 expected. Drink plenty of fluids.",
    ),
    AlertPreset(
        label="Special Weather Statement (Minor)",
        event="Special Weather Statement",
        severity="Minor",
        urgency="Future",
        headline="Special Weather Statement.",
        description="A hazardous weather outlook is in effect for the area.",
    ),
    AlertPreset(
        label="Air Quality Alert (Unknown)",
        event="Air Quality Alert",
        severity="Unknown",
        urgency="Expected",
        headline="Air Quality Alert in effect.",
        description="Air quality index values are forecast to reach the Unhealthy for Sensitive "
        "Groups range.",
    ),
]


class DebugAlertDialog(wx.Dialog):
    """Dialog for sending test alert notifications with selectable type and severity."""

    def __init__(self, parent: wx.Window, app) -> None:
        """Initialize the debug alert notification dialog."""
        super().__init__(
            parent,
            title="Test Alert Notification",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self._app = app
        self._build_ui()
        self._update_candidates()
        self.SetSize((520, 440))
        if self.GetParent() is not None:
            self.CentreOnParent()
        else:
            self.Centre()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # --- Alert preset list ---
        sizer.Add(
            wx.StaticText(panel, label="Select alert type to send:"),
            0,
            wx.ALL,
            8,
        )
        self._list = wx.ListBox(
            panel,
            choices=[p.label for p in ALERT_PRESETS],
            style=wx.LB_SINGLE,
        )
        self._list.SetSelection(0)
        self._list.Bind(wx.EVT_LISTBOX, self._on_selection_changed)
        sizer.Add(self._list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        # --- Sound candidates preview ---
        sizer.Add(
            wx.StaticText(panel, label="Sound event candidates (tried in order):"),
            0,
            wx.LEFT | wx.RIGHT,
            8,
        )
        self._candidates_label = wx.TextCtrl(
            panel,
            style=wx.TE_READONLY | wx.TE_MULTILINE | wx.TE_NO_VSCROLL,
            size=(-1, 48),
        )
        sizer.Add(self._candidates_label, 0, wx.EXPAND | wx.ALL, 8)

        # --- Status line ---
        self._status = wx.StaticText(panel, label="")
        sizer.Add(self._status, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        # --- Buttons ---
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self._send_btn = wx.Button(panel, label="&Send Test Notification")
        self._send_btn.Bind(wx.EVT_BUTTON, self._on_send)
        close_btn = wx.Button(panel, wx.ID_CLOSE, label="&Close")
        close_btn.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CLOSE))
        btn_sizer.Add(self._send_btn, 0, wx.RIGHT, 8)
        btn_sizer.Add(close_btn, 0)
        sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 8)

        panel.SetSizer(sizer)
        panel.Layout()

        # Make the send button the default
        self._send_btn.SetDefault()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _selected_preset(self) -> AlertPreset:
        idx = self._list.GetSelection()
        if idx == wx.NOT_FOUND:
            return ALERT_PRESETS[0]
        return ALERT_PRESETS[idx]

    def _make_alert(self, preset: AlertPreset) -> WeatherAlert:
        return WeatherAlert(
            id=f"debug-test-{preset.event.lower().replace(' ', '-')}",
            title=preset.event,
            event=preset.event,
            severity=preset.severity,
            urgency=preset.urgency,
            headline=preset.headline,
            description=preset.description,
            expires=datetime.now(UTC) + timedelta(hours=2),
        )

    def _update_candidates(self) -> None:
        from ...notifications.alert_sound_mapper import get_candidate_sound_events

        preset = self._selected_preset()
        alert = self._make_alert(preset)
        candidates = get_candidate_sound_events(alert)
        self._candidates_label.SetValue(" → ".join(candidates))

    def _get_notifier(self, settings):
        from ...notifications.toast_notifier import SafeToastNotifier

        notifier = getattr(self._app, "notifier", None)
        if notifier is None:
            notifier = SafeToastNotifier(
                sound_enabled=bool(getattr(settings, "sound_enabled", True)),
                soundpack=getattr(settings, "sound_pack", "default"),
            )
        return notifier

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_selection_changed(self, event) -> None:
        self._update_candidates()
        self._status.SetLabel("")

    def _on_send(self, event) -> None:
        from ...notifications.alert_sound_mapper import get_candidate_sound_events

        try:
            settings = self._app.config_manager.get_settings()
        except Exception:
            from ...models import AppSettings

            settings = AppSettings()

        preset = self._selected_preset()
        alert = self._make_alert(preset)
        candidates = get_candidate_sound_events(alert)

        notifier = self._get_notifier(settings)

        title = f"{preset.severity.upper()} ALERT: {preset.event}"
        message = preset.headline
        if preset.description:
            message += f"\n{preset.description}"

        logger.debug(
            "[debug] Sending test alert: title=%r, sound_candidates=%s",
            title,
            candidates,
        )

        sent = notifier.send_notification(
            title=title,
            message=message,
            timeout=10,
            sound_candidates=candidates,
            play_sound=True,
        )

        if sent:
            self._status.SetLabel(f"✓ Sent: {preset.label}")
            logger.info("[debug] Test alert notification sent: %r", title)
        else:
            self._status.SetLabel("✗ Notification not sent — check system permissions")
            logger.warning("[debug] Test alert notification returned False: %r", title)

        self.Layout()
