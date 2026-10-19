import Foundation

/// National AFOS text products from the Iowa Environmental Mesonet, as in Rust `products::iem`.
struct IEMClient {
    static let baseURL = "https://mesonet.agron.iastate.edu"

    var http = HTTPClient.shared

    /// The latest issuance of an AFOS product (`retrieve.py?pil=…&fmt=text&limit=1&order=desc`).
    func latestText(pil: String) async throws -> String {
        let productID = pil.trimmingCharacters(in: .whitespacesAndNewlines).uppercased()
        var components = URLComponents(string: "\(Self.baseURL)/cgi-bin/afos/retrieve.py")!
        components.queryItems = [
            URLQueryItem(name: "pil", value: productID),
            URLQueryItem(name: "fmt", value: "text"),
            URLQueryItem(name: "limit", value: "1"),
            URLQueryItem(name: "order", value: "desc"),
        ]
        let data = try await http.data(from: components.url!, serviceName: "IEM AFOS")
        return try Self.productText(String(decoding: data, as: UTF8.self), productID: productID)
    }

    /// `clean_iem_text` plus the empty and in-body `ERROR:` checks from Rust `afos_text`.
    static func productText(_ body: String, productID: String) throws -> String {
        let kept = String(String.UnicodeScalarView(body.unicodeScalars.filter {
            $0 == "\n" || $0 == "\r" || $0 == "\t" || $0.value >= 32
        }))
        let text = kept.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else {
            throw WeatherError.unsupported("IEM AFOS returned no text for \(productID)")
        }
        let firstLine = text.split(whereSeparator: \.isNewline)
            .map { $0.trimmingCharacters(in: .whitespaces) }
            .first { !$0.isEmpty } ?? ""
        if firstLine.uppercased().hasPrefix("ERROR:") {
            throw WeatherError.unsupported(firstLine)
        }
        return text
    }
}

/// `NATIONAL_TABS`, in the desktop National Products dialog's order.
enum NationalProduct: String, CaseIterable, Identifiable {
    case wpcShortRange = "PMDSPD"
    case wpcMediumRange = "PMDEPD"
    case wpcExtended = "PMDET4"
    case wpcQPF = "QPFPFD"
    case cpcOutlook = "PMDMRD"
    case nhcAtlantic = "TWOAT"
    case nhcEastPacific = "TWOEP"
    case spcDay1 = "SWODY1"
    case spcDay2 = "SWODY2"
    case spcDay3 = "SWODY3"

    var id: String { rawValue }

    var label: String {
        switch self {
        case .wpcShortRange: return "WPC Short Range"
        case .wpcMediumRange: return "WPC Medium Range"
        case .wpcExtended: return "WPC Extended"
        case .wpcQPF: return "WPC QPF Discussion"
        case .cpcOutlook: return "CPC Outlook"
        case .nhcAtlantic: return "NHC Atlantic Outlook"
        case .nhcEastPacific: return "NHC East Pacific Outlook"
        case .spcDay1: return "SPC Day 1 Outlook"
        case .spcDay2: return "SPC Day 2 Outlook"
        case .spcDay3: return "SPC Day 3 Outlook"
        }
    }
}
