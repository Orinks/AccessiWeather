"""Handlers for applying and collecting settings in the dialog."""

from __future__ import annotations

import contextlib
import logging

from ..models import AppSettings

logger = logging.getLogger(__name__)


def apply_settings_to_ui(dialog):
    """Populate dialog widgets from the dialog's working settings copy."""
    try:
        settings = dialog.current_settings

        if getattr(dialog, "temperature_unit_selection", None):
            dialog.temperature_unit_selection.value = dialog.temperature_value_to_display.get(
                getattr(settings, "temperature_unit", "both"),
                "Both (Fahrenheit and Celsius)",
            )

        if getattr(dialog, "update_interval_input", None):
            dialog.update_interval_input.value = getattr(settings, "update_interval_minutes", 10)

        if getattr(dialog, "show_detailed_forecast_switch", None):
            dialog.show_detailed_forecast_switch.value = getattr(
                settings, "show_detailed_forecast", True
            )

        if getattr(dialog, "enable_alerts_switch", None):
            dialog.enable_alerts_switch.value = getattr(settings, "enable_alerts", True)

        if getattr(dialog, "air_quality_threshold_input", None):
            try:
                dialog.air_quality_threshold_input.value = int(
                    getattr(settings, "air_quality_notify_threshold", 3)
                )
            except Exception:  # pragma: no cover - defensive default
                dialog.air_quality_threshold_input.value = 3

        if getattr(dialog, "data_source_selection", None):
            display = dialog.data_source_value_to_display.get(
                getattr(settings, "data_source", "auto")
            )
            if display:
                dialog.data_source_selection.value = display

        if getattr(dialog, "visual_crossing_api_key_input", None) is not None:
            dialog.visual_crossing_api_key_input.value = getattr(
                settings, "visual_crossing_api_key", ""
            )

        with contextlib.suppress(Exception):
            dialog._update_visual_crossing_visibility()

        if getattr(dialog, "sound_enabled_switch", None) is not None:
            dialog.sound_enabled_switch.value = getattr(settings, "sound_enabled", True)

        if getattr(dialog, "sound_pack_selection", None) is not None:
            target_pack = getattr(settings, "sound_pack", "default")
            display_name = None
            for name, pack_id in getattr(dialog, "sound_pack_map", {}).items():
                if pack_id == target_pack:
                    display_name = name
                    break

            if not display_name and getattr(dialog, "sound_pack_options", []):
                display_name = dialog.sound_pack_options[0]

            if display_name:
                dialog.sound_pack_selection.value = display_name

            dialog.sound_pack_selection.enabled = bool(  # keep enabled state in sync
                dialog.sound_enabled_switch.value
            )

        if getattr(dialog, "alert_sound_override_inputs", None):
            overrides = getattr(settings, "alert_sound_overrides", {}) or {}
            for key, widget in dialog.alert_sound_override_inputs.items():
                if widget is not None:
                    widget.value = str(overrides.get(key, ""))

        if getattr(dialog, "alert_tts_switch", None):
            dialog.alert_tts_switch.value = getattr(settings, "alert_tts_enabled", False)

        if getattr(dialog, "alert_tts_voice_input", None):
            dialog.alert_tts_voice_input.value = getattr(settings, "alert_tts_voice", "")

        if getattr(dialog, "alert_tts_rate_input", None):
            rate_value = getattr(settings, "alert_tts_rate", 0)
            dialog.alert_tts_rate_input.value = str(rate_value if rate_value else "")

        if getattr(dialog, "auto_update_switch", None) is not None:
            dialog.auto_update_switch.value = getattr(settings, "auto_update_enabled", True)

        if getattr(dialog, "update_channel_selection", None) is not None:
            channel = getattr(settings, "update_channel", "stable")
            if channel == "dev":
                dialog.update_channel_selection.value = (
                    "Development (Latest features, may be unstable)"
                )
            elif channel == "beta":
                dialog.update_channel_selection.value = "Beta (Pre-release testing)"
            else:
                dialog.update_channel_selection.value = "Stable (Production releases only)"

            with contextlib.suppress(Exception):
                dialog._update_channel_description()

        if getattr(dialog, "update_check_interval_input", None) is not None:
            dialog.update_check_interval_input.value = getattr(
                settings, "update_check_interval_hours", 24
            )

        if getattr(dialog, "minimize_to_tray_switch", None) is not None:
            dialog.minimize_to_tray_switch.value = getattr(settings, "minimize_to_tray", False)

        if getattr(dialog, "startup_enabled_switch", None) is not None:
            try:
                actual_startup = dialog.config_manager.is_startup_enabled()
                dialog.startup_enabled_switch.value = actual_startup
            except Exception as exc:  # pragma: no cover - platform failures
                logger.warning("Failed to sync startup state: %s", exc)
                dialog.startup_enabled_switch.value = getattr(settings, "startup_enabled", False)

        if getattr(dialog, "debug_mode_switch", None) is not None:
            dialog.debug_mode_switch.value = getattr(settings, "debug_mode", False)

    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("Failed to apply settings to UI: %s", exc)


def map_channel_display_to_value(display: str) -> str:
    """Return the internal channel value for the provided display text."""
    if "Development" in display:
        return "dev"
    if "Beta" in display:
        return "beta"
    return "stable"


def collect_settings_from_ui(dialog) -> AppSettings:
    """Read current widget values and return an AppSettings instance."""
    try:
        selected_display = str(dialog.data_source_selection.value)
        data_source = dialog.data_source_display_to_value.get(selected_display, "auto")
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.warning("Failed to get data source selection: %s", exc)
        data_source = "auto"

    try:
        selected_display = str(dialog.temperature_unit_selection.value)
        temperature_unit = dialog.temperature_display_to_value.get(selected_display, "both")
    except Exception as exc:  # pragma: no cover
        logger.warning("Failed to get temperature unit selection: %s", exc)
        temperature_unit = "both"

    try:
        update_interval = int(dialog.update_interval_input.value)
        update_interval = max(1, min(1440, update_interval))
    except (ValueError, TypeError):
        update_interval = 10

    auto_update_enabled = getattr(dialog.auto_update_switch, "value", True)

    if getattr(dialog, "update_channel_selection", None) and hasattr(
        dialog.update_channel_selection, "value"
    ):
        channel_value = str(dialog.update_channel_selection.value)
        update_channel = map_channel_display_to_value(channel_value)
    else:
        update_channel = "stable"

    if getattr(dialog, "update_check_interval_input", None) and hasattr(
        dialog.update_check_interval_input, "value"
    ):
        try:
            update_check_interval_hours = int(dialog.update_check_interval_input.value)
            update_check_interval_hours = max(1, min(168, update_check_interval_hours))
        except (ValueError, TypeError):
            update_check_interval_hours = 24
    else:
        update_check_interval_hours = 24

    sound_enabled = getattr(dialog.sound_enabled_switch, "value", True)

    pack_display = None
    if getattr(dialog, "sound_pack_selection", None) and hasattr(
        dialog.sound_pack_selection, "value"
    ):
        pack_display = dialog.sound_pack_selection.value
    sound_pack = getattr(dialog, "sound_pack_map", {}).get(pack_display, "default")

    visual_crossing_api_key = ""
    if getattr(dialog, "visual_crossing_api_key_input", None):
        visual_crossing_api_key = str(dialog.visual_crossing_api_key_input.value or "").strip()

    startup_enabled = getattr(dialog.startup_enabled_switch, "value", False)

    overrides: dict[str, str] = {}
    for key, widget in getattr(dialog, "alert_sound_override_inputs", {}).items():
        value = getattr(widget, "value", "")
        if value and value.strip():
            overrides[key] = value.strip()

    tts_enabled = bool(getattr(getattr(dialog, "alert_tts_switch", None), "value", False))
    tts_voice = str(getattr(getattr(dialog, "alert_tts_voice_input", None), "value", "")).strip()
    tts_rate_text = str(getattr(getattr(dialog, "alert_tts_rate_input", None), "value", "")).strip()
    try:
        tts_rate = int(tts_rate_text) if tts_rate_text else 0
    except ValueError:
        tts_rate = getattr(dialog.current_settings, "alert_tts_rate", 0)

    alerts_enabled = bool(
        getattr(
            getattr(dialog, "alert_notifications_switch", None),
            "value",
            getattr(dialog.current_settings, "alert_notifications_enabled", True),
        )
    )
    notify_extreme = bool(
        getattr(
            getattr(dialog, "alert_notify_extreme_switch", None),
            "value",
            getattr(dialog.current_settings, "alert_notify_extreme", True),
        )
    )
    notify_severe = bool(
        getattr(
            getattr(dialog, "alert_notify_severe_switch", None),
            "value",
            getattr(dialog.current_settings, "alert_notify_severe", True),
        )
    )
    notify_moderate = bool(
        getattr(
            getattr(dialog, "alert_notify_moderate_switch", None),
            "value",
            getattr(dialog.current_settings, "alert_notify_moderate", True),
        )
    )
    notify_minor = bool(
        getattr(
            getattr(dialog, "alert_notify_minor_switch", None),
            "value",
            getattr(dialog.current_settings, "alert_notify_minor", False),
        )
    )
    notify_unknown = bool(
        getattr(
            getattr(dialog, "alert_notify_unknown_switch", None),
            "value",
            getattr(dialog.current_settings, "alert_notify_unknown", False),
        )
    )

    def _as_int(value, default):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    global_cooldown = _as_int(
        getattr(getattr(dialog, "alert_global_cooldown_input", None), "value", None),
        getattr(dialog.current_settings, "alert_global_cooldown_minutes", 5),
    )
    per_alert_cooldown = _as_int(
        getattr(getattr(dialog, "alert_per_alert_cooldown_input", None), "value", None),
        getattr(dialog.current_settings, "alert_per_alert_cooldown_minutes", 60),
    )
    escalation_cooldown = _as_int(
        getattr(getattr(dialog, "alert_escalation_cooldown_input", None), "value", None),
        getattr(dialog.current_settings, "alert_escalation_cooldown_minutes", 15),
    )
    max_per_hour = _as_int(
        getattr(getattr(dialog, "alert_max_notifications_input", None), "value", None),
        getattr(dialog.current_settings, "alert_max_notifications_per_hour", 10),
    )

    if hasattr(dialog, "_collect_ignored_categories"):
        try:
            ignored_categories = list(dialog._collect_ignored_categories())  # type: ignore[attr-defined]
        except Exception:
            ignored_categories = list(
                getattr(dialog.current_settings, "alert_ignored_categories", [])
            )
    else:
        ignored_categories = list(getattr(dialog.current_settings, "alert_ignored_categories", []))

    aq_threshold = 3
    if getattr(dialog, "air_quality_threshold_input", None) is not None:
        try:
            aq_threshold = int(dialog.air_quality_threshold_input.value)
        except (TypeError, ValueError):
            aq_threshold = getattr(dialog.current_settings, "air_quality_notify_threshold", 3)
    aq_threshold = max(0, min(500, aq_threshold))

    return AppSettings(
        temperature_unit=temperature_unit,
        update_interval_minutes=update_interval,
        show_detailed_forecast=dialog.show_detailed_forecast_switch.value,
        enable_alerts=dialog.enable_alerts_switch.value,
        minimize_to_tray=dialog.minimize_to_tray_switch.value,
        startup_enabled=startup_enabled,
        data_source=data_source,
        visual_crossing_api_key=visual_crossing_api_key,
        auto_update_enabled=auto_update_enabled,
        update_channel=update_channel,
        update_check_interval_hours=update_check_interval_hours,
        debug_mode=dialog.debug_mode_switch.value,
        sound_enabled=sound_enabled,
        sound_pack=sound_pack,
        github_backend_url="",
        alert_notifications_enabled=alerts_enabled,
        alert_notify_extreme=notify_extreme,
        alert_notify_severe=notify_severe,
        alert_notify_moderate=notify_moderate,
        alert_notify_minor=notify_minor,
        alert_notify_unknown=notify_unknown,
        alert_global_cooldown_minutes=global_cooldown,
        alert_per_alert_cooldown_minutes=per_alert_cooldown,
        alert_escalation_cooldown_minutes=escalation_cooldown,
        alert_max_notifications_per_hour=max_per_hour,
        alert_ignored_categories=ignored_categories,
        alert_sound_overrides=overrides,
        alert_tts_enabled=tts_enabled,
        alert_tts_voice=tts_voice,
        alert_tts_rate=tts_rate,
        international_alerts_enabled=getattr(
            dialog.current_settings, "international_alerts_enabled", True
        ),
        international_alerts_provider=getattr(
            dialog.current_settings, "international_alerts_provider", "meteosalarm"
        ),
        trend_insights_enabled=getattr(dialog.current_settings, "trend_insights_enabled", True),
        trend_hours=getattr(dialog.current_settings, "trend_hours", 24),
        air_quality_enabled=getattr(dialog.current_settings, "air_quality_enabled", True),
        pollen_enabled=getattr(dialog.current_settings, "pollen_enabled", True),
        air_quality_notify_threshold=aq_threshold,
        offline_cache_enabled=getattr(dialog.current_settings, "offline_cache_enabled", True),
        offline_cache_max_age_minutes=getattr(
            dialog.current_settings, "offline_cache_max_age_minutes", 180
        ),
    )
