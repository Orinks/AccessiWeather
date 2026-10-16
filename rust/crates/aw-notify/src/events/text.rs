//! Text helpers for event notifications, ported from
//! `notifications/notification_event_text.py` and
//! `notifications/notification_sps_helpers.py`.

use std::sync::LazyLock;

use aw_core::model::{TextProduct, Timestamp, WeatherAlert};
use regex::Regex;
use sha2::{Digest, Sha256};

use crate::py::{self, collapse_whitespace, splitlines, truncate_chars};

const HWO_SUMMARY_MIN_CHARS: usize = 20;
const SPS_MAX_BODY_CHARS: usize = 160;

static ISSUED_PATTERNS: LazyLock<Vec<Regex>> = LazyLock::new(|| {
    [
        r"(?i)\bISSUED\s+(\d{1,2})(\d{2})\s+([AP]M)\s+([A-Z]{2,4})\b",
        r"(?i)\bISSUED\s+(\d{1,2}):(\d{2})\s+([AP]M)\s+([A-Z]{2,4})\b",
        r"(?i)(?:^|\n)\s*(\d{1,2})(\d{2})\s+([AP]M)\s+([A-Z]{2,4})\s+(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\b",
        r"(?i)(?:^|\n)\s*(\d{1,2}):(\d{2})\s+([AP]M)\s+([A-Z]{2,4})\s+(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\b",
    ]
    .iter()
    .map(|p| Regex::new(p).expect("static regex"))
    .collect()
});

/// `extract_discussion_issued_time_label`: "935 AM EST Tue ..." -> "9:35 AM EST".
pub fn extract_discussion_issued_time_label(text: Option<&str>) -> Option<String> {
    let text = text.filter(|t| !t.is_empty())?;
    ISSUED_PATTERNS.iter().find_map(|re| {
        let c = re.captures(text)?;
        let hour: u32 = c[1].parse().ok()?;
        Some(format!(
            "{hour}:{} {} {}",
            &c[2],
            c[3].to_uppercase(),
            c[4].to_uppercase()
        ))
    })
}

/// `format_issuance_time_label`: "5:35 PM UTC" in the timestamp's own offset.
pub fn format_issuance_time_label(t: &Timestamp) -> String {
    format!("{} {}", py::clock_12h(t), py::fixed_tzname(t.offset()))
        .trim()
        .to_string()
}

/// `get_risk_category`.
pub fn get_risk_category(risk: i64) -> &'static str {
    match risk {
        r if r >= 80 => "extreme",
        r if r >= 60 => "high",
        r if r >= 40 => "moderate",
        r if r >= 20 => "low",
        _ => "minimal",
    }
}

fn category_level(category: &str) -> u8 {
    match category {
        "minimal" => 0,
        "low" => 1,
        "moderate" => 2,
        "high" => 3,
        _ => 4,
    }
}

/// Whether `current` is a higher risk band than `previous`.
pub fn risk_increased(previous: &str, current: &str) -> bool {
    category_level(current) > category_level(previous)
}

/// `extract_section`: the joined, stripped lines after `start_marker` up to
/// the first line starting with an end marker.
pub fn extract_section(text: &str, start_marker: &str, end_markers: &[&str]) -> Option<String> {
    let mut in_section = false;
    let mut body: Vec<&str> = Vec::new();
    let start_upper = start_marker.to_uppercase();
    for line in splitlines(text) {
        let stripped = line.trim();
        if !in_section {
            if stripped.to_uppercase().starts_with(&start_upper) {
                in_section = true;
            }
            continue;
        }
        let upper = stripped.to_uppercase();
        if end_markers
            .iter()
            .any(|m| stripped.starts_with(m) || upper.starts_with(&m.to_uppercase()))
        {
            break;
        }
        body.push(stripped);
    }
    if !in_section {
        return None;
    }
    let content = body
        .into_iter()
        .filter(|p| !p.is_empty())
        .collect::<Vec<_>>()
        .join(" ");
    (!content.is_empty()).then_some(content)
}

const SECTION_END: &[&str] = &[".", "&&"];

pub fn what_has_changed_section(text: &str) -> Option<String> {
    extract_section(text, ".WHAT HAS CHANGED", SECTION_END)
}

/// `normalize_discussion_summary`.
pub fn normalize_discussion_summary(text: Option<&str>) -> String {
    match text {
        Some(t) if !t.is_empty() => collapse_whitespace(t)
            .to_lowercase()
            .trim_matches([' ', '.'])
            .to_string(),
        _ => String::new(),
    }
}

/// `is_no_change_summary`.
pub fn is_no_change_summary(text: Option<&str>) -> bool {
    let n = normalize_discussion_summary(text);
    matches!(
        n.as_str(),
        "no change"
            | "no changes"
            | "no significant change"
            | "no significant changes"
            | "no significant changes made to forecast"
            | "no significant changes made to the forecast"
    )
}

/// `summarize_discussion_change`.
pub fn summarize_discussion_change(
    previous: Option<&str>,
    current: Option<&str>,
) -> Option<String> {
    let current = current.filter(|c| !c.is_empty())?;
    let what_changed = what_has_changed_section(current);
    let declares_no_changes = is_no_change_summary(what_changed.as_deref());
    if let Some(section) = what_changed.as_deref() {
        if !declares_no_changes {
            return Some(truncate_chars(section, 300).to_string());
        }
    }

    if let Some(section) = extract_section(current, ".KEY MESSAGES", SECTION_END) {
        let previous_section =
            extract_section(previous.unwrap_or(""), ".KEY MESSAGES", SECTION_END);
        let changed = previous_section.as_deref().is_none_or(|prev| {
            normalize_discussion_summary(Some(&section)) != normalize_discussion_summary(Some(prev))
        });
        if changed {
            return Some(truncate_chars(&section, 300).to_string());
        }
        if declares_no_changes {
            return None;
        }
    }
    if declares_no_changes {
        return None;
    }

    let previous_lines: Vec<&str> = splitlines(previous.unwrap_or(""))
        .into_iter()
        .map(str::trim)
        .filter(|l| !l.is_empty() && !l.starts_with('$'))
        .collect();
    splitlines(current)
        .into_iter()
        .map(str::trim)
        .find(|l| !l.is_empty() && !l.starts_with('$') && !previous_lines.contains(l))
        .map(|l| truncate_chars(l, 300).to_string())
}

/// `hash_product_text`: sha256 of the stripped text.
pub fn hash_product_text(text: &str) -> String {
    let digest = Sha256::digest(text.trim().as_bytes());
    digest.iter().map(|b| format!("{b:02x}")).collect()
}

/// `format_hwo_body`.
pub fn format_hwo_body(stored_text: Option<&str>, product: &TextProduct) -> String {
    match summarize_discussion_change(stored_text, Some(&product.product_text)) {
        Some(s) if s.trim().chars().count() > HWO_SUMMARY_MIN_CHARS => s.trim().to_string(),
        _ => format!(
            "Hazardous Weather Outlook updated for {} - tap to view.",
            product.cwa_office
        ),
    }
}

/// `normalize_for_match`.
pub fn normalize_for_match(text: Option<&str>) -> String {
    text.map(|t| collapse_whitespace(t).to_lowercase())
        .unwrap_or_default()
}

/// `first_nonempty_line`.
pub fn first_nonempty_line(text: Option<&str>) -> Option<&str> {
    splitlines(text?)
        .into_iter()
        .map(str::trim)
        .find(|l| !l.is_empty())
}

/// `truncate`: cut to `limit` characters, ending in "..." when cut.
pub fn truncate(text: &str, limit: usize) -> String {
    if text.chars().count() <= limit {
        return text.to_string();
    }
    if limit <= 3 {
        return truncate_chars(text, limit).to_string();
    }
    format!("{}...", truncate_chars(text, limit - 3))
}

/// `sps_alert_signatures`.
pub fn sps_alert_signatures(alerts: &[WeatherAlert]) -> Vec<String> {
    let mut out = Vec::new();
    for alert in alerts {
        let event = alert.event.as_deref().unwrap_or("").trim().to_lowercase();
        if event != "special weather statement" {
            continue;
        }
        for candidate in [
            alert.headline.as_deref(),
            first_nonempty_line(Some(&alert.description)),
        ] {
            let sig = normalize_for_match(candidate);
            if !sig.is_empty() {
                out.push(sig);
            }
        }
    }
    out
}

/// `sps_is_case_a`: the product is the event-style SPS an active alert covers.
pub fn sps_is_case_a(product: &TextProduct, alert_signatures: &[String]) -> bool {
    if alert_signatures.is_empty() {
        return false;
    }
    let haystack = format!(
        "{} {}",
        product.headline.as_deref().unwrap_or(""),
        product.product_text
    );
    let norm = normalize_for_match(Some(&haystack));
    if norm.is_empty() {
        return false;
    }
    alert_signatures
        .iter()
        .any(|sig| norm.contains(sig.as_str()) || sig.contains(norm.as_str()))
}

/// `format_sps_body`: headline plus office, else the first line.
pub fn format_sps_body(product: &TextProduct) -> String {
    let headline = product.headline.as_deref().unwrap_or("").trim();
    if !headline.is_empty() {
        return truncate(
            &format!("{headline} - {}", product.cwa_office),
            SPS_MAX_BODY_CHARS,
        );
    }
    let fallback = first_nonempty_line(Some(&product.product_text)).unwrap_or("");
    truncate(fallback.trim(), SPS_MAX_BODY_CHARS)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn issued_label_from_afd_header() {
        let text = "\n000\nFXUS61 KOKX 201435\nAFDOKX\n\nArea Forecast Discussion\n\
                    National Weather Service New York NY\n935 AM EST Tue Jan 20 2026\n";
        assert_eq!(
            extract_discussion_issued_time_label(Some(text)).as_deref(),
            Some("9:35 AM EST")
        );
        assert_eq!(
            extract_discussion_issued_time_label(Some("no header")),
            None
        );
    }

    #[test]
    fn summaries() {
        assert_eq!(summarize_discussion_change(Some("a"), Some("")), None);
        assert_eq!(
            summarize_discussion_change(Some("line1\nline2"), Some("line1\n$$\nline3")).as_deref(),
            Some("line3")
        );
        let current = ".WHAT HAS CHANGED...\nRain arrives earlier.\n\n&&\n";
        assert_eq!(
            summarize_discussion_change(None, Some(current)).as_deref(),
            Some("Rain arrives earlier.")
        );
        let no_change = ".WHAT HAS CHANGED...\nNo changes.\n&&\n.KEY MESSAGES...\nSame.\n&&";
        let prev = ".KEY MESSAGES...\nSame.\n&&";
        assert_eq!(
            summarize_discussion_change(Some(prev), Some(no_change)),
            None
        );
        assert!(is_no_change_summary(Some(" No significant changes. ")));
    }

    #[test]
    fn truncation_and_risk() {
        assert_eq!(truncate("abcdef", 5), "ab...");
        assert_eq!(truncate("abc", 5), "abc");
        assert_eq!(get_risk_category(19), "minimal");
        assert_eq!(get_risk_category(80), "extreme");
        assert!(risk_increased("low", "high"));
    }
}
