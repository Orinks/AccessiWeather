import XCTest
@testable import AccessiWeather

/// Opt-in live checks; skipped unless the test run sets PIRATE_WEATHER_LIVE_KEY (via TEST_RUNNER_PIRATE_WEATHER_LIVE_KEY).
final class LiveFusionTests: XCTestCase {
    private var key: String {
        get throws {
            guard let key = ProcessInfo.processInfo.environment["PIRATE_WEATHER_LIVE_KEY"], !key.isEmpty else {
                throw XCTSkip("Set TEST_RUNNER_PIRATE_WEATHER_LIVE_KEY to run live fusion checks")
            }
            return key
        }
    }

    func testInternationalAutomaticFusesOpenMeteoAndPirateWeather() async throws {
        let london = SavedLocation(name: "London", latitude: 51.5074, longitude: -0.1278)
        let report = try await WeatherService().report(for: london, source: .automatic, forceRefresh: true, pirateWeatherKey: try key)
        print("London sources: \(report.sourceDescription)")
        XCTAssertEqual(report.sourceDescription.components(separatedBy: ", ").count, 2)
        XCTAssertNotNil(report.current.temperatureC)
        XCTAssertFalse(report.daily.isEmpty)
        XCTAssertFalse(report.hourly.isEmpty)
        XCTAssertFalse(report.minutely?.isEmpty ?? true)
    }

    func testUSAutomaticFusesAllThreeSources() async throws {
        let nyc = SavedLocation(name: "New York", latitude: 40.7128, longitude: -74.0060)
        let report = try await WeatherService().report(for: nyc, source: .automatic, forceRefresh: true, pirateWeatherKey: try key)
        print("New York sources: \(report.sourceDescription)")
        XCTAssertEqual(report.sourceDescription.components(separatedBy: ", ").count, 3)
        XCTAssertNotNil(report.forecastOfficeID)
        XCTAssertFalse(report.minutely?.isEmpty ?? true)
    }

    func testInternationalWithoutPirateKeyUsesOpenMeteoOnly() async throws {
        _ = try key
        let tokyo = SavedLocation(name: "Tokyo", latitude: 35.6762, longitude: 139.6503)
        let report = try await WeatherService().report(for: tokyo, source: .automatic, forceRefresh: true, pirateWeatherKey: "")
        print("Tokyo sources: \(report.sourceDescription)")
        XCTAssertEqual(report.sourceDescription.components(separatedBy: ", ").count, 1)
        XCTAssertNotNil(report.current.temperatureC)
        XCTAssertFalse(report.daily.isEmpty)
    }
}
