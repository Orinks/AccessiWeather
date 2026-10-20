import Foundation

/// EPA AirNow current observations, as in Rust `environmental::airnow`. US only; needs a free AirNow API key.
struct AirNowClient {
    static let endpoint = "https://www.airnowapi.org/aq/observation/current/ziplatlong/"
    static let source = "EPA AirNow and participating agencies"

    struct Observation: Equatable {
        var aqi: Int
        var category: String?
        var pollutant: String
        var reportingArea: String?
    }

    var http = HTTPClient.shared

    func current(latitude: Double, longitude: Double, key: String) async throws -> Observation? {
        var components = URLComponents(string: Self.endpoint)!
        components.queryItems = [
            URLQueryItem(name: "format", value: "application/json"),
            URLQueryItem(name: "latitude", value: String(latitude)),
            URLQueryItem(name: "longitude", value: String(longitude)),
            URLQueryItem(name: "distance", value: "25"),
            URLQueryItem(name: "API_KEY", value: key.trimmingCharacters(in: .whitespacesAndNewlines)),
        ]
        let data = try await http.data(from: components.url!, accept: "application/json", serviceName: "AirNow")
        return Self.parse(try JSONSerialization.jsonObject(with: data))
    }

    /// `parse_observations`: the highest valid AQI, reading documented PascalCase and live camelCase fields.
    static func parse(_ payload: Any) -> Observation? {
        guard let items = payload as? [[String: Any]] else { return nil }
        func field(_ item: [String: Any], _ names: [String]) -> Any? {
            names.lazy.compactMap { item[$0] }.first
        }
        func text(_ value: Any?) -> String? {
            let string = ((value as? [String: Any])?["Name"] ?? value) as? String
            return string.map { $0.trimmingCharacters(in: .whitespaces) }.flatMap { $0.isEmpty ? nil : $0 }
        }
        var best: (aqi: Int, item: [String: Any])?
        for item in items {
            let raw = field(item, ["AQI", "nowcastAQI"])
            guard !(raw is Bool), let value = (raw as? NSNumber)?.doubleValue ?? (raw as? String).flatMap(Double.init),
                  value.isFinite, value >= 0 else { continue }
            let aqi = Int(value.rounded())
            if aqi > (best?.aqi ?? -1) { best = (aqi, item) }
        }
        guard let best else { return nil }
        return Observation(
            aqi: best.aqi,
            category: text(field(best.item, ["Category", "aqiCategoryName"])),
            pollutant: text(field(best.item, ["ParameterName", "parameterName"])) ?? "Unknown",
            reportingArea: text(field(best.item, ["ReportingArea", "reportingAreaName"]))
        )
    }
}
