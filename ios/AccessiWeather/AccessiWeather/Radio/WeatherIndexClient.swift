import Foundation
import CoreFoundation

/// One station record from the WeatherIndex directory (`GET /v1/stations/all`).
struct WeatherIndexDirectoryStation: Decodable {
    struct Feed: Decodable {
        let streamURL: String?

        enum CodingKeys: String, CodingKey {
            case streamURL = "stream_url"
        }
    }

    let callsign: String
    let city: String?
    let stateSlug: String?
    let frequency: String?
    let status: String?
    let latitude: Double?
    let longitude: Double?
    let feeds: [Feed]?

    enum CodingKeys: String, CodingKey {
        case callsign, city, frequency, status, latitude, longitude, feeds
        case stateSlug = "state_slug"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        callsign = try container.decode(String.self, forKey: .callsign)
        city = try container.decodeIfPresent(String.self, forKey: .city)
        stateSlug = try container.decodeIfPresent(String.self, forKey: .stateSlug)
        status = try container.decodeIfPresent(String.self, forKey: .status)
        latitude = Self.flexibleDouble(container, .latitude)
        longitude = Self.flexibleDouble(container, .longitude)
        feeds = try container.decodeIfPresent([Feed].self, forKey: .feeds)
        if let number = try? container.decodeIfPresent(Double.self, forKey: .frequency) {
            frequency = String(number)
        } else {
            frequency = try container.decodeIfPresent(String.self, forKey: .frequency)
        }
    }

    private static func flexibleDouble(_ container: KeyedDecodingContainer<CodingKeys>, _ key: CodingKeys) -> Double? {
        if let value = try? container.decodeIfPresent(Double.self, forKey: key) { return value }
        if let text = try? container.decodeIfPresent(String.self, forKey: key) { return Double(text) }
        return nil
    }

    /// The player's station model, or nil when the record has no coordinates or no live feed.
    var radioStation: RadioStation? {
        guard let latitude, let longitude else { return nil }
        var urls: [String] = []
        for feed in feeds ?? [] {
            guard let url = feed.streamURL?.trimmingCharacters(in: .whitespacesAndNewlines), !url.isEmpty, !urls.contains(url) else { continue }
            urls.append(url)
        }
        guard !urls.isEmpty else { return nil }
        let callSign = callsign.trimmingCharacters(in: .whitespacesAndNewlines).uppercased()
        guard !callSign.isEmpty else { return nil }
        let state = stateSlug?.trimmingCharacters(in: .whitespacesAndNewlines).uppercased() ?? ""
        var name = city?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        if !state.isEmpty, !name.uppercased().hasSuffix(", \(state)") {
            name = name.isEmpty ? state : "\(name), \(state)"
        }
        return RadioStation(
            callSign: callSign,
            frequency: Double(frequency ?? "") ?? 0,
            name: name,
            latitude: latitude,
            longitude: longitude,
            state: state,
            streamURLs: urls,
            status: status?.trimmingCharacters(in: .whitespacesAndNewlines).uppercased()
        )
    }
}

/// Fetches the WeatherIndex station directory, which is the source of truth for
/// which NOAA Weather Radio transmitters currently have a live stream.
struct WeatherIndexClient {
    static let directoryURL = URL(string: "https://api.wxindex.org/v1/stations/all")!
    static let stationMetadataURL = URL(string: "https://api.wxindex.org/v1/stations")!
    static let stationMetadataCacheLifetime: TimeInterval = 30 * 60

    private let http: HTTPClient
    private let url: URL
    private let stationMetadataCache = WeatherIndexStationMetadataCache()

    init(http: HTTPClient = .shared, url: URL = WeatherIndexClient.directoryURL) {
        self.http = http
        self.url = url
    }

    /// Downloads the directory and returns the raw payload with the parsed stations.
    func fetchDirectory() async throws -> (data: Data, stations: [RadioStation]) {
        let data = try await http.data(from: url, accept: "application/json", serviceName: "WeatherIndex")
        let stations = try Self.parse(data)
        guard !stations.isEmpty else { throw WeatherError.invalidResponse("WeatherIndex") }
        return (data, stations)
    }

    func stationMetadata(callSign: String) async -> WeatherIndexStationMetadata? {
        let normalizedCallSign = callSign.trimmingCharacters(in: .whitespacesAndNewlines).uppercased()
        guard !normalizedCallSign.isEmpty else { return nil }
        let cached = await stationMetadataCache.value(
            for: normalizedCallSign,
            now: Date(),
            lifetime: Self.stationMetadataCacheLifetime
        )
        if cached.found { return cached.metadata }

        let stationURL = Self.stationMetadataURL.appendingPathComponent(normalizedCallSign)
        do {
            let data = try await http.data(
                from: stationURL,
                accept: "application/json",
                serviceName: "WeatherIndex"
            )
            let metadata = Self.parseStationMetadata(data, requestedCallSign: normalizedCallSign)
            await stationMetadataCache.store(metadata, for: normalizedCallSign, at: Date())
            return metadata
        } catch {
            return nil
        }
    }

    static func parse(_ data: Data) throws -> [RadioStation] {
        let decoder = JSONDecoder()
        let entries: [WeatherIndexDirectoryStation]
        if let list = try? decoder.decode([WeatherIndexDirectoryStation].self, from: data) {
            entries = list
        } else {
            entries = try decoder.decode(Wrapper.self, from: data).stations
        }
        var seen: Set<String> = []
        var stations: [RadioStation] = []
        for entry in entries {
            guard let station = entry.radioStation, !seen.contains(station.callSign) else { continue }
            seen.insert(station.callSign)
            stations.append(station)
        }
        return stations
    }

    static func parseStationMetadata(
        _ data: Data,
        requestedCallSign: String
    ) -> WeatherIndexStationMetadata? {
        guard let payload = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            return nil
        }
        let station = payload["station"] as? [String: Any] ?? payload
        guard !station.isEmpty else { return nil }
        let servedCounties = (station["served_counties"] as? [[String: Any]] ?? []).compactMap {
            county -> WeatherIndexServedCounty? in
            guard let rawCode = county["same_code"],
                  let sameCode = normalizeSameCode(rawCode),
                  let name = county["county"] as? String,
                  let state = county["state"] as? String else {
                return nil
            }
            let area = (county["area"] as? String)?.trimmingCharacters(in: .whitespacesAndNewlines)
            return WeatherIndexServedCounty(
                county: name.trimmingCharacters(in: .whitespacesAndNewlines),
                sameCode: sameCode,
                state: state.trimmingCharacters(in: .whitespacesAndNewlines).uppercased(),
                area: area?.isEmpty == false ? area : nil
            )
        }
        let callSign = (station["callsign"] as? String)
            ?? (station["call_sign"] as? String)
            ?? requestedCallSign
        return WeatherIndexStationMetadata(
            callSign: callSign.trimmingCharacters(in: .whitespacesAndNewlines).uppercased(),
            wfo: (station["wfo"] as? String)?.trimmingCharacters(in: .whitespacesAndNewlines),
            latitude: Self.double(station["latitude"]),
            longitude: Self.double(station["longitude"]),
            servedCounties: servedCounties
        )
    }

    static func normalizeSameCode(_ value: String) -> String? {
        let digits = value.filter { $0.isASCII && $0.isNumber }
        guard !digits.isEmpty else { return nil }
        return String(repeating: "0", count: max(0, 6 - digits.count)) + digits
    }

    private static func normalizeSameCode(_ value: Any) -> String? {
        if let string = value as? String {
            return normalizeSameCode(string)
        }
        guard let number = value as? NSNumber else { return nil }
        guard CFGetTypeID(number) != CFBooleanGetTypeID() else { return nil }
        let type = String(cString: number.objCType)
        guard type != "d", type != "f" else { return nil }
        return String(format: "%06lld", number.int64Value)
    }

    private static func double(_ value: Any?) -> Double? {
        if let number = value as? NSNumber { return number.doubleValue }
        if let string = value as? String { return Double(string) }
        return nil
    }

    private struct Wrapper: Decodable {
        let stations: [WeatherIndexDirectoryStation]
    }
}

struct WeatherIndexServedCounty: Equatable, Sendable {
    let county: String
    let sameCode: String
    let state: String
    let area: String?
}

struct WeatherIndexStationMetadata: Equatable, Sendable {
    let callSign: String
    let wfo: String?
    let latitude: Double?
    let longitude: Double?
    let servedCounties: [WeatherIndexServedCounty]
}

private actor WeatherIndexStationMetadataCache {
    private var entries: [String: (metadata: WeatherIndexStationMetadata?, storedAt: Date)] = [:]

    func value(
        for callSign: String,
        now: Date,
        lifetime: TimeInterval
    ) -> (found: Bool, metadata: WeatherIndexStationMetadata?) {
        guard let entry = entries[callSign] else { return (false, nil) }
        guard now.timeIntervalSince(entry.storedAt) < lifetime else {
            entries[callSign] = nil
            return (false, nil)
        }
        return (true, entry.metadata)
    }

    func store(_ metadata: WeatherIndexStationMetadata?, for callSign: String, at date: Date) {
        entries[callSign] = (metadata, date)
    }
}

enum WeatherIndexCoverageResolver {
    static func firstCoveringStation(
        candidates: [RadioStation],
        sameCountyCodes: [String],
        metadataFor: (String) async -> WeatherIndexStationMetadata?
    ) async -> (station: RadioStation, matchedCountyCodes: Set<String>)? {
        let alertCodes = Set(sameCountyCodes)
        guard !alertCodes.isEmpty else { return nil }
        for station in candidates.prefix(10) {
            guard let metadata = await metadataFor(station.callSign) else { continue }
            let coveredCodes = Set(metadata.servedCounties.map(\.sameCode))
            let matches = alertCodes.intersection(coveredCodes)
            if !matches.isEmpty {
                return (station, matches)
            }
        }
        return nil
    }
}
