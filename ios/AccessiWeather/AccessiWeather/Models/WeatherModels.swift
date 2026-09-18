import Foundation

enum WeatherSource: String, Codable, CaseIterable, Identifiable {
    case automatic
    case nws
    case openMeteo
    case pirateWeather

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .automatic: return "Automatic"
        case .nws: return "National Weather Service"
        case .openMeteo: return "Open-Meteo"
        case .pirateWeather: return "Pirate Weather"
        }
    }
}

struct AirQuality: Equatable {
    var aqi: Int
    var dominantPollutant: String?

    var category: String {
        switch aqi {
        case ..<51: return "Good"
        case 51...100: return "Moderate"
        case 101...150: return "Unhealthy for Sensitive Groups"
        case 151...200: return "Unhealthy"
        case 201...300: return "Very Unhealthy"
        default: return "Hazardous"
        }
    }

    var advice: String {
        switch aqi {
        case ..<51: return "Air quality is satisfactory and poses little or no risk."
        case 51...100: return "Air quality is acceptable. People unusually sensitive to air pollution should reduce prolonged or heavy outdoor exertion."
        case 101...150: return "Members of sensitive groups may experience health effects. Consider reducing prolonged outdoor exertion."
        case 151...200: return "Everyone may begin to experience health effects. Limit prolonged outdoor exertion."
        case 201...300: return "Health alert: everyone may experience more serious health effects. Avoid outdoor exertion."
        default: return "Health emergency: everyone is more likely to be affected. Stay indoors."
        }
    }
}

struct CurrentConditions: Equatable {
    var description: String?
    var temperatureC: Double?
    var dewpointC: Double?
    var humidityPercent: Double?
    var windSpeedKph: Double?
    var windDirectionDegrees: Double?
    var pressureHpa: Double?
    var visibilityKm: Double?
    var uvIndex: Double?
    var sunrise: Date?
    var sunset: Date?
    var airQuality: AirQuality?
    var observedAt: Date?
}

struct HourlyPeriod: Identifiable, Equatable {
    var id: Date { time }
    var time: Date
    var temperatureC: Double?
    var condition: String
    var windSpeedKph: Double?
    var windDirectionDegrees: Double?
    var precipitationChance: Int?
}

struct DailyPeriod: Identifiable, Equatable {
    var id: String
    var name: String
    var date: Date
    var isDaytime: Bool
    var highC: Double?
    var lowC: Double?
    var condition: String
    var detailedForecast: String?
    var windSpeedKph: Double?
    var windDirectionDegrees: Double?
    var windText: String?
    var precipitationChance: Int?
}

struct WeatherAlert: Identifiable, Equatable, Hashable {
    var id: String
    var event: String
    var severity: String
    var urgency: String?
    var certainty: String?
    var headline: String?
    var description: String?
    var instruction: String?
    var areaDescription: String?
    var sender: String?
    var effective: Date?
    var expires: Date?
}

struct WeatherReport: Equatable {
    var location: SavedLocation
    var current: CurrentConditions
    var hourly: [HourlyPeriod]
    var daily: [DailyPeriod]
    var alerts: [WeatherAlert]
    var sourceDescription: String
    var timeZone: TimeZone
    var fetchedAt: Date
    var forecastOfficeID: String?
}

enum WeatherError: LocalizedError {
    case invalidResponse(String)
    case httpStatus(Int, String)
    case noData(String)
    case unsupported(String)

    var errorDescription: String? {
        switch self {
        case .invalidResponse(let what): return "The \(what) response could not be read."
        case .httpStatus(let code, let what): return "The \(what) service returned status \(code)."
        case .noData(let what): return "No \(what) data is available for this location."
        case .unsupported(let what): return what
        }
    }
}
