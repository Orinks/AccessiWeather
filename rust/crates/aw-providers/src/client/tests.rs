use std::collections::HashSet;
use std::sync::{Arc, Mutex};

use aw_core::golden::{self, assert_json_eq, field};
use aw_core::model::{
    AviationData, CurrentConditions, EnvironmentalConditions, Forecast, HourlyForecast,
    HourlyForecastPeriod, MinutelyPrecipitationForecast, Timestamp,
};
use chrono::TimeZone;
use serde::de::DeserializeOwned;
use serde_json::{json, Value};

use super::enrichment::build_marine_highlights;
use super::*;

/// Every data source, scripted from a golden scenario's fake table:
/// `{source: {call: {"value": ...} | {"error": "..."}}}`. Calls are logged
/// with the same names the Python harness records.
#[derive(Default)]
struct Fakes {
    table: Mutex<Value>,
    log: Mutex<Vec<String>>,
}

impl Fakes {
    fn get<T: DeserializeOwned>(&self, name: &str, source: &str, call: &str) -> SourceResult<T> {
        self.log.lock().unwrap().push(name.to_string());
        self.peek(source, call)
    }

    fn peek<T: DeserializeOwned>(&self, source: &str, call: &str) -> SourceResult<T> {
        let entry = self.table.lock().unwrap()[source][call].clone();
        if let Some(error) = entry.get("error").and_then(Value::as_str) {
            return Err(SourceError::new(error));
        }
        Ok(serde_json::from_value(entry["value"].clone())
            .unwrap_or_else(|e| panic!("fake {source}.{call}: {e}")))
    }
}

type Nws6 = (
    Option<CurrentConditions>,
    Option<Forecast>,
    Option<String>,
    Option<Timestamp>,
    Option<WeatherAlerts>,
    Option<HourlyForecast>,
);

impl NwsSource for Fakes {
    fn get_all_data(&self, _: &Location, _: &str) -> SourceResult<NwsAllData> {
        let (current, forecast, discussion, discussion_issuance_time, alerts, hourly_forecast): Nws6 =
            self.get("nws.all", "nws", "all")?;
        Ok(NwsAllData {
            current,
            forecast,
            discussion,
            discussion_issuance_time,
            alerts,
            hourly_forecast,
        })
    }
    fn get_forecast_and_discussion(
        &self,
        _: &Location,
    ) -> SourceResult<(Option<Forecast>, Option<String>, Option<Timestamp>)> {
        self.get(
            "nws.forecast_and_discussion",
            "nws",
            "forecast_and_discussion",
        )
    }
    fn get_discussion_only(
        &self,
        _: &Location,
    ) -> SourceResult<(Option<String>, Option<Timestamp>)> {
        self.get("nws.discussion_only", "nws", "discussion_only")
    }
    fn get_alerts(&self, _: &Location, _: &str) -> SourceResult<Option<WeatherAlerts>> {
        self.get("nws.alerts", "nws", "alerts")
    }
    fn fetch_cancel_references(&self, lookback_minutes: i64) -> HashSet<String> {
        assert_eq!(lookback_minutes, 15);
        self.get("nws.cancel_refs", "nws", "cancel_refs")
            .unwrap_or_default()
    }
}

impl OpenMeteoSource for Fakes {
    fn get_all_data(
        &self,
        _: &Location,
        _: i64,
        _: i64,
    ) -> SourceResult<(
        Option<CurrentConditions>,
        Option<Forecast>,
        Option<HourlyForecast>,
    )> {
        self.get("openmeteo.all", "openmeteo", "all")
    }
    fn get_current_conditions(&self, _: &Location) -> SourceResult<Option<CurrentConditions>> {
        self.get("openmeteo.current", "openmeteo", "current")
    }
}

impl PirateWeatherSource for Fakes {
    fn get_current_conditions(
        &self,
        _: &Location,
        _: &str,
    ) -> SourceResult<Option<CurrentConditions>> {
        self.get("pirateweather.current", "pirateweather", "current")
    }
    fn get_forecast(&self, _: &Location, _: i64, _: &str) -> SourceResult<Option<Forecast>> {
        self.get("pirateweather.forecast", "pirateweather", "forecast")
    }
    fn get_hourly_forecast(&self, _: &Location, _: &str) -> SourceResult<Option<HourlyForecast>> {
        self.get("pirateweather.hourly", "pirateweather", "hourly")
    }
    fn get_alerts(&self, _: &Location, _: &str) -> SourceResult<Option<WeatherAlerts>> {
        self.get("pirateweather.alerts", "pirateweather", "alerts")
    }
    fn get_minutely(&self, _: &Location, _: &str) -> Option<MinutelyPrecipitationForecast> {
        self.get("pirateweather.minutely", "pirateweather", "minutely")
            .ok()
            .flatten()
    }
}

impl EnvironmentalSource for Fakes {
    fn fetch(
        &self,
        _: &Location,
        _: bool,
        _: bool,
        _: bool,
        _: bool,
    ) -> SourceResult<Option<EnvironmentalConditions>> {
        self.log.lock().unwrap().push("environmental".into());
        let entry = self.table.lock().unwrap()["environmental"].clone();
        if let Some(error) = entry.get("error").and_then(Value::as_str) {
            return Err(SourceError::new(error));
        }
        Ok(serde_json::from_value(entry["value"].clone()).unwrap())
    }
}

impl AviationSource for Fakes {
    fn primary_station_info(&self, _: &Location) -> SourceResult<(Option<String>, Option<String>)> {
        self.get("aviation.station", "aviation", "station")
    }
    fn aviation_weather(&self, _: &str, _: &AviationOptions) -> SourceResult<AviationData> {
        self.get("aviation.weather", "aviation", "data")
    }
}

impl MarineSource for Fakes {
    fn marine_zones(&self, _: &Location) -> SourceResult<Value> {
        self.get("marine.zones", "marine", "zones")
    }
    fn marine_forecast(&self, _: &str) -> SourceResult<Option<Value>> {
        self.get("marine.forecast", "marine", "forecast")
    }
    fn marine_alerts(&self, _: &str) -> SourceResult<WeatherAlerts> {
        self.get("marine.alerts", "marine", "alerts")
    }
}

fn sources(fakes: &Arc<Fakes>, pirate: bool, environmental: bool) -> ClientSources {
    ClientSources {
        nws: fakes.clone(),
        openmeteo: fakes.clone(),
        pirate_weather: pirate.then(|| fakes.clone() as Arc<dyn PirateWeatherSource>),
        environmental: environmental.then(|| fakes.clone() as Arc<dyn EnvironmentalSource>),
        aviation: fakes.clone(),
        marine: fakes.clone(),
    }
}

fn settings_from(overrides: &Value) -> AppSettings {
    serde_json::from_value(overrides.clone()).expect("settings overrides")
}

/// Round-trip the expected location through `Location` so its
/// skip-if-default serialisation rules match ours.
fn normalized(mut weather: Value) -> Value {
    if let Some(location) = weather.get_mut("location") {
        let typed: Location = serde_json::from_value(location.clone()).unwrap();
        *location = serde_json::to_value(typed).unwrap();
    }
    weather
}

/// Merge a step's fake overrides (`{source: {call: entry}}`) into the table.
fn with_overrides(mut table: Value, overrides: &Value) -> Value {
    for (source, entries) in overrides.as_object().into_iter().flatten() {
        match (
            table.get_mut(source).and_then(Value::as_object_mut),
            entries.as_object(),
        ) {
            (Some(existing), Some(entries)) => existing.extend(entries.clone()),
            _ => table[source.as_str()] = entries.clone(),
        }
    }
    table
}

#[test]
fn golden_client_scenarios() {
    let dir = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../../testdata/golden/client");
    let mut files: Vec<_> = std::fs::read_dir(dir)
        .unwrap()
        .map(|e| e.unwrap().file_name().to_string_lossy().into_owned())
        .collect();
    files.sort();
    assert!(files.len() >= 30, "golden scenarios missing");
    for file in files {
        let scenario = golden::load(&format!("client/{file}"));
        let name = scenario["name"].as_str().unwrap();
        let fakes = Arc::new(Fakes::default());
        let environmental = !scenario["fakes"]["environmental"].is_null();
        let cache_dir = tempfile::tempdir().unwrap();
        let cache = scenario["cache"]
            .as_bool()
            .unwrap()
            .then(|| WeatherDataCache::new(cache_dir.path(), 180).unwrap());
        let now = Arc::new(Mutex::new(Utc::now()));
        let clock_now = now.clone();
        let client = WeatherClient::new(
            sources(&fakes, field(&scenario, "pirate"), environmental),
            settings_from(&scenario["settings"]),
            scenario["data_source"].as_str().unwrap(),
            cache,
        )
        .with_clock(Arc::new(move || *clock_now.lock().unwrap()));
        let location: Location = field(&scenario, "location");

        for (i, step) in scenario["steps"].as_array().unwrap().iter().enumerate() {
            *fakes.table.lock().unwrap() =
                with_overrides(scenario["fakes"].clone(), &step["fakes"]);
            *now.lock().unwrap() = field(step, "now");
            fakes.log.lock().unwrap().clear();
            let weather = match step["call"].as_str().unwrap() {
                "weather" => client.get_weather_data(&location, field(step, "force")),
                _ => client.get_notification_event_data(&location),
            };
            let context = format!("{name} step {i}");
            let mut requests = fakes.log.lock().unwrap().clone();
            requests.sort();
            let expected_requests: Vec<String> = field(step, "requests");
            assert_eq!(requests, expected_requests, "{context}");
            assert_json_eq(&weather, &normalized(step["weather"].clone()), &context);
        }
    }
}

// ---------------------------------------------------------------------------
// ported unit tests
// ---------------------------------------------------------------------------

fn us() -> Location {
    Location::new("New York", 40.7128, -74.006).with_country("US")
}

#[test]
fn location_key_matches_python_format() {
    assert_eq!(location_key(&us()), "40.7128,-74.0060");
    assert_eq!(
        location_key(&Location::new("x", 1.0, 2.123456)),
        "1.0000,2.1235"
    );
}

#[test]
fn marine_highlights_deduplicate_and_limit() {
    let periods = vec![
        json!({"shortForecast": "South winds 10 to 15 knots. Waves 1 to 2 feet.",
               "detailedForecast": "South winds 10 to 15 knots. Seas around 2 feet."}),
        json!({"shortForecast": "Gusts up to 20 knots. Swells 3 feet.",
               "detailedForecast": "Gusts up to 20 knots. Swells 3 feet."}),
        json!({"shortForecast": "North winds 5 knots.", "detailedForecast": ""}),
    ];
    assert_eq!(
        build_marine_highlights(&periods),
        [
            "South winds 10 to 15 knots",
            "Waves 1 to 2 feet",
            "Seas around 2 feet",
            "Gusts up to 20 knots"
        ]
    );
    let not_whole_word = vec![json!({"shortForecast": "Windy. Seasonal swelling."})];
    assert!(build_marine_highlights(&not_whole_word).is_empty());
}

fn fakes_with(table: Value) -> Arc<Fakes> {
    let fakes = Arc::new(Fakes::default());
    *fakes.table.lock().unwrap() = table;
    fakes
}

fn hourly_rain_at(start: DateTime<Utc>, hours_ahead: i64) -> HourlyForecast {
    HourlyForecast {
        periods: (0..8)
            .map(|h| HourlyForecastPeriod {
                precipitation_probability: Some(if h == hours_ahead { 60.0 } else { 0.0 }),
                ..HourlyForecastPeriod::new((start + Duration::hours(h)).fixed_offset())
            })
            .collect(),
        ..Default::default()
    }
}

#[test]
fn minutely_poll_cadence() {
    let t0 = Utc.with_ymd_and_hms(2026, 7, 15, 16, 0, 0).unwrap();
    let now = Arc::new(Mutex::new(t0));
    let clock_now = now.clone();
    let settings = AppSettings {
        update_interval_minutes: 3,
        minutely_precipitation_fast_polling: true,
        ..AppSettings::default()
    };
    let client = WeatherClient::new(
        sources(&fakes_with(json!({})), false, false),
        settings,
        "auto",
        None,
    )
    .with_clock(Arc::new(move || *clock_now.lock().unwrap()));
    let location = us();
    let key = location_key(&location);
    assert!(
        client.should_fetch_minutely_precipitation(&location),
        "never polled"
    );

    client.state().last_minutely_poll.insert(key.clone(), t0);
    *now.lock().unwrap() = t0 + Duration::minutes(14);
    assert!(
        !client.should_fetch_minutely_precipitation(&location),
        "15 minute floor"
    );
    *now.lock().unwrap() = t0 + Duration::minutes(15);
    assert!(client.should_fetch_minutely_precipitation(&location));

    // Rain likely within six hours: poll at the (shorter) update interval.
    let mut weather = WeatherData::new(location.clone());
    weather.hourly_forecast = Some(hourly_rain_at(t0, 5));
    client.remember_weather_data(&weather);
    *now.lock().unwrap() = t0 + Duration::minutes(3);
    assert!(client.should_fetch_minutely_precipitation(&location));
    *now.lock().unwrap() = t0 + Duration::minutes(2);
    assert!(!client.should_fetch_minutely_precipitation(&location));

    // Rain only beyond the six-hour lookahead does not speed polling up.
    weather.hourly_forecast = Some(hourly_rain_at(t0, 7));
    client.remember_weather_data(&weather);
    *now.lock().unwrap() = t0 + Duration::minutes(10);
    assert!(!client.should_fetch_minutely_precipitation(&location));
}

#[test]
fn concurrent_requests_share_one_fetch() {
    struct SlowOpenMeteo(Mutex<usize>);
    impl OpenMeteoSource for SlowOpenMeteo {
        fn get_all_data(
            &self,
            _: &Location,
            _: i64,
            _: i64,
        ) -> SourceResult<(
            Option<CurrentConditions>,
            Option<Forecast>,
            Option<HourlyForecast>,
        )> {
            *self.0.lock().unwrap() += 1;
            std::thread::sleep(std::time::Duration::from_millis(200));
            Ok((
                Some(CurrentConditions {
                    temperature_f: Some(70.0),
                    ..Default::default()
                }),
                None,
                None,
            ))
        }
        fn get_current_conditions(&self, _: &Location) -> SourceResult<Option<CurrentConditions>> {
            Ok(None)
        }
    }
    let fakes = fakes_with(json!({"aviation": {"station": {"value": [null, null]}}}));
    let openmeteo = Arc::new(SlowOpenMeteo(Mutex::new(0)));
    let mut client_sources = sources(&fakes, false, false);
    client_sources.openmeteo = openmeteo.clone();
    let client = WeatherClient::new(client_sources, AppSettings::default(), "openmeteo", None);
    let location = us();
    let results: Vec<WeatherData> = std::thread::scope(|scope| {
        let handles: Vec<_> = (0..3)
            .map(|_| scope.spawn(|| client.get_weather_data(&location, false)))
            .collect();
        handles.into_iter().map(|h| h.join().unwrap()).collect()
    });
    assert_eq!(*openmeteo.0.lock().unwrap(), 1);
    assert!(results
        .iter()
        .all(|w| w.current.as_ref().unwrap().temperature_f == Some(70.0)));
    // Force refresh bypasses sharing.
    client.get_weather_data(&location, true);
    assert_eq!(*openmeteo.0.lock().unwrap(), 2);
}

#[test]
fn aviation_weather_requires_a_station() {
    let client = WeatherClient::new(
        sources(
            &fakes_with(json!({"aviation": {"data": {"value": {"station_id": "KJFK"}}}})),
            false,
            false,
        ),
        AppSettings::default(),
        "auto",
        None,
    );
    assert!(client
        .get_aviation_weather("  ", &AviationOptions::default())
        .is_err());
    let data = client
        .get_aviation_weather(" kjfk ", &AviationOptions::default())
        .unwrap();
    assert_eq!(data.station_id.as_deref(), Some("KJFK"));
}

#[test]
fn pre_warm_counts_locations_with_data() {
    let table = json!({
        "openmeteo": {"all": {"value": [{"temperature_f": 70.0}, null, null]}},
        "aviation": {"station": {"value": [null, null]}},
    });
    let client = WeatherClient::new(
        sources(&fakes_with(table), false, false),
        AppSettings::default(),
        "openmeteo",
        None,
    );
    assert!(client.pre_warm_cache(&us()));
    assert_eq!(
        client.pre_warm_batch(&[us(), Location::new("Paris", 48.85, 2.35).with_country("FR")]),
        2
    );
    assert_eq!(client.pre_warm_batch(&[]), 0);
}

#[test]
fn cached_weather_and_force_refresh_invalidation() {
    let dir = tempfile::tempdir().unwrap();
    let cache = WeatherDataCache::new(dir.path(), 180).unwrap();
    let location = us();
    let stored = WeatherData {
        current: Some(CurrentConditions {
            temperature_f: Some(72.0),
            ..Default::default()
        }),
        ..WeatherData::new(location.clone())
    };
    cache.store(&location, &stored, Utc::now());
    // NWS fails, so a normal refresh falls back to the cache...
    let table = json!({"nws": {"all": {"error": "down"}}});
    let client = WeatherClient::new(
        sources(&fakes_with(table), false, false),
        AppSettings::default(),
        "nws",
        Some(cache.clone()),
    );
    let cached = client.get_cached_weather(&location).unwrap();
    assert_eq!(cached.current.unwrap().temperature_f, Some(72.0));
    let fallback = client.get_weather_data(&location, false);
    assert_eq!(fallback.stale_reason.as_deref(), Some("Cached data"));
    // ...but a forced refresh drops the entry first.
    let forced = client.get_weather_data(&location, true);
    assert_eq!(
        forced.discussion.as_deref(),
        Some("Weather data not available.")
    );
    assert!(client.get_cached_weather(&location).is_none());
}
