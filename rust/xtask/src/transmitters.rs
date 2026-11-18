//! `cargo xtask nwr-transmitters`: regenerate
//! `crates/aw-radio/data/nwr_transmitters.json` from weather.gov's NOAA
//! Weather Radio station data (every transmitter, its site, frequency,
//! status and the SAME counties it covers).

use std::collections::BTreeSet;

use serde_json::{json, Value};

use crate::Result;

const SOURCE_URL: &str = "https://www.weather.gov/source/nwr/JS/ccl-data.js";
const USER_AGENT: &str = "AccessiWeather-Build/1.0 (https://github.com/Orinks/AccessiWeather)";

pub fn run() -> Result<()> {
    let client = reqwest::blocking::Client::builder()
        .user_agent(USER_AGENT)
        .timeout(std::time::Duration::from_secs(60))
        .build()?;
    let text = client.get(SOURCE_URL).send()?.error_for_status()?.text()?;
    let transmitters = parse(&text)?;
    let date = chrono::Utc::now().format("%Y-%m-%d").to_string();
    let out = render(&transmitters, &date);
    let path = crate::rust_dir().join("crates/aw-radio/data/nwr_transmitters.json");
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(&path, out)?;
    eprintln!(
        "Wrote {} transmitters to {}",
        transmitters.len(),
        path.display()
    );
    Ok(())
}

/// `var cclData = [ ... ];` → one compact object per transmitter, sorted by
/// state then call sign. Entries without a call sign, state, frequency or
/// coordinates are skipped.
fn parse(text: &str) -> Result<Vec<Value>> {
    let (Some(start), Some(end)) = (text.find('['), text.rfind(']')) else {
        return Err("ccl-data.js holds no array".into());
    };
    let entries: Vec<Value> = serde_json::from_str(&text[start..=end])?;
    let mut out = Vec::new();
    for entry in &entries {
        let text = |key: &str| entry.get(key).and_then(Value::as_str).unwrap_or("").trim();
        let number = |key: &str| match entry.get(key) {
            Some(Value::Number(n)) => n.as_f64(),
            Some(Value::String(s)) => s.trim().parse::<f64>().ok(),
            _ => None,
        };
        let call_sign = text("callsign").to_uppercase();
        let state = text("sitestate").to_uppercase();
        let (Some(frequency), Some(lat), Some(lon)) =
            (number("freq"), number("lat"), number("lon"))
        else {
            continue;
        };
        if call_sign.is_empty() || state.len() != 2 {
            continue;
        }
        let site = Some(text("siteloc"))
            .filter(|s| !s.is_empty())
            .unwrap_or_else(|| text("sitename"));
        let same: BTreeSet<String> = entry
            .get("counties")
            .and_then(Value::as_array)
            .into_iter()
            .flatten()
            .filter_map(|c| c.get("same").and_then(Value::as_str))
            .map(str::trim)
            .filter(|c| c.len() == 6 && c.bytes().all(|b| b.is_ascii_digit()))
            .map(str::to_string)
            .collect();
        out.push(json!({
            "call_sign": call_sign,
            "frequency": frequency,
            "site": site,
            "state": state,
            "lat": lat,
            "lon": lon,
            "status": text("status").to_uppercase(),
            "same": same,
        }));
    }
    out.sort_by(|a, b| {
        (a["state"].as_str(), a["call_sign"].as_str())
            .cmp(&(b["state"].as_str(), b["call_sign"].as_str()))
    });
    out.dedup_by(|a, b| a["call_sign"] == b["call_sign"]);
    if out.len() < 500 {
        return Err(format!("only {} transmitters parsed; refusing to write", out.len()).into());
    }
    Ok(out)
}

/// One transmitter per line, so a refresh diffs cleanly.
fn render(transmitters: &[Value], date: &str) -> String {
    let lines: Vec<String> = transmitters
        .iter()
        .map(|t| format!("    {}", serde_json::to_string(t).unwrap_or_default()))
        .collect();
    format!(
        "{{\n  \"source\": {},\n  \"retrieved\": {},\n  \"transmitters\": [\n{}\n  ]\n}}\n",
        json!(SOURCE_URL),
        json!(date),
        lines.join(",\n")
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_cleans_sorts_and_renders() {
        let mut entries = vec![
            r#"{"freq":"162.450","wfo":"Kansas City|MO","status":"NORMAL","sitestate":"MO","counties":[{"county":"Chariton","same":"029041","st":"MO"},{"county":"Carroll","same":"029033"},{"same":"029033"},{"same":"bad"}],"lon":"-93.403556","siteloc":"Carrollton","lat":"39.3665","sitename":"Carrollton","callsign":"KZZ34"}"#.to_string(),
            r#"{"lon":"-153.376944","siteloc":"","sitename":"Raspberry Island","lat":"58.066389","callsign":"KZZ90","freq":"162.425","counties":[],"sitestate":"AK","status":"out of service"}"#.to_string(),
            r#"{"callsign":"NOPOS","freq":"162.4","sitestate":"TX"}"#.to_string(),
        ];
        // Pad past the sanity floor with distinct filler stations.
        for i in 0..600 {
            entries.push(format!(
                r#"{{"callsign":"WZZ{i:03}","freq":162.5,"lat":30,"lon":-90,"sitestate":"ZZ","siteloc":"X"}}"#
            ));
        }
        let text = format!("var cclData = [{}];\n", entries.join(","));
        let parsed = parse(&text).unwrap();
        assert_eq!(parsed.len(), 602);
        assert_eq!(parsed[0]["call_sign"], "KZZ90");
        assert_eq!(parsed[0]["site"], "Raspberry Island");
        assert_eq!(parsed[0]["status"], "OUT OF SERVICE");
        assert_eq!(parsed[1]["call_sign"], "KZZ34");
        assert_eq!(parsed[1]["frequency"], 162.45);
        assert_eq!(parsed[1]["same"], json!(["029033", "029041"]));

        let rendered = render(&parsed[..2], "2026-11-07");
        let value: Value = serde_json::from_str(&rendered).unwrap();
        assert_eq!(value["transmitters"].as_array().unwrap().len(), 2);
        assert_eq!(rendered.lines().count(), 8);

        assert!(parse("var cclData = [];").is_err());
        assert!(parse("nothing").is_err());
    }
}
