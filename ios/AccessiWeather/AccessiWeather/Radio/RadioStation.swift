import Foundation

/// A NOAA Weather Radio transmitter, ported from the desktop app's station database.
struct RadioStation: Codable, Identifiable, Hashable {
    let callSign: String
    let frequency: Double
    let name: String
    let latitude: Double
    let longitude: Double
    let state: String
    let streamURLs: [String]

    var id: String { callSign }

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

/// Loads the bundled station list and finds stations nearest a coordinate.
struct RadioStationDatabase {
    let stations: [RadioStation]

    init(bundle: Bundle = .main) {
        guard let url = bundle.url(forResource: "noaa_radio_stations", withExtension: "json"),
              let data = try? Data(contentsOf: url),
              let decoded = try? JSONDecoder().decode([RadioStation].self, from: data) else {
            stations = []
            return
        }
        stations = decoded
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
