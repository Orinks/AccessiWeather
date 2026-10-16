import XCTest
@testable import AccessiWeather

final class DataFusionTests: XCTestCase {
    private let us = SavedLocation(name: "Philadelphia", latitude: 39.95, longitude: -75.16)
    private let london = SavedLocation(name: "London", latitude: 51.5, longitude: -0.12)
    private let start = Date(timeIntervalSince1970: 1_800_000_000)

    private func report(_ source: String, _ current: CurrentConditions, hourly: [HourlyPeriod] = [], alerts: [WeatherAlert] = [], location: SavedLocation) -> WeatherReport {
        WeatherReport(location: location, current: current, hourly: hourly, daily: [], alerts: alerts,
                      sourceDescription: source, timeZone: .gmt, fetchedAt: start, forecastOfficeID: source == "NWS" ? "PHI" : nil)
    }

    func testUSFieldsFollowNWSThenOpenMeteoThenPirate() throws {
        let nws = report("NWS", CurrentConditions(description: "Unknown", temperatureC: 10, windSpeedKph: nil),
                         hourly: [HourlyPeriod(time: start, temperatureC: 10, condition: "Cloudy")],
                         alerts: [WeatherAlert(id: "nws1", event: "Flood Warning", severity: "Severe")], location: us)
        let om = report("Open-Meteo", CurrentConditions(description: "Overcast", temperatureC: 11, windSpeedKph: 20, windDirectionDegrees: 90, uvIndex: 3),
                        hourly: [HourlyPeriod(time: start.addingTimeInterval(600), temperatureC: 11, condition: "Overcast", uvIndex: 2)], location: us)
        var pw = report("Pirate Weather", CurrentConditions(temperatureC: 12, humidityPercent: 80, windSpeedKph: 30, windDirectionDegrees: 180),
                        alerts: [WeatherAlert(id: "pw1", event: "Flood Warning", severity: "Severe")], location: us)
        pw.minutely = []
        let fused = try XCTUnwrap(DataFusion.merge(location: us, nws: nws, openMeteo: om, pirateWeather: pw))
        XCTAssertEqual(fused.current.temperatureC, 10)
        XCTAssertEqual(fused.current.description, "Overcast")
        XCTAssertEqual(fused.current.humidityPercent, 80)
        XCTAssertEqual(fused.current.windSpeedKph, 20)
        XCTAssertEqual(fused.current.windDirectionDegrees, 90)
        XCTAssertEqual(fused.hourly.map(\.condition), ["Cloudy"])
        XCTAssertEqual(fused.hourly.first?.uvIndex, 2)
        XCTAssertEqual(fused.alerts.map(\.id), ["nws1"])
        XCTAssertEqual(fused.forecastOfficeID, "PHI")
        XCTAssertNotNil(fused.minutely)
        XCTAssertEqual(fused.sourceDescription, "Automatic: NWS, Open-Meteo, Pirate Weather")
    }

    func testInternationalUsesOpenMeteoAndPirateAlerts() throws {
        let om = report("Open-Meteo", CurrentConditions(temperatureC: 15), location: london)
        let pw = report("Pirate Weather", CurrentConditions(temperatureC: 16, pressureHpa: 1012),
                        alerts: [WeatherAlert(id: "uk1", event: "Wind Warning", severity: "Moderate")], location: london)
        let fused = try XCTUnwrap(DataFusion.merge(location: london, nws: nil, openMeteo: om, pirateWeather: pw))
        XCTAssertEqual(fused.current.temperatureC, 15)
        XCTAssertEqual(fused.current.pressureHpa, 1012)
        XCTAssertEqual(fused.alerts.map(\.id), ["uk1"])
        XCTAssertNil(fused.forecastOfficeID)
    }

    func testNoSourcesIsNil() {
        XCTAssertNil(DataFusion.merge(location: london, nws: nil, openMeteo: nil, pirateWeather: nil))
    }
}
