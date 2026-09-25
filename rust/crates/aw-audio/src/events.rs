//! Shared user-facing sound event metadata (`sound_events.py`).

/// Events muted out of the box (`DEFAULT_MUTED_SOUND_EVENTS`).
pub const DEFAULT_MUTED_SOUND_EVENTS: &[&str] = &["data_updated"];

/// `(title, description, [(event_key, label)])` in display order.
pub type SoundEventSection = (
    &'static str,
    &'static str,
    &'static [(&'static str, &'static str)],
);

pub const SOUND_EVENT_SECTIONS: &[SoundEventSection] = &[
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

/// Specific alert keys older packs map (`LEGACY_SOUND_EVENT_KEYS`).
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

/// `USER_MUTABLE_SOUND_EVENTS`: every `(event_key, label)` in section order.
pub fn user_mutable_sound_events() -> impl Iterator<Item = (&'static str, &'static str)> {
    SOUND_EVENT_SECTIONS
        .iter()
        .flat_map(|(_, _, events)| events.iter().copied())
}

/// `FRIENDLY_SOUND_EVENT_CHOICES` / `FRIENDLY_ALERT_CATEGORIES`: `(label, event_key)`.
pub fn friendly_sound_event_choices() -> Vec<(&'static str, &'static str)> {
    user_mutable_sound_events()
        .map(|(key, label)| (label, key))
        .collect()
}

pub fn is_user_mutable_event(key: &str) -> bool {
    user_mutable_sound_events().any(|(k, _)| k == key)
}

/// Membership in `KNOWN_SOUND_EVENT_KEYS`.
pub fn is_known_event(key: &str) -> bool {
    is_user_mutable_event(key) || LEGACY_SOUND_EVENT_KEYS.contains(&key)
}

/// Friendly label for an event key, or the key title-cased
/// (`key.replace("_", " ").title()`) when it is not in the catalog.
pub fn friendly_event_name(key: &str) -> String {
    user_mutable_sound_events()
        .find(|(k, _)| *k == key)
        .map(|(_, label)| label.to_string())
        .unwrap_or_else(|| crate::py::py_title(&key.replace('_', " ")))
}

/// `normalize_muted_sound_events`: trim, drop blanks and duplicates, keep order.
pub fn normalize_muted_sound_events<S: AsRef<str>>(events: &[S]) -> Vec<String> {
    let mut out: Vec<String> = Vec::new();
    for item in events {
        let event = item.as_ref().trim();
        if !event.is_empty() && !out.iter().any(|e| e == event) {
            out.push(event.to_string());
        }
    }
    out
}

/// `normalize_known_muted_sound_events`: as above, dropping unknown keys.
pub fn normalize_known_muted_sound_events<S: AsRef<str>>(events: &[S]) -> Vec<String> {
    normalize_muted_sound_events(events)
        .into_iter()
        .filter(|e| is_known_event(e))
        .collect()
}

/// `is_sound_event_muted`.
pub fn is_sound_event_muted<S: AsRef<str>>(event: &str, muted_events: &[S]) -> bool {
    !event.is_empty()
        && muted_events
            .iter()
            .any(|e| !e.as_ref().trim().is_empty() && e.as_ref().trim() == event)
}
