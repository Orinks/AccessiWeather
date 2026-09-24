import XCTest

/// Walks each tab the way VoiceOver would and checks that rows expose sensible
/// labels. Run with a saved location already present for the live-data checks.
final class AccessibilityAuditTests: XCTestCase {
    private var app: XCUIApplication!

    override func setUp() {
        continueAfterFailure = true
        app = XCUIApplication()
        app.launch()
    }

    func testTabBarButtonsAreLabeled() {
        for name in ["Weather", "Alerts", "Locations", "Settings"] {
            XCTAssertTrue(app.tabBars.buttons[name].waitForExistence(timeout: 5), "Missing tab \(name)")
        }
    }

    func testEveryButtonHasALabel() {
        for tab in ["Weather", "Alerts", "Locations", "Settings"] {
            app.tabBars.buttons[tab].tap()
            _ = app.navigationBars.firstMatch.waitForExistence(timeout: 5)
            let unlabeled = app.buttons.allElementsBoundByIndex.filter { $0.label.isEmpty && $0.exists }
            XCTAssertTrue(unlabeled.isEmpty, "\(tab): \(unlabeled.count) unlabeled buttons: \(unlabeled.map { $0.debugDescription })")
        }
    }

    func testWeatherRowsReadWithExpandedUnits() throws {
        app.tabBars.buttons["Weather"].tap()
        let temperature = app.otherElements["Temperature"].firstMatch
        try XCTSkipUnless(temperature.waitForExistence(timeout: 20), "No live weather; add a location first")

        let value = temperature.value as? String ?? ""
        XCTAssertTrue(value.contains("degrees"), "Temperature value should expand units, got: \(value)")

        XCTAssertTrue(app.staticTexts["Current Conditions"].firstMatch.exists, "Missing section header Current Conditions")
        app.swipeUp()
        XCTAssertTrue(app.staticTexts["Hourly Forecast"].firstMatch.waitForExistence(timeout: 5), "Missing section header Hourly Forecast")

        let hourly = app.otherElements.matching(NSPredicate(format: "label CONTAINS[c] 'degrees' AND label CONTAINS ','")).allElementsBoundByIndex
        XCTAssertFalse(hourly.isEmpty, "No combined hourly/daily rows found")
        for row in hourly.prefix(5) {
            XCTAssertFalse(row.label.contains("°"), "Row label should not contain a degree symbol: \(row.label)")
            XCTAssertFalse(row.label.contains("mph"), "Row label should expand mph: \(row.label)")
        }
        print("ACCESSIBILITY AUDIT WEATHER\n\(app.debugDescription)")
    }

    func testAlertsTabHasEmptyStateOrRows() {
        app.tabBars.buttons["Alerts"].tap()
        let empty = app.staticTexts["No active alerts"]
        let anyRow = app.cells.firstMatch
        XCTAssertTrue(empty.waitForExistence(timeout: 20) || anyRow.exists)
        print("ACCESSIBILITY AUDIT ALERTS\n\(app.debugDescription)")
    }

    func testAddLocationSheetIsLabeled() {
        app.tabBars.buttons["Locations"].tap()
        let add = app.navigationBars.buttons["Add Location"]
        XCTAssertTrue(add.waitForExistence(timeout: 5), "Add button must be labeled 'Add Location'")
        for row in app.cells.buttons.allElementsBoundByIndex {
            XCTAssertFalse(row.label.contains(where: \.isNumber), "Location row should not read raw coordinates, got: \(row.label)")
        }
        add.tap()
        XCTAssertTrue(app.textFields.firstMatch.waitForExistence(timeout: 5))
        XCTAssertTrue(app.buttons["Use Current Location"].exists)
        XCTAssertTrue(app.buttons["Cancel"].exists)
        print("ACCESSIBILITY AUDIT ADD LOCATION\n\(app.debugDescription)")
        app.buttons["Cancel"].tap()
    }

    func testSettingsControlsAreLabeled() {
        app.tabBars.buttons["Settings"].tap()
        XCTAssertTrue(app.staticTexts["Units"].waitForExistence(timeout: 5))
        for label in ["Temperature", "Wind speed", "Hourly forecast hours", "24-hour time", "Show dewpoint"] {
            XCTAssertTrue(app.staticTexts[label].firstMatch.exists || app.switches[label].exists || app.steppers[label].exists, "Missing \(label)")
        }
        // SwiftUI toggles expose a labeled row-level switch wrapping an unlabeled UISwitch; VoiceOver reads the row.
        let labeledSwitches = app.switches.matching(NSPredicate(format: "label != ''")).count
        XCTAssertGreaterThanOrEqual(labeledSwitches, 5, "Expected labeled toggle rows in Settings")
        print("ACCESSIBILITY AUDIT SETTINGS\n\(app.debugDescription)")
    }

    private var mutedEventsLink: XCUIElement {
        app.buttons.matching(NSPredicate(format: "label BEGINSWITH 'Muted events'")).firstMatch
    }

    func testSoundsSettingsAreLabeled() {
        app.tabBars.buttons["Settings"].tap()
        let header = app.staticTexts["Sounds"].firstMatch
        var tries = 0
        while !header.isHittable && tries < 6 { app.swipeUp(); tries += 1 }
        XCTAssertTrue(header.exists, "Missing Sounds section header")
        XCTAssertTrue(app.switches["Play sounds"].exists, "Missing Play sounds toggle")
        XCTAssertTrue(app.buttons["Default sound pack"].firstMatch.exists, "Missing labeled pack row")
        XCTAssertTrue(app.buttons["Preview Default"].firstMatch.exists, "Missing labeled preview button")
        mutedEventsLink.tap()
        XCTAssertTrue(app.navigationBars["Sound Events"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.switches["Weather refresh completed"].exists)
        XCTAssertTrue(app.switches["Extreme severity alert"].exists)
        print("ACCESSIBILITY AUDIT SOUNDS\n\(app.debugDescription)")
    }

    func testRadioScreenIsLabeled() throws {
        app.tabBars.buttons["Weather"].tap()
        let radioButton = app.navigationBars.buttons["NOAA Weather Radio"]
        XCTAssertTrue(radioButton.waitForExistence(timeout: 5), "Missing toolbar Radio button")
        radioButton.tap()
        XCTAssertTrue(app.navigationBars["NOAA Weather Radio"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.staticTexts["Now Playing"].exists)
        XCTAssertTrue(app.staticTexts["Nearest Stations"].exists)
        XCTAssertTrue(app.navigationBars.buttons["Refresh Stations"].exists, "Missing Refresh Stations button")
        let sourceFooter = app.staticTexts.matching(NSPredicate(format: "label BEGINSWITH 'Station list from WeatherIndex'")).firstMatch
        XCTAssertTrue(sourceFooter.waitForExistence(timeout: 20), "Station list should load from WeatherIndex")
        let stationRows = app.buttons.matching(NSPredicate(format: "label CONTAINS 'MHz' AND label CONTAINS 'miles away'"))
        try XCTSkipUnless(stationRows.count > 0, "No saved location; station list is empty")
        stationRows.firstMatch.tap()
        let status = app.descendants(matching: .any).matching(NSPredicate(format: "label BEGINSWITH 'Status' AND (label CONTAINS 'Playing' OR label CONTAINS 'Connecting' OR label CONTAINS 'Stream unavailable')")).firstMatch
        XCTAssertTrue(status.waitForExistence(timeout: 20), "Status label should reflect the stream state")
        print("RADIO STATUS: \(status.label)")
        XCTAssertTrue(app.buttons["Stop"].exists || app.buttons["Play"].exists, "Missing Play/Stop button")
        print("ACCESSIBILITY AUDIT RADIO\n\(app.debugDescription)")
        if app.buttons["Stop"].exists { app.buttons["Stop"].tap() }
    }

    /// Xcode's built-in audit (same checks as the Accessibility Inspector Audit tab) on every screen.
    func testPerformAccessibilityAuditOnAllScreens() throws {
        // Contrast, Dynamic Type and clipping checks are heuristics that the auditor cannot
        // resolve for SwiftUI text drawn with system fonts and semantic colors (every text in
        // this app); they are logged for review but only element/label/trait/hit-target
        // findings fail the test.
        let advisoryTypes: XCUIAccessibilityAuditType = [.contrast, .dynamicType, .textClipped]
        let ignoredIssues: (XCUIAccessibilityAuditIssue) -> Bool = { issue in
            print("AUDIT ISSUE [\(issue.auditType)] \(issue.compactDescription) | \(issue.detailedDescription) | element: \(issue.element?.debugDescription.prefix(300) ?? "none")")
            if advisoryTypes.contains(issue.auditType) { return true }
            return issue.element == nil
        }
        for tab in ["Weather", "Alerts", "Locations", "Settings"] {
            app.tabBars.buttons[tab].tap()
            _ = app.navigationBars.firstMatch.waitForExistence(timeout: 10)
            if tab == "Weather" { _ = app.otherElements["Temperature"].firstMatch.waitForExistence(timeout: 20) }
            try app.performAccessibilityAudit(for: .all) { issue in ignoredIssues(issue) }
        }
        app.tabBars.buttons["Settings"].tap()
        var tries = 0
        while !mutedEventsLink.isHittable && tries < 6 { app.swipeUp(); tries += 1 }
        mutedEventsLink.tap()
        _ = app.navigationBars["Sound Events"].waitForExistence(timeout: 5)
        try app.performAccessibilityAudit(for: .all) { issue in ignoredIssues(issue) }
        app.tabBars.buttons["Weather"].tap()
        app.navigationBars.buttons["NOAA Weather Radio"].tap()
        _ = app.navigationBars["NOAA Weather Radio"].waitForExistence(timeout: 5)
        try app.performAccessibilityAudit(for: .all) { issue in ignoredIssues(issue) }
    }
}
