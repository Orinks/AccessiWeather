//! The computer's region, language and clock style, so first-run defaults
//! and location search fit users outside the US.
//!
//! Everything here is best-effort: any failure is `None` and callers keep
//! their existing defaults. Each value is read from the OS once per run.

use std::sync::OnceLock;

use aw_core::countries::known_country;

/// Countries where a 12-hour clock is the everyday convention. Used only
/// when the OS does not say directly.
const TWELVE_HOUR_COUNTRIES: &[&str] = &[
    "US", "CA", "AU", "NZ", "IN", "PK", "BD", "PH", "MY", "EG", "SA", "JO", "CO", "SV", "HN", "NI",
    "PR",
];

/// The OS locale as `(language, region)`.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct SystemLocale {
    /// ISO 639-1/2 language code, lowercase.
    pub language: Option<String>,
    /// ISO 3166-1 alpha-2 region, uppercase and known.
    pub region: Option<String>,
}

/// Split a locale name such as `en_GB.UTF-8`, `ms-MY`, `zh-Hant-TW` or
/// macOS's `en_US@rg=gbzzzz` (a region override, which wins).
pub fn parse_locale_name(value: &str) -> SystemLocale {
    let value = value.trim();
    let (base, modifiers) = value.split_once('@').unwrap_or((value, ""));
    let base = base.split('.').next().unwrap_or("");
    let mut parts = base.split(['_', '-']).filter(|p| !p.is_empty());

    let language = parts
        .next()
        .filter(|l| (2..=3).contains(&l.len()) && l.chars().all(|c| c.is_ascii_alphabetic()))
        .map(str::to_ascii_lowercase);
    if language.is_none() {
        return SystemLocale::default();
    }
    let mut region = parts
        .find(|p| p.len() == 2 && p.chars().all(|c| c.is_ascii_alphabetic()))
        .and_then(known_country)
        .map(str::to_string);
    for modifier in modifiers.split(';') {
        if let Some(rg) = modifier.trim().strip_prefix("rg=") {
            if let Some(code) = rg.get(..2).and_then(known_country) {
                region = Some(code.to_string());
            }
        }
    }
    SystemLocale { language, region }
}

/// Whether a region conventionally uses a 12-hour clock.
pub fn region_prefers_12_hour(region: &str) -> bool {
    TWELVE_HOUR_COUNTRIES
        .iter()
        .any(|c| c.eq_ignore_ascii_case(region))
}

#[cfg(windows)]
mod os {
    use super::{parse_locale_name, SystemLocale};
    use aw_core::countries::known_country;

    #[link(name = "kernel32")]
    extern "system" {
        fn GetUserDefaultLocaleName(name: *mut u16, len: i32) -> i32;
        fn GetUserDefaultGeoName(name: *mut u16, len: i32) -> i32;
        fn GetLocaleInfoEx(locale: *const u16, lctype: u32, data: *mut u16, len: i32) -> i32;
    }
    /// `LOCALE_ITIME`: "0" for a 12-hour clock, "1" for 24-hour.
    const LOCALE_ITIME: u32 = 0x0000_0023;

    fn read(f: impl FnOnce(*mut u16, i32) -> i32) -> Option<String> {
        let mut buffer = [0u16; 128];
        let written = f(buffer.as_mut_ptr(), buffer.len() as i32);
        if written <= 1 {
            return None;
        }
        let end = buffer.iter().position(|&c| c == 0).unwrap_or(buffer.len());
        Some(String::from_utf16_lossy(&buffer[..end]))
    }

    pub fn locale() -> SystemLocale {
        // SAFETY: each call writes at most `len` UTF-16 units into the buffer.
        let name = read(|p, n| unsafe { GetUserDefaultLocaleName(p, n) });
        let mut locale = name.as_deref().map(parse_locale_name).unwrap_or_default();
        // "Country or region" in Settings (Windows 10 1709+) beats the format locale.
        let geo = read(|p, n| unsafe { GetUserDefaultGeoName(p, n) });
        if let Some(code) = geo.as_deref().and_then(known_country) {
            locale.region = Some(code.to_string());
        }
        locale
    }

    pub fn prefers_12_hour() -> Option<bool> {
        // SAFETY: a null locale name means the user default; the buffer is
        // sized by `len`.
        let value = read(|p, n| unsafe { GetLocaleInfoEx(std::ptr::null(), LOCALE_ITIME, p, n) })?;
        match value.trim() {
            "0" => Some(true),
            "1" => Some(false),
            _ => None,
        }
    }
}

#[cfg(target_os = "macos")]
mod os {
    use super::{parse_locale_name, SystemLocale};
    use std::process::Command;

    fn defaults(key: &str) -> Option<String> {
        let output = Command::new("/usr/bin/defaults")
            .args(["read", "-g", key])
            .output()
            .ok()?;
        output
            .status
            .success()
            .then(|| String::from_utf8_lossy(&output.stdout).trim().to_string())
    }

    pub fn locale() -> SystemLocale {
        defaults("AppleLocale")
            .map(|v| parse_locale_name(&v))
            .unwrap_or_default()
    }

    pub fn prefers_12_hour() -> Option<bool> {
        if defaults("AppleICUForce24HourTime").as_deref() == Some("1") {
            return Some(false);
        }
        if defaults("AppleICUForce12HourTime").as_deref() == Some("1") {
            return Some(true);
        }
        None
    }
}

#[cfg(not(any(windows, target_os = "macos")))]
mod os {
    use super::{parse_locale_name, SystemLocale};

    pub fn locale() -> SystemLocale {
        ["LC_ALL", "LC_TIME", "LANG"]
            .iter()
            .filter_map(|name| std::env::var(name).ok())
            .find(|v| !v.trim().is_empty())
            .map(|v| parse_locale_name(&v))
            .unwrap_or_default()
    }

    pub fn prefers_12_hour() -> Option<bool> {
        None
    }
}

/// The OS locale, read once.
pub fn system_locale() -> &'static SystemLocale {
    static LOCALE: OnceLock<SystemLocale> = OnceLock::new();
    LOCALE.get_or_init(os::locale)
}

/// The computer's region as an ISO 3166-1 alpha-2 code, if known.
pub fn detect_region() -> Option<&'static str> {
    system_locale().region.as_deref()
}

/// The computer's language as an ISO 639-1 code, if known.
pub fn detect_language() -> Option<&'static str> {
    system_locale().language.as_deref()
}

/// True for a 12-hour clock, false for 24-hour, `None` when unknown: the OS
/// setting first, then the region's convention.
pub fn prefers_12_hour_clock() -> Option<bool> {
    static CLOCK: OnceLock<Option<bool>> = OnceLock::new();
    *CLOCK.get_or_init(|| {
        os::prefers_12_hour().or_else(|| detect_region().map(region_prefers_12_hour))
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn parsed(value: &str) -> (Option<String>, Option<String>) {
        let l = parse_locale_name(value);
        (l.language, l.region)
    }

    #[test]
    fn locale_names() {
        let some = |s: &str| Some(s.to_string());
        assert_eq!(parsed("en_GB.UTF-8"), (some("en"), some("GB")));
        assert_eq!(parsed("ms-MY"), (some("ms"), some("MY")));
        assert_eq!(parsed("zh-Hant-TW"), (some("zh"), some("TW")));
        assert_eq!(parsed("en_US@rg=gbzzzz"), (some("en"), some("GB")));
        assert_eq!(parsed("de"), (some("de"), None));
        assert_eq!(parsed("en-XX"), (some("en"), None));
        assert_eq!(parsed("C.UTF-8"), (None, None));
        assert_eq!(parsed("POSIX"), (None, None));
        assert_eq!(parsed(""), (None, None));
    }

    #[test]
    fn clock_by_region() {
        assert!(region_prefers_12_hour("us"));
        assert!(region_prefers_12_hour("MY"));
        assert!(!region_prefers_12_hour("DE"));
        assert!(!region_prefers_12_hour("GB"));
    }
}
