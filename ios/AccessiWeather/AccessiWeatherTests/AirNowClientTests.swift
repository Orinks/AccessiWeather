import XCTest
@testable import AccessiWeather

final class AirNowClientTests: XCTestCase {
    func testPicksHighestAQIAcrossSpellings() throws {
        let payload: [[String: Any]] = [
            ["AQI": 42, "ParameterName": "O3", "Category": ["Number": 1, "Name": "Good"], "ReportingArea": "Philadelphia"],
            ["nowcastAQI": "88.6", "parameterName": "PM2.5", "aqiCategoryName": "Moderate", "reportingAreaName": "Philadelphia"],
            ["AQI": true, "ParameterName": "Bogus"],
            ["AQI": -1, "ParameterName": "PM10"],
        ]
        let observation = try XCTUnwrap(AirNowClient.parse(payload))
        XCTAssertEqual(observation, AirNowClient.Observation(aqi: 89, category: "Moderate", pollutant: "PM2.5", reportingArea: "Philadelphia"))
    }

    func testEmptyOrInvalidPayloadIsNil() {
        XCTAssertNil(AirNowClient.parse([[String: Any]]()))
        XCTAssertNil(AirNowClient.parse(["error": "bad key"]))
    }
}
