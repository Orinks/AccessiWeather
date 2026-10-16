//! Terminal Aerodrome Forecast decoding into screen-reader-friendly text
//! (`utils/taf_decoder.py`, `taf_elements.py`, `taf_segments.py`,
//! `taf_time.py`, `taf_patterns.py`). The Python regexes are all anchored
//! token shapes, matched here by hand.

fn is_digits(s: &str) -> bool {
    !s.is_empty() && s.bytes().all(|b| b.is_ascii_digit())
}

/// `\d{4}/\d{4}`
fn is_time_range(s: &str) -> bool {
    s.len() == 9 && s.is_ascii() && is_digits(&s[..4]) && &s[4..5] == "/" && is_digits(&s[5..])
}

/// `ISSUE_TIME_RE`: `\d{6}Z`
fn is_issue_time(s: &str) -> bool {
    s.len() == 7 && s.is_ascii() && is_digits(&s[..6]) && s.ends_with('Z')
}

/// `FM_TIME_RE`: `FM\d{6}`
fn is_fm_time(s: &str) -> bool {
    s.len() == 8 && s.starts_with("FM") && is_digits(&s[2..])
}

/// `^<prefix>(\d{4}/\d{4})?$`: `Some(period)` on a match.
fn match_period_group<'a>(token: &'a str, prefix: &str) -> Option<Option<&'a str>> {
    let rest = token.strip_prefix(prefix)?;
    if rest.is_empty() {
        Some(None)
    } else if is_time_range(rest) {
        Some(Some(rest))
    } else {
        None
    }
}

/// `PROB_RE`: `PROB(\d{2})(\d{4}/\d{4})?`
fn match_prob(token: &str) -> Option<(u32, Option<&str>)> {
    let rest = token.strip_prefix("PROB")?;
    if rest.len() < 2 || !rest.is_ascii() || !is_digits(&rest[..2]) {
        return None;
    }
    let prob = rest[..2].parse().ok()?;
    match &rest[2..] {
        "" => Some((prob, None)),
        period if is_time_range(period) => Some((prob, Some(period))),
        _ => None,
    }
}

fn format_day(day: u32) -> String {
    let suffix = if (10..=20).contains(&(day % 100)) {
        "th"
    } else {
        match day % 10 {
            1 => "st",
            2 => "nd",
            3 => "rd",
            _ => "th",
        }
    };
    format!("{day}{suffix}")
}

fn two(s: &str) -> u32 {
    s.parse().unwrap_or(0)
}

/// `_format_issue_time` ("DDHHMMZ").
fn format_issue_time(token: &str) -> String {
    format!(
        "{:02}:{:02} UTC on the {}",
        two(&token[2..4]),
        two(&token[4..6]),
        format_day(two(&token[..2]))
    )
}

/// `_format_time_range` ("DDHH/DDHH").
fn format_time_range(token: &str) -> String {
    if !is_time_range(token) {
        return token.to_string();
    }
    format!(
        "from {:02}:00 UTC on the {} until {:02}:00 UTC on the {}",
        two(&token[2..4]),
        format_day(two(&token[..2])),
        two(&token[7..9]),
        format_day(two(&token[5..7]))
    )
}

/// `_format_from_time` ("DDHHMM").
fn format_from_time(token: &str) -> String {
    if token.len() != 6 || !is_digits(token) {
        return token.to_string();
    }
    format_issue_time(token)
}

// ---------------------------------------------------------------------------
// Elements
// ---------------------------------------------------------------------------

/// `_decode_wind` (`WIND_RE`: `(\d{3}|VRB)(\d{2,3})(G\d{2,3})?(KT|MPS|KMH)`).
fn decode_wind(token: &str) -> Option<String> {
    let (dir, rest) = if let Some(rest) = token.strip_prefix("VRB") {
        ("VRB", rest)
    } else if token.get(..3).is_some_and(is_digits) {
        token.split_at(3)
    } else {
        return None;
    };
    let (rest, unit) = ["KT", "MPS", "KMH"]
        .iter()
        .find_map(|u| rest.strip_suffix(u).map(|r| (r, *u)))?;
    let (speed, gust) = match rest.split_once('G') {
        Some((s, g)) => (s, Some(g)),
        None => (rest, None),
    };
    let digits_2_3 = |s: &str| (2..=3).contains(&s.len()) && is_digits(s);
    if !digits_2_3(speed) || gust.is_some_and(|g| !digits_2_3(g)) {
        return None;
    }
    let unit_text = match unit {
        "KT" => "knots",
        "MPS" => "meters per second",
        _ => "kilometres per hour",
    };
    let speed: u32 = speed.parse().ok()?;
    let mut base = if dir == "000" && speed == 0 {
        "Calm winds".to_string()
    } else if dir == "VRB" {
        format!("Winds variable at {speed} {unit_text}")
    } else {
        format!("Winds from {dir} degrees at {speed} {unit_text}")
    };
    if let Some(g) = gust {
        base.push_str(&format!(
            " with gusts to {} {unit_text}",
            g.parse::<u32>().ok()?
        ));
    }
    Some(format!("{base} ({token})"))
}

/// Python `f"{x:.Nf}"`, including its spelling of non-finite values.
fn fixed(x: f64, precision: usize) -> String {
    if x.is_nan() {
        "nan".into()
    } else if x.is_infinite() {
        if x > 0.0 { "inf" } else { "-inf" }.into()
    } else {
        format!("{x:.precision$}")
    }
}

/// `_decode_visibility`.
fn decode_visibility(token: &str) -> Option<String> {
    let working = token.trim();
    if working.is_empty() {
        return None;
    }
    if working.ends_with("SM") {
        return Some(decode_statute_mile_visibility(token, working));
    }
    if working.len() == 4 && is_digits(working) {
        let meters: u32 = working.parse().ok()?;
        if meters == 9999 {
            return Some("Visibility 10 kilometres or more (9999 meters)".into());
        }
        let km = f64::from(meters) / 1000.0;
        return Some(format!(
            "Visibility {} kilometres ({working} meters)",
            fixed(km, 1)
        ));
    }
    None
}

fn decode_statute_mile_visibility(token: &str, working: &str) -> String {
    let mut magnitude = working[..working.len() - 2].trim();
    let mut prefix = None;
    if magnitude.starts_with(['P', 'M']) {
        prefix = magnitude.chars().next();
        magnitude = &magnitude[1..];
    }

    let mut whole = None;
    let mut fraction = magnitude.to_string();
    if magnitude.contains(' ') {
        let parts: Vec<&str> = magnitude.split_whitespace().collect();
        whole = parts.first().map(|s| s.to_string());
        fraction = parts.last().map(|s| s.to_string()).unwrap_or_default();
    } else if token.contains(' ') {
        let replaced = token.replace("SM", "");
        let parts: Vec<&str> = replaced.split_whitespace().collect();
        if let [w, f] = parts[..] {
            whole = Some(w.to_string());
            fraction = f.to_string();
        }
    }

    let (decimal, display) = parse_visibility_magnitude(whole.as_deref(), &fraction);
    let descriptor = match prefix {
        Some('P') => "Visibility greater than",
        Some('M') => "Visibility less than",
        _ => "Visibility",
    };
    let decimal_text = match decimal {
        Some(d) => {
            let s = fixed(d, 2);
            let s = s.trim_end_matches('0').trim_end_matches('.');
            format!(" ({s} SM)")
        }
        None => String::new(),
    };
    format!("{descriptor} {display} statute miles{decimal_text} ({token})")
}

/// `Fraction("a/b")` as a float, `None` where Python raises.
fn parse_fraction(text: &str) -> Option<f64> {
    let (num, den) = text.trim().split_once('/')?;
    let num = num.strip_prefix(['+', '-']).map_or(num, |n| n);
    let negative = text.trim().starts_with('-');
    if !is_digits(num) || !is_digits(den) {
        return None;
    }
    let (n, d): (f64, f64) = (num.parse().ok()?, den.parse().ok()?);
    if d == 0.0 {
        return None;
    }
    Some(if negative { -n / d } else { n / d })
}

/// Python `int(text)`.
fn parse_int(text: &str) -> Option<i64> {
    text.trim().parse().ok()
}

fn parse_visibility_magnitude(whole: Option<&str>, fraction: &str) -> (Option<f64>, String) {
    if let (Some(w), true) = (whole, fraction.contains('/')) {
        let value = parse_fraction(fraction).and_then(|f| Some(parse_int(w)? as f64 + f));
        return (value, format!("{w} {fraction}"));
    }
    if fraction.contains('/') {
        return (parse_fraction(fraction), fraction.to_string());
    }
    (
        super::common::py_parse_float(fraction),
        fraction.to_string(),
    )
}

const DESCRIPTORS: [(&str, &str); 9] = [
    ("MI", "shallow"),
    ("PR", "partial"),
    ("BC", "patches of"),
    ("DR", "low drifting"),
    ("BL", "blowing"),
    ("SH", "showers of"),
    ("TS", "thunderstorms with"),
    ("FZ", "freezing"),
    ("RE", "recent"),
];

const PHENOMENA: [(&str, &str); 24] = [
    ("DZ", "drizzle"),
    ("RA", "rain"),
    ("SN", "snow"),
    ("SG", "snow grains"),
    ("IC", "ice crystals"),
    ("PL", "ice pellets"),
    ("GR", "hail"),
    ("GS", "small hail"),
    ("UP", "unknown precipitation"),
    ("BR", "mist"),
    ("FG", "fog"),
    ("FU", "smoke"),
    ("VA", "volcanic ash"),
    ("DU", "dust"),
    ("SA", "sand"),
    ("HZ", "haze"),
    ("PY", "spray"),
    ("PO", "dust/sand whirls"),
    ("SQ", "squalls"),
    ("FC", "funnel clouds"),
    ("SS", "sandstorm"),
    ("DS", "dust storm"),
    ("SH", "showers"),
    ("TS", "thunderstorms"),
];

const KNOWN_PRECIP_CODES: [&str; 8] = ["DZ", "RA", "SN", "SG", "IC", "PL", "GR", "GS"];

fn lookup(table: &[(&'static str, &'static str)], code: &str) -> Option<&'static str> {
    table.iter().find(|(c, _)| *c == code).map(|(_, t)| *t)
}

/// `_decode_weather`.
fn decode_weather(token: &str) -> Option<String> {
    if token.is_empty() {
        return None;
    }
    let mut working = token;
    let mut qualifier = "";
    if let Some(rest) = working.strip_prefix("VC") {
        qualifier = "In the vicinity, ";
        working = rest;
    }
    let mut intensity = "";
    if let Some(rest) = working.strip_prefix('+') {
        intensity = "heavy";
        working = rest;
    } else if let Some(rest) = working.strip_prefix('-') {
        intensity = "light";
        working = rest;
    }

    let (mut descriptor_codes, mut descriptors) = (Vec::new(), Vec::new());
    let (mut phenomenon_codes, mut phenomena) = (Vec::new(), Vec::new());
    while !working.is_empty() {
        let code = working.get(..2).unwrap_or(working);
        if let Some(text) = lookup(&DESCRIPTORS, code) {
            descriptor_codes.push(code);
            descriptors.push(text);
        } else if let Some(text) = lookup(&PHENOMENA, code) {
            phenomenon_codes.push(code);
            phenomena.push(text);
        } else {
            break;
        }
        working = &working[2..];
    }

    if phenomenon_codes.contains(&"UP") {
        let inferred = infer_unknown_precipitation_label(&descriptor_codes, &phenomenon_codes);
        if inferred == "mixed precipitation" {
            phenomena = vec![inferred];
        } else {
            let known: Vec<&str> = phenomenon_codes
                .iter()
                .zip(&phenomena)
                .filter(|(code, _)| **code != "UP")
                .map(|(_, text)| *text)
                .collect();
            phenomena = if known.is_empty() {
                vec![inferred]
            } else {
                known
            };
        }
    }

    if descriptors.is_empty() && phenomena.is_empty() && intensity.is_empty() {
        return None;
    }
    let descriptor_text = descriptors.join(" ");
    let phenomena_text = phenomena.join(" and ");
    let pieces: Vec<&str> = [intensity, descriptor_text.trim(), phenomena_text.trim()]
        .into_iter()
        .filter(|p| !p.is_empty())
        .collect();
    let description = pieces.join(" ").replace("  ", " ");
    Some(format!("{qualifier}{} ({token})", description.trim()))
}

/// `_infer_unknown_precipitation_label` for TAF "UP" codes.
fn infer_unknown_precipitation_label(descriptors: &[&str], phenomena: &[&str]) -> &'static str {
    if phenomena
        .iter()
        .any(|c| *c != "UP" && KNOWN_PRECIP_CODES.contains(c))
    {
        "mixed precipitation"
    } else if descriptors.contains(&"FZ") {
        "freezing precipitation"
    } else if descriptors.contains(&"TS") {
        "thunderstorm precipitation"
    } else if descriptors.contains(&"SH") {
        "showery precipitation"
    } else {
        "unidentified precipitation"
    }
}

/// `f"{n:,}"`.
fn thousands(n: u32) -> String {
    let digits = n.to_string();
    let mut out = String::new();
    for (i, c) in digits.chars().enumerate() {
        if i > 0 && (digits.len() - i).is_multiple_of(3) {
            out.push(',');
        }
        out.push(c);
    }
    out
}

/// `_decode_cloud` (`CLOUD_RE`: `(FEW|SCT|BKN|OVC|NSC|SKC|CLR|VV)(\d{3}|///)?(CB|TCU|///)?`).
fn decode_cloud(token: &str) -> Option<String> {
    if token.is_empty() {
        return None;
    }
    if token == "SKC" || token == "CLR" {
        return Some(format!("Sky clear ({token})"));
    }
    if token == "NSC" {
        return Some("No significant clouds (NSC)".into());
    }
    let (cover, rest) = ["FEW", "SCT", "BKN", "OVC", "NSC", "SKC", "CLR", "VV"]
        .iter()
        .find_map(|c| token.strip_prefix(c).map(|r| (*c, r)))?;
    let (height, rest) = match rest.get(..3) {
        Some(h) if is_digits(h) || h == "///" => (Some(h), &rest[3..]),
        _ => (None, rest),
    };
    let cloud_type = match rest {
        "" => None,
        "CB" | "TCU" | "///" => Some(rest),
        _ => return None,
    };

    let cover_text = match cover {
        "FEW" => "A few clouds",
        "SCT" => "Scattered clouds",
        "BKN" => "Broken clouds",
        "OVC" => "Overcast",
        "VV" => "Vertical visibility",
        other => other,
    };
    let altitude = height
        .filter(|h| is_digits(h))
        .and_then(|h| h.parse::<u32>().ok())
        .map(|h| h * 100);
    if cover == "VV" {
        if let Some(alt) = altitude {
            return Some(format!(
                "Vertical visibility {} feet ({token})",
                thousands(alt)
            ));
        }
    }
    let altitude_text = altitude
        .map(|a| format!(" at {} feet", thousands(a)))
        .unwrap_or_default();
    let type_text = match cloud_type {
        Some("CB") => " with cumulonimbus",
        Some("TCU") => " with towering cumulus",
        _ => "",
    };
    Some(format!("{cover_text}{altitude_text}{type_text} ({token})"))
}

// ---------------------------------------------------------------------------
// Segments
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, PartialEq)]
enum Kind<'a> {
    Base,
    From(&'a str),
    Tempo(Option<&'a str>),
    Becmg(Option<&'a str>),
    Probability {
        prob: u32,
        period: Option<&'a str>,
        tempo: bool,
    },
}

struct Segment<'a> {
    kind: Kind<'a>,
    tokens: Vec<&'a str>,
}

/// `_new_change_segment`: a change group starting at `tokens[i]`, with the
/// index of the first token after its header.
fn new_change_segment<'a>(tokens: &[&'a str], i: usize) -> Option<(Kind<'a>, usize)> {
    let token = tokens[i];
    if is_fm_time(token) {
        return Some((Kind::From(&token[2..]), i + 1));
    }
    let trailing_period = |period: Option<&'a str>, next: usize| match period {
        Some(p) => (Some(p), next),
        None => match tokens.get(next) {
            Some(t) if is_time_range(t) => (Some(*t), next + 1),
            _ => (None, next),
        },
    };
    if let Some(period) = match_period_group(token, "TEMPO") {
        let (period, next) = trailing_period(period, i + 1);
        return Some((Kind::Tempo(period), next));
    }
    if let Some(period) = match_period_group(token, "BECMG") {
        let (period, next) = trailing_period(period, i + 1);
        return Some((Kind::Becmg(period), next));
    }
    let (prob, period) = match_prob(token)?;
    let (mut period, mut next) = trailing_period(period, i + 1);
    let mut tempo = false;
    if let Some(t) = tokens.get(next).filter(|t| t.starts_with("TEMPO")) {
        tempo = true;
        next += 1;
        if let Some(tempo_period) = match_period_group(t, "TEMPO") {
            match tempo_period {
                Some(p) => period = Some(p),
                None => {
                    if let Some(p) = tokens.get(next).filter(|p| is_time_range(p)) {
                        period = Some(p);
                        next += 1;
                    }
                }
            }
        }
    }
    Some((
        Kind::Probability {
            prob,
            period,
            tempo,
        },
        next,
    ))
}

/// `_split_segments`: change groups plus the remarks after `RMK`.
fn split_segments<'a>(tokens: &[&'a str]) -> (Vec<Segment<'a>>, Option<String>) {
    let mut segments = vec![Segment {
        kind: Kind::Base,
        tokens: Vec::new(),
    }];
    let mut remarks = None;
    let mut i = 0;
    while i < tokens.len() {
        if tokens[i] == "RMK" {
            remarks = Some(tokens[i + 1..].join(" ").trim().to_string());
            break;
        }
        if let Some((kind, next)) = new_change_segment(tokens, i) {
            segments.push(Segment {
                kind,
                tokens: Vec::new(),
            });
            i = next;
            continue;
        }
        segments
            .last_mut()
            .expect("base segment")
            .tokens
            .push(tokens[i]);
        i += 1;
    }
    let base_kind = segments[0].kind.clone();
    let mut filtered: Vec<Segment> = segments
        .into_iter()
        .filter(|s| !s.tokens.is_empty())
        .collect();
    if filtered.is_empty() {
        filtered.push(Segment {
            kind: base_kind,
            tokens: Vec::new(),
        });
    }
    (filtered, remarks)
}

/// `_segment_intro`.
fn segment_intro(kind: &Kind) -> String {
    match kind {
        Kind::Base => "Base forecast:".into(),
        Kind::From(time) => format!("From {}:", format_from_time(time)),
        Kind::Tempo(Some(p)) => format!("Temporary between {}:", format_time_range(p)),
        Kind::Tempo(None) => "Temporary conditions:".into(),
        Kind::Becmg(Some(p)) => format!("Becoming {}:", format_time_range(p)),
        Kind::Becmg(None) => "Becoming conditions:".into(),
        Kind::Probability {
            prob,
            period,
            tempo,
        } => {
            let mut prefix = format!("Probability {prob}%");
            if *tempo {
                prefix.push_str(" of temporary conditions");
            }
            match period {
                Some(p) => format!("{prefix} {}:", format_time_range(p)),
                None => format!("{prefix}:"),
            }
        }
    }
}

/// `_describe_segment`.
fn describe_segment(tokens: &[&str]) -> String {
    if tokens.is_empty() {
        return "No additional details provided.".into();
    }
    let mut wind: Option<String> = None;
    let mut visibility: Option<String> = None;
    let mut weather: Vec<String> = Vec::new();
    let mut clouds: Vec<String> = Vec::new();
    let mut extra: Vec<&str> = Vec::new();

    let mut i = 0;
    while i < tokens.len() {
        let token = tokens[i];
        // "1 1/2SM" arrives as two tokens.
        if let Some(next) = tokens.get(i + 1) {
            if is_digits(token) && next.ends_with("SM") && next.contains('/') {
                if let Some(v) = decode_visibility(&format!("{token} {next}")) {
                    if visibility.is_none() {
                        visibility = Some(v);
                    } else {
                        weather.push(v);
                    }
                }
                i += 2;
                continue;
            }
        }
        if wind.is_none() {
            if let Some(w) = decode_wind(token) {
                wind = Some(w);
                i += 1;
                continue;
            }
        }
        if visibility.is_none() {
            if let Some(v) = decode_visibility(token) {
                visibility = Some(v);
                i += 1;
                continue;
            }
        }
        if let Some(w) = decode_weather(token) {
            weather.push(w);
        } else if let Some(c) = decode_cloud(token) {
            clouds.push(c);
        } else if token == "CAVOK" {
            clouds.push("Ceiling and visibility OK (CAVOK)".into());
        } else if token == "NSW" {
            weather.push("No significant weather (NSW)".into());
        } else {
            extra.push(token);
        }
        i += 1;
    }

    let mut sentences = Vec::new();
    if let Some(w) = wind {
        sentences.push(format!("{w}."));
    }
    if let Some(v) = visibility {
        sentences.push(format!("{v}."));
    }
    if !weather.is_empty() {
        sentences.push(format!("Weather: {}.", weather.join("; ")));
    }
    if !clouds.is_empty() {
        sentences.push(format!("Clouds: {}.", clouds.join("; ")));
    }
    if !extra.is_empty() {
        sentences.push(format!("Additional codes: {}.", extra.join(" ")));
    }
    if sentences.is_empty() {
        "No additional details provided.".into()
    } else {
        sentences.join(" ")
    }
}

fn decode_tokens(tokens: &[&str]) -> String {
    let mut working = tokens;
    while let Some((first, rest)) = working.split_first() {
        if matches!(*first, "TAF" | "AMD" | "COR") {
            working = rest;
        } else {
            break;
        }
    }
    // Python tests the station's truthiness, so an empty token counts as none.
    let station = working.first().copied();
    working = working.get(1..).unwrap_or_default();
    if working.is_empty() {
        return match station.filter(|s| !s.is_empty()) {
            Some(s) => format!("TAF issued for station {s}."),
            None => "TAF issued, but no additional information was provided.".into(),
        };
    }
    if working[0] == "NIL" {
        let station_text = station
            .filter(|s| !s.is_empty())
            .map(|s| format!(" for station {s}"))
            .unwrap_or_default();
        return format!("No TAF available{station_text}.");
    }

    let issue_time = working.first().copied().filter(|t| is_issue_time(t));
    if issue_time.is_some() {
        working = &working[1..];
    }
    let validity = working.first().copied().filter(|t| is_time_range(t));
    if validity.is_some() {
        working = &working[1..];
    }
    let (segments, remarks) = split_segments(working);

    let mut lines = vec![match station.filter(|s| !s.is_empty()) {
        Some(s) => format!("Forecast for station {s}."),
        None => "Terminal Aerodrome Forecast.".into(),
    }];
    if let Some(t) = issue_time {
        lines.push(format!("Issued at {}.", format_issue_time(t)));
    }
    if let Some(v) = validity {
        lines.push(format!("Valid {}.", format_time_range(v)));
    }
    for segment in &segments {
        let intro = segment_intro(&segment.kind);
        let description = describe_segment(&segment.tokens);
        lines.push(format!("{intro} {description}").trim().to_string());
    }
    if let Some(r) = remarks.filter(|r| !r.is_empty()) {
        lines.push(format!("Remarks: {r}."));
    }
    lines.join("\n")
}

/// `decode_taf_text`: an accessible summary of a raw TAF.
pub fn decode_taf_text(raw_taf: &str) -> String {
    let cleaned = raw_taf.split_whitespace().collect::<Vec<_>>().join(" ");
    if cleaned.is_empty() {
        return "No TAF available.".into();
    }
    let tokens: Vec<&str> = cleaned
        .split(' ')
        .filter(|t| *t != "=")
        .map(|t| t.trim_end_matches('='))
        .collect();
    if tokens.is_empty() {
        return "No TAF available.".into();
    }
    decode_tokens(&tokens)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fixed_point_ties_round_like_python() {
        let cases = [
            (0.25, 1, "0.2"),
            (0.75, 1, "0.8"),
            (0.125, 2, "0.12"),
            (0.375, 2, "0.38"),
            (0.625, 2, "0.62"),
            (0.0625, 2, "0.06"),
        ];
        for (x, p, want) in cases {
            assert_eq!(fixed(x, p), want, "{x}");
        }
        assert_eq!(fixed(f64::NAN, 2), "nan");
    }

    #[test]
    fn wind_group_variants() {
        assert_eq!(decode_wind("00000KT").unwrap(), "Calm winds (00000KT)");
        assert_eq!(
            decode_wind("VRB05KT").unwrap(),
            "Winds variable at 5 knots (VRB05KT)"
        );
        assert_eq!(
            decode_wind("27015G25KT").unwrap(),
            "Winds from 270 degrees at 15 knots with gusts to 25 knots (27015G25KT)"
        );
        assert_eq!(
            decode_wind("18010MPS").unwrap(),
            "Winds from 180 degrees at 10 meters per second (18010MPS)"
        );
        assert!(decode_wind("2701KT").is_none());
        assert!(decode_wind("27015G5KT").is_none());
        assert!(decode_wind("P6SM").is_none());
    }

    #[test]
    fn visibility_variants() {
        assert_eq!(
            decode_visibility("P6SM").unwrap(),
            "Visibility greater than 6 statute miles (6 SM) (P6SM)"
        );
        assert_eq!(
            decode_visibility("1/2SM").unwrap(),
            "Visibility 1/2 statute miles (0.5 SM) (1/2SM)"
        );
        assert_eq!(
            decode_visibility("1 1/2SM").unwrap(),
            "Visibility 1 1/2 statute miles (1.5 SM) (1 1/2SM)"
        );
        assert_eq!(
            decode_visibility("M1/4SM").unwrap(),
            "Visibility less than 1/4 statute miles (0.25 SM) (M1/4SM)"
        );
        assert_eq!(
            decode_visibility("9999").unwrap(),
            "Visibility 10 kilometres or more (9999 meters)"
        );
        assert_eq!(
            decode_visibility("0800").unwrap(),
            "Visibility 0.8 kilometres (0800 meters)"
        );
        assert_eq!(
            decode_visibility("1/0SM").unwrap(),
            "Visibility 1/0 statute miles (1/0SM)"
        );
        assert!(decode_visibility("BKN020").is_none());
    }

    #[test]
    fn weather_and_cloud_groups() {
        assert_eq!(decode_weather("-RA").unwrap(), "light rain (-RA)");
        assert_eq!(
            decode_weather("+TSRA").unwrap(),
            "heavy thunderstorms with rain (+TSRA)"
        );
        assert_eq!(
            decode_weather("VCSH").unwrap(),
            "In the vicinity, showers of (VCSH)"
        );
        assert_eq!(
            decode_weather("UP").unwrap(),
            "unidentified precipitation (UP)"
        );
        assert_eq!(
            decode_weather("FZUP").unwrap(),
            "freezing freezing precipitation (FZUP)"
        );
        assert_eq!(
            decode_weather("RAUP").unwrap(),
            "mixed precipitation (RAUP)"
        );
        assert!(decode_weather("BKN020").is_none());
        assert_eq!(
            decode_cloud("BKN020CB").unwrap(),
            "Broken clouds at 2,000 feet with cumulonimbus (BKN020CB)"
        );
        assert_eq!(
            decode_cloud("VV005").unwrap(),
            "Vertical visibility 500 feet (VV005)"
        );
        assert_eq!(decode_cloud("OVC///").unwrap(), "Overcast (OVC///)");
        assert_eq!(decode_cloud("SKC").unwrap(), "Sky clear (SKC)");
        assert!(decode_cloud("OVC02").is_none());
    }

    #[test]
    fn full_taf_decodes_in_order() {
        let raw = "TAF KJFK 121130Z 1212/1318 27015G25KT P6SM FEW050 \
                   TEMPO 1214/1218 BKN030 \
                   FM130000 30010KT 6SM -SHRA OVC020 \
                   PROB30 1306/1310 TSRA BKN015CB \
                   BECMG 1312/1314 VRB03KT RMK NXT FCST BY 18Z=";
        let expected = [
            "Forecast for station KJFK.",
            "Issued at 11:30 UTC on the 12th.",
            "Valid from 12:00 UTC on the 12th until 18:00 UTC on the 13th.",
            "Base forecast: Winds from 270 degrees at 15 knots with gusts to 25 knots (27015G25KT). Visibility greater than 6 statute miles (6 SM) (P6SM). Clouds: A few clouds at 5,000 feet (FEW050).",
            "Temporary between from 14:00 UTC on the 12th until 18:00 UTC on the 12th: Clouds: Broken clouds at 3,000 feet (BKN030).",
            "From 00:00 UTC on the 13th: Winds from 300 degrees at 10 knots (30010KT). Visibility 6 statute miles (6 SM) (6SM). Weather: light showers of rain (-SHRA). Clouds: Overcast at 2,000 feet (OVC020).",
            "Probability 30% from 06:00 UTC on the 13th until 10:00 UTC on the 13th: Weather: thunderstorms with rain (TSRA). Clouds: Broken clouds at 1,500 feet with cumulonimbus (BKN015CB).",
            "Becoming from 12:00 UTC on the 13th until 14:00 UTC on the 13th: Winds variable at 3 knots (VRB03KT).",
            "Remarks: NXT FCST BY 18Z.",
        ];
        assert_eq!(decode_taf_text(raw), expected.join("\n"));
    }

    #[test]
    fn empty_nil_and_header_only() {
        assert_eq!(decode_taf_text(""), "No TAF available.");
        assert_eq!(decode_taf_text("   "), "No TAF available.");
        assert_eq!(
            decode_taf_text("TAF KXYZ NIL="),
            "No TAF available for station KXYZ."
        );
        assert_eq!(decode_taf_text("TAF KXYZ"), "TAF issued for station KXYZ.");
        assert_eq!(
            decode_taf_text("TAF"),
            "TAF issued, but no additional information was provided."
        );
        assert_eq!(
            decode_taf_text("TAF KXYZ 121130Z 1212/1318"),
            "Forecast for station KXYZ.\nIssued at 11:30 UTC on the 12th.\nValid from 12:00 UTC on the 12th until 18:00 UTC on the 13th.\nBase forecast: No additional details provided."
        );
    }

    #[test]
    fn prob_tempo_combination() {
        let out = decode_taf_text("TAF KXYZ 121130Z 1212/1318 PROB40 TEMPO 1220/1222 -SN");
        assert!(out.ends_with(
            "Probability 40% of temporary conditions from 20:00 UTC on the 12th until 22:00 UTC on the 12th: Weather: light snow (-SN)."
        ));
    }
}
