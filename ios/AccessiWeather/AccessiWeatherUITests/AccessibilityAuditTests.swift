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
}
