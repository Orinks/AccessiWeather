import Foundation

struct MarineForecastPeriod: Equatable {
    var name: String
    var summary: String
}

/// NWS marine zone essentials for a location in Marine Mode, as in Rust `build_marine_forecast`.
struct MarineForecast: Equatable {
    var zoneID: String
    var zoneName: String?
    var summary: String?
    var periods: [MarineForecastPeriod]
    var highlights: [String]

    var hasData: Bool {
        !(summary ?? "").isEmpty || !(zoneName ?? "").isEmpty || !periods.isEmpty || !highlights.isEmpty
    }

    static let keywords: Set<String> = ["wind", "winds", "gust", "gusts", "wave", "waves", "seas", "swell", "swells"]

    /// Every `.`/`;`-delimited clause containing a wind or wave keyword as a whole word.
    static func highlightClauses(_ text: String) -> [String] {
        text.split(whereSeparator: { $0 == "." || $0 == ";" }).map(String.init).filter { clause in
            clause.split(whereSeparator: { !($0.isLetter || $0.isNumber || $0 == "_") })
                .contains { keywords.contains($0.lowercased()) }
        }
    }

    /// Up to four distinct wind/wave clauses from the periods' short and detailed forecasts.
    static func highlights(periods: [[String: Any]]) -> [String] {
        var result: [String] = []
        var seen: Set<String> = []
        for period in periods {
            for field in ["shortForecast", "detailedForecast"] {
                let text = (period[field] as? String ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
                guard !text.isEmpty else { continue }
                for clause in highlightClauses(text) {
                    let candidate = clause.split(whereSeparator: \.isWhitespace).joined(separator: " ")
                        .trimmingCharacters(in: CharacterSet(charactersIn: " ."))
                    guard !candidate.isEmpty, seen.insert(candidate.lowercased()).inserted else { continue }
                    result.append(candidate)
                    if result.count >= 4 { return result }
                }
            }
        }
        return result
    }

    /// The first marine zone's id and name from `/zones?type=marine&point=`.
    static func zone(from zones: [String: Any]) -> (id: String, name: String?)? {
        guard let feature = (zones["features"] as? [[String: Any]])?.first else { return nil }
        let properties = feature["properties"] as? [String: Any]
        let id = (properties?["id"] as? String).flatMap { $0.isEmpty ? nil : $0 } ?? (feature["id"] as? String)
        guard let id, !id.isEmpty else { return nil }
        return (id, properties?["name"] as? String)
    }

    static func build(zoneID: String, zoneName: String?, forecast: [String: Any]) -> MarineForecast {
        let properties = forecast["properties"] as? [String: Any]
        let periods = properties?["periods"] as? [[String: Any]] ?? []
        func text(_ period: [String: Any]) -> String? {
            ["detailedForecast", "shortForecast"].lazy.compactMap { period[$0] as? String }.first { !$0.isEmpty }
        }
        let name = (properties?["name"] as? String).flatMap { $0.isEmpty ? nil : $0 } ?? zoneName
        return MarineForecast(
            zoneID: zoneID,
            zoneName: name,
            summary: periods.first.flatMap(text),
            periods: periods.prefix(3).compactMap { period in
                guard let summary = text(period) else { return nil }
                let periodName = period["name"] as? String ?? ""
                return MarineForecastPeriod(
                    name: periodName.isEmpty ? "Marine period" : periodName,
                    summary: summary.trimmingCharacters(in: .whitespacesAndNewlines)
                )
            },
            highlights: highlights(periods: Array(periods.prefix(4)))
        )
    }

    /// "Zone name (ID)", like the desktop "Marine zone:" line.
    var zoneLabel: String? {
        guard let zoneName, !zoneName.isEmpty else { return nil }
        return "\(zoneName) (\(zoneID))"
    }
}
