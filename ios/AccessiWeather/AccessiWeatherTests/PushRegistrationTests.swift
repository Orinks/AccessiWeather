import XCTest
@testable import AccessiWeather

@MainActor
final class PushRegistrationTests: XCTestCase {
    private let events = EventNotificationSettings(
        discussionUpdates: true, hazardousWeatherOutlook: false, specialWeatherStatements: true,
        precipitationStart: true, precipitationStop: false
    )

    func testBodySendsAllLocationsSettingsAndKey() throws {
        let nyc = SavedLocation(name: "New York", latitude: 40.7128, longitude: -74.006)
        let london = SavedLocation(name: "London", latitude: 51.5074, longitude: -0.1278)
        let body = PushRegistration.body(
            token: "ab", enabled: true, severities: ["severe"], notifyUnknown: false,
            events: events, pirateWeatherKey: " key ", locations: [nyc, london]
        )
        let locations = try XCTUnwrap(body["locations"] as? [[String: Any]])
        XCTAssertEqual(locations.map { $0["name"] as? String }, ["New York", "London"])
        XCTAssertEqual(locations.first?["id"] as? String, nyc.id.uuidString)
        XCTAssertEqual(body["severities"] as? [String], ["severe"])
        XCTAssertEqual(body["environment"] as? String, "sandbox")
        XCTAssertEqual(body["pirateWeatherKey"] as? String, "key")
        let sent = try XCTUnwrap(body["events"] as? [String: Bool])
        XCTAssertEqual(sent["discussion"], true)
        XCTAssertEqual(sent["hwo"], false)
        XCTAssertEqual(sent["precip_start"], true)
        XCTAssertNoThrow(try JSONSerialization.data(withJSONObject: body))
    }

    func testBodyMarksTheCurrentLocation() throws {
        var here = SavedLocation(name: "Here", latitude: 39.98, longitude: -74.78)
        here.isCurrentLocation = true
        let home = SavedLocation(name: "Home", latitude: 40, longitude: -74)
        let body = PushRegistration.body(
            token: "ab", enabled: true, severities: [], notifyUnknown: false,
            events: events, pirateWeatherKey: "", locations: [here, home]
        )
        let locations = try XCTUnwrap(body["locations"] as? [[String: Any]])
        XCTAssertEqual(locations.map { $0["current"] as? Bool }, [true, false])
    }

    func testSavedLocationsWithoutCurrentFlagStillDecode() throws {
        let json = #"[{"id":"A79BD8FA-7017-4B10-AD50-FD3EBE1F7864","name":"Home","latitude":40,"longitude":-74}]"#
        let decoded = try JSONDecoder().decode([SavedLocation].self, from: Data(json.utf8))
        XCTAssertEqual(decoded.first?.isCurrentLocation, false)
    }

    func testBodyCapsLocations() throws {
        let many = (0..<25).map { SavedLocation(name: "L\($0)", latitude: 40, longitude: -74) }
        let body = PushRegistration.body(
            token: "ab", enabled: true, severities: [], notifyUnknown: true,
            events: events, pirateWeatherKey: "", locations: many
        )
        XCTAssertEqual((body["locations"] as? [Any])?.count, PushRegistration.maxLocations)
    }
}
