import XCTest
@testable import AccessiWeather

final class AlertNotificationGateTests: XCTestCase {
    private let home = SavedLocation(name: "Home", latitude: 40, longitude: -75)
    private let all = AlertGateSettings(notificationsEnabled: true, notifiedSeverities: ["extreme", "severe", "moderate", "minor"])
    private let start = Date(timeIntervalSince1970: 1_800_000_000)

    private func alert(_ id: String = "a1", severity: String = "Moderate", headline: String = "Wind advisory until 6 PM") -> WeatherAlert {
        WeatherAlert(id: id, event: "Wind Advisory", severity: severity, headline: headline, expires: start.addingTimeInterval(86_400))
    }

    func testNewAlertNotifiesOnceAndSurvivesRelaunch() throws {
        var gate = AlertNotificationGate()
        XCTAssertEqual(gate.process([(home, [alert()])], settings: all, now: start).map(\.reason), [.new])

        let relaunched = try JSONDecoder().decode(AlertNotificationGate.self, from: JSONEncoder().encode(gate))
        var restored = relaunched
        XCTAssertTrue(restored.process([(home, [alert()])], settings: all, now: start.addingTimeInterval(3600)).isEmpty)
    }

    func testChangedContentIsAnUpdateAndHigherSeverityIsAnEscalation() {
        var gate = AlertNotificationGate()
        _ = gate.process([(home, [alert()])], settings: all, now: start)
        let updated = gate.process([(home, [alert(headline: "Wind advisory extended to 9 PM")])], settings: all, now: start.addingTimeInterval(600))
        XCTAssertEqual(updated.map(\.reason), [.updated])
        let escalated = gate.process([(home, [alert(severity: "Severe")])], settings: all, now: start.addingTimeInterval(1200))
        XCTAssertEqual(escalated.map(\.reason), [.escalated])
    }

    func testGlobalCooldownDefersAlertsUntilLaterCheck() {
        var gate = AlertNotificationGate()
        _ = gate.process([(home, [alert("a1")])], settings: all, now: start)
        XCTAssertTrue(gate.process([(home, [alert("a1"), alert("a2")])], settings: all, now: start.addingTimeInterval(120)).isEmpty)
        let later = gate.process([(home, [alert("a1"), alert("a2")])], settings: all, now: start.addingTimeInterval(400))
        XCTAssertEqual(later.map(\.alert.id), ["a2"])
    }

    func testHourlyRateLimitCapsABurst() {
        var gate = AlertNotificationGate()
        let burst = (1...15).map { alert("a\($0)") }
        XCTAssertEqual(gate.process([(home, burst)], settings: all, now: start).count, 10)
    }

    func testDisabledSeveritiesExpiredAndDuplicateAlertsAreSkipped() {
        var gate = AlertNotificationGate()
        let severeOnly = AlertGateSettings(notificationsEnabled: true, notifiedSeverities: ["severe"])
        var expired = alert("old", severity: "Severe")
        expired.expires = start.addingTimeInterval(-60)
        let work = SavedLocation(name: "Work", latitude: 40.1, longitude: -75.1)
        let notices = gate.process(
            [(home, [alert("minor"), expired, alert("s1", severity: "Severe")]), (work, [alert("s1", severity: "Severe")])],
            settings: severeOnly,
            now: start
        )
        XCTAssertEqual(notices.map(\.alert.id), ["s1"])
        XCTAssertEqual(notices.first?.locationName, "Home")
    }

    func testNotificationsOffRecordsNothing() {
        var gate = AlertNotificationGate()
        var off = all
        off.notificationsEnabled = false
        XCTAssertTrue(gate.process([(home, [alert()])], settings: off, now: start).isEmpty)
        XCTAssertEqual(gate.process([(home, [alert()])], settings: all, now: start).count, 1)
    }
}

final class NotificationEventStateTests: XCTestCase {
    private let now = Date(timeIntervalSince1970: 1_800_000_000)
    private let both = EventNotificationSettings(
        discussionUpdates: true, hazardousWeatherOutlook: true, specialWeatherStatements: true,
        precipitationStart: true, precipitationStop: true
    )

    private func minutes(wetFrom: Int?, until: Int? = nil) -> [MinutelyPoint] {
        (0..<60).map { minute in
            let wet = wetFrom.map { minute >= $0 && minute < (until ?? 60) } ?? false
            return MinutelyPoint(time: now.addingTimeInterval(Double(minute) * 60), precipitationIntensity: wet ? 0.05 : 0, precipitationProbability: wet ? 0.8 : 0, precipitationType: wet ? "rain" : nil)
        }
    }

    func testDiscussionFirstSightingIsABaselineThenNewIssuanceNotifies() {
        var state = NotificationEventState()
        XCTAssertNil(state.checkDiscussion(issuance: now, text: "Old", locationName: "Home", enabled: true))
        let text = ".WHAT HAS CHANGED...\nAdded thunderstorm chances Friday.\n\n&&"
        let event = state.checkDiscussion(issuance: now.addingTimeInterval(3600), text: text, locationName: "Home", enabled: true)
        XCTAssertEqual(event?.title, "Forecast Discussion Updated")
        XCTAssertTrue(event?.body.contains("Added thunderstorm chances Friday.") ?? false)
    }

    func testDiscussionThatDeclaresNoChangesIsQuiet() {
        var state = NotificationEventState()
        _ = state.checkDiscussion(issuance: now, text: "Old", locationName: "Home", enabled: true)
        let text = ".WHAT HAS CHANGED...\nNo significant changes.\n\n&&"
        XCTAssertNil(state.checkDiscussion(issuance: now.addingTimeInterval(3600), text: text, locationName: "Home", enabled: true))
    }

    func testHWOChangeNotifiesAndIsRateLimited() {
        var state = NotificationEventState()
        XCTAssertNil(state.checkHWO(issuance: now, text: "A", officeID: "PHI", enabled: true, now: now))
        XCTAssertNotNil(state.checkHWO(issuance: now.addingTimeInterval(60), text: "B", officeID: "PHI", enabled: true, now: now))
        XCTAssertNil(state.checkHWO(issuance: now.addingTimeInterval(120), text: "C", officeID: "PHI", enabled: true, now: now.addingTimeInterval(60)))
    }

    func testNewSPSNotifiesUnlessAnAlertCoversIt() async {
        var state = NotificationEventState()
        let body = "Strong thunderstorms will affect northern Chester County through 545 PM with gusty winds."
        let none = await state.checkSPS(productIDs: ["1"], coveredByAlert: false, enabled: true, now: now) { _ in body }
        XCTAssertNil(none)
        let covered = await state.checkSPS(productIDs: ["2", "1"], coveredByAlert: true, enabled: true, now: now) { _ in body }
        XCTAssertNil(covered)
        let fresh = await state.checkSPS(productIDs: ["3", "2", "1"], coveredByAlert: false, enabled: true, now: now) { _ in body }
        XCTAssertEqual(fresh?.body, body)
    }

    func testFirstRainStartNotifiesWhenFirstSeenBeyondLeadTime() {
        var state = NotificationEventState()
        XCTAssertNil(state.checkMinutely(minutes(wetFrom: 30), locationName: "Home", settings: both, now: now))
        XCTAssertEqual(state.checkMinutely(minutes(wetFrom: 5), locationName: "Home", settings: both, now: now)?.title, "Rain starting in 5 minutes")
    }

    func testPrecipitationStartAndStopTransitions() {
        var state = NotificationEventState()
        XCTAssertNil(state.checkMinutely(minutes(wetFrom: nil), locationName: "Home", settings: both, now: now))
        XCTAssertNil(state.checkMinutely(minutes(wetFrom: 30), locationName: "Home", settings: both, now: now), "Too far out to announce yet")
        XCTAssertEqual(state.checkMinutely(minutes(wetFrom: 5), locationName: "Home", settings: both, now: now)?.title, "Rain starting in 5 minutes")
        XCTAssertNil(state.checkMinutely(minutes(wetFrom: 4), locationName: "Home", settings: both, now: now), "Same transition only notifies once")
        XCTAssertEqual(state.checkMinutely(minutes(wetFrom: 0, until: 8), locationName: "Home", settings: both, now: now)?.title, "Rain stopping in 8 minutes")
    }
}
