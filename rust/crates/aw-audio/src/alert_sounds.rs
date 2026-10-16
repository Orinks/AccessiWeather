//! Alert-to-sound mapping (`notifications/alert_sound_mapper.py`).
//!
//! Severity first, so providers need not agree on event text. Packs that
//! opt into specific alert sounds try normalized event keys first.

use aw_core::model::WeatherAlert;

pub const KNOWN_ALERT_TYPE_KEYS: &[&str] = &["warning", "watch", "advisory", "statement"];
pub const KNOWN_SEVERITY_KEYS: &[&str] = &["extreme", "severe", "moderate", "minor", "unknown"];
pub const GENERIC_FALLBACKS: &[&str] = &["alert", "notify"];
pub const ALERT_UPDATED_EVENT: &str = "alert_updated";
pub const ALERT_UPDATED_REASONS: &[&str] = &["content_changed", "alert_updated", "updated"];

const HAZARD_KEYWORDS: &[(&str, &[&str])] = &[
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

fn is_word_char(c: char) -> bool {
    c.is_alphanumeric() || c == '_'
}

/// `re.search(rf"\b{token}\b", text, re.IGNORECASE)` for an ASCII token.
fn contains_token(text: Option<&str>, token: &str) -> bool {
    let Some(text) = text else { return false };
    let chars: Vec<char> = text.chars().collect();
    let tok: Vec<char> = token.chars().collect();
    (0..chars.len().saturating_sub(tok.len() - 1)).any(|i| {
        chars[i..i + tok.len()]
            .iter()
            .zip(&tok)
            .all(|(a, b)| a.eq_ignore_ascii_case(b))
            && (i == 0 || !is_word_char(chars[i - 1]))
            && chars.get(i + tok.len()).is_none_or(|c| !is_word_char(*c))
    })
}

fn extract_alert_type(alert: &WeatherAlert) -> Option<&'static str> {
    KNOWN_ALERT_TYPE_KEYS.iter().copied().find(|key| {
        contains_token(alert.event.as_deref(), key)
            || contains_token(alert.headline.as_deref(), key)
            || contains_token(Some(&alert.title), key)
    })
}

fn normalize_severity(severity: &str) -> &'static str {
    let s = severity.trim().to_lowercase();
    if let Some(known) = KNOWN_SEVERITY_KEYS.iter().find(|k| **k == s) {
        return known;
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
        .map(|(key, _)| *key)
}

fn extract_hazard(alert: &WeatherAlert) -> Option<&'static str> {
    let primary = [
        alert.event.as_deref().unwrap_or(""),
        alert.headline.as_deref().unwrap_or(""),
        &alert.title,
    ]
    .join(" ");
    find_hazard_in_text(&primary).or_else(|| find_hazard_in_text(&alert.description))
}

/// `_normalize_event_to_key`: "Excessive Heat Watch" -> "excessive_heat_watch".
fn normalize_event_to_key(text: Option<&str>) -> Option<String> {
    let lowered = text?.trim().to_lowercase();
    let mut key = String::with_capacity(lowered.len());
    for c in lowered.chars() {
        if c.is_ascii_lowercase() || c.is_ascii_digit() {
            key.push(c);
        } else if !key.ends_with('_') {
            key.push('_');
        }
    }
    let key = key.trim_matches('_');
    (!key.is_empty()).then(|| key.to_string())
}

fn add_unique(candidates: &mut Vec<String>, key: Option<&str>) {
    if let Some(key) = key.filter(|k| !k.is_empty()) {
        if !candidates.iter().any(|c| c == key) {
            candidates.push(key.to_string());
        }
    }
}

/// `get_candidate_sound_events`: ordered sound keys for an alert:
/// `alert_updated` for update notifications, specific keys when requested,
/// the severity, then `alert` and `notify`.
pub fn get_candidate_sound_events(
    alert: &WeatherAlert,
    include_specific_events: bool,
    notification_reason: Option<&str>,
) -> Vec<String> {
    let mut candidates = Vec::new();
    if notification_reason.is_some_and(|r| ALERT_UPDATED_REASONS.contains(&r)) {
        add_unique(&mut candidates, Some(ALERT_UPDATED_EVENT));
    }
    let severity = normalize_severity(&alert.severity);
    if include_specific_events {
        add_unique(
            &mut candidates,
            normalize_event_to_key(alert.event.as_deref()).as_deref(),
        );
        let alert_type = extract_alert_type(alert);
        let hazard = extract_hazard(alert);
        if let (Some(h), Some(t)) = (hazard, alert_type) {
            add_unique(&mut candidates, Some(&format!("{h}_{t}")));
        }
        if let Some(h) = hazard {
            add_unique(&mut candidates, Some(&format!("{h}_{severity}")));
        }
        add_unique(&mut candidates, hazard);
        add_unique(&mut candidates, alert_type);
    }
    add_unique(&mut candidates, Some(severity));
    for fallback in GENERIC_FALLBACKS {
        add_unique(&mut candidates, Some(fallback));
    }
    candidates
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn token_match_respects_word_boundaries() {
        assert!(contains_token(Some("Tornado WARNING issued"), "warning"));
        assert!(!contains_token(Some("prewarnings"), "warning"));
        assert!(!contains_token(None, "watch"));
        assert!(contains_token(Some("watch"), "watch"));
    }
}
