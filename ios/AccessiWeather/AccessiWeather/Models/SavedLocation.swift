import Foundation

struct SavedLocation: Identifiable, Codable, Hashable {
    var id: UUID
    var name: String
    var latitude: Double
    var longitude: Double
    /// Adds the nearby NWS marine zone forecast and marine alerts (US only).
    var marineMode: Bool = false
    /// Follows the device's position instead of staying put.
    var isCurrentLocation: Bool = false

    init(id: UUID = UUID(), name: String, latitude: Double, longitude: Double) {
        self.id = id
        self.name = name
        self.latitude = latitude
        self.longitude = longitude
    }

    /// True when the coordinate falls inside the NWS coverage area (CONUS, Alaska, Hawaii, Puerto Rico, Guam).
    var isInUnitedStates: Bool {
        let boxes: [(latMin: Double, latMax: Double, lonMin: Double, lonMax: Double)] = [
            (24.0, 49.5, -125.0, -66.5),   // Contiguous US
            (51.0, 71.5, -180.0, -129.0),  // Alaska
            (18.5, 22.5, -161.0, -154.0),  // Hawaii
            (17.5, 18.6, -67.5, -65.0),    // Puerto Rico / USVI
            (13.0, 14.0, 144.0, 145.5),    // Guam
        ]
        return boxes.contains { latitude >= $0.latMin && latitude <= $0.latMax && longitude >= $0.lonMin && longitude <= $0.lonMax }
    }

    var coordinateDescription: String {
        String(format: "%.4f, %.4f", latitude, longitude)
    }
}

extension SavedLocation {
    enum CodingKeys: String, CodingKey {
        case id, name, latitude, longitude, marineMode, isCurrentLocation
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        self.init(
            id: try c.decode(UUID.self, forKey: .id),
            name: try c.decode(String.self, forKey: .name),
            latitude: try c.decode(Double.self, forKey: .latitude),
            longitude: try c.decode(Double.self, forKey: .longitude)
        )
        marineMode = try c.decodeIfPresent(Bool.self, forKey: .marineMode) ?? false
        isCurrentLocation = try c.decodeIfPresent(Bool.self, forKey: .isCurrentLocation) ?? false
    }
}
