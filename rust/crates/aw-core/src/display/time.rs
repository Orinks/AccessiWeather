//! Date and time formatting.
//!
//! Ports `display/presentation/time_formatters.py` and `forecast_time.py`,
//! plus the injectable clock the Python code reads implicitly
//! (`datetime.now()`, the system timezone).
//!
//! Python datetimes carry their tzinfo, which decides the `%Z` label the
//! timezone suffix shows. The data model stores fixed offsets only, so a
//! timestamp whose offset matches the location's IANA zone at that instant
//! is labelled with that zone's abbreviation ("EDT"), the way the Python
//! parsers' `ZoneInfo` datetimes are; anything else gets Python's
//! fixed-offset name ("UTC-04:00").

use chrono::{DateTime, FixedOffset, NaiveDateTime, Offset, TimeZone, Utc};
use chrono_tz::Tz;

/// The moment "now" and the user's system timezone. Tests pass a fixed
/// clock; the app uses [`Clock::system`].
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Clock {
    pub now: DateTime<Utc>,
    pub local_tz: Tz,
}

impl Clock {
    pub fn fixed(now: DateTime<Utc>, local_tz: Tz) -> Self {
        Self { now, local_tz }
    }

    /// The real clock and the system timezone (UTC if it can't be resolved).
    pub fn system() -> Self {
        let local_tz = iana_time_zone::get_timezone()
            .ok()
            .and_then(|name| name.parse().ok())
            .unwrap_or(Tz::UTC);
        Self {
            now: Utc::now(),
            local_tz,
        }
    }
}

/// Where a timestamp's `%Z` label comes from.
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum TzLabel {
    /// A naive datetime: no label.
    Naive,
    /// `datetime.timezone` with a fixed offset.
    Fixed,
    /// A `ZoneInfo` zone.
    Zone(Tz),
    /// `datetime.now().astimezone().tzinfo`: the system zone's offset and
    /// name at `at`, applied as a fixed offset.
    Local { tz: Tz, at: DateTime<Utc> },
}

/// A timestamp as the Python presenter sees it.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct PyDateTime {
    /// Wall clock plus offset (offset is 0 and meaningless when naive).
    pub dt: DateTime<FixedOffset>,
    pub label: TzLabel,
}

/// The IANA zone for a location's `timezone` field, if it resolves.
pub fn location_zone(timezone: Option<&str>) -> Option<Tz> {
    timezone.filter(|s| !s.is_empty())?.parse().ok()
}

impl PyDateTime {
    /// An aware model timestamp, labelled by `zone` when the offsets agree.
    pub fn aware(dt: DateTime<FixedOffset>, zone: Option<Tz>) -> Self {
        let label = match zone {
            Some(tz) if tz.offset_from_utc_datetime(&dt.naive_utc()).fix() == *dt.offset() => {
                TzLabel::Zone(tz)
            }
            _ => TzLabel::Fixed,
        };
        Self { dt, label }
    }

    pub fn naive(wall: NaiveDateTime) -> Self {
        Self {
            dt: Utc.fix().from_utc_datetime(&wall),
            label: TzLabel::Naive,
        }
    }

    pub fn is_aware(&self) -> bool {
        self.label != TzLabel::Naive
    }

    pub fn wall(&self) -> NaiveDateTime {
        self.dt.naive_local()
    }

    pub fn strftime(&self, fmt: &str) -> String {
        self.wall().format(fmt).to_string()
    }

    /// `astimezone(UTC)` (naive values are left alone, as Python's callers do).
    fn to_utc(self) -> Self {
        if !self.is_aware() {
            return self;
        }
        Self {
            dt: self.dt.with_timezone(&Utc.fix()),
            label: TzLabel::Fixed,
        }
    }

    fn utcoffset_is_zero(&self) -> bool {
        self.is_aware() && self.dt.offset().local_minus_utc() == 0
    }

    /// `dt.strftime("%Z")`.
    fn tzname(&self) -> String {
        match self.label {
            TzLabel::Naive => String::new(),
            TzLabel::Fixed => fixed_offset_name(self.dt.offset().local_minus_utc()),
            TzLabel::Zone(tz) => tz
                .offset_from_utc_datetime(&self.dt.naive_utc())
                .to_string(),
            TzLabel::Local { tz, at } => tz.offset_from_utc_datetime(&at.naive_utc()).to_string(),
        }
    }
}

/// `datetime.timezone.tzname()` for an unnamed fixed offset.
fn fixed_offset_name(seconds: i32) -> String {
    if seconds == 0 {
        return "UTC".into();
    }
    let sign = if seconds < 0 { '-' } else { '+' };
    let s = seconds.abs();
    let (h, m, sec) = (s / 3600, (s % 3600) / 60, s % 60);
    if sec != 0 {
        format!("UTC{sign}{h:02}:{m:02}:{sec:02}")
    } else {
        format!("UTC{sign}{h:02}:{m:02}")
    }
}

/// `_get_timezone_abbreviation`.
pub fn timezone_abbreviation(dt: &PyDateTime) -> String {
    let name = dt.tzname();
    match name.as_str() {
        "Eastern Standard Time" => "EST".into(),
        "Eastern Daylight Time" => "EDT".into(),
        "Central Standard Time" => "CST".into(),
        "Central Daylight Time" => "CDT".into(),
        "Mountain Standard Time" => "MST".into(),
        "Mountain Daylight Time" => "MDT".into(),
        "Pacific Standard Time" => "PST".into(),
        "Pacific Daylight Time" => "PDT".into(),
        "Coordinated Universal Time" => "UTC".into(),
        _ => name,
    }
}

fn time_format(use_12hour: bool) -> &'static str {
    if use_12hour {
        "%I:%M %p"
    } else {
        "%H:%M"
    }
}

fn fmt_time(dt: &PyDateTime, use_12hour: bool) -> String {
    let s = dt.strftime(time_format(use_12hour));
    match s.strip_prefix('0') {
        Some(rest) if use_12hour => rest.to_string(),
        _ => s,
    }
}

/// `format_display_time` (also `format_hour_time`, `format_timestamp`).
pub fn format_display_time(
    start_time: Option<&PyDateTime>,
    time_display_mode: &str,
    use_12hour: bool,
    show_timezone: bool,
) -> String {
    let Some(start) = start_time else {
        return "Unknown".into();
    };
    match time_display_mode {
        "utc" => {
            let mut s = fmt_time(&start.to_utc(), use_12hour);
            if show_timezone {
                s.push_str(" UTC");
            }
            s
        }
        "both" => {
            let mut local = fmt_time(start, use_12hour);
            if show_timezone {
                let abbr = timezone_abbreviation(start);
                if !abbr.is_empty() {
                    local.push(' ');
                    local.push_str(&abbr);
                }
            }
            let utc = fmt_time(&start.to_utc(), use_12hour);
            format!("{local} ({utc} UTC)")
        }
        _ => {
            let mut s = fmt_time(start, use_12hour);
            if show_timezone {
                let abbr = timezone_abbreviation(start);
                if !abbr.is_empty() && !start.utcoffset_is_zero() {
                    s.push(' ');
                    s.push_str(&abbr);
                }
            }
            s
        }
    }
}

/// `format_sun_time`.
pub fn format_sun_time(
    sun_time: Option<&PyDateTime>,
    time_display_mode: &str,
    use_12hour: bool,
    show_timezone: bool,
) -> Option<String> {
    sun_time.map(|t| format_display_time(Some(t), time_display_mode, use_12hour, show_timezone))
}

/// `format_display_datetime` (`date_format` is a strftime pattern).
pub fn format_display_datetime(
    value: &PyDateTime,
    time_display_mode: &str,
    use_12hour: bool,
    show_timezone: bool,
    date_format: &str,
) -> String {
    let fmt =
        |dt: &PyDateTime| format!("{} {}", dt.strftime(date_format), fmt_time(dt, use_12hour));
    match time_display_mode {
        "utc" => {
            let mut s = fmt(&value.to_utc());
            if show_timezone {
                s.push_str(" UTC");
            }
            s
        }
        "both" => {
            let mut local = fmt(value);
            if show_timezone {
                let abbr = timezone_abbreviation(value);
                if !abbr.is_empty() {
                    local.push(' ');
                    local.push_str(&abbr);
                }
            }
            format!("{local} ({} UTC)", fmt(&value.to_utc()))
        }
        _ => {
            let mut s = fmt(value);
            if show_timezone {
                let abbr = timezone_abbreviation(value);
                if !abbr.is_empty() {
                    s.push(' ');
                    s.push_str(&abbr);
                }
            }
            s
        }
    }
}

/// The default `date_format` of `format_display_datetime`.
pub const DEFAULT_DATE_FORMAT: &str = "%b %d";

fn date_style_format(style: &str) -> &'static str {
    match style {
        "us_short" => "%m/%d/%Y",
        "us_long" => "%B %d, %Y",
        "eu" => "%d/%m/%Y",
        _ => "%Y-%m-%d",
    }
}

/// `format_date`: a preset `date_format` setting key; unknown keys fall back to ISO.
pub fn format_date(dt: Option<&PyDateTime>, style: &str) -> String {
    dt.map(|d| d.strftime(date_style_format(style)))
        .unwrap_or_default()
}

/// `format_datetime`: "<date> <time>", 12h output without the leading zero.
pub fn format_datetime(dt: Option<&PyDateTime>, date_style: &str, time_12hour: bool) -> String {
    let Some(d) = dt else {
        return String::new();
    };
    let date_part = format_date(Some(d), date_style);
    let time_part = d.strftime(time_format(time_12hour));
    let time_part = if time_12hour {
        time_part.trim_start_matches('0').to_string()
    } else {
        time_part
    };
    format!("{date_part} {time_part}")
}

/// `_resolve_forecast_display_time`: location mode shows the location's
/// zone; `user_local` converts to the system zone's offset as of now.
pub fn resolve_forecast_display_time(
    start: &PyDateTime,
    forecast_time_reference: &str,
    location_tz: Option<Tz>,
    clock: &Clock,
) -> PyDateTime {
    if !start.is_aware() {
        return *start;
    }
    if forecast_time_reference != "user_local" {
        return match location_tz {
            None => *start,
            Some(tz) => PyDateTime {
                dt: start.dt.with_timezone(&tz).fixed_offset(),
                label: TzLabel::Zone(tz),
            },
        };
    }
    let offset = clock
        .local_tz
        .offset_from_utc_datetime(&clock.now.naive_utc())
        .fix();
    PyDateTime {
        dt: start.dt.with_timezone(&offset),
        label: TzLabel::Local {
            tz: clock.local_tz,
            at: clock.now,
        },
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::NaiveDate;

    fn at(h: u32, m: u32, offset_h: i32, zone: Option<Tz>) -> PyDateTime {
        let off = FixedOffset::east_opt(offset_h * 3600).unwrap();
        let dt = off.with_ymd_and_hms(2026, 7, 4, h, m, 0).unwrap();
        PyDateTime::aware(dt, zone)
    }

    #[test]
    fn modes_and_suffixes() {
        let ny = Some(chrono_tz::America::New_York);
        let t = at(15, 5, -4, ny);
        assert_eq!(
            format_display_time(Some(&t), "local", true, false),
            "3:05 PM"
        );
        assert_eq!(
            format_display_time(Some(&t), "local", true, true),
            "3:05 PM EDT"
        );
        assert_eq!(
            format_display_time(Some(&t), "local", false, false),
            "15:05"
        );
        assert_eq!(
            format_display_time(Some(&t), "utc", true, true),
            "7:05 PM UTC"
        );
        assert_eq!(
            format_display_time(Some(&t), "both", false, true),
            "15:05 EDT (19:05 UTC)"
        );
        let fixed = at(9, 0, -4, None);
        assert_eq!(
            format_display_time(Some(&fixed), "local", true, true),
            "9:00 AM UTC-04:00"
        );
        let utc = at(9, 0, 0, None);
        assert_eq!(
            format_display_time(Some(&utc), "local", true, true),
            "9:00 AM"
        );
        assert_eq!(format_display_time(None, "local", true, true), "Unknown");
    }

    #[test]
    fn display_datetime_and_date_styles() {
        let t = at(8, 30, -5, None);
        assert_eq!(
            format_display_datetime(&t, "local", true, false, "%m/%d"),
            "07/04 8:30 AM"
        );
        assert_eq!(format_date(Some(&t), "us_long"), "July 04, 2026");
        assert_eq!(format_date(Some(&t), "nope"), "2026-07-04");
        assert_eq!(format_datetime(Some(&t), "eu", true), "04/07/2026 8:30 AM");
        assert_eq!(
            format_datetime(Some(&t), "us_short", false),
            "07/04/2026 08:30"
        );
        let naive = PyDateTime::naive(
            NaiveDate::from_ymd_opt(2026, 1, 2)
                .unwrap()
                .and_hms_opt(0, 15, 0)
                .unwrap(),
        );
        assert_eq!(
            format_display_datetime(&naive, "both", true, true, "%b %d"),
            "Jan 02 12:15 AM (Jan 02 12:15 AM UTC)"
        );
    }

    #[test]
    fn user_local_uses_the_offset_in_effect_now() {
        let clock = Clock::fixed(
            Utc.with_ymd_and_hms(2026, 1, 15, 12, 0, 0).unwrap(),
            chrono_tz::America::New_York,
        );
        // A July timestamp still gets January's EST offset, as in Python.
        let t = at(12, 0, 0, None);
        let shown = resolve_forecast_display_time(&t, "user_local", None, &clock);
        assert_eq!(
            format_display_time(Some(&shown), "local", true, true),
            "7:00 AM EST"
        );
        let loc =
            resolve_forecast_display_time(&t, "location", Some(chrono_tz::Europe::London), &clock);
        assert_eq!(
            format_display_time(Some(&loc), "local", true, true),
            "1:00 PM BST"
        );
    }
}
