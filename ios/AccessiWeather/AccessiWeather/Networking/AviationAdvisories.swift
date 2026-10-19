import Foundation

/// SIGMET/AIRMET and Center Weather Advisory lookups plus AVWX TAFs, after Rust `nws::aviation` and `nws::avwx`.
enum AviationAdvisories {
    static let usICAOPrefixes = ["K", "PA", "PH", "PG", "PF", "PK", "PP"]

    static func isUSStation(_ icao: String) -> Bool {
        let code = icao.trimmingCharacters(in: .whitespaces).uppercased()
        return !code.isEmpty && usICAOPrefixes.contains { code.hasPrefix($0) }
    }

    /// `station_tokens`: the station, its CWSU, WFO, state, and airport-name words longer than two letters.
    static func tokens(station: String, metadata: [String: Any], airportName: String?) -> Set<String> {
        var tokens: Set<String> = [station.uppercased()]
        for key in ["cwa", "wfo", "state"] {
            if let value = normalized(metadata[key]) { tokens.insert(value) }
        }
        for part in (airportName ?? "").replacingOccurrences(of: "-", with: " ").split(separator: " ") {
            let word = part.trimmingCharacters(in: .whitespaces).uppercased()
            if word.count > 2 { tokens.insert(word) }
        }
        return tokens
    }

    static let filterKeys = ["fir", "area", "regions", "airspace", "name", "event", "hazard", "description",
                             "summary", "text", "issuingOffice", "cwsu", "cwsuId", "stationId", "stations"]

    /// `filter_advisories`: entries mentioning any token (substring, case-insensitive); all entries when no tokens.
    static func filter(_ entries: [[String: Any]], tokens: Set<String>) -> [[String: Any]] {
        let tokens = tokens.filter { !$0.isEmpty }
        guard !entries.isEmpty, !tokens.isEmpty else { return entries }
        return entries.filter { entry in
            let text = filterKeys.flatMap { strings(entry[$0]) }.map { $0.uppercased() }
            return text.contains { candidate in tokens.contains { candidate.contains($0) } }
        }
    }

    /// `_summarize_sigmet`.
    static func summarizeSIGMET(_ data: [String: Any]) -> String {
        var summary = first(data, ["name", "event", "hazard", "phenomenon"]) ?? "SIGMET"
        if let severity = first(data, ["severity", "intensity"]) { summary += " severity \(severity)" }
        var details: [String] = []
        if let area = area(data, ["fir", "area", "regions", "airspace"]) { details.append("Area: \(area)") }
        if let valid = validity(first(data, ["startTime", "beginTime", "validTimeStart", "issueTime"]),
                                first(data, ["endTime", "expires", "validTimeEnd", "validUntil"]), "Effective") {
            details.append(valid)
        }
        if let description = first(data, ["description", "text", "summary"]) { details.append(description) }
        return details.isEmpty ? summary : "\(summary); \(details.joined(separator: "; "))"
    }

    /// `_summarize_cwa`.
    static func summarizeCWA(_ data: [String: Any]) -> String {
        let name = first(data, ["event", "phenomenon", "hazard", "productType"]) ?? "Center Weather Advisory"
        let cwsu = first(data, ["cwsu", "issuingOffice"])
        var summary = name
        if let cwsu, cwsu != name { summary += " (\(cwsu))" }
        var details: [String] = []
        if let area = area(data, ["area", "regions", "airspace"]) ?? cwsu, !summary.contains(area) {
            details.append("Area: \(area)")
        }
        if let valid = validity(first(data, ["startTime", "issueTime"]), first(data, ["endTime", "expires"]), "Issued") {
            details.append(valid)
        }
        if let description = first(data, ["description", "text", "summary"]) { details.append(description) }
        return details.isEmpty ? summary : "\(summary); \(details.joined(separator: "; "))"
    }

    /// `features[*].properties` (or the feature itself) of an advisory listing.
    static func features(_ json: Any) -> [[String: Any]] {
        ((json as? [String: Any])?["features"] as? [[String: Any]] ?? []).map { $0["properties"] as? [String: Any] ?? $0 }
    }

    // MARK: - Helpers

    private static func normalized(_ value: Any?) -> String? {
        guard let text = (value as? String)?.trimmingCharacters(in: .whitespaces), !text.isEmpty else { return nil }
        return text.uppercased()
    }

    private static func strings(_ value: Any?) -> [String] {
        switch value {
        case let text as String: return [text]
        case let array as [Any]: return array.flatMap { strings($0) }
        case let dict as [String: Any]: return dict.values.flatMap { strings($0) }
        default: return []
        }
    }

    private static func first(_ data: [String: Any], _ keys: [String]) -> String? {
        for key in keys {
            if let text = data[key] as? String, !text.isEmpty { return text }
            if let number = data[key] as? NSNumber, !(data[key] is Bool) { return number.stringValue }
        }
        return nil
    }

    private static func area(_ data: [String: Any], _ keys: [String]) -> String? {
        for key in keys {
            if let items = data[key] as? [Any] {
                let text = items.compactMap { $0 as? String }.filter { !$0.isEmpty }.joined(separator: ", ")
                if !text.isEmpty { return text }
            } else if let text = first(data, [key]) {
                return text
            }
        }
        return nil
    }

    private static func validity(_ start: String?, _ end: String?, _ startWord: String) -> String? {
        switch (start, end) {
        case let (s?, e?): return "Valid \(s) to \(e)"
        case let (nil, e?): return "Valid until \(e)"
        case let (s?, nil): return "\(startWord) \(s)"
        default: return nil
        }
    }
}

extension NWSClient {
    /// SIGMETs (US stations, ATSU KKCI) and CWAs for the station's CWSU, filtered to the station like the desktop.
    func aviationAdvisories(icao: String, http: HTTPClient = .shared) async -> (sigmets: [String], cwas: [String]) {
        let station = icao.uppercased()
        let metadataURL = NWSClient.baseURL.appendingPathComponent("stations/\(station)")
        let metadataJSON = (try? await http.data(from: metadataURL, accept: "application/geo+json", serviceName: "NWS station"))
            .flatMap { try? JSONSerialization.jsonObject(with: $0) as? [String: Any] }
        let properties = metadataJSON?["properties"] as? [String: Any] ?? [:]
        let tokens = AviationAdvisories.tokens(station: station, metadata: properties, airportName: properties["name"] as? String)
        var sigmetsURL = URLComponents(url: NWSClient.baseURL.appendingPathComponent("aviation/sigmets"), resolvingAgainstBaseURL: false)!
        if AviationAdvisories.isUSStation(station) { sigmetsURL.queryItems = [URLQueryItem(name: "atsu", value: "KKCI")] }
        func list(_ url: URL) async -> [[String: Any]] {
            guard let data = try? await http.data(from: url, accept: "application/geo+json", serviceName: "NWS aviation"),
                  let json = try? JSONSerialization.jsonObject(with: data) else { return [] }
            return AviationAdvisories.features(json)
        }
        let sigmets = AviationAdvisories.filter(await list(sigmetsURL.url!), tokens: tokens).map(AviationAdvisories.summarizeSIGMET)
        var cwas: [String] = []
        if let cwsu = (properties["cwa"] as? String)?.trimmingCharacters(in: .whitespaces).uppercased(), !cwsu.isEmpty {
            let url = NWSClient.baseURL.appendingPathComponent("aviation/cwsus/\(cwsu)/cwas")
            cwas = AviationAdvisories.filter(await list(url), tokens: tokens).map(AviationAdvisories.summarizeCWA)
        }
        return (sigmets, cwas)
    }
}

/// AVWX TAFs for international stations (`fetch_avwx_taf`), with AVWX's spoken summary.
struct AVWXClient {
    var http = HTTPClient.shared

    func taf(icao: String, key: String) async throws -> (raw: String, speech: String?) {
        var components = URLComponents(string: "https://avwx.rest/api/taf/\(icao.uppercased())")!
        components.queryItems = [
            URLQueryItem(name: "token", value: key),
            URLQueryItem(name: "options", value: "info,translate,speech,summary"),
        ]
        let data = try await http.data(from: components.url!, accept: "application/json", serviceName: "AVWX")
        guard let json = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              let raw = (json["raw"] as? String)?.trimmingCharacters(in: .whitespacesAndNewlines), !raw.isEmpty else {
            throw WeatherError.noData("AVWX TAF")
        }
        return (raw, (json["speech"] as? String).flatMap { $0.isEmpty ? nil : $0 })
    }
}
