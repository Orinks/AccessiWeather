import XCTest
@testable import AccessiWeather

final class DailyForecastTests: XCTestCase {
    private var calendar: Calendar {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(identifier: "America/New_York")!
        return calendar
    }

    private func period(day: Int, hour: Int) -> DailyPeriod {
        let date = calendar.date(from: DateComponents(year: 2026, month: 10, day: day, hour: hour))!
        return DailyPeriod(id: "\(day)-\(hour)", name: "\(day)", date: date, isDaytime: hour < 18, condition: "Clear")
    }

    private func report(source: String, periods: [DailyPeriod]) -> WeatherReport {
        WeatherReport(
            location: SavedLocation(name: "New York", latitude: 40.71, longitude: -74.01),
            current: CurrentConditions(), hourly: [], daily: periods, alerts: [],
            sourceDescription: source, timeZone: calendar.timeZone, fetchedAt: Date(), forecastOfficeID: nil
        )
    }

    func testSevenDaysIncludesBothLocalPeriodsInEitherNWSMode() {
        let periods = (1...8).flatMap { [period(day: $0, hour: 6), period(day: $0, hour: 20)] }
        let expected = Array(periods.prefix(14))
        for source in ["National Weather Service", "Automatic: National Weather Service, Open-Meteo"] {
            XCTAssertEqual(report(source: source, periods: periods).dailyForecast(days: 7), expected)
        }
    }

    func testFirstPartialDayCountsAndKeepsItsNightPeriod() {
        let tonight = period(day: 1, hour: 20)
        let tomorrow = period(day: 2, hour: 6)
        let tomorrowNight = period(day: 2, hour: 20)
        let nextDay = period(day: 3, hour: 6)
        let forecast = report(source: "Automatic: National Weather Service", periods: [tonight, tomorrow, tomorrowNight, nextDay])

        XCTAssertEqual(forecast.dailyForecast(days: 2), [tonight, tomorrow, tomorrowNight])
    }

    func testOnceDailyProvidersStillReturnOnePeriodPerDay() {
        let periods = (1...8).map { period(day: $0, hour: 0) }
        XCTAssertEqual(report(source: "Open-Meteo", periods: periods).dailyForecast(days: 3), Array(periods.prefix(3)))
    }
}
