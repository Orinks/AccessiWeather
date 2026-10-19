import Foundation

/// A NOAA Weather Radio transmitter from the WeatherIndex directory (or the bundled fallback list).
struct RadioStation: Codable, Identifiable, Hashable {
    static let outOfServiceStatus = "OUT OF SERVICE"

    let callSign: String
    let frequency: Double
    let name: String
    let latitude: Double
    let longitude: Double
    let state: String
    let streamURLs: [String]
    var status: String?

    init(callSign: String, frequency: Double, name: String, latitude: Double, longitude: Double, state: String, streamURLs: [String], status: String? = nil) {
        self.callSign = callSign
        self.frequency = frequency
        self.name = name
        self.latitude = latitude
        self.longitude = longitude
        self.state = state
        self.streamURLs = streamURLs
        self.status = status
    }

    var id: String { callSign }

    var isOutOfService: Bool {
        status?.trimmingCharacters(in: .whitespacesAndNewlines).uppercased() == Self.outOfServiceStatus
    }

    var frequencyText: String {
        String(format: "%.3f MHz", frequency)
    }

    /// Relays whose TLS setup iOS cannot negotiate; their plain-HTTP variant is tried right after.
    private static let plainHTTPFallbackHosts: Set<String> = ["radio.weatherusa.net"]

    /// Ordered list of stream URLs to try, ending with the Broadcastify fallback the desktop app uses.
    var candidateURLs: [URL] {
        var strings: [String] = []
        for string in streamURLs {
            strings.append(string)
            if let url = URL(string: string), url.scheme == "https",
               let host = url.host, Self.plainHTTPFallbackHosts.contains(host) {
                strings.append("http" + string.dropFirst("https".count))
            }
        }
        strings.append("https://broadcastify.cdnstream1.com/noaa/\(callSign)")
        return strings.compactMap(URL.init(string:))
    }
}

struct NearbyStation: Identifiable, Hashable {
    let station: RadioStation
    let distanceKm: Double

    var id: String { station.id }

    var distanceMiles: Double { distanceKm * 0.621371 }
}

/// A station list with nearest-station search. `RadioStationDirectory` builds one from
/// WeatherIndex; `bundled` is the last-resort copy shipped with the app.
struct RadioStationDatabase {
    let stations: [RadioStation]

    init(stations: [RadioStation]) {
        self.stations = stations
    }

    static func bundled(bundle: Bundle = .main) -> RadioStationDatabase {
        guard let url = bundle.url(forResource: "noaa_radio_stations", withExtension: "json"),
              let data = try? Data(contentsOf: url),
              let decoded = try? JSONDecoder().decode([RadioStation].self, from: data) else {
            return RadioStationDatabase(stations: [])
        }
        return RadioStationDatabase(stations: decoded)
    }

    func station(withCallSign callSign: String) -> RadioStation? {
        stations.first { $0.callSign == callSign }
    }

    func nearest(latitude: Double, longitude: Double, limit: Int = 8) -> [NearbyStation] {
        stations
            .map { NearbyStation(station: $0, distanceKm: Self.haversineKm(latitude, longitude, $0.latitude, $0.longitude)) }
            .sorted { $0.distanceKm < $1.distanceKm }
            .prefix(limit)
            .map { $0 }
    }

    static func haversineKm(_ lat1: Double, _ lon1: Double, _ lat2: Double, _ lon2: Double) -> Double {
        let r = 6371.0
        let dLat = (lat2 - lat1) * .pi / 180
        let dLon = (lon2 - lon1) * .pi / 180
        let a = sin(dLat / 2) * sin(dLat / 2)
            + cos(lat1 * .pi / 180) * cos(lat2 * .pi / 180) * sin(dLon / 2) * sin(dLon / 2)
        return r * 2 * atan2(sqrt(a), sqrt(1 - a))
    }
}
