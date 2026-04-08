"""Notifications settings tab."""

from __future__ import annotations

import logging

import wx

logger = logging.getLogger(__name__)

_RADIUS_TYPE_VALUES = ["county", "point", "zone", "state"]
_RADIUS_TYPE_MAP = {"county": 0, "point": 1, "zone": 2, "state": 3}


class NotificationsTab:
    """Notifications tab: alert settings, severity levels, event notifications, rate limiting."""

    def __init__(self, dialog):
        """Store reference to the parent settings dialog."""
        self.dialog = dialog

    def create(self):
        """Build the Notifications tab panel and add it to the notebook."""
        panel = wx.ScrolledWindow(self.dialog.notebook)
        panel.SetScrollRate(0, 20)
        sizer = wx.BoxSizer(wx.VERTICAL)
        controls = self.dialog._controls

        sizer.Add(wx.StaticText(panel, label="Alert Notification Settings"), 0, wx.ALL, 5)
        sizer.Add(
            wx.StaticText(
                panel,
                label="Configure which weather alerts trigger notifications based on severity.",
            ),
            0,
            wx.LEFT | wx.BOTTOM,
            5,
        )

        controls["enable_alerts"] = wx.CheckBox(panel, label="Enable weather alerts")
        sizer.Add(controls["enable_alerts"], 0, wx.ALL, 5)

        controls["alert_notif"] = wx.CheckBox(panel, label="Enable alert notifications")
        sizer.Add(controls["alert_notif"], 0, wx.LEFT | wx.BOTTOM, 5)

        controls["immediate_alert_details_popups"] = wx.CheckBox(
            panel,
            label="Open alert details popups immediately while AccessiWeather is running",
        )
        sizer.Add(controls["immediate_alert_details_popups"], 0, wx.LEFT | wx.BOTTOM, 5)

        row_area = wx.BoxSizer(wx.HORIZONTAL)
        row_area.Add(
            wx.StaticText(panel, label="Alert Area:"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )
        controls["alert_radius_type"] = wx.Choice(
            panel,
            choices=[
                "County (recommended — alerts for your county only)",
                "Point (exact coordinate — may miss alerts)",
                "Zone (NWS forecast zone — slightly broader than county)",
                "State (entire state — noisy)",
            ],
        )
        row_area.Add(controls["alert_radius_type"], 0)
        sizer.Add(row_area, 0, wx.ALL, 5)

        sizer.Add(wx.StaticText(panel, label="Alert Severity Levels:"), 0, wx.ALL, 5)

        controls["notify_extreme"] = wx.CheckBox(
            panel, label="Extreme - Life-threatening events (e.g., Tornado Warning)"
        )
        sizer.Add(controls["notify_extreme"], 0, wx.LEFT, 10)

        controls["notify_severe"] = wx.CheckBox(
            panel, label="Severe - Significant hazards (e.g., Severe Thunderstorm Warning)"
        )
        sizer.Add(controls["notify_severe"], 0, wx.LEFT, 10)

        controls["notify_moderate"] = wx.CheckBox(
            panel, label="Moderate - Potentially hazardous (e.g., Winter Weather Advisory)"
        )
        sizer.Add(controls["notify_moderate"], 0, wx.LEFT, 10)

        controls["notify_minor"] = wx.CheckBox(
            panel, label="Minor - Low impact events (e.g., Frost Advisory, Fog Advisory)"
        )
        sizer.Add(controls["notify_minor"], 0, wx.LEFT, 10)

        controls["notify_unknown"] = wx.CheckBox(panel, label="Unknown - Uncategorized alerts")
        sizer.Add(controls["notify_unknown"], 0, wx.LEFT, 10)

        sizer.Add(wx.StaticText(panel, label="Event-Based Notifications:"), 0, wx.ALL, 5)
        sizer.Add(
            wx.StaticText(
                panel,
                label="Get notified when specific weather events occur (disabled by default).",
            ),
            0,
            wx.LEFT | wx.BOTTOM,
            5,
        )

        controls["notify_discussion_update"] = wx.CheckBox(
            panel, label="Notify when Area Forecast Discussion is updated (NWS US only)"
        )
        sizer.Add(controls["notify_discussion_update"], 0, wx.LEFT, 10)

        controls["notify_severe_risk_change"] = wx.CheckBox(
            panel, label="Notify when severe weather risk level changes (Visual Crossing only)"
        )
        sizer.Add(controls["notify_severe_risk_change"], 0, wx.LEFT | wx.BOTTOM, 10)

        controls["notify_minutely_precipitation_start"] = wx.CheckBox(
            panel, label="Notify when precipitation is expected to start soon (Pirate Weather)"
        )
        sizer.Add(controls["notify_minutely_precipitation_start"], 0, wx.LEFT, 10)

        controls["notify_minutely_precipitation_stop"] = wx.CheckBox(
            panel, label="Notify when precipitation is expected to stop soon (Pirate Weather)"
        )
        sizer.Add(controls["notify_minutely_precipitation_stop"], 0, wx.LEFT | wx.BOTTOM, 10)

        # Hidden alert timing controls (values managed via Advanced dialog)
        controls["global_cooldown"] = wx.SpinCtrl(panel, min=0, max=60, initial=5)
        controls["global_cooldown"].Hide()
        controls["per_alert_cooldown"] = wx.SpinCtrl(panel, min=0, max=1440, initial=60)
        controls["per_alert_cooldown"].Hide()
        controls["freshness_window"] = wx.SpinCtrl(panel, min=0, max=120, initial=15)
        controls["freshness_window"].Hide()

        sizer.Add(wx.StaticText(panel, label="Rate Limiting:"), 0, wx.ALL, 5)

        row_max = wx.BoxSizer(wx.HORIZONTAL)
        row_max.Add(
            wx.StaticText(panel, label="Maximum notifications per hour:"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )
        controls["max_notifications"] = wx.SpinCtrl(panel, min=1, max=100, initial=10)
        row_max.Add(controls["max_notifications"], 0)
        sizer.Add(row_max, 0, wx.LEFT | wx.TOP, 10)

        advanced_btn = wx.Button(panel, label="Advanced...")
        advanced_btn.SetName("Advanced alert timing settings")
        advanced_btn.SetToolTip("Configure cooldown periods and alert freshness window")
        advanced_btn.Bind(wx.EVT_BUTTON, self.dialog._on_alert_advanced)
        sizer.Add(advanced_btn, 0, wx.LEFT | wx.TOP, 10)

        panel.SetSizer(sizer)
        self.dialog.notebook.AddPage(panel, "Notifications")
        return panel

    def load(self, settings):
        """Populate Notifications tab controls from settings."""
        controls = self.dialog._controls

        controls["enable_alerts"].SetValue(getattr(settings, "enable_alerts", True))
        controls["alert_notif"].SetValue(getattr(settings, "alert_notifications_enabled", True))

        radius_type = getattr(settings, "alert_radius_type", "county")
        controls["alert_radius_type"].SetSelection(_RADIUS_TYPE_MAP.get(radius_type, 0))

        controls["notify_extreme"].SetValue(getattr(settings, "alert_notify_extreme", True))
        controls["notify_severe"].SetValue(getattr(settings, "alert_notify_severe", True))
        controls["notify_moderate"].SetValue(getattr(settings, "alert_notify_moderate", True))
        controls["notify_minor"].SetValue(getattr(settings, "alert_notify_minor", False))
        controls["notify_unknown"].SetValue(getattr(settings, "alert_notify_unknown", False))
        controls["immediate_alert_details_popups"].SetValue(
            getattr(settings, "immediate_alert_details_popups", False)
        )

        controls["global_cooldown"].SetValue(getattr(settings, "alert_global_cooldown_minutes", 5))
        controls["per_alert_cooldown"].SetValue(
            getattr(settings, "alert_per_alert_cooldown_minutes", 60)
        )
        controls["freshness_window"].SetValue(
            getattr(settings, "alert_freshness_window_minutes", 15)
        )
        controls["max_notifications"].SetValue(
            getattr(settings, "alert_max_notifications_per_hour", 10)
        )

        controls["notify_discussion_update"].SetValue(
            getattr(settings, "notify_discussion_update", True)
        )
        controls["notify_severe_risk_change"].SetValue(
            getattr(settings, "notify_severe_risk_change", False)
        )
        controls["notify_minutely_precipitation_start"].SetValue(
            getattr(settings, "notify_minutely_precipitation_start", False)
        )
        controls["notify_minutely_precipitation_stop"].SetValue(
            getattr(settings, "notify_minutely_precipitation_stop", False)
        )

    def save(self) -> dict:
        """Return Notifications tab settings as a dict."""
        controls = self.dialog._controls
        return {
            "enable_alerts": controls["enable_alerts"].GetValue(),
            "alert_notifications_enabled": controls["alert_notif"].GetValue(),
            "alert_radius_type": _RADIUS_TYPE_VALUES[controls["alert_radius_type"].GetSelection()],
            "alert_notify_extreme": controls["notify_extreme"].GetValue(),
            "alert_notify_severe": controls["notify_severe"].GetValue(),
            "alert_notify_moderate": controls["notify_moderate"].GetValue(),
            "alert_notify_minor": controls["notify_minor"].GetValue(),
            "alert_notify_unknown": controls["notify_unknown"].GetValue(),
            "immediate_alert_details_popups": controls["immediate_alert_details_popups"].GetValue(),
            "alert_global_cooldown_minutes": controls["global_cooldown"].GetValue(),
            "alert_per_alert_cooldown_minutes": controls["per_alert_cooldown"].GetValue(),
            "alert_freshness_window_minutes": controls["freshness_window"].GetValue(),
            "alert_max_notifications_per_hour": controls["max_notifications"].GetValue(),
            "notify_discussion_update": controls["notify_discussion_update"].GetValue(),
            "notify_severe_risk_change": controls["notify_severe_risk_change"].GetValue(),
            "notify_minutely_precipitation_start": controls[
                "notify_minutely_precipitation_start"
            ].GetValue(),
            "notify_minutely_precipitation_stop": controls[
                "notify_minutely_precipitation_stop"
            ].GetValue(),
        }

    def setup_accessibility(self):
        """Set accessibility names for Notifications tab controls."""
        controls = self.dialog._controls
        names = {
            "enable_alerts": "Enable weather alerts",
            "alert_notif": "Enable alert notifications",
            "alert_radius_type": "Alert Area",
            "notify_extreme": "Extreme - Life-threatening events (e.g., Tornado Warning)",
            "notify_severe": "Severe - Significant hazards (e.g., Severe Thunderstorm Warning)",
            "notify_moderate": "Moderate - Potentially hazardous (e.g., Winter Weather Advisory)",
            "notify_minor": "Minor - Low impact events (e.g., Frost Advisory, Fog Advisory)",
            "notify_unknown": "Unknown - Uncategorized alerts",
            "immediate_alert_details_popups": "Open alert details popups immediately while AccessiWeather is running",
            "notify_discussion_update": "Notify when Area Forecast Discussion is updated (NWS US only)",
            "notify_severe_risk_change": "Notify when severe weather risk level changes (Visual Crossing only)",
            "notify_minutely_precipitation_start": "Notify when precipitation is expected to start soon (Pirate Weather)",
            "notify_minutely_precipitation_stop": "Notify when precipitation is expected to stop soon (Pirate Weather)",
            "global_cooldown": "Minimum time between any alert notifications (minutes)",
            "per_alert_cooldown": "Re-notify for same alert after (minutes)",
            "freshness_window": "Only notify for alerts issued within (minutes)",
            "max_notifications": "Maximum notifications per hour",
        }
        for key, name in names.items():
            controls[key].SetName(name)
