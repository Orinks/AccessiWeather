import XCTest
@testable import AccessiWeather

final class IEMClientTests: XCTestCase {
    func testStripsControlCharactersAndTrims() throws {
        let body = "\u{1}\n000\r\nFXUS01 KWBC 161200\nPMDSPD\u{3}\n\n"
        XCTAssertEqual(try IEMClient.productText(body, productID: "PMDSPD"), "000\r\nFXUS01 KWBC 161200\nPMDSPD")
    }

    func testEmptyBodyIsAnError() {
        XCTAssertThrowsError(try IEMClient.productText(" \n\u{1}", productID: "SWODY1")) { error in
            XCTAssertEqual(error.localizedDescription, "IEM AFOS returned no text for SWODY1")
        }
    }

    func testInBodyErrorReportsFirstLine() {
        XCTAssertThrowsError(try IEMClient.productText("\n  ERROR: No products found\nmore", productID: "TWOAT")) { error in
            XCTAssertEqual(error.localizedDescription, "ERROR: No products found")
        }
    }

    func testNationalProductsMatchDesktopTabs() {
        XCTAssertEqual(NationalProduct.allCases.map(\.rawValue), [
            "PMDSPD", "PMDEPD", "PMDET4", "QPFPFD", "PMDMRD", "TWOAT", "TWOEP", "SWODY1", "SWODY2", "SWODY3",
        ])
    }
}
