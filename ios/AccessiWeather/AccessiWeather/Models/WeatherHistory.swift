import Foundation

struct WeatherHistoryDay: Identifiable, Equatable {
    var id: Date { date }
    var date: Date
    var highC: Double?
    var lowC: Double?
    var meanC: Double?
    var condition: String
}

struct WeatherHistory: Equatable {
    var days: [WeatherHistoryDay]
    var yesterdayComparison: String?
    var lastWeekComparison: String?

    static func comparison(
        currentTemperatureC: Double?,
        currentCondition: String?,
        historicalDay: WeatherHistoryDay?,
        daysAgo: Int,
        unit: TemperatureUnit
    ) -> String? {
        guard let currentTemperatureC,
              let historicalDay,
              let historicalTemperatureC = historicalDay.meanC else {
            return nil
        }
        let currentValue = displayTemperature(currentTemperatureC, unit: unit)
        let historicalValue = displayTemperature(historicalTemperatureC, unit: unit)
        let difference = currentValue - historicalValue
        let temperatureDescription: String
        if abs(difference) < 1 {
            temperatureDescription = "about the same temperature"
        } else if difference > 0 {
            temperatureDescription = String(format: "%.1f degrees warmer", difference)
        } else {
            temperatureDescription = String(format: "%.1f degrees cooler", abs(difference))
        }
        let timeReference = daysAgo == 1 ? "yesterday" : "last week"
        var sentence = "Compared to \(timeReference): \(temperatureDescription)"
        if let currentCondition,
           historicalDay.condition.caseInsensitiveCompare(currentCondition) != .orderedSame {
            sentence += ". Changed from \(historicalDay.condition) to \(currentCondition)"
        }
        return sentence + "."
    }

    private static func displayTemperature(_ celsius: Double, unit: TemperatureUnit) -> Double {
        switch unit {
        case .celsius: return celsius
        case .fahrenheit, .both: return celsius * 9 / 5 + 32
        }
    }
}
