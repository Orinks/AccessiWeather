//! `scripts/check_streams.py`: probe every bundled NOAA Weather Radio stream
//! URL (`aw_radio::stream_url::bundled_stream_urls`) and report dead ones.

use std::collections::BTreeSet;
use std::io::Read;
use std::time::{Duration, Instant};

use serde_json::{json, Map, Value};

use crate::Result;

const USER_AGENT: &str = "AccessiWeather-StreamCheck/1.0";

#[derive(clap::Args)]
pub struct Args {
    /// Connection timeout per URL (seconds)
    #[arg(long, default_value_t = 10)]
    timeout: u64,
    /// Output results as JSON
    #[arg(long)]
    json: bool,
    /// Exit with code 1 if any streams are dead or errored
    #[arg(long)]
    fail_on_errors: bool,
}

pub fn run(args: &Args) -> Result<u8> {
    let client = reqwest::blocking::Client::builder()
        .user_agent(USER_AGENT)
        .timeout(Duration::from_secs(args.timeout))
        .build()?;
    let mut stations = aw_radio::stream_url::bundled_stream_urls().to_vec();
    stations.sort_by_key(|(call_sign, _)| *call_sign);
    let total_streams: usize = stations.iter().map(|(_, urls)| urls.len()).sum();
    eprintln!(
        "Checking {} stations with {total_streams} total streams...\n",
        stations.len()
    );

    let mut checked = 0;
    let mut healthy = 0;
    let mut errors = Vec::new();
    let mut dead = BTreeSet::new();
    for (call_sign, urls) in &stations {
        let mut station_ok = false;
        for url in urls.iter() {
            checked += 1;
            let mut result = check_url(&client, url, args.timeout);
            result.insert("call_sign".into(), json!(call_sign));
            if result["status"] == "ok" {
                healthy += 1;
                station_ok = true;
            } else {
                if !args.json {
                    eprintln!(
                        "  ✗ {call_sign}: {url} — {}",
                        result["error"].as_str().unwrap_or("")
                    );
                }
                errors.push(Value::Object(result));
            }
        }
        if !station_ok && !urls.is_empty() {
            dead.insert(*call_sign);
        }
    }

    let summary = json!({
        "total_stations": stations.len(),
        "total_urls_checked": checked,
        "healthy_urls": healthy,
        "errored_urls": errors.len(),
        "dead_station_call_signs": dead,
        "all_errors": errors,
        "summary": {
            "healthy_ratio": if checked > 0 { healthy as f64 / checked as f64 } else { 0.0 },
            "dead_station_count": dead.len(),
        },
    });
    if args.json {
        println!("{}", serde_json::to_string_pretty(&summary)?);
    } else {
        eprintln!("\n{}", "=".repeat(60));
        eprintln!("Stream Check Complete:");
        eprintln!("  Total Stations: {}", stations.len());
        eprintln!("  Total URLs Checked: {checked}");
        eprintln!("  Healthy URLs: {healthy}");
        eprintln!("  Errored URLs: {}", errors.len());
        if !dead.is_empty() {
            eprintln!("\nStations with NO working streams ({}):", dead.len());
            for call_sign in &dead {
                eprintln!("  - {call_sign}");
            }
        } else if errors.is_empty() {
            eprintln!("\nAll streams are healthy ✓");
        }
        println!("\n--- All Errored URLs ---");
        if errors.is_empty() {
            println!("  No errors found.");
        }
        for e in &errors {
            println!(
                "  {}: {} — {} (Response Time: {}ms)",
                e["call_sign"].as_str().unwrap_or(""),
                e["url"].as_str().unwrap_or(""),
                e["error"].as_str().unwrap_or(""),
                e["response_time_ms"]
            );
        }
    }
    Ok(u8::from(
        args.fail_on_errors && (!errors.is_empty() || !dead.is_empty()),
    ))
}

/// GET `url` and read up to 1 KB to confirm audio is flowing.
fn check_url(client: &reqwest::blocking::Client, url: &str, timeout: u64) -> Map<String, Value> {
    let start = Instant::now();
    let (status, error, content_type) = match client.get(url).header("Icy-MetaData", "1").send() {
        Ok(response) if !response.status().is_success() => {
            let s = response.status();
            let reason = s.canonical_reason().unwrap_or("");
            (
                "http_error",
                Some(format!("HTTP {}: {reason}", s.as_u16())),
                None,
            )
        }
        Ok(response) => {
            let content_type = response
                .headers()
                .get(reqwest::header::CONTENT_TYPE)
                .and_then(|v| v.to_str().ok())
                .unwrap_or("N/A")
                .to_string();
            let mut chunk = Vec::new();
            match response.take(1024).read_to_end(&mut chunk) {
                Err(e) => failure(&e, timeout),
                Ok(_) if chunk.is_empty() => (
                    "empty_stream",
                    Some("No data received from stream".into()),
                    None,
                ),
                Ok(_) => {
                    let (status, error) = classify_content_type(&content_type);
                    (status, error, Some(content_type))
                }
            }
        }
        Err(e) => failure(&e, timeout),
    };
    let mut result = Map::new();
    result.insert("url".into(), json!(url));
    result.insert("status".into(), json!(status));
    result.insert("error".into(), json!(error));
    result.insert(
        "response_time_ms".into(),
        json!(start.elapsed().as_millis() as u64),
    );
    if let Some(content_type) = content_type {
        result.insert("content_type".into(), json!(content_type));
    }
    result
}

/// A stream that answers with HTML or plain text isn't audio.
fn classify_content_type(content_type: &str) -> (&'static str, Option<String>) {
    let lower = content_type.to_lowercase();
    if lower.contains("html") || lower.contains("text/plain") && !lower.contains("audio") {
        (
            "non_stream_content",
            Some(format!("Expected audio, got content type: {content_type}")),
        )
    } else {
        ("ok", None)
    }
}

/// Python's `except` ladder: timeouts, connection failures (`URLError`),
/// anything else.
fn failure(
    error: &(dyn std::error::Error + 'static),
    timeout: u64,
) -> (&'static str, Option<String>, Option<String>) {
    let chain = || std::iter::successors(Some(error), |e| e.source());
    let timed_out = chain().any(|e| {
        e.downcast_ref::<reqwest::Error>()
            .is_some_and(reqwest::Error::is_timeout)
            || e.downcast_ref::<std::io::Error>()
                .is_some_and(|io| io.kind() == std::io::ErrorKind::TimedOut)
    });
    if timed_out {
        let message = format!("Connection timed out after {timeout}s");
        return ("timeout", Some(message), None);
    }
    let connect = |e: &(dyn std::error::Error + 'static)| {
        e.downcast_ref::<reqwest::Error>()
            .is_some_and(reqwest::Error::is_connect)
    };
    // The innermost cause, like Python's `e.reason` ("dns error: ...").
    let reason = chain().last().unwrap_or(error).to_string();
    if chain().any(connect) {
        return ("url_error", Some(reason), None);
    }
    ("error", Some(reason), None)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn only_audio_counts_as_a_stream() {
        assert_eq!(classify_content_type("audio/mpeg").0, "ok");
        assert_eq!(classify_content_type("N/A").0, "ok");
        assert_eq!(classify_content_type("text/plain; audio").0, "ok");
        let (status, error) = classify_content_type("text/HTML; charset=utf-8");
        assert_eq!(status, "non_stream_content");
        assert_eq!(
            error.unwrap(),
            "Expected audio, got content type: text/HTML; charset=utf-8"
        );
        assert_eq!(classify_content_type("text/plain").0, "non_stream_content");
    }
}
