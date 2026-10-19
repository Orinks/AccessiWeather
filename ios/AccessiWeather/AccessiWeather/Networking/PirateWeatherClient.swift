import Foundation

struct PirateWeatherClient {
    private let http: HTTPClient

    init(http: HTTPClient = .shared) {
        self.http = http
    }

    struct Response: Decodable {
        var timezone: String?
        var currently: Point?
        var minutely: Block?
        var hourly: Block?
        var daily: Block?
        var alerts: [Alert]?

        struct Block: Decodable {
            var summary: String?
            var data: [Point]?
        }

        struct Point: Decodable {
            var time: Double?
            var summary: String?
            var icon: String?
            var temperature: Double?
            var temperatureHigh: Double?
            var temperatureLow: Double?
            var humidity: Double?
            var windSpeed: Double?
            var windBearing: Double?
            var pressure: Double?
            var visibility: Double?
            var uvIndex: Double?
            var precipProbability: Double?
            var precipIntensity: Double?
            var precipType: String?
            var sunriseTime: Double?
            var sunsetTime: Double?
        }

        struct Alert: Decodable {
            var title: String?
            var severity: String?
            var time: Double?
            var expires: Double?
            var description: String?
            var uri: String?
            var regions: [String]?
        }
    }

    func forecast(latitude: Double, longitude: Double, key: String) async throws -> Response {
        var components = URLComponents(
            url: URL(string: "https://api.pirateweather.net/forecast/\(key)/\(latitude),\(longitude)")!,
            resolvingAgainstBaseURL: false
        )!
        components.queryItems = [
            URLQueryItem(name: "units", value: "si"),
            URLQueryItem(name: "extend", value: "hourly"),
            URLQueryItem(name: "version", value: "2"),
        ]
        do {
            return try await http.json(Response.self, from: components.url!, serviceName: "Pirate Weather")
        } catch WeatherError.httpStatus(let code, _) where code == 401 || code == 403 {
            throw WeatherError.unsupported("Your Pirate Weather API key is invalid. Please check the key in Settings.")
        }
    }

    static func report(from response: Response, location: SavedLocation, fetchedAt: Date = Date()) -> WeatherReport {
        let zone = response.timezone.flatMap(TimeZone.init(identifier:)) ?? .current
        let currentPoint = response.currently
        let current = CurrentConditions(
            description: condition(summary: currentPoint?.summary, icon: currentPoint?.icon),
            temperatureC: currentPoint?.temperature,
            dewpointC: nil,
            humidityPercent: currentPoint?.humidity.map { $0 * 100 },
            windSpeedKph: currentPoint?.windSpeed.map { $0 * 3.6 },
            windDirectionDegrees: currentPoint?.windBearing,
            pressureHpa: currentPoint?.pressure,
            visibilityKm: currentPoint?.visibility,
            uvIndex: currentPoint?.uvIndex,
            sunrise: date(response.daily?.data?.first?.sunriseTime),
            sunset: date(response.daily?.data?.first?.sunsetTime),
            airQuality: nil,
            observedAt: date(currentPoint?.time)
        )
        let hourly = (response.hourly?.data ?? []).compactMap { point -> HourlyPeriod? in
            guard let time = date(point.time) else { return nil }
            return HourlyPeriod(
                time: time,
                temperatureC: point.temperature,
                condition: condition(summary: point.summary, icon: point.icon) ?? "Unknown",
                windSpeedKph: point.windSpeed.map { $0 * 3.6 },
                windDirectionDegrees: point.windBearing,
                precipitationChance: point.precipProbability.map { Int(($0 * 100).rounded()) }
            )
        }
        let daily = (response.daily?.data ?? []).enumerated().compactMap { index, point -> DailyPeriod? in
            guard let time = date(point.time) else { return nil }
            return DailyPeriod(
                id: "pw-\(Int(point.time ?? 0))",
                name: index == 0 ? "Today" : dayName(time, timeZone: zone),
                date: time,
                isDaytime: true,
                highC: point.temperatureHigh,
                lowC: point.temperatureLow,
                condition: condition(summary: point.summary, icon: point.icon) ?? "Unknown",
                detailedForecast: nil,
                windSpeedKph: point.windSpeed.map { $0 * 3.6 },
                windDirectionDegrees: point.windBearing,
                windText: nil,
                precipitationChance: point.precipProbability.map { Int(($0 * 100).rounded()) }
            )
        }
        let alerts = (response.alerts ?? []).enumerated().map { index, alert in
            WeatherAlert(
                id: alert.uri ?? "pirate-\(alert.title ?? "alert")-\(Int(alert.time ?? 0))-\(index)",
                event: alert.title ?? "Weather Alert",
                severity: alert.severity?.capitalized ?? "Unknown",
                urgency: nil,
                certainty: nil,
                headline: alert.title,
                description: alert.description,
                instruction: nil,
                areaDescription: alert.regions?.joined(separator: ", "),
                sender: "Pirate Weather",
                effective: date(alert.time),
                expires: date(alert.expires)
            )
        }
        let minutely = response.minutely?.data?.compactMap { point -> MinutelyPoint? in
            guard let time = date(point.time) else { return nil }
            return MinutelyPoint(
                time: time,
                precipitationIntensity: point.precipIntensity,
                precipitationProbability: point.precipProbability,
                precipitationType: point.precipType
            )
        }
        return WeatherReport(
            location: location,
            current: current,
            hourly: hourly,
            daily: daily,
            alerts: alerts,
            sourceDescription: "Pirate Weather",
            timeZone: zone,
            fetchedAt: fetchedAt,
            forecastOfficeID: nil,
            minutely: minutely
        )
    }

    private static func date(_ timestamp: Double?) -> Date? {
        timestamp.map(Date.init(timeIntervalSince1970:))
    }

    private static func condition(summary: String?, icon: String?) -> String? {
        if let summary, !summary.isEmpty { return summary }
        guard let icon, !icon.isEmpty else { return nil }
        switch icon {
        case "clear-day", "clear-night": return "Clear"
        case "rain": return "Rain"
        case "snow": return "Snow"
        case "sleet": return "Sleet"
        case "wind": return "Windy"
        case "fog": return "Fog"
        case "cloudy": return "Cloudy"
        case "partly-cloudy-day", "partly-cloudy-night": return "Partly Cloudy"
        case "thunderstorm": return "Thunderstorm"
        default: return icon.replacingOccurrences(of: "-", with: " ").capitalized
        }
    }

    private static func dayName(_ date: Date, timeZone: TimeZone) -> String {
        let formatter = DateFormatter()
        formatter.timeZone = timeZone
        formatter.dateFormat = "EEEE"
        return formatter.string(from: date)
    }
}
