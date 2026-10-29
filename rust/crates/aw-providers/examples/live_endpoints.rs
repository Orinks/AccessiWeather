//! Live check of every outside service the international work talks to.
//! It runs the app's own provider code against the real endpoints and
//! prints PASS or FAIL per check, with what came back.
//!
//!     cargo run -p aw-providers --example live_endpoints
//!
//! Set OPENAQ_API_KEY to also check OpenAQ (free key from explore.openaq.org).

use std::sync::Arc;

use aw_core::air_quality::{AqiPreference, AqiStandard};
use aw_core::model::{Location, Timestamp};
use aw_providers::environmental::openaq::OpenAqClient;
use aw_providers::environmental::{EnvironmentalDataClient, FetchOptions};
use aw_providers::geocoding::LocationManager;
use aw_providers::http::{HttpClient, ReqwestClient};
use aw_providers::regional::{self, default_sources, fetch_local_readings};

const UA: &str = "AccessiWeather live endpoint check";

fn place(name: &str, lat: f64, lon: f64, country: &str, tz: &str) -> Location {
    Location {
        name: name.into(),
        latitude: lat,
        longitude: lon,
        country_code: Some(country.into()),
        timezone: Some(tz.into()),
        ..Location::default()
    }
}

struct Tally(usize, usize);
impl Tally {
    fn check(&mut self, name: &str, ok: bool, detail: impl AsRef<str>) {
        if ok {
            self.0 += 1
        } else {
            self.1 += 1
        }
        println!(
            "{} {name}\n    {}",
            if ok { "PASS" } else { "FAIL" },
            detail.as_ref().replace('\n', "\n    ")
        );
    }
}

fn now() -> Timestamp {
    chrono::Utc::now().fixed_offset()
}

fn main() {
    let http: Arc<dyn HttpClient> = Arc::new(ReqwestClient::new().expect("HTTP client"));
    let mut t = Tally(0, 0);

    // Location search with a country filter, a non-US postcode, and coordinates.
    let lm = LocationManager::new(http.as_ref());
    for (query, country, lang, expect) in [
        ("Paris", Some("FR"), Some("fr"), "FR"),
        ("Paris", Some("US"), Some("en"), "US"),
        ("10115", Some("DE"), Some("de"), "DE"),
        ("Singapore", None, Some("en"), "SG"),
        ("1.35, 103.82", None, Some("en"), ""),
    ] {
        let label = format!(
            "Location search {query:?} in {}",
            country.unwrap_or("any country")
        );
        match lm.search_location_results(query, 10, country, lang) {
            Ok(r) => {
                let first = r.first();
                let ok = first.is_some()
                    && (expect.is_empty()
                        || first.unwrap().location.country_code.as_deref() == Some(expect));
                let lines: Vec<String> = r
                    .iter()
                    .take(3)
                    .map(|x| {
                        format!(
                            "{} | {} | {} ({:.3}, {:.3}) cc={:?}",
                            x.location.name,
                            x.region,
                            x.country,
                            x.location.latitude,
                            x.location.longitude,
                            x.location.country_code
                        )
                    })
                    .collect();
                t.check(
                    &label,
                    ok,
                    if lines.is_empty() {
                        "no results".into()
                    } else {
                        lines.join("\n")
                    },
                );
            }
            Err(e) => t.check(&label, false, e.to_string()),
        }
    }

    // Open-Meteo air quality on both indexes, with the per-pollutant detail.
    let env = EnvironmentalDataClient::new(http.clone(), UA, "");
    let berlin = place("Berlin", 52.52, 13.405, "DE", "Europe/Berlin");
    let denver = place("Denver", 39.7392, -104.9903, "US", "America/Denver");
    for (loc, standard) in [(&berlin, AqiStandard::European), (&denver, AqiStandard::Us)] {
        let label = format!("Hourly air quality, {standard:?} index, {}", loc.name);
        match env.fetch_hourly_air_quality(loc, 6, now(), standard) {
            Some(h) => t.check(
                &label,
                !h.is_empty(),
                format!("{} hours, first: {:?}", h.len(), h[0]),
            ),
            None => t.check(&label, false, "no data"),
        }
    }
    for loc in [&berlin, &denver] {
        let options = FetchOptions {
            include_air_quality: true,
            include_pollen: false,
            include_hourly_air_quality: false,
            include_hourly_uv: false,
            hourly_hours: 0,
            prefer_airnow: false,
            aqi_preference: AqiPreference::Auto,
            pollutant_detail: true,
        };
        let label = format!("Current air quality with pollutant list, {}", loc.name);
        match env.fetch(loc, options, now()) {
            Some(e) => {
                let rows: Vec<String> = e
                    .pollutant_readings
                    .iter()
                    .map(|p| format!("{p:?}"))
                    .collect();
                t.check(
                    &label,
                    e.air_quality_index.is_some() && !rows.is_empty(),
                    format!(
                        "AQI {:?} ({:?}) on {:?} from {:?}\n{}",
                        e.air_quality_index,
                        e.air_quality_category,
                        e.air_quality_index_standard,
                        e.sources,
                        rows.join("\n")
                    ),
                );
            }
            None => t.check(&label, false, "no data"),
        }
    }

    // OpenAQ (needs a key).
    match std::env::var("OPENAQ_API_KEY")
        .ok()
        .filter(|k| !k.trim().is_empty())
    {
        None => println!("SKIP OpenAQ (set OPENAQ_API_KEY to check it)"),
        Some(key) => {
            let client = OpenAqClient::new(http.clone(), key.trim(), UA);
            let (valid, why) = client.validate_api_key();
            t.check("OpenAQ key check", valid, format!("{why:?}"));
            for loc in [
                &berlin,
                &denver,
                &place("Singapore", 1.3521, 103.8198, "SG", "Asia/Singapore"),
            ] {
                let label = format!("OpenAQ nearest station, {}", loc.name);
                match client.fetch_nearest(loc, now()) {
                    Ok(Some(s)) => t.check(
                        &label,
                        !s.readings.is_empty(),
                        format!(
                            "{} ({:.1} km, monitor={}), {} readings: {:?}",
                            s.display_name(),
                            s.distance_km.unwrap_or(f64::NAN),
                            s.is_monitor,
                            s.readings.len(),
                            s.readings
                        ),
                    ),
                    Ok(None) => t.check(
                        &label,
                        true,
                        "no station within 25 km with recent data (allowed)",
                    ),
                    Err(e) => t.check(&label, false, e.to_string()),
                }
            }
        }
    }

    // Local Readings: every regional source on its own, then the full report.
    let places = [
        place("Singapore", 1.3521, 103.8198, "SG", "Asia/Singapore"),
        berlin.clone(),
        place("Tokyo", 35.6762, 139.6503, "JP", "Asia/Tokyo"),
        place("Nairobi", -1.2921, 36.8219, "KE", "Africa/Nairobi"),
        denver.clone(),
    ];
    let sources = default_sources();
    for loc in &places {
        for source in sources.iter().filter(|s| s.covers(loc)) {
            let label = format!("{} for {}", source.name(), loc.name);
            match source.fetch(http.as_ref(), loc) {
                Ok(r) => t.check(
                    &label,
                    !r.is_empty(),
                    r.iter()
                        .map(|x| {
                            format!(
                                "{}: {}{} | {} {:?} | {:?}",
                                x.label,
                                x.value,
                                x.detail
                                    .as_ref()
                                    .map(|d| format!(" ({d})"))
                                    .unwrap_or_default(),
                                x.coverage.name,
                                x.coverage.distance_km,
                                x.time
                            )
                        })
                        .collect::<Vec<_>>()
                        .join("\n"),
                ),
                Err(e) => t.check(&label, false, e.to_string()),
            }
        }
        let report = fetch_local_readings(http.as_ref(), loc, &sources);
        t.check(
            &format!("Full Local Readings report for {}", loc.name),
            report.failures.is_empty(),
            format!(
                "{} readings from {:?}, failures {:?}",
                report.readings.len(),
                report.sources,
                report.failures
            ),
        );
    }
    let _ = regional::distance_km;

    println!("\n{} passed, {} failed", t.0, t.1);
    if t.1 > 0 {
        std::process::exit(1);
    }
}
