import XCTest

/// Fast VoiceOver smoke check: one launch, no live-data waits, one built-in audit per tab.
final class AccessibilityAuditTests: XCTestCase {
    private let tabs = ["Weather", "Alerts", "Locations", "Settings"]

    func testTabsAreLabeledAndPassAudit() throws {
        continueAfterFailure = true
        let app = XCUIApplication()
        app.launch()

        for tab in tabs {
            let button = app.tabBars.buttons[tab]
            XCTAssertTrue(button.waitForExistence(timeout: 5), "Missing tab \(tab)")
            button.tap()
            XCTAssertTrue(app.navigationBars.firstMatch.waitForExistence(timeout: 3), "\(tab) has no navigation bar")
            let unlabeled = app.buttons.matching(NSPredicate(format: "label == ''")).count
            XCTAssertEqual(unlabeled, 0, "\(tab) has \(unlabeled) unlabeled buttons")
            try app.performAccessibilityAudit(for: [.sufficientElementDescription, .trait, .hitRegion]) { issue in
                issue.element == nil
            }
        }
    }

    func testSettingsAndAddLocationControlsAreLabeled() {
        let app = XCUIApplication()
        app.launch()

        app.tabBars.buttons["Settings"].tap()
        XCTAssertTrue(app.staticTexts["Units"].waitForExistence(timeout: 5))
        for label in ["Temperature", "Wind speed"] {
            XCTAssertTrue(app.staticTexts[label].firstMatch.exists || app.buttons[label].firstMatch.exists, "Missing \(label)")
        }
        XCTAssertGreaterThan(app.switches.matching(NSPredicate(format: "label != ''")).count, 0, "Settings toggles need labels")

        app.tabBars.buttons["Locations"].tap()
        let add = app.navigationBars.buttons["Add Location"]
        XCTAssertTrue(add.waitForExistence(timeout: 5), "Add button must be labeled 'Add Location'")
        add.tap()
        XCTAssertTrue(app.buttons["Use Current Location"].waitForExistence(timeout: 3))
        XCTAssertTrue(app.buttons["Cancel"].exists)
        app.buttons["Cancel"].tap()
    }
}
