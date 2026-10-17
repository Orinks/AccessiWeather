import XCTest
@testable import AccessiWeather

final class AviationAdvisoriesTests: XCTestCase {
    func testTokensAndFilterKeepNearbyAdvisories() {
        let tokens = AviationAdvisories.tokens(station: "KJFK", metadata: ["cwa": "zny", "wfo": "OKX", "state": "NY"], airportName: "New York-Kennedy Intl")
        XCTAssertEqual(tokens, ["KJFK", "ZNY", "OKX", "NY", "NEW", "YORK", "KENNEDY", "INTL"])
        let entries: [[String: Any]] = [["name": "Convective SIGMET", "area": ["ZNY", "ZBW"]], ["name": "Turbulence", "fir": "ZLA"]]
        XCTAssertEqual(AviationAdvisories.filter(entries, tokens: ["ZNY"]).count, 1)
        XCTAssertEqual(AviationAdvisories.filter(entries, tokens: []).count, 2)
    }

    func testSummaries() {
        XCTAssertEqual(
            AviationAdvisories.summarizeSIGMET(["hazard": "TURB", "severity": "MOD", "fir": ["ZNY", "ZBW"], "startTime": "1200Z", "endTime": "1600Z", "text": "Below FL180"]),
            "TURB severity MOD; Area: ZNY, ZBW; Valid 1200Z to 1600Z; Below FL180"
        )
        XCTAssertEqual(AviationAdvisories.summarizeCWA(["cwsu": "ZNY", "issueTime": "1300Z"]), "Center Weather Advisory (ZNY); Issued 1300Z")
        XCTAssertTrue(AviationAdvisories.isUSStation(" kjfk"))
        XCTAssertFalse(AviationAdvisories.isUSStation("EGLL"))
    }
}
