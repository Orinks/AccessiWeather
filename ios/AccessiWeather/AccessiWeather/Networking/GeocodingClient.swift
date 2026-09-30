import Foundation

struct GeocodingResult: Identifiable, Hashable {
    var id: String
    var displayName: String
    var shortName: String
    var latitude: Double
    var longitude: Double
}

/// Nominatim (OpenStreetMap) geocoding. Requests carry the app User-Agent as the usage policy requires.
struct GeocodingClient {
    private let http: HTTPClient

    init(http: HTTPClient = .shared) {
        self.http = http
    }

    private struct NominatimPlace: Decodable {
        var place_id: Int
        var lat: String
        var lon: String
        var display_name: String
        var name: String?
        var address: Address?

        struct Address: Decodable {
            var city: String?
            var town: String?
            var village: String?
            var hamlet: String?
            var county: String?
            var state: String?
            var country: String?
            var postcode: String?
        }
    }

    func search(_ query: String, limit: Int = 8) async throws -> [GeocodingResult] {
        var components = URLComponents(string: "https://nominatim.openstreetmap.org/search")!
        components.queryItems = [
            .init(name: "q", value: query),
            .init(name: "format", value: "jsonv2"),
            .init(name: "addressdetails", value: "1"),
            .init(name: "limit", value: String(limit)),
        ]
        let places = try await http.json([NominatimPlace].self, from: components.url!, serviceName: "geocoding")
        return places.compactMap(GeocodingClient.result(from:))
    }

    func reverse(latitude: Double, longitude: Double) async throws -> GeocodingResult? {
        var components = URLComponents(string: "https://nominatim.openstreetmap.org/reverse")!
        components.queryItems = [
            .init(name: "lat", value: String(latitude)),
            .init(name: "lon", value: String(longitude)),
            .init(name: "format", value: "jsonv2"),
            .init(name: "addressdetails", value: "1"),
        ]
        let place = try await http.json(NominatimPlace.self, from: components.url!, serviceName: "reverse geocoding")
        return GeocodingClient.result(from: place)
    }

    private static func result(from place: NominatimPlace) -> GeocodingResult? {
        guard let lat = Double(place.lat), let lon = Double(place.lon) else { return nil }
        let address = place.address
        let locality = address?.city ?? address?.town ?? address?.village ?? address?.hamlet ?? place.name
        var parts: [String] = []
        if let locality, !locality.isEmpty { parts.append(locality) }
        if let state = address?.state, !state.isEmpty { parts.append(state) }
        if let country = address?.country, !country.isEmpty, country != "United States" { parts.append(country) }
        let shortName = parts.isEmpty ? place.display_name : parts.joined(separator: ", ")
        return GeocodingResult(id: String(place.place_id), displayName: place.display_name, shortName: shortName, latitude: lat, longitude: lon)
    }
}
