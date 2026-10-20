import XCTest
@testable import AccessiWeather

final class WeatherAssistantTests: XCTestCase {
    func testToolDefinitionsMatchDesktopNames() {
        let names = WeatherAssistantTools.definitions.compactMap { ($0["function"] as? [String: Any])?["name"] as? String }
        XCTAssertEqual(names, ["get_current_weather", "get_forecast", "get_hourly_forecast", "get_alerts", "search_location",
                               "list_locations", "get_area_forecast_discussion", "get_wpc_discussion", "get_spc_outlook"])
        XCTAssertNoThrow(try JSONSerialization.data(withJSONObject: WeatherAssistantTools.definitions))
    }

    func testContextAndHelpers() {
        XCTAssertEqual(WeatherAssistantTools.context(nil), "No weather data currently loaded.")
        XCTAssertEqual(WeatherAssistantTools.fahrenheit(20), "68°F")
        XCTAssertEqual(WeatherAssistantTools.mph(16.09344), "10 mph")
        XCTAssertTrue(WeatherAssistantTools.welcome(locationName: nil).contains("your area"))
        XCTAssertTrue(WeatherAssistantTools.truncated(String(repeating: "a", count: 3001)).hasSuffix("[Truncated — full discussion is longer]"))
    }
}
