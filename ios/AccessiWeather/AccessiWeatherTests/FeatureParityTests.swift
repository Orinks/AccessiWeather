import Foundation
import XCTest
@testable import AccessiWeather

final class FeatureParityTests: XCTestCase {
    func testPirateWeatherMapsForecastAlertsAndPrecipitationTimeline() throws {
        let response = try JSONDecoder().decode(
            PirateWeatherClient.Response.self,
            from: fixture("pirate-weather")
        )
        let report = PirateWeatherClient.report(
            from: response,
            location: SavedLocation(name: "Springdale", latitude: 36.18, longitude: -94.13),
            fetchedAt: Date(timeIntervalSince1970: 1_790_683_300)
        )

        XCTAssertEqual(report.current.temperatureC, 24)
        XCTAssertEqual(report.current.humidityPercent, 50)
        XCTAssertEqual(report.current.windSpeedKph, 18)
        XCTAssertEqual(report.hourly.first?.precipitationChance, 62)
        XCTAssertEqual(report.daily.first?.highC, 29)
        XCTAssertEqual(report.alerts.first?.event, "Severe Thunderstorm Warning")
        XCTAssertEqual(report.minutely?.first?.precipitationType, "rain")
        XCTAssertEqual(PrecipitationTimelineText.condition(report.minutely![0]), "Rain")
    }

    func testPrecipitationTimelineSummariesAndAccessibleRows() {
        let start = Date(timeIntervalSince1970: 0)
        let dry = MinutelyPoint(time: start, precipitationIntensity: 0, precipitationProbability: 0, precipitationType: nil)
        let wet = MinutelyPoint(time: start.addingTimeInterval(60), precipitationIntensity: 0.5, precipitationProbability: 0.4, precipitationType: "rain")

        XCTAssertEqual(PrecipitationTimelineText.summary([dry, wet]), "Rain starting in about 1 minutes.")
        XCTAssertEqual(PrecipitationTimelineText.summary([dry]), "No precipitation expected in the next hour.")
        let row = PrecipitationTimelineText.row(wet, offset: 1, timeZone: TimeZone(secondsFromGMT: 0)!)
        XCTAssertTrue(row.contains("+01m"))
        XCTAssertTrue(row.contains("Rain"))
        XCTAssertTrue(row.contains("40% chance"))
        XCTAssertTrue(row.contains("0.500 mm/h"))
    }

    @MainActor
    func testWeatherExplanationPromptsAndMarkdownStripping() {
        let report = sampleReport()
        let defaults = UserDefaults(suiteName: "FeatureParityTests.\(UUID().uuidString)")!
        let formatter = WeatherFormatter(
            settings: SettingsStore(defaults: defaults),
            timeZone: report.timeZone
        )
        let messages = WeatherExplainer.messages(report: report, style: .brief, formatter: formatter)
        XCTAssertEqual(messages.map(\.role), ["system", "user"])
        XCTAssertTrue(messages[0].content.contains("plain text only"))
        XCTAssertTrue(messages[0].content.contains("1-2 sentences"))
        XCTAssertTrue(messages[1].content.contains("Location: Springdale"))
        XCTAssertTrue(messages[1].content.contains("Severe Thunderstorm Warning"))
        XCTAssertTrue(messages[1].content.contains(WeatherExplainer.closingSentence))
        XCTAssertEqual(
            WeatherExplainer.textProductPrompt(
                text: "A cold front will cross the area.",
                productType: "AFD",
                locationName: "Springdale",
                style: .brief
            ),
            "Please explain this National Weather Service text product (AFD) for Springdale in plain language:\n\nA cold front will cross the area.\n\nProvide a 2-3 sentence summary of the key points."
        )
        XCTAssertEqual(
            WeatherExplainer.stripMarkdown("## **A note**\n\n- *Rain* and [travel](https://example.test)\n\n\nMore"),
            "A note\nRain and travel\n\nMore"
        )
    }

    func testOpenRouterErrorsAndRequiredRequestHeadersUseStubbedURLProtocol() async throws {
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [URLProtocolStub.self]
        let client = OpenRouterClient(session: URLSession(configuration: configuration))
        var capturedRequest: URLRequest?
        URLProtocolStub.handler = { request in
            capturedRequest = request
            return (401, Data(#"{"error":"unauthorized"}"#.utf8))
        }
        defer { URLProtocolStub.handler = nil }

        do {
            _ = try await client.complete(
                system: "System prompt",
                user: "User prompt",
                model: "openrouter/free",
                key: "unit-test-key"
            )
            XCTFail("Expected an OpenRouter authorization error")
        } catch WeatherError.unsupported(let message) {
            XCTAssertEqual(
                message,
                "Your OpenRouter API key is invalid. Please check Settings > AI and verify your API key. Get a free key at: openrouter.ai/keys"
            )
        }
        XCTAssertEqual(capturedRequest?.value(forHTTPHeaderField: "HTTP-Referer"), "https://accessiweather.orinks.net")
        XCTAssertEqual(capturedRequest?.value(forHTTPHeaderField: "X-Title"), "AccessiWeather")
        let body = try XCTUnwrap(capturedRequest?.httpBody)
        let json = try XCTUnwrap(JSONSerialization.jsonObject(with: body) as? [String: Any])
        XCTAssertEqual(json["model"] as? String, "openrouter/free")

        URLProtocolStub.handler = { _ in (402, Data(#"{"error":"payment required"}"#.utf8)) }
        do {
            _ = try await client.complete(system: "", user: "", model: "openrouter/free", key: "unit-test-key")
            XCTFail("Expected an OpenRouter payment error")
        } catch WeatherError.unsupported(let message) {
            XCTAssertEqual(
                message,
                "Your OpenRouter account has no funds. Add credits at openrouter.ai/credits or switch to a free model in Settings > AI."
            )
        }
    }

    func testOpenMeteoHistoryAndAirQualityFixturesDecode() throws {
        let history = try JSONDecoder().decode(
            OpenMeteoClient.ForecastResponse.self,
            from: fixture("history-springdale")
        )
        XCTAssertEqual(history.timezone, "America/Chicago")
        XCTAssertEqual(history.daily?.time.count, 8)
        XCTAssertEqual(history.daily?.temperature_2m_mean?.count, 8)

        let airQuality = try JSONDecoder().decode(
            OpenMeteoClient.AirQualityResponse.self,
            from: fixture("air-quality-springdale")
        )
        XCTAssertNotNil(airQuality.current?.us_aqi)
        XCTAssertEqual(airQuality.hourly?.time.count, 24)
    }

    func testWeatherHistoryComparisonsRespectUnitsAndConditions() {
        let day = WeatherHistoryDay(
            date: Date(timeIntervalSince1970: 0),
            highC: 24,
            lowC: 14,
            meanC: 20,
            condition: "Rain"
        )
        XCTAssertEqual(
            WeatherHistory.comparison(
                currentTemperatureC: 21,
                currentCondition: "Clear",
                historicalDay: day,
                daysAgo: 7,
                unit: .fahrenheit
            ),
            "Compared to last week: 1.8 degrees warmer. Changed from Rain to Clear."
        )
        XCTAssertEqual(
            WeatherHistory.comparison(
                currentTemperatureC: 20,
                currentCondition: "Rain",
                historicalDay: day,
                daysAgo: 1,
                unit: .celsius
            ),
            "Compared to yesterday: about the same temperature."
        )
        XCTAssertNil(
            WeatherHistory.comparison(
                currentTemperatureC: nil,
                currentCondition: nil,
                historicalDay: day,
                daysAgo: 1,
                unit: .celsius
            )
        )
    }

    func testUVCategoriesAndSafetyGuidance() {
        let cases: [(Double, String)] = [
            (2.99, "Low"), (3, "Moderate"), (5.99, "Moderate"),
            (6, "High"), (7.99, "High"), (8, "Very High"),
            (10.99, "Very High"), (11, "Extreme"),
        ]
        for (index, expected) in cases {
            XCTAssertEqual(WeatherFormatter.uvCategory(index), expected)
        }
        XCTAssertEqual(UVIndexGuidance.guidance(for: "Extreme"), "Try to avoid sun exposure between 10am and 4pm. Shirt, sunscreen, and hat are essential.")
        XCTAssertTrue(UVIndexGuidance.recommendations(for: "High")?.contains("Stay hydrated") == true)
        XCTAssertNil(UVIndexGuidance.recommendations(for: "Unknown"))
    }

    @MainActor
    func testRadioAutoTunePreferenceDefaultsOffAndPersists() {
        let defaults = UserDefaults(suiteName: "RadioAutoTuneTests.\(UUID().uuidString)")!
        let settings = SettingsStore(defaults: defaults)
        XCTAssertFalse(settings.radioAutoTuneEnabled)
        settings.radioAutoTuneEnabled = true
        XCTAssertTrue(SettingsStore(defaults: defaults).radioAutoTuneEnabled)
    }

    func testICAOValidationAndKXNAAviationFixtures() throws {
        XCTAssertNil(ICAOCodeValidation.error(for: " kjfk\n"))
        XCTAssertEqual(
            ICAOCodeValidation.error(for: ""),
            "Please enter a four-letter ICAO airport code."
        )
        XCTAssertEqual(
            ICAOCodeValidation.error(for: "ABC"),
            "Airport codes must be exactly four letters (e.g., KJFK)."
        )
        XCTAssertEqual(
            ICAOCodeValidation.error(for: "KJ1K"),
            "Airport codes must be exactly four letters (e.g., KJFK)."
        )

        let metars = try JSONDecoder().decode([METARObservation].self, from: fixture("metar-kxna"))
        XCTAssertEqual(String(metars.first?.rawOb?.prefix(5) ?? ""), "METAR")
        XCTAssertEqual(AviationWeatherFormatting.visibility(metars.first?.visib), "10+ statute miles")
        XCTAssertNotNil(metars.first?.observationDate)

        let variable = try JSONDecoder().decode(METARObservation.self, from: fixture("metar-variable"))
        XCTAssertEqual(
            AviationWeatherFormatting.wind(direction: variable.wdir, speed: variable.wspd, gust: nil),
            "from variable direction, at 8 knots"
        )
        XCTAssertEqual(AviationWeatherFormatting.visibility(variable.visib), "10+ statute miles")

        let tafs = try JSONDecoder().decode([TAFProduct].self, from: fixture("taf-kxna"))
        XCTAssertFalse(tafs.first?.fcsts?.isEmpty ?? true)
        XCTAssertNotNil(tafs.first?.fcsts?.first?.startDate)
    }

    @MainActor
    func testEventLogDiffsAlertLifecyclePersistsAndCapsEntries() throws {
        let directory = FileManager.default.temporaryDirectory
            .appendingPathComponent("AccessiWeatherTests-\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: directory) }
        let fileURL = directory.appendingPathComponent("events.json")
        let log = EventLog(fileURL: fileURL)
        let existing = alert(id: "existing", headline: "Original headline", expires: Date(timeIntervalSince1970: 100))
        let ended = alert(id: "ended", headline: "Ending alert", expires: Date(timeIntervalSince1970: 200))
        var updated = existing
        updated.headline = "Updated headline"
        updated.expires = Date(timeIntervalSince1970: 300)
        let added = alert(id: "new", headline: "New warning", expires: nil)

        let changes = log.recordAlertChanges(
            previous: [existing, ended],
            current: [updated, added],
            locationName: "Springdale"
        )
        XCTAssertEqual(changes.new.map(\.id), ["new"])
        XCTAssertEqual(changes.updated.map(\.id), ["existing"])
        XCTAssertEqual(changes.ended.map(\.id), ["ended"])
        XCTAssertEqual(Set(log.entries.map(\.kind)), [.newAlert, .updatedAlert, .alertEnded])
        XCTAssertTrue(log.entries.first(where: { $0.kind == .newAlert })?.accessibleSummary.contains("New alert, Severe Thunderstorm Warning, Springdale") == true)

        for index in 0..<205 {
            log.record(kind: .discussionUpdated, locationName: "Springdale", title: "\(index)", detail: "")
        }
        XCTAssertEqual(log.entries.count, EventLog.maximumEntries)
        XCTAssertEqual(log.entries.first?.title, "204")
        XCTAssertEqual(EventLog(fileURL: fileURL).entries.count, EventLog.maximumEntries)
        log.clear()
        XCTAssertTrue(EventLog(fileURL: fileURL).entries.isEmpty)
    }

    @MainActor
    func testLocationReorderingPersistsAcrossStoreReloads() throws {
        let directory = FileManager.default.temporaryDirectory
            .appendingPathComponent("AccessiWeatherLocations-\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: directory) }
        let fileURL = directory.appendingPathComponent("locations.json")
        let store = LocationStore(fileURL: fileURL)
        let first = SavedLocation(name: "Springdale", latitude: 36.18, longitude: -94.13)
        let second = SavedLocation(name: "Fayetteville", latitude: 36.06, longitude: -94.16)
        let third = SavedLocation(name: "Bentonville", latitude: 36.37, longitude: -94.21)
        store.add(first)
        store.add(second)
        store.add(third)
        store.move(fromOffsets: IndexSet(integer: 0), toOffset: 3)

        XCTAssertEqual(LocationStore(fileURL: fileURL).locations.map(\.id), [second.id, third.id, first.id])
    }

    private func fixture(_ name: String) throws -> Data {
        let bundle = Bundle(for: Self.self)
        let url = bundle.url(forResource: name, withExtension: "json", subdirectory: "Fixtures")
            ?? bundle.url(forResource: name, withExtension: "json")
        return try Data(contentsOf: XCTUnwrap(url))
    }

    private func alert(id: String, headline: String?, expires: Date?) -> WeatherAlert {
        WeatherAlert(
            id: id,
            event: "Severe Thunderstorm Warning",
            severity: "Severe",
            urgency: nil,
            certainty: nil,
            headline: headline,
            description: nil,
            instruction: nil,
            areaDescription: nil,
            sender: "NWS",
            effective: nil,
            expires: expires
        )
    }

    private func sampleReport() -> WeatherReport {
        let location = SavedLocation(name: "Springdale", latitude: 36.18, longitude: -94.13)
        let current = CurrentConditions(
            description: "Light Rain",
            temperatureC: 24,
            dewpointC: 18,
            humidityPercent: 50,
            windSpeedKph: 18,
            windDirectionDegrees: 180,
            pressureHpa: 1012,
            visibilityKm: 9.5,
            uvIndex: nil,
            sunrise: nil,
            sunset: nil,
            airQuality: nil,
            observedAt: nil
        )
        let daily = DailyPeriod(
            id: "today",
            name: "Today",
            date: Date(timeIntervalSince1970: 0),
            isDaytime: true,
            highC: 29,
            lowC: 18,
            condition: "Rain",
            detailedForecast: nil,
            windSpeedKph: 18,
            windDirectionDegrees: 180,
            windText: nil,
            precipitationChance: 70
        )
        return WeatherReport(
            location: location,
            current: current,
            hourly: [],
            daily: [daily],
            alerts: [alert(id: "warning", headline: "Warning in Springdale", expires: nil)],
            sourceDescription: "National Weather Service",
            timeZone: TimeZone(identifier: "America/Chicago")!,
            fetchedAt: Date(timeIntervalSince1970: 1_790_683_200),
            forecastOfficeID: "TSA"
        )
    }
}

private final class URLProtocolStub: URLProtocol {
    static var handler: ((URLRequest) -> (Int, Data))?

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        guard let handler, let url = request.url else {
            client?.urlProtocol(self, didFailWithError: URLError(.badServerResponse))
            return
        }
        let (status, data) = handler(request)
        guard let response = HTTPURLResponse(
                  url: url,
                  statusCode: status,
                  httpVersion: nil,
                  headerFields: ["Content-Type": "application/json"]
              ) else {
            client?.urlProtocol(self, didFailWithError: URLError(.badServerResponse))
            return
        }
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: data)
        client?.urlProtocolDidFinishLoading(self)
    }

    override func stopLoading() {}
}
