//! Terminal Aerodrome Forecast decoding into readable text.
//!
//! Port of `utils/taf_decoder.py`, `taf_segments.py`, `taf_elements.py`,
//! `taf_patterns.py` and `taf_time.py`. The regexes are matched by hand.

fn is_digits(s: &str) -> bool {
    !s.is_empty() && s.chars().all(|c| c.is_ascii_digit())
}

fn digits_n(s: &str, n: usize) -> bool {
    s.len() == n && is_digits(s)
}

/// `^\d{6}Z$`
fn is_issue_time(t: &str) -> bool {
    t.strip_suffix('Z').is_some_and(|d| digits_n(d, 6))
}

/// `^\d{4}/\d{4}$`
fn is_time_range(t: &str) -> bool {
    t.split_once('/')
        .is_some_and(|(a, b)| digits_n(a, 4) && digits_n(b, 4))
}

/// `^FM\d{6}$`
fn is_fm_time(t: &str) -> bool {
    t.strip_prefix("FM").is_some_and(|d| digits_n(d, 6))
}

/// `^<prefix>(?P<period>\d{4}/\d{4})?$` -> Some(period) on a match.
fn match_prefixed_period<'a>(t: &'a str, prefix: &str) -> Option<Option<&'a str>> {
    let rest = t.strip_prefix(prefix)?;
    if rest.is_empty() {
        Some(None)
    } else if is_time_range(rest) {
        Some(Some(rest))
    } else {
        None
    }
}

/// `^PROB(?P<prob>\d{2})(?P<period>\d{4}/\d{4})?$`
fn match_prob(t: &str) -> Option<(u32, Option<&str>)> {
    let rest = t.strip_prefix("PROB")?;
    let prob = rest.get(..2).filter(|p| digits_n(p, 2))?;
    let period = &rest[2..];
    let period = if period.is_empty() {
        None
    } else if is_time_range(period) {
        Some(period)
    } else {
        return None;
    };
    Some((prob.parse().ok()?, period))
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

fn num(s: &str) -> u32 {
    s.parse().unwrap_or(0)
}

fn format_issue_time(token: &str) -> String {
    format!(
        "{:02}:{:02} UTC on the {}",
        num(&token[2..4]),
        num(&token[4..6]),
        format_day(num(&token[..2]))
    )
}

fn format_time_range(token: &str) -> String {
    if !is_time_range(token) {
        return token.to_string();
    }
    let (start, end) = token.split_once('/').unwrap_or((token, ""));
    format!(
        "from {:02}:00 UTC on the {} until {:02}:00 UTC on the {}",
        num(&start[2..4]),
        format_day(num(&start[..2])),
        num(&end[2..4]),
        format_day(num(&end[..2]))
    )
}

fn format_from_time(token: &str) -> String {
    if !digits_n(token, 6) {
        return token.to_string();
    }
    format_issue_time(token)
}

// ---------------------------------------------------------------------------
// elements
// ---------------------------------------------------------------------------

/// `WIND_RE`: `^(\d{3}|VRB)(\d{2,3})(G\d{2,3})?(KT|MPS|KMH)$`.
pub fn decode_wind(token: &str) -> Option<String> {
    let dir = token.get(..3)?;
    if !(digits_n(dir, 3) || dir == "VRB") {
        return None;
    }
    let rest = &token[3..];
    let take_digits = |s: &str| s.chars().take_while(char::is_ascii_digit).count();
    let n = take_digits(rest);
    if !(2..=3).contains(&n) {
        return None;
    }
    let (speed, mut rest) = rest.split_at(n);
    let mut gust = None;
    if let Some(g) = rest.strip_prefix('G') {
        let gn = take_digits(g);
        if !(2..=3).contains(&gn) {
            return None;
        }
        gust = Some(&g[..gn]);
        rest = &g[gn..];
    }
    let unit_text = match rest {
        "KT" => "knots",
        "MPS" => "meters per second",
        "KMH" => "kilometres per hour",
        _ => return None,
    };
    let speed_value = num(speed);
    let mut base = if dir == "000" && speed_value == 0 {
        "Calm winds".to_string()
    } else if dir == "VRB" {
        format!("Winds variable at {speed_value} {unit_text}")
    } else {
        format!("Winds from {dir} degrees at {speed_value} {unit_text}")
    };
    if let Some(g) = gust {
        base.push_str(&format!(" with gusts to {} {unit_text}", num(g)));
    }
    Some(format!("{base} ({token})"))
}

/// `Fraction(text)` for the "a/b" form, as a float (`None` when invalid or /0).
fn parse_fraction(text: &str) -> Option<f64> {
    let t = text.trim();
    let (n, d) = t.split_once('/')?;
    let digits = n.strip_prefix(['+', '-']).unwrap_or(n);
    if !is_digits(digits) || !is_digits(d) {
        return None;
    }
    let (n, d): (f64, f64) = (n.parse().ok()?, d.parse().ok()?);
    (d != 0.0).then(|| n / d)
}

fn parse_float(text: &str) -> Option<f64> {
    text.trim().parse().ok()
}

pub fn decode_visibility(token: &str) -> Option<String> {
    let working = token.trim();
    if working.is_empty() {
        return None;
    }
    if working.ends_with("SM") {
        return Some(decode_statute_mile_visibility(token, working));
    }
    if working.chars().count() == 4 && is_digits(working) {
        let distance_m = num(working);
        if distance_m == 9999 {
            return Some("Visibility 10 kilometres or more (9999 meters)".into());
        }
        return Some(format!(
            "Visibility {:.1} kilometres ({working} meters)",
            distance_m as f64 / 1000.0
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
    let mut whole: Option<String> = None;
    let mut fraction_part = magnitude.to_string();
    if magnitude.contains(' ') {
        let parts: Vec<&str> = magnitude.split_whitespace().collect();
        whole = parts.first().map(|s| s.to_string());
        fraction_part = parts.last().map(|s| s.to_string()).unwrap_or_default();
    } else if token.contains(' ') {
        let replaced = token.replace("SM", "");
        let parts: Vec<&str> = replaced.split_whitespace().collect();
        if parts.len() == 2 {
            whole = Some(parts[0].to_string());
            fraction_part = parts[1].to_string();
        }
    }

    let (decimal, display) = match &whole {
        Some(w) if fraction_part.contains('/') => {
            let decimal = parse_fraction(&fraction_part)
                .and_then(|f| w.trim().parse::<i64>().ok().map(|w| w as f64 + f));
            (decimal, format!("{w} {fraction_part}"))
        }
        _ if fraction_part.contains('/') => (parse_fraction(&fraction_part), fraction_part.clone()),
        _ => (parse_float(&fraction_part), fraction_part.clone()),
    };
    let descriptor = match prefix {
        Some('P') => "Visibility greater than",
        Some('M') => "Visibility less than",
        _ => "Visibility",
    };
    let decimal_text = decimal
        .map(|d| {
            let s = format!("{d:.2}");
            format!(" ({} SM)", s.trim_end_matches('0').trim_end_matches('.'))
        })
        .unwrap_or_default();
    format!("{descriptor} {display} statute miles{decimal_text} ({token})")
}

fn descriptor(code: &str) -> Option<&'static str> {
    Some(match code {
        "MI" => "shallow",
        "PR" => "partial",
        "BC" => "patches of",
        "DR" => "low drifting",
        "BL" => "blowing",
        "SH" => "showers of",
        "TS" => "thunderstorms with",
        "FZ" => "freezing",
        "RE" => "recent",
        _ => return None,
    })
}

fn phenomenon(code: &str) -> Option<&'static str> {
    Some(match code {
        "DZ" => "drizzle",
        "RA" => "rain",
        "SN" => "snow",
        "SG" => "snow grains",
        "IC" => "ice crystals",
        "PL" => "ice pellets",
        "GR" => "hail",
        "GS" => "small hail",
        "UP" => "unknown precipitation",
        "BR" => "mist",
        "FG" => "fog",
        "FU" => "smoke",
        "VA" => "volcanic ash",
        "DU" => "dust",
        "SA" => "sand",
        "HZ" => "haze",
        "PY" => "spray",
        "PO" => "dust/sand whirls",
        "SQ" => "squalls",
        "FC" => "funnel clouds",
        "SS" => "sandstorm",
        "DS" => "dust storm",
        "SH" => "showers",
        "TS" => "thunderstorms",
        _ => return None,
    })
}

const KNOWN_PRECIP_CODES: [&str; 8] = ["DZ", "RA", "SN", "SG", "IC", "PL", "GR", "GS"];

/// `_infer_unknown_precipitation_label`.
pub fn infer_unknown_precipitation_label(
    descriptor_codes: &[String],
    phenomenon_codes: &[String],
) -> &'static str {
    let has = |codes: &[String], c: &str| codes.iter().any(|x| x == c);
    if phenomenon_codes
        .iter()
        .any(|c| c != "UP" && KNOWN_PRECIP_CODES.contains(&c.as_str()))
    {
        "mixed precipitation"
    } else if has(descriptor_codes, "FZ") {
        "freezing precipitation"
    } else if has(descriptor_codes, "TS") {
        "thunderstorm precipitation"
    } else if has(descriptor_codes, "SH") {
        "showery precipitation"
    } else {
        "unidentified precipitation"
    }
}

pub fn decode_weather(token: &str) -> Option<String> {
    if token.is_empty() {
        return None;
    }
    let mut working: &str = token;
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
    let chars: Vec<char> = working.chars().collect();
    let mut descriptor_codes: Vec<String> = Vec::new();
    let mut descriptors: Vec<&str> = Vec::new();
    let mut phenomenon_codes: Vec<String> = Vec::new();
    let mut phenomena: Vec<&str> = Vec::new();
    for pair in chars.chunks(2) {
        let code: String = pair.iter().collect();
        if let Some(d) = descriptor(&code) {
            descriptor_codes.push(code);
            descriptors.push(d);
        } else if let Some(p) = phenomenon(&code) {
            phenomenon_codes.push(code);
            phenomena.push(p);
        } else {
            break;
        }
    }
    if phenomenon_codes.iter().any(|c| c == "UP") {
        let inferred = infer_unknown_precipitation_label(&descriptor_codes, &phenomenon_codes);
        let known: Vec<&str> = phenomenon_codes
            .iter()
            .zip(&phenomena)
            .filter(|(c, _)| *c != "UP")
            .map(|(_, p)| *p)
            .collect();
        phenomena = if inferred == "mixed precipitation" || known.is_empty() {
            vec![inferred]
        } else {
            known
        };
    }
    if descriptors.is_empty() && phenomena.is_empty() && intensity.is_empty() {
        return None;
    }
    let descriptor_text = descriptors.join(" ");
    let phenomena_text = phenomena.join(" and ");
    let mut pieces: Vec<&str> = [intensity, descriptor_text.trim(), phenomena_text.trim()]
        .into_iter()
        .filter(|p| !p.is_empty())
        .collect();
    if pieces.is_empty() {
        pieces.push("weather conditions");
    }
    let description = pieces.join(" ").replace("  ", " ");
    Some(format!("{qualifier}{} ({token})", description.trim()))
}

fn with_thousands(n: u32) -> String {
    let s = n.to_string();
    let mut out = String::new();
    for (i, c) in s.chars().enumerate() {
        if i > 0 && (s.len() - i).is_multiple_of(3) {
            out.push(',');
        }
        out.push(c);
    }
    out
}

/// `CLOUD_RE`: `^(FEW|SCT|BKN|OVC|NSC|SKC|CLR|VV)(\d{3}|///)?(CB|TCU|///)?$`.
fn match_cloud(token: &str) -> Option<(&str, Option<&str>, Option<&str>)> {
    let cover = ["FEW", "SCT", "BKN", "OVC", "NSC", "SKC", "CLR", "VV"]
        .into_iter()
        .find(|c| token.starts_with(c))?;
    let rest = &token[cover.len()..];
    let tail_ok = |t: &str| matches!(t, "" | "CB" | "TCU" | "///");
    let tail = |t: &'static str| (!t.is_empty()).then_some(t);
    if let Some(h) = rest.get(..3).filter(|h| digits_n(h, 3) || *h == "///") {
        let after = &rest[3..];
        if tail_ok(after) {
            let t = ["CB", "TCU", "///"].into_iter().find(|t| *t == after);
            return Some((cover, Some(h), t.and_then(tail)));
        }
    }
    if tail_ok(rest) {
        let t = ["CB", "TCU", "///"].into_iter().find(|t| *t == rest);
        return Some((cover, None, t.and_then(tail)));
    }
    None
}

pub fn decode_cloud(token: &str) -> Option<String> {
    if token.is_empty() {
        return None;
    }
    if token == "SKC" || token == "CLR" {
        return Some(format!("Sky clear ({token})"));
    }
    if token == "NSC" {
        return Some("No significant clouds (NSC)".into());
    }
    let (cover, height, cloud_type) = match_cloud(token)?;
    let cover_text = match cover {
        "FEW" => "A few clouds",
        "SCT" => "Scattered clouds",
        "BKN" => "Broken clouds",
        "OVC" => "Overcast",
        "VV" => "Vertical visibility",
        other => other,
    };
    let altitude = height.filter(|h| is_digits(h)).map(|h| num(h) * 100);
    if cover == "VV" {
        if let Some(a) = altitude {
            return Some(format!(
                "Vertical visibility {} feet ({token})",
                with_thousands(a)
            ));
        }
    }
    let altitude_text = altitude
        .map(|a| format!(" at {} feet", with_thousands(a)))
        .unwrap_or_default();
    let type_text = match cloud_type {
        Some("CB") => " with cumulonimbus",
        Some("TCU") => " with towering cumulus",
        _ => "",
    };
    Some(format!("{cover_text}{altitude_text}{type_text} ({token})"))
}

// ---------------------------------------------------------------------------
// segments
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, PartialEq)]
enum SegmentKind {
    Base,
    From(String),
    Tempo(Option<String>),
    Becmg(Option<String>),
    Probability {
        prob: u32,
        period: Option<String>,
        tempo: bool,
    },
}

#[derive(Debug, Clone)]
struct Segment {
    kind: SegmentKind,
    tokens: Vec<String>,
}

fn new_change_segment(tokens: &[String], index: usize) -> Option<(SegmentKind, usize)> {
    let token = tokens[index].as_str();
    let next_range = |i: usize| tokens.get(i).filter(|t| is_time_range(t)).cloned();
    if is_fm_time(token) {
        return Some((SegmentKind::From(token[2..].to_string()), index + 1));
    }
    for (prefix, tempo) in [("TEMPO", true), ("BECMG", false)] {
        if let Some(period) = match_prefixed_period(token, prefix) {
            let mut next = index + 1;
            let mut period = period.map(str::to_string);
            if period.is_none() {
                if let Some(r) = next_range(next) {
                    period = Some(r);
                    next += 1;
                }
            }
            let kind = if tempo {
                SegmentKind::Tempo(period)
            } else {
                SegmentKind::Becmg(period)
            };
            return Some((kind, next));
        }
    }
    let (prob, period) = match_prob(token)?;
    let mut period = period.map(str::to_string);
    let mut next = index + 1;
    if period.is_none() {
        if let Some(r) = next_range(next) {
            period = Some(r);
            next += 1;
        }
    }
    let mut tempo = false;
    if tokens.get(next).is_some_and(|t| t.starts_with("TEMPO")) {
        tempo = true;
        let tempo_match = match_prefixed_period(&tokens[next], "TEMPO");
        next += 1;
        match tempo_match {
            Some(Some(p)) => period = Some(p.to_string()),
            Some(None) => {
                if let Some(r) = next_range(next) {
                    period = Some(r);
                    next += 1;
                }
            }
            None => {}
        }
    }
    Some((
        SegmentKind::Probability {
            prob,
            period,
            tempo,
        },
        next,
    ))
}

fn split_segments(tokens: &[String]) -> (Vec<Segment>, Option<String>) {
    let mut segments = vec![Segment {
        kind: SegmentKind::Base,
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
        if let Some(current) = segments.last_mut() {
            current.tokens.push(tokens[i].clone());
        }
        i += 1;
    }
    let first = segments[0].clone();
    let filtered: Vec<Segment> = segments
        .into_iter()
        .filter(|s| !s.tokens.is_empty())
        .collect();
    (
        if filtered.is_empty() {
            vec![first]
        } else {
            filtered
        },
        remarks,
    )
}

fn segment_intro(kind: &SegmentKind) -> String {
    match kind {
        SegmentKind::Base => "Base forecast:".into(),
        SegmentKind::From(t) => format!("From {}:", format_from_time(t)),
        SegmentKind::Tempo(Some(p)) => format!("Temporary between {}:", format_time_range(p)),
        SegmentKind::Tempo(None) => "Temporary conditions:".into(),
        SegmentKind::Becmg(Some(p)) => format!("Becoming {}:", format_time_range(p)),
        SegmentKind::Becmg(None) => "Becoming conditions:".into(),
        SegmentKind::Probability {
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

fn describe_segment(tokens: &[String]) -> String {
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
        let token = tokens[i].as_str();
        let next = tokens.get(i + 1).map(String::as_str);
        if is_digits(token)
            && next.is_some_and(|n| !n.is_empty() && n.ends_with("SM") && n.contains('/'))
        {
            if let Some(v) = decode_visibility(&format!("{token} {}", next.unwrap_or(""))) {
                if visibility.as_deref().is_none_or(str::is_empty) {
                    visibility = Some(v);
                } else {
                    weather.push(v);
                }
            }
            i += 2;
            continue;
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

/// `decode_taf_text`: a raw TAF as an accessible summary.
pub fn decode_taf_text(raw_taf: &str) -> String {
    let cleaned = raw_taf.split_whitespace().collect::<Vec<_>>().join(" ");
    if cleaned.is_empty() {
        return "No TAF available.".into();
    }
    let mut working: Vec<String> = cleaned
        .split(' ')
        .filter(|t| !t.is_empty() && *t != "=")
        .map(|t| t.trim_end_matches('=').to_string())
        .collect();
    if working.is_empty() {
        return "No TAF available.".into();
    }
    while working
        .first()
        .is_some_and(|t| matches!(t.as_str(), "TAF" | "AMD" | "COR"))
    {
        working.remove(0);
    }
    let station = (!working.is_empty()).then(|| working.remove(0));
    let station = station.filter(|s| !s.is_empty());
    if working.is_empty() {
        return match station {
            Some(s) => format!("TAF issued for station {s}."),
            None => "TAF issued, but no additional information was provided.".into(),
        };
    }
    if working[0] == "NIL" {
        let station_text = station
            .map(|s| format!(" for station {s}"))
            .unwrap_or_default();
        return format!("No TAF available{station_text}.");
    }
    let issue_time = is_issue_time(&working[0]).then(|| working.remove(0));
    let validity = if working.first().is_some_and(|t| is_time_range(t)) {
        Some(working.remove(0))
    } else {
        None
    };
    let (segments, remarks) = split_segments(&working);

    let mut lines = vec![match &station {
        Some(s) => format!("Forecast for station {s}."),
        None => "Terminal Aerodrome Forecast.".into(),
    }];
    if let Some(t) = issue_time {
        lines.push(format!("Issued at {}.", format_issue_time(&t)));
    }
    if let Some(v) = validity {
        lines.push(format!("Valid {}.", format_time_range(&v)));
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn decodes_a_full_taf() {
        let raw = "TAF KJFK 251730Z 2518/2624 18010G20KT P6SM BKN030CB \
                   FM260000 20008KT 3SM -RA BR OVC015 \
                   TEMPO 2604/2608 1 1/2SM +TSRA \
                   PROB30 2610/2614 VCSH RMK NXT FCST BY 00Z=";
        let text = decode_taf_text(raw);
        assert_eq!(
            text,
            "Forecast for station KJFK.\n\
             Issued at 17:30 UTC on the 25th.\n\
             Valid from 18:00 UTC on the 25th until 24:00 UTC on the 26th.\n\
             Base forecast: Winds from 180 degrees at 10 knots with gusts to 20 knots (18010G20KT). Visibility greater than 6 statute miles (6 SM) (P6SM). Clouds: Broken clouds at 3,000 feet with cumulonimbus (BKN030CB).\n\
             From 00:00 UTC on the 26th: Winds from 200 degrees at 8 knots (20008KT). Visibility 3 statute miles (3 SM) (3SM). Weather: light rain (-RA); mist (BR). Clouds: Overcast at 1,500 feet (OVC015).\n\
             Temporary between from 04:00 UTC on the 26th until 08:00 UTC on the 26th: Visibility 1 1/2 statute miles (1.5 SM) (1 1/2SM). Weather: heavy thunderstorms with rain (+TSRA).\n\
             Probability 30% from 10:00 UTC on the 26th until 14:00 UTC on the 26th: Weather: In the vicinity, showers of (VCSH).\n\
             Remarks: NXT FCST BY 00Z."
        );
    }

    #[test]
    fn header_only_and_nil() {
        assert_eq!(decode_taf_text("   "), "No TAF available.");
        assert_eq!(decode_taf_text("TAF KJFK"), "TAF issued for station KJFK.");
        assert_eq!(
            decode_taf_text("TAF KJFK NIL="),
            "No TAF available for station KJFK."
        );
    }

    #[test]
    fn unknown_precipitation_is_named() {
        assert_eq!(
            decode_weather("FZUP").unwrap(),
            "freezing freezing precipitation (FZUP)"
        );
        assert_eq!(
            decode_weather("RAUP").unwrap(),
            "mixed precipitation (RAUP)"
        );
        assert_eq!(decode_weather("BLDU").unwrap(), "blowing dust (BLDU)");
        assert_eq!(
            decode_cloud("VV002").unwrap(),
            "Vertical visibility 200 feet (VV002)"
        );
        assert_eq!(
            decode_visibility("9999").unwrap(),
            "Visibility 10 kilometres or more (9999 meters)"
        );
        assert_eq!(
            decode_visibility("0800").unwrap(),
            "Visibility 0.8 kilometres (0800 meters)"
        );
    }
}
