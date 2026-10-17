import Foundation

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

    private let http: HTTPClient
    private let url: URL

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

    private struct Wrapper: Decodable {
        let stations: [WeatherIndexDirectoryStation]
    }
}
