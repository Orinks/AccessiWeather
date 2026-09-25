//! Offline fixtures for `--offline`, `--smoke` and `--check`.

use std::sync::Arc;

use aw_providers::http::FixtureClient;
use aw_providers::{geocoding, nws, openmeteo};
use chrono::{Duration, Utc};
use serde_json::json;

pub fn offline_client() -> Arc<FixtureClient> {
    let now = Utc::now();
    let iso = |d: Duration| (now + d).to_rfc3339();
    let hour = |h: i64| {
        (now + Duration::hours(h))
            .format("%Y-%m-%dT%H:00")
            .to_string()
    };
    let day = |d: i64| (now + Duration::days(d)).format("%Y-%m-%d").to_string();

    let points = json!({"properties": {
        "forecast": format!("{}/gridpoints/PHI/49,75/forecast", nws::BASE_URL),
        "forecastHourly": format!("{}/gridpoints/PHI/49,75/forecast/hourly", nws::BASE_URL),
        "observationStations": format!("{}/gridpoints/PHI/49,75/stations", nws::BASE_URL),
        "forecastZone": format!("{}/zones/forecast/PAZ106", nws::BASE_URL),
        "county": format!("{}/zones/county/PAC101", nws::BASE_URL),
        "fireWeatherZone": format!("{}/zones/fire/PAZ106", nws::BASE_URL),
        "cwa": "PHI", "radarStation": "KDIX", "timeZone": "America/New_York"
    }});
    let stations = json!({"features": [{"properties": {"stationIdentifier": "KPHL"}}]});
    let observation = json!({"properties": {
        "timestamp": iso(Duration::minutes(-20)),
        "textDescription": "Partly Cloudy",
        "temperature": {"value": 21.7, "unitCode": "wmoUnit:degC"},
        "dewpoint": {"value": 12.0, "unitCode": "wmoUnit:degC"},
        "relativeHumidity": {"value": 54.0, "unitCode": "wmoUnit:percent"},
        "windSpeed": {"value": 14.8, "unitCode": "wmoUnit:km_h-1"},
        "windGust": {"value": 27.7, "unitCode": "wmoUnit:km_h-1"},
        "windDirection": {"value": 250, "unitCode": "wmoUnit:degree_(angle)"},
        "barometricPressure": {"value": 101690, "unitCode": "wmoUnit:Pa"},
        "visibility": {"value": 16090, "unitCode": "wmoUnit:m"}
    }});
    let forecast = json!({"properties": {"generatedAt": iso(Duration::zero()), "periods": [
        {"name": "Today", "temperature": 74, "temperatureUnit": "F", "isDaytime": true,
         "windSpeed": "5 to 10 mph", "windDirection": "W", "startTime": iso(Duration::zero()),
         "shortForecast": "Partly Sunny", "detailedForecast": "Partly sunny, with a high near 74. West wind 5 to 10 mph.",
         "probabilityOfPrecipitation": {"value": 10}},
        {"name": "Tonight", "temperature": 55, "temperatureUnit": "F", "isDaytime": false,
         "windSpeed": "5 mph", "windDirection": "NW", "startTime": iso(Duration::hours(8)),
         "shortForecast": "Mostly Clear", "detailedForecast": "Mostly clear, with a low around 55.",
         "probabilityOfPrecipitation": {"value": 0}},
        {"name": "Saturday", "temperature": 71, "temperatureUnit": "F", "isDaytime": true,
         "windSpeed": "10 mph", "windDirection": "N", "startTime": iso(Duration::hours(20)),
         "shortForecast": "Sunny", "detailedForecast": "Sunny, with a high near 71.",
         "probabilityOfPrecipitation": {"value": 0}},
        {"name": "Saturday Night", "temperature": 52, "temperatureUnit": "F", "isDaytime": false,
         "windSpeed": "5 mph", "windDirection": "N", "startTime": iso(Duration::hours(32)),
         "shortForecast": "Clear", "detailedForecast": "Clear, with a low around 52."},
        {"name": "Sunday", "temperature": 69, "temperatureUnit": "F", "isDaytime": true,
         "windSpeed": "5 to 10 mph", "windDirection": "NE", "startTime": iso(Duration::hours(44)),
         "shortForecast": "Chance Showers", "detailedForecast": "A chance of showers after 2pm. High near 69.",
         "probabilityOfPrecipitation": {"value": 40}}
    ]}});
    let hourly_periods: Vec<_> = (0..24)
        .map(|h| {
            json!({"startTime": iso(Duration::hours(h)), "temperature": 70 - (h % 12),
                "temperatureUnit": "F", "shortForecast": if h % 5 == 0 {"Partly Cloudy"} else {"Sunny"},
                "windSpeed": "8 mph", "windDirection": "W",
                "relativeHumidity": {"value": 50 + h}, "probabilityOfPrecipitation": {"value": h * 2}})
        })
        .collect();
    let hourly =
        json!({"properties": {"generatedAt": iso(Duration::zero()), "periods": hourly_periods}});
    let alerts = json!({"features": [{"id": "urn:oid:2.49.0.1.840.0.demo", "properties": {
        "id": "urn:oid:2.49.0.1.840.0.demo",
        "event": "Wind Advisory", "headline": "Wind Advisory issued for Philadelphia",
        "severity": "Moderate", "urgency": "Expected", "certainty": "Likely",
        "areaDesc": "Philadelphia; Delaware",
        "onset": iso(Duration::hours(-1)), "expires": iso(Duration::hours(6)),
        "description": "West winds 20 to 30 mph with gusts up to 45 mph expected.",
        "instruction": "Use extra caution when driving, especially if operating a high profile vehicle.",
        "parameters": {"SAME": ["042101"]}
    }}]});
    let afd_list = json!({"@graph": [{"id": "demo-afd"}]});
    let afd = json!({"productText": "Area Forecast Discussion\nNational Weather Service Mount Holly NJ\n\n.SYNOPSIS...\nHigh pressure builds in behind a departing cold front, bringing breezy northwest winds and dry conditions through the weekend."});

    let om_days: Vec<String> = (0..7).map(day).collect();
    let om_hours: Vec<String> = (0..48).map(hour).collect();
    let open_meteo = json!({
        "utc_offset_seconds": 0,
        "current": {"time": hour(0), "temperature_2m": 61.0, "relative_humidity_2m": 62,
            "dew_point_2m": 48.0, "apparent_temperature": 60.0, "weather_code": 2,
            "cloud_cover": 40, "pressure_msl": 1015.0, "wind_speed_10m": 9.0,
            "wind_direction_10m": 220, "wind_gusts_10m": 15.0, "uv_index": 3.0, "visibility": 52800},
        "daily": {"time": om_days, "weather_code": [2, 61, 3, 0, 1, 80, 2],
            "temperature_2m_max": [64.0, 58.0, 60.0, 66.0, 68.0, 63.0, 65.0],
            "temperature_2m_min": [48.0, 47.0, 45.0, 49.0, 51.0, 50.0, 48.0],
            "sunrise": (0..7).map(|d| format!("{}T06:40", day(d))).collect::<Vec<_>>(),
            "sunset": (0..7).map(|d| format!("{}T19:20", day(d))).collect::<Vec<_>>(),
            "precipitation_probability_max": [10, 70, 20, 0, 0, 60, 10],
            "precipitation_sum": [0.0, 0.3, 0.0, 0.0, 0.0, 0.2, 0.0],
            "wind_speed_10m_max": [12.0, 15.0, 10.0, 8.0, 9.0, 14.0, 11.0],
            "wind_direction_10m_dominant": [220, 180, 300, 90, 120, 200, 250],
            "uv_index_max": [4.0, 2.0, 3.0, 5.0, 5.0, 3.0, 4.0]},
        "hourly": {"time": om_hours,
            "temperature_2m": (0..48).map(|h| 60.0 - (h % 12) as f64).collect::<Vec<_>>(),
            "relative_humidity_2m": (0..48).map(|h| 55 + h % 20).collect::<Vec<_>>(),
            "precipitation_probability": (0..48).map(|h| (h * 3) % 100).collect::<Vec<_>>(),
            "weather_code": (0..48).map(|h| if h % 7 == 0 { 61 } else { 1 }).collect::<Vec<_>>(),
            "wind_speed_10m": (0..48).map(|h| 6.0 + (h % 5) as f64).collect::<Vec<_>>(),
            "wind_direction_10m": (0..48).map(|h| (h * 15) % 360).collect::<Vec<_>>(),
            "pressure_msl": (0..48).map(|_| 1015.0).collect::<Vec<_>>()}
    });
    let geocode = json!({"results": [
        {"name": "Philadelphia", "latitude": 39.9526, "longitude": -75.1652, "admin1": "Pennsylvania",
         "country": "United States", "country_code": "us", "timezone": "America/New_York"},
        {"name": "London", "latitude": 51.5072, "longitude": -0.1276, "admin1": "England",
         "country": "United Kingdom", "country_code": "gb", "timezone": "Europe/London"},
        {"name": "Tokyo", "latitude": 35.6762, "longitude": 139.6503, "country": "Japan",
         "country_code": "jp", "timezone": "Asia/Tokyo"}
    ]});

    Arc::new(
        FixtureClient::new()
            .with(&format!("{}/points/", nws::BASE_URL), points)
            .with(
                &format!("{}/gridpoints/PHI/49,75/stations", nws::BASE_URL),
                stations,
            )
            .with(
                &format!("{}/gridpoints/PHI/49,75/forecast/hourly", nws::BASE_URL),
                hourly,
            )
            .with(
                &format!("{}/gridpoints/PHI/49,75/forecast", nws::BASE_URL),
                forecast,
            )
            .with(&format!("{}/stations/", nws::BASE_URL), observation)
            .with(&format!("{}/alerts/active", nws::BASE_URL), alerts)
            .with(&format!("{}/products/types/AFD", nws::BASE_URL), afd_list)
            .with(&format!("{}/products/demo-afd", nws::BASE_URL), afd)
            .with(openmeteo::BASE_URL, open_meteo)
            .with(geocoding::OPEN_METEO_GEOCODING, geocode),
    )
}
