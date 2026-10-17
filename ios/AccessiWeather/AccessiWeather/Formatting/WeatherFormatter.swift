import Foundation

/// Produces two renderings for every value: compact visible text ("75°F (24°C)") and a spoken
/// VoiceOver label with expanded units ("75 degrees Fahrenheit, 24 degrees Celsius").
struct WeatherFormatter {
    var temperatureUnit: TemperatureUnit
    var windSpeedUnit: WindSpeedUnit
    var use24HourTime: Bool
    var roundValues: Bool
    var timeZone: TimeZone

    @MainActor
    init(settings: SettingsStore, timeZone: TimeZone) {
        temperatureUnit = settings.temperatureUnit
        windSpeedUnit = settings.windSpeedUnit
        use24HourTime = settings.use24HourTime
        roundValues = settings.roundValues
        self.timeZone = timeZone
    }

    // MARK: Numbers

    private func number(_ value: Double, decimals: Int = 1) -> String {
        if roundValues {
            return String(Int(value.rounded()))
        }
        return String(format: "%.\(decimals)f", value)
    }

    // MARK: Temperature

    func temperature(_ celsius: Double?) -> String? {
        guard let celsius else { return nil }
        let f = celsius * 9 / 5 + 32
        switch temperatureUnit {
        case .fahrenheit: return "\(number(f))°F"
        case .celsius: return "\(number(celsius))°C"
        case .both: return "\(number(f))°F (\(number(celsius))°C)"
        }
    }

    func spokenTemperature(_ celsius: Double?) -> String? {
        guard let celsius else { return nil }
        let f = celsius * 9 / 5 + 32
        switch temperatureUnit {
        case .fahrenheit: return "\(number(f)) degrees Fahrenheit"
        case .celsius: return "\(number(celsius)) degrees Celsius"
        case .both: return "\(number(f)) degrees Fahrenheit, \(number(celsius)) degrees Celsius"
        }
    }

    // MARK: Wind

    static func compass(_ degrees: Double?) -> String? {
        guard let degrees else { return nil }
        let names = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
        let index = Int(((degrees.truncatingRemainder(dividingBy: 360) + 360).truncatingRemainder(dividingBy: 360) + 11.25) / 22.5) % 16
        return names[index]
    }

    static func spokenCompass(_ degrees: Double?) -> String? {
        guard let abbreviation = compass(degrees) else { return nil }
        let words: [Character: String] = ["N": "north", "S": "south", "E": "east", "W": "west"]
        let letters = Array(abbreviation)
        switch letters.count {
        case 1:
            return words[letters[0]]
        case 2:
            return (words[letters[0]] ?? "") + (words[letters[1]] ?? "")
        default:
            let primary = words[letters[0]] ?? ""
            let secondary = (words[letters[1]] ?? "") + (words[letters[2]] ?? "")
            return "\(primary)-\(secondary)"
        }
    }

    func windSpeed(_ kph: Double?) -> String? {
        guard let kph else { return nil }
        let mph = kph / 1.609344
        switch windSpeedUnit {
        case .mph: return "\(number(mph)) mph"
        case .kmh: return "\(number(kph)) km/h"
        case .both: return "\(number(mph)) mph (\(number(kph)) km/h)"
        }
    }

    func spokenWindSpeed(_ kph: Double?) -> String? {
        guard let kph else { return nil }
        let mph = kph / 1.609344
        switch windSpeedUnit {
        case .mph: return "\(number(mph)) miles per hour"
        case .kmh: return "\(number(kph)) kilometers per hour"
        case .both: return "\(number(mph)) miles per hour, \(number(kph)) kilometers per hour"
        }
    }

    func wind(speedKph: Double?, directionDegrees: Double?) -> String? {
        guard let speed = windSpeed(speedKph) else { return nil }
        if speedKph == 0 { return "Calm" }
        if let direction = WeatherFormatter.compass(directionDegrees) {
            return "\(direction) at \(speed)"
        }
        return speed
    }

    func spokenWind(speedKph: Double?, directionDegrees: Double?) -> String? {
        guard let speed = spokenWindSpeed(speedKph) else { return nil }
        if speedKph == 0 { return "wind calm" }
        if let direction = WeatherFormatter.spokenCompass(directionDegrees) {
            return "wind \(direction) \(speed)"
        }
        return "wind \(speed)"
    }

    // MARK: Other measurements

    func pressure(_ hPa: Double?) -> String? {
        guard let hPa else { return nil }
        let inHg = hPa / 33.8638866667
        return String(format: "%.2f inHg (%.1f hPa)", inHg, hPa)
    }

    func spokenPressure(_ hPa: Double?) -> String? {
        guard let hPa else { return nil }
        let inHg = hPa / 33.8638866667
        return String(format: "%.2f inches of mercury, %.1f hectopascals", inHg, hPa)
    }

    func visibility(_ km: Double?) -> String? {
        guard let km else { return nil }
        let miles = km / 1.609344
        return String(format: "%.1f mi (%.1f km)", miles, km)
    }

    func spokenVisibility(_ km: Double?) -> String? {
        guard let km else { return nil }
        let miles = km / 1.609344
        return String(format: "%.1f miles, %.1f kilometers", miles, km)
    }

    func humidity(_ percent: Double?) -> String? {
        percent.map { "\(Int($0.rounded()))%" }
    }

    func spokenHumidity(_ percent: Double?) -> String? {
        percent.map { "\(Int($0.rounded())) percent" }
    }

    static func uvCategory(_ index: Double) -> String {
        switch index {
        case ..<3: return "Low"
        case 3..<6: return "Moderate"
        case 6..<8: return "High"
        case 8..<11: return "Very High"
        default: return "Extreme"
        }
    }

    func uvIndex(_ index: Double?) -> String? {
        index.map { String(format: "%.1f (%@)", $0, WeatherFormatter.uvCategory($0)) }
    }

    func precipitationChance(_ percent: Int?) -> String? {
        percent.map { "Precip \($0)%" }
    }

    func spokenPrecipitationChance(_ percent: Int?) -> String? {
        percent.map { "\($0) percent chance of precipitation" }
    }

    // MARK: Time

    func time(_ date: Date?) -> String? {
        guard let date else { return nil }
        let formatter = DateFormatter()
        formatter.timeZone = timeZone
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = use24HourTime ? "HH:mm" : "h:mm a"
        return formatter.string(from: date)
    }

    /// Hour label for hourly rows: "11 PM" or "23:00".
    func hour(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.timeZone = timeZone
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = use24HourTime ? "HH:mm" : "h a"
        return formatter.string(from: date)
    }

    func spokenHour(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.timeZone = timeZone
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = use24HourTime ? "HH:mm" : "h a"
        return formatter.string(from: date)
    }

    func dateTime(_ date: Date?) -> String? {
        guard let date else { return nil }
        let formatter = DateFormatter()
        formatter.timeZone = timeZone
        formatter.dateStyle = .medium
        formatter.timeStyle = .short
        return formatter.string(from: date)
    }
}
