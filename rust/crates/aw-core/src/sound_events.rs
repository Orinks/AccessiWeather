//! Shared user-facing sound event metadata (`sound_events.py`).

/// `DEFAULT_MUTED_SOUND_EVENTS`.
pub const DEFAULT_MUTED_SOUND_EVENTS: [&str; 1] = ["data_updated"];

/// (title, description, [(event key, label)]).
pub type SoundEventSection = (
    &'static str,
    &'static str,
    &'static [(&'static str, &'static str)],
);

/// `SOUND_EVENT_SECTIONS`.
pub const SOUND_EVENT_SECTIONS: [SoundEventSection; 3] = [
    (
        "Core notifications",
        "General app sounds.",
        &[
            ("alert", "General alert"),
            ("notify", "General notification"),
            ("error", "General error"),
            ("success", "General success"),
            ("data_updated", "Weather refresh completed"),
            ("fetch_error", "Weather refresh failed"),
            ("discussion_update", "Forecast discussion updated"),
            ("severe_risk", "Severe weather risk changed"),
            ("alert_updated", "Weather alert updated"),
        ],
    ),
    (
        "App lifecycle",
        "Startup and exit sounds.",
        &[("startup", "App startup"), ("exit", "App exit")],
    ),
    (
        "Alert severities",
        "Weather alert sounds by severity.",
        &[
            ("extreme", "Extreme severity"),
            ("severe", "Severe severity"),
            ("moderate", "Moderate severity"),
            ("minor", "Minor severity"),
            ("unknown", "Unknown/uncategorized severity"),
        ],
    ),
];

/// `LEGACY_SOUND_EVENT_KEYS`: specific-alert keys older packs map.
pub const LEGACY_SOUND_EVENT_KEYS: &[&str] = &[
    "warning",
    "watch",
    "advisory",
    "statement",
    "tornado_warning",
    "tornado_watch",
    "thunderstorm_warning",
    "thunderstorm_watch",
    "flood_warning",
    "flood_watch",
    "flood_advisory",
    "flash_flood_warning",
    "flash_flood_watch",
    "coastal_flood_warning",
    "coastal_flood_watch",
    "coastal_flood_advisory",
    "river_flood_warning",
    "river_flood_watch",
    "excessive_heat_warning",
    "excessive_heat_watch",
    "heat_advisory",
    "winter_storm_warning",
    "winter_storm_watch",
    "winter_weather_advisory",
    "blizzard_warning",
    "ice_storm_warning",
    "ice_warning",
    "snow_warning",
    "snow_squall_warning",
    "freeze_warning",
    "freeze_watch",
    "frost_advisory",
    "extreme_cold_warning",
    "cold_weather_advisory",
    "high_wind_warning",
    "high_wind_watch",
    "wind_advisory",
    "wind_warning",
    "extreme_wind_warning",
    "hurricane_warning",
    "hurricane_watch",
    "tropical_storm_warning",
    "tropical_storm_watch",
    "storm_surge_warning",
    "storm_surge_watch",
    "red_flag_warning",
    "fire_weather_watch",
    "fire_warning",
    "small_craft_advisory",
    "gale_warning",
    "storm_warning",
    "hurricane_force_wind_warning",
    "special_marine_warning",
    "dense_fog_advisory",
    "fog_advisory",
    "air_quality_alert",
    "dust_storm_warning",
    "dust_advisory",
    "dust_warning",
    "tornado",
    "flood",
    "heat",
    "wind",
    "winter",
    "snow",
    "ice",
    "thunderstorm",
    "hurricane",
    "fire",
    "fog",
    "dust",
    "air_quality",
];

/// `USER_MUTABLE_SOUND_EVENTS`: every section's events, in display order.
pub fn user_mutable_sound_events() -> impl Iterator<Item = (&'static str, &'static str)> {
    SOUND_EVENT_SECTIONS
        .iter()
        .flat_map(|(_, _, events)| events.iter().copied())
}

pub fn is_user_mutable_sound_event(key: &str) -> bool {
    user_mutable_sound_events().any(|(k, _)| k == key)
}

/// `KNOWN_SOUND_EVENT_KEYS` membership.
pub fn is_known_sound_event(key: &str) -> bool {
    is_user_mutable_sound_event(key) || LEGACY_SOUND_EVENT_KEYS.contains(&key)
}

/// `normalize_known_muted_sound_events`: trimmed, de-duplicated in order,
/// unknown keys dropped.
pub fn normalize_known_muted_sound_events(events: &[String]) -> Vec<String> {
    let mut out: Vec<String> = Vec::new();
    for event in events {
        let event = event.trim();
        if !event.is_empty() && is_known_sound_event(event) && !out.iter().any(|e| e == event) {
            out.push(event.to_string());
        }
    }
    out
}
