import Foundation

/// Client for the free Open-Meteo forecast and air-quality APIs (no key required).
struct OpenMeteoClient {
    private let http: HTTPClient

    init(http: HTTPClient = .shared) {
        self.http = http
    }

    struct ForecastResponse: Decodable {
        var timezone: String
        var current: Current?
        var hourly: Hourly?
        var daily: Daily?

        struct Current: Decodable {
            var time: String
            var temperature_2m: Double?
            var relative_humidity_2m: Double?
            var dew_point_2m: Double?
            var weather_code: Int?
            var surface_pressure: Double?
            var wind_speed_10m: Double?
            var wind_direction_10m: Double?
        }

        struct Hourly: Decodable {
            var time: [String]
            var temperature_2m: [Double?]
            var precipitation_probability: [Int?]?
            var weather_code: [Int?]
            var wind_speed_10m: [Double?]?
            var wind_direction_10m: [Double?]?
            var uv_index: [Double?]?
            var visibility: [Double?]?
        }

        struct Daily: Decodable {
            var time: [String]
            var weather_code: [Int?]
            var temperature_2m_max: [Double?]
            var temperature_2m_min: [Double?]
            var precipitation_probability_max: [Int?]?
            var wind_speed_10m_max: [Double?]?
            var wind_direction_10m_dominant: [Double?]?
            var sunrise: [String]?
            var sunset: [String]?
            var uv_index_max: [Double?]?
        }
    }

    struct AirQualityResponse: Decodable {
        var current: Current?

        struct Current: Decodable {
            var us_aqi: Int?
            var pm2_5: Double?
            var pm10: Double?
            var ozone: Double?
            var nitrogen_dioxide: Double?
            var sulphur_dioxide: Double?
            var carbon_monoxide: Double?
        }
    }

    func forecast(latitude: Double, longitude: Double, days: Int = 7) async throws -> ForecastResponse {
        var components = URLComponents(string: "https://api.open-meteo.com/v1/forecast")!
        components.queryItems = [
            .init(name: "latitude", value: String(latitude)),
            .init(name: "longitude", value: String(longitude)),
            .init(name: "current", value: "temperature_2m,relative_humidity_2m,dew_point_2m,weather_code,surface_pressure,wind_speed_10m,wind_direction_10m"),
            .init(name: "hourly", value: "temperature_2m,precipitation_probability,weather_code,wind_speed_10m,wind_direction_10m,uv_index,visibility"),
            .init(name: "daily", value: "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,wind_speed_10m_max,wind_direction_10m_dominant,sunrise,sunset,uv_index_max"),
            .init(name: "timezone", value: "auto"),
            .init(name: "forecast_days", value: String(max(1, min(days, 16)))),
        ]
        return try await http.json(ForecastResponse.self, from: components.url!, serviceName: "Open-Meteo")
    }

    func airQuality(latitude: Double, longitude: Double) async throws -> AirQualityResponse {
        var components = URLComponents(string: "https://air-quality-api.open-meteo.com/v1/air-quality")!
        components.queryItems = [
            .init(name: "latitude", value: String(latitude)),
            .init(name: "longitude", value: String(longitude)),
            .init(name: "current", value: "us_aqi,pm2_5,pm10,ozone,nitrogen_dioxide,sulphur_dioxide,carbon_monoxide"),
            .init(name: "timezone", value: "auto"),
        ]
        return try await http.json(AirQualityResponse.self, from: components.url!, serviceName: "Open-Meteo air quality")
    }

    /// Open-Meteo returns local times without an offset ("2026-09-18T15:00"); interpret them in the given zone.
    static func date(from local: String, in timeZone: TimeZone) -> Date? {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = timeZone
        formatter.dateFormat = local.count > 10 ? "yyyy-MM-dd'T'HH:mm" : "yyyy-MM-dd"
        return formatter.date(from: local)
    }

    /// WMO weather interpretation codes to plain text.
    static func condition(forCode code: Int?) -> String {
        switch code {
        case 0: return "Clear"
        case 1: return "Mainly Clear"
        case 2: return "Partly Cloudy"
        case 3: return "Overcast"
        case 45: return "Fog"
        case 48: return "Freezing Fog"
        case 51: return "Light Drizzle"
        case 53: return "Drizzle"
        case 55: return "Heavy Drizzle"
        case 56, 57: return "Freezing Drizzle"
        case 61: return "Light Rain"
        case 63: return "Rain"
        case 65: return "Heavy Rain"
        case 66, 67: return "Freezing Rain"
        case 71: return "Light Snow"
        case 73: return "Snow"
        case 75: return "Heavy Snow"
        case 77: return "Snow Grains"
        case 80: return "Light Rain Showers"
        case 81: return "Rain Showers"
        case 82: return "Heavy Rain Showers"
        case 85: return "Snow Showers"
        case 86: return "Heavy Snow Showers"
        case 95: return "Thunderstorm"
        case 96, 99: return "Thunderstorm with Hail"
        default: return "Unknown"
        }
    }

    static func dominantPollutant(_ current: AirQualityResponse.Current) -> String? {
        // Rough breakpoints relative to US AQI 100 for each pollutant; the largest ratio wins.
        let candidates: [(String, Double?)] = [
            ("PM2.5", current.pm2_5.map { $0 / 35.4 }),
            ("PM10", current.pm10.map { $0 / 154 }),
            ("Ozone", current.ozone.map { $0 / 140 }),
            ("NO2", current.nitrogen_dioxide.map { $0 / 188 }),
            ("SO2", current.sulphur_dioxide.map { $0 / 196 }),
            ("CO", current.carbon_monoxide.map { $0 / 10_800 }),
        ]
        return candidates.compactMap { name, ratio in ratio.map { (name, $0) } }.max { $0.1 < $1.1 }?.0
    }
}
