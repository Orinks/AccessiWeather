"""Notifications settings tab."""

from __future__ import annotations

import logging

import wx

logger = logging.getLogger(__name__)

_RADIUS_TYPE_VALUES = ["county", "point", "zone", "state"]
_RADIUS_TYPE_MAP = {"county": 0, "point": 1, "zone": 2, "state": 3}

_SENSITIVITY_VALUES = ["light", "moderate", "heavy"]
_SENSITIVITY_MAP = {"light": 0, "moderate": 1, "heavy": 2}


class NotificationsTab:
    """Notifications tab: alert settings, severity levels, event notifications, rate limiting."""

    def __init__(self, dialog):
        """Store reference to the parent settings dialog."""
        self.dialog = dialog

    def create(self, page_label: str = "Alerts"):
        """Build the Notifications tab panel and add it to the notebook."""
        panel = wx.ScrolledWindow(self.dialog.notebook)
        panel.SetScrollRate(0, 20)
        sizer = wx.BoxSizer(wx.VERTICAL)
        controls = self.dialog._controls

        self.dialog.add_help_text(
            panel,
            sizer,
            "Control which alerts notify you, how broad the alert area is, and how aggressively notifications repeat.",
            left=5,
        )

        delivery_section = self.dialog.create_section(
            panel,
            sizer,
            "Alert delivery",
            "Turn alert monitoring on or off, then choose whether AccessiWeather should notify you when alerts arrive.",
        )
        controls["enable_alerts"] = wx.CheckBox(panel, label="Monitor weather alerts")
        delivery_section.Add(controls["enable_alerts"], 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        controls["alert_notif"] = wx.CheckBox(panel, label="Send alert notifications")
        delivery_section.Add(controls["alert_notif"], 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        controls["immediate_alert_details_popups"] = wx.CheckBox(
            panel,
            label="Open alert details immediately while AccessiWeather is running",
        )
        delivery_section.Add(
            controls["immediate_alert_details_popups"],
            0,
            wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND,
            10,
        )

        coverage_section = self.dialog.create_section(
            panel,
            sizer,
            "Coverage and severity",
            "Smaller alert areas are quieter. Broader areas catch more alerts but can be noisier.",
        )
        controls["alert_radius_type"] = self.dialog.add_labeled_control_row(
            panel,
            coverage_section,
            "Alert area:",
            lambda parent: wx.Choice(
                parent,
                choices=[
                    "County (recommended)",
                    "Point (exact coordinate, may miss alerts)",
                    "Zone (slightly broader than county)",
                    "State (broadest and noisiest)",
                ],
            ),
        )
        controls["notify_extreme"] = wx.CheckBox(
            panel,
            label="Extreme severity alerts",
        )
        coverage_section.Add(controls["notify_extreme"], 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        controls["notify_severe"] = wx.CheckBox(
            panel,
            label="Severe severity alerts",
        )
        coverage_section.Add(controls["notify_severe"], 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        controls["notify_moderate"] = wx.CheckBox(
            panel,
            label="Moderate severity alerts",
        )
        coverage_section.Add(controls["notify_moderate"], 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        controls["notify_minor"] = wx.CheckBox(
            panel,
            label="Minor severity alerts",
        )
        coverage_section.Add(controls["notify_minor"], 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        controls["notify_unknown"] = wx.CheckBox(
            panel,
            label="Uncategorized alerts",
        )
        coverage_section.Add(controls["notify_unknown"], 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        event_section = self.dialog.create_section(
            panel,
            sizer,
            "Extra weather event notifications",
            "These are optional updates beyond standard alerts and are off unless you turn them on.",
        )
        controls["notify_discussion_update"] = wx.CheckBox(
            panel,
            label="Notify when the Area Forecast Discussion changes (NWS US only)",
        )
        event_section.Add(
            controls["notify_discussion_update"],
            0,
            wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND,
            10,
        )
        controls["notify_severe_risk_change"] = wx.CheckBox(
            panel,
            label="Notify when severe weather risk changes (Visual Crossing)",
        )
        event_section.Add(
            controls["notify_severe_risk_change"],
            0,
            wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND,
            10,
        )
        controls["notify_minutely_precipitation_start"] = wx.CheckBox(
            panel,
            label="Notify when precipitation is expected to start soon (Pirate Weather)",
        )
        event_section.Add(
            controls["notify_minutely_precipitation_start"],
            0,
            wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND,
            10,
        )
        controls["notify_minutely_precipitation_stop"] = wx.CheckBox(
            panel,
            label="Notify when precipitation is expected to stop soon (Pirate Weather)",
        )
        event_section.Add(
            controls["notify_minutely_precipitation_stop"],
            0,
            wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND,
            10,
        )

        row_sensitivity = wx.BoxSizer(wx.HORIZONTAL)
        row_sensitivity.Add(
            wx.StaticText(panel, label="Notify for:"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )
        controls["precipitation_sensitivity"] = wx.Choice(
            panel,
            choices=[
                "Light rain and above (default, \u22650.01\u00a0mm/h)",
                "Moderate rain and above (\u22650.1\u00a0mm/h)",
                "Heavy rain only (\u22651.0\u00a0mm/h)",
            ],
        )
        row_sensitivity.Add(controls["precipitation_sensitivity"], 0)
        event_section.Add(row_sensitivity, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # Hidden alert timing controls (values managed via Advanced dialog)
        controls["global_cooldown"] = wx.SpinCtrl(panel, min=0, max=60, initial=5)
        controls["global_cooldown"].Hide()
        controls["per_alert_cooldown"] = wx.SpinCtrl(panel, min=0, max=1440, initial=60)
        controls["per_alert_cooldown"].Hide()
        controls["freshness_window"] = wx.SpinCtrl(panel, min=0, max=120, initial=15)
        controls["freshness_window"].Hide()

        rate_section = self.dialog.create_section(
            panel,
            sizer,
            "Rate limiting",
            "Use the advanced timing dialog if you need cooldown and freshness controls beyond the hourly limit.",
        )
        controls["max_notifications"] = self.dialog.add_labeled_control_row(
            panel,
            rate_section,
            "Maximum notifications per hour:",
            lambda parent: wx.SpinCtrl(parent, min=1, max=100, initial=10),
        )
        advanced_btn = wx.Button(panel, label="Advanced timing...")
        advanced_btn.SetName("Advanced alert timing settings")
        advanced_btn.SetToolTip("Configure cooldown periods and the alert freshness window")
        advanced_btn.Bind(wx.EVT_BUTTON, self.dialog._on_alert_advanced)
        rate_section.Add(advanced_btn, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        panel.SetSizer(sizer)
        self.dialog.notebook.AddPage(panel, page_label)
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
        sensitivity = getattr(settings, "precipitation_sensitivity", "light")
        controls["precipitation_sensitivity"].SetSelection(_SENSITIVITY_MAP.get(sensitivity, 0))

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
            "precipitation_sensitivity": _SENSITIVITY_VALUES[
                controls["precipitation_sensitivity"].GetSelection()
            ],
        }

    def setup_accessibility(self):
        """Set accessibility names for Notifications tab controls."""
        controls = self.dialog._controls
        names = {
            "enable_alerts": "Monitor weather alerts",
            "alert_notif": "Send alert notifications",
            "alert_radius_type": "Alert area",
            "notify_extreme": "Extreme severity alerts",
            "notify_severe": "Severe severity alerts",
            "notify_moderate": "Moderate severity alerts",
            "notify_minor": "Minor severity alerts",
            "notify_unknown": "Uncategorized alerts",
            "immediate_alert_details_popups": "Open alert details immediately while AccessiWeather is running",
            "notify_discussion_update": "Notify when the Area Forecast Discussion changes",
            "notify_severe_risk_change": "Notify when severe weather risk changes",
            "notify_minutely_precipitation_start": "Notify when precipitation is expected to start soon",
            "notify_minutely_precipitation_stop": "Notify when precipitation is expected to stop soon",
            "precipitation_sensitivity": "Notify for: precipitation sensitivity level",
            "global_cooldown": "Minimum time between any alert notifications in minutes",
            "per_alert_cooldown": "Minutes before repeating the same alert notification",
            "freshness_window": "Only notify for alerts issued within this many minutes",
            "max_notifications": "Maximum notifications per hour",
        }
        for key, name in names.items():
            controls[key].SetName(name)
