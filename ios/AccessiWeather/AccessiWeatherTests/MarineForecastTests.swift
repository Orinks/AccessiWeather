import XCTest
@testable import AccessiWeather

final class MarineForecastTests: XCTestCase {
    func testHighlightsKeepDistinctWindAndWaveClauses() {
        let periods: [[String: Any]] = [
            ["shortForecast": "SW winds 10 kt", "detailedForecast": "SW winds 10 kt. Seas 2 to 3 ft; Showers likely."],
            ["detailedForecast": "sw winds 10 kt. Waves 1 ft. Swell 4 ft. Gusts to 25 kt."],
        ]
        XCTAssertEqual(MarineForecast.highlights(periods: periods), ["SW winds 10 kt", "Seas 2 to 3 ft", "Waves 1 ft", "Swell 4 ft"])
    }

    func testBuildUsesZoneAndFirstThreePeriods() throws {
        let zones: [String: Any] = ["features": [["id": "https://api.weather.gov/zones/marine/ANZ338", "properties": ["id": "ANZ338", "name": "New York Harbor"]]]]
        let zone = try XCTUnwrap(MarineForecast.zone(from: zones))
        XCTAssertEqual(zone.id, "ANZ338")
        let forecast: [String: Any] = ["properties": ["periods": [
            ["name": "Tonight", "detailedForecast": "E winds 5 kt. Waves 1 ft."],
            ["name": "Sat", "shortForecast": "NE winds 10 kt."],
            ["name": "", "detailedForecast": " Seas 2 ft. "],
            ["name": "Sun", "detailedForecast": "Calm."],
        ]]]
        let marine = MarineForecast.build(zoneID: zone.id, zoneName: zone.name, forecast: forecast)
        XCTAssertEqual(marine.zoneLabel, "New York Harbor (ANZ338)")
        XCTAssertEqual(marine.summary, "E winds 5 kt. Waves 1 ft.")
        XCTAssertEqual(marine.periods.map(\.name), ["Tonight", "Sat", "Marine period"])
        XCTAssertEqual(marine.periods.last?.summary, "Seas 2 ft.")
        XCTAssertTrue(marine.hasData)
    }

    func testOldSavedLocationsDecodeWithMarineModeOff() throws {
        let json = #"{"id":"6F9619FF-8B86-D011-B42D-00C04FC964FF","name":"Home","latitude":40,"longitude":-74}"#
        let location = try JSONDecoder().decode(SavedLocation.self, from: Data(json.utf8))
        XCTAssertFalse(location.marineMode)
        var marine = location
        marine.marineMode = true
        let roundTrip = try JSONDecoder().decode(SavedLocation.self, from: JSONEncoder().encode(marine))
        XCTAssertTrue(roundTrip.marineMode)
    }
}
