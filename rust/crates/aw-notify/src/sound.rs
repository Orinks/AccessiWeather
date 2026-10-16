//! Sound event catalogue and alert-to-sound mapping, ported from
//! `sound_events.py`, `notifications/alert_sound_mapper.py` and the mute /
//! pack-inspection parts of `notifications/sound_player.py` and
//! `sound_pack_helpers.py`. Resolving a key to a file and playing it is the
//! audio layer's job; this module only decides which keys to try.

use std::path::Path;
use std::sync::LazyLock;

use aw_core::model::WeatherAlert;
use aw_core::settings::AppSettings;
use regex::Regex;
use serde_json::Value;

pub const DEFAULT_MUTED_SOUND_EVENTS: &[&str] = &["data_updated"];

/// (section title, description, [(event key, label)]).
pub type SoundEventSection = (
    &'static str,
    &'static str,
    &'static [(&'static str, &'static str)],
);

/// `SOUND_EVENT_SECTIONS`.
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

/// `LEGACY_SOUND_EVENT_KEYS`: specific alert keys older packs ship.
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

/// `USER_MUTABLE_SOUND_EVENTS` in display order.
pub fn user_mutable_sound_events() -> impl Iterator<Item = (&'static str, &'static str)> {
    SOUND_EVENT_SECTIONS
        .iter()
        .flat_map(|(_, _, events)| events.iter().copied())
}

/// `FRIENDLY_SOUND_EVENT_CHOICES`: (label, event key).
pub fn friendly_sound_event_choices() -> Vec<(&'static str, &'static str)> {
    user_mutable_sound_events().map(|(k, l)| (l, k)).collect()
}

pub fn is_known_sound_event(key: &str) -> bool {
    user_mutable_sound_events().any(|(k, _)| k == key) || LEGACY_SOUND_EVENT_KEYS.contains(&key)
}

/// `normalize_muted_sound_events`: trimmed, de-duplicated, order kept.
pub fn normalize_muted_sound_events<S: AsRef<str>>(events: &[S]) -> Vec<String> {
    let mut out: Vec<String> = Vec::new();
    for e in events {
        let e = e.as_ref().trim();
        if !e.is_empty() && !out.iter().any(|o| o == e) {
            out.push(e.to_string());
        }
    }
    out
}

/// `normalize_known_muted_sound_events`: also drops unknown keys.
pub fn normalize_known_muted_sound_events<S: AsRef<str>>(events: &[S]) -> Vec<String> {
    normalize_muted_sound_events(events)
        .into_iter()
        .filter(|e| is_known_sound_event(e))
        .collect()
}

pub fn is_sound_event_muted<S: AsRef<str>>(event: &str, muted: &[S]) -> bool {
    !event.is_empty()
        && normalize_muted_sound_events(muted)
            .iter()
            .any(|m| m == event)
}

/// The keys the audio layer should try, in order, for one notification
/// (`_play_sound` + `play_notification_sound[_candidates]`), or `None` when
/// the sound is muted. With candidates, the logical event (the explicit
/// `sound_event`, else the first candidate) silences the whole cue when
/// muted; otherwise muted candidates are just skipped. Without candidates the
/// single `sound_event` (default `"alert"`) is used.
pub fn sound_keys_to_try<S: AsRef<str>>(
    sound_event: Option<&str>,
    candidates: Option<&[String]>,
    muted: &[S],
) -> Option<Vec<String>> {
    match candidates.filter(|c| !c.is_empty()) {
        Some(candidates) => {
            let logical = sound_event.unwrap_or(&candidates[0]);
            if is_sound_event_muted(logical, muted) {
                return None;
            }
            let keys: Vec<String> = candidates
                .iter()
                .filter(|c| !is_sound_event_muted(c, muted))
                .cloned()
                .collect();
            (!keys.is_empty()).then_some(keys)
        }
        None => {
            let event = sound_event.unwrap_or("alert");
            (!is_sound_event_muted(event, muted)).then(|| vec![event.to_string()])
        }
    }
}

// ---------------------------------------------------------------------------
// alert_sound_mapper
// ---------------------------------------------------------------------------

pub const KNOWN_ALERT_TYPE_KEYS: &[&str] = &["warning", "watch", "advisory", "statement"];
pub const KNOWN_SEVERITY_KEYS: &[&str] = &["extreme", "severe", "moderate", "minor", "unknown"];
pub const GENERIC_FALLBACKS: &[&str] = &["alert", "notify"];
pub const ALERT_UPDATED_EVENT: &str = "alert_updated";
pub const ALERT_UPDATED_REASONS: &[&str] = &["content_changed", "alert_updated", "updated"];

/// `HAZARD_KEYWORDS`, in Python's dict order (first match wins).
pub const HAZARD_KEYWORDS: &[(&str, &[&str])] = &[
    ("flood", &["flood"]),
    ("tornado", &["tornado"]),
    ("heat", &["heat", "excessive heat"]),
    ("wind", &["wind", "high wind"]),
    ("winter", &["winter", "winter storm"]),
    ("snow", &["snow", "heavy snow"]),
    ("ice", &["ice", "freezing rain", "freezing drizzle"]),
    ("thunderstorm", &["thunderstorm", "severe thunderstorm"]),
    ("hurricane", &["hurricane"]),
    ("fire", &["fire", "red flag"]),
    ("fog", &["fog", "dense fog"]),
    ("dust", &["dust", "blowing dust"]),
    ("air_quality", &["air quality", "smoke"]),
];

static ALERT_TYPE_PATTERNS: LazyLock<Vec<(&'static str, Regex)>> = LazyLock::new(|| {
    KNOWN_ALERT_TYPE_KEYS
        .iter()
        .map(|k| {
            (
                *k,
                Regex::new(&format!(r"(?i)\b{k}\b")).expect("static regex"),
            )
        })
        .collect()
});

fn extract_alert_type(alert: &WeatherAlert) -> Option<&'static str> {
    let texts = [
        alert.event.as_deref(),
        alert.headline.as_deref(),
        Some(alert.title.as_str()),
    ];
    ALERT_TYPE_PATTERNS.iter().find_map(|(key, re)| {
        texts
            .iter()
            .flatten()
            .any(|t| re.is_match(t))
            .then_some(*key)
    })
}

fn normalize_severity(sev: &str) -> &'static str {
    let s = sev.trim().to_lowercase();
    if let Some(k) = KNOWN_SEVERITY_KEYS.iter().find(|k| **k == s) {
        return k;
    }
    match s.as_str() {
        "high" => "severe",
        "medium" => "moderate",
        "low" => "minor",
        "critical" => "extreme",
        _ => "unknown",
    }
}

fn find_hazard_in_text(text: &str) -> Option<&'static str> {
    let text = text.to_lowercase();
    HAZARD_KEYWORDS
        .iter()
        .find(|(_, phrases)| phrases.iter().any(|p| text.contains(p)))
        .map(|(k, _)| *k)
}

fn extract_hazard(alert: &WeatherAlert) -> Option<&'static str> {
    let primary = [
        alert.event.as_deref().unwrap_or(""),
        alert.headline.as_deref().unwrap_or(""),
        alert.title.as_str(),
    ]
    .join(" ");
    find_hazard_in_text(&primary).or_else(|| find_hazard_in_text(&alert.description))
}

/// `_normalize_event_to_key`: "Excessive Heat Watch" -> "excessive_heat_watch".
pub fn normalize_event_to_key(text: &str) -> Option<String> {
    let mut out = String::new();
    for c in text.trim().to_lowercase().chars() {
        if c.is_ascii_lowercase() || c.is_ascii_digit() {
            out.push(c);
        } else if !out.ends_with('_') {
            out.push('_');
        }
    }
    let out = out.trim_matches('_');
    (!out.is_empty()).then(|| out.to_string())
}

fn add_unique(candidates: &mut Vec<String>, key: Option<&str>) {
    if let Some(key) = key.filter(|k| !k.is_empty()) {
        if !candidates.iter().any(|c| c == key) {
            candidates.push(key.to_string());
        }
    }
}

/// `get_candidate_sound_events`: update cue, optional specific keys,
/// severity, then `alert` / `notify`.
pub fn get_candidate_sound_events(
    alert: &WeatherAlert,
    include_specific_events: bool,
    notification_reason: Option<&str>,
) -> Vec<String> {
    let mut candidates = Vec::new();
    if notification_reason.is_some_and(|r| ALERT_UPDATED_REASONS.contains(&r)) {
        add_unique(&mut candidates, Some(ALERT_UPDATED_EVENT));
    }
    let sev = normalize_severity(&alert.severity);
    if include_specific_events {
        let event_key = alert.event.as_deref().and_then(normalize_event_to_key);
        add_unique(&mut candidates, event_key.as_deref());
        let atype = extract_alert_type(alert);
        let hazard = extract_hazard(alert);
        if let (Some(h), Some(t)) = (hazard, atype) {
            add_unique(&mut candidates, Some(&format!("{h}_{t}")));
        }
        if let Some(h) = hazard {
            add_unique(&mut candidates, Some(&format!("{h}_{sev}")));
        }
        add_unique(&mut candidates, hazard);
        add_unique(&mut candidates, atype);
    }
    add_unique(&mut candidates, Some(sev));
    for fb in GENERIC_FALLBACKS {
        add_unique(&mut candidates, Some(fb));
    }
    candidates
}

/// `choose_sound_event`: the first candidate.
pub fn choose_sound_event(alert: &WeatherAlert, include_specific_events: bool) -> String {
    get_candidate_sound_events(alert, include_specific_events, None).remove(0)
}

/// `sound_pack_prefers_specific_alert_sounds`: an explicit
/// `"specific_alert_sounds"` flag in `pack.json`, else whether the pack maps
/// any legacy specific alert key.
pub fn sound_pack_prefers_specific_alert_sounds(soundpacks_dir: &Path, pack: &str) -> bool {
    let path = soundpacks_dir.join(pack).join("pack.json");
    let Ok(text) = std::fs::read_to_string(&path) else {
        return false;
    };
    let data: Value = match serde_json::from_str(&text) {
        Ok(v) => v,
        Err(e) => {
            tracing::error!("Failed to inspect sound pack {pack}: {e}");
            return false;
        }
    };
    if let Some(explicit) = data.get("specific_alert_sounds").and_then(Value::as_bool) {
        return explicit;
    }
    data.get("sounds")
        .and_then(Value::as_object)
        .is_some_and(|sounds| {
            sounds
                .keys()
                .any(|k| LEGACY_SOUND_EVENT_KEYS.contains(&k.as_str()))
        })
}

/// `AlertNotificationSystem._should_use_specific_alert_sounds`.
pub fn should_use_specific_alert_sounds(
    settings: &AppSettings,
    soundpacks_dir: Option<&Path>,
) -> bool {
    let pack = settings.sound_pack.as_str();
    if settings
        .specific_alert_sound_packs
        .iter()
        .any(|p| p == pack)
    {
        return true;
    }
    soundpacks_dir.is_some_and(|dir| sound_pack_prefers_specific_alert_sounds(dir, pack))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn alert(severity: &str, event: &str) -> WeatherAlert {
        let mut a = WeatherAlert::new(event, "Test alert text.");
        a.severity = severity.into();
        a.event = Some(event.into());
        a
    }

    fn strs(v: &[&str]) -> Vec<String> {
        v.iter().map(|s| s.to_string()).collect()
    }

    #[test]
    fn severity_first_with_aliases() {
        for (sev, key) in [
            ("Extreme", "extreme"),
            ("SEVERE", "severe"),
            ("critical", "extreme"),
            ("high", "severe"),
            ("medium", "moderate"),
            ("low", "minor"),
            ("Unknown", "unknown"),
            ("", "unknown"),
        ] {
            assert_eq!(
                get_candidate_sound_events(&alert(sev, "Tornado Warning"), false, None),
                strs(&[key, "alert", "notify"])
            );
        }
    }

    #[test]
    fn specific_candidates_follow_python_order() {
        assert_eq!(
            get_candidate_sound_events(&alert("Extreme", "Tornado Warning"), true, None),
            strs(&[
                "tornado_warning",
                "tornado_extreme",
                "tornado",
                "warning",
                "extreme",
                "alert",
                "notify"
            ])
        );
        let c = get_candidate_sound_events(&alert("Unknown", "Air Quality Alert"), true, None);
        assert_eq!(
            c[..3],
            strs(&["air_quality_alert", "air_quality_unknown", "air_quality"])
        );
        let c = get_candidate_sound_events(
            &alert("Severe", "Severe Thunderstorm Warning"),
            true,
            Some("content_changed"),
        );
        assert_eq!(
            c[..4],
            strs(&[
                "alert_updated",
                "severe_thunderstorm_warning",
                "thunderstorm_warning",
                "thunderstorm_severe"
            ])
        );
    }

    #[test]
    fn muted_cues() {
        let muted = ["data_updated", " alert_updated "];
        let c = strs(&["alert_updated", "moderate", "alert"]);
        assert_eq!(sound_keys_to_try(None, Some(&c), &muted), None);
        let c = strs(&["moderate", "alert_updated", "alert"]);
        assert_eq!(
            sound_keys_to_try(None, Some(&c), &muted),
            Some(strs(&["moderate", "alert"]))
        );
        assert_eq!(sound_keys_to_try(Some("data_updated"), None, &muted), None);
        assert_eq!(
            sound_keys_to_try(None, Some(&[]), &muted),
            Some(strs(&["alert"]))
        );
        assert_eq!(
            normalize_known_muted_sound_events(&["alert", "alert", "bogus", " notify "]),
            strs(&["alert", "notify"])
        );
    }

    #[test]
    fn pack_json_opt_in() {
        let dir = tempfile::tempdir().unwrap();
        let write = |name: &str, body: &str| {
            std::fs::create_dir_all(dir.path().join(name)).unwrap();
            std::fs::write(dir.path().join(name).join("pack.json"), body).unwrap();
        };
        write(
            "explicit",
            r#"{"specific_alert_sounds": false, "sounds": {"tornado_warning": "t.wav"}}"#,
        );
        write("legacy", r#"{"sounds": {"watch": "w.wav"}}"#);
        write("plain", r#"{"sounds": {"alert": "a.wav"}}"#);
        assert!(!sound_pack_prefers_specific_alert_sounds(
            dir.path(),
            "explicit"
        ));
        assert!(sound_pack_prefers_specific_alert_sounds(
            dir.path(),
            "legacy"
        ));
        assert!(!sound_pack_prefers_specific_alert_sounds(
            dir.path(),
            "plain"
        ));
        assert!(!sound_pack_prefers_specific_alert_sounds(
            dir.path(),
            "missing"
        ));
    }
}
