import Foundation

/// Client for api.weather.gov. Every request carries the AccessiWeather User-Agent as NWS requires.
struct NWSClient {
    static let baseURL = URL(string: "https://api.weather.gov")!
    private static let geoJSON = "application/geo+json"
    private static let ldJSON = "application/ld+json"

    private let http: HTTPClient

    init(http: HTTPClient = .shared) {
        self.http = http
    }

    // MARK: - Response types

    struct QuantitativeValue: Decodable {
        var value: Double?
        var unitCode: String?
    }

    struct PointProperties: Decodable {
        var gridId: String?
        var gridX: Int?
        var gridY: Int?
        var cwa: String?
        var forecast: URL?
        var forecastHourly: URL?
        var observationStations: URL?
        var timeZone: String?
        var forecastOffice: URL?
    }

    struct PointResponse: Decodable {
        var properties: PointProperties
    }

    struct ForecastPeriod: Decodable {
        var number: Int
        var name: String
        var startTime: Date
        var endTime: Date
        var isDaytime: Bool
        var temperature: Double
        var temperatureUnit: String
        var probabilityOfPrecipitation: QuantitativeValue?
        var dewpoint: QuantitativeValue?
        var relativeHumidity: QuantitativeValue?
        var windSpeed: String?
        var windDirection: String?
        var shortForecast: String
        var detailedForecast: String?
    }

    struct ForecastProperties: Decodable {
        var periods: [ForecastPeriod]
    }

    struct ForecastResponse: Decodable {
        var properties: ForecastProperties
    }

    struct StationProperties: Decodable {
        var stationIdentifier: String
        var name: String?
    }

    struct StationFeature: Decodable {
        var properties: StationProperties
    }

    struct StationsResponse: Decodable {
        var features: [StationFeature]
    }

    struct ObservationProperties: Decodable {
        var timestamp: Date?
        var textDescription: String?
        var temperature: QuantitativeValue?
        var dewpoint: QuantitativeValue?
        var windDirection: QuantitativeValue?
        var windSpeed: QuantitativeValue?
        var barometricPressure: QuantitativeValue?
        var visibility: QuantitativeValue?
        var relativeHumidity: QuantitativeValue?
    }

    struct ObservationResponse: Decodable {
        var properties: ObservationProperties
    }

    struct AlertProperties: Decodable {
        var id: String
        var areaDesc: String?
        var effective: Date?
        var expires: Date?
        var severity: String?
        var certainty: String?
        var urgency: String?
        var event: String
        var senderName: String?
        var headline: String?
        var description: String?
        var instruction: String?
    }

    struct AlertFeature: Decodable {
        var properties: AlertProperties
    }

    struct AlertsResponse: Decodable {
        var features: [AlertFeature]
    }

    struct ProductListItem: Decodable {
        var id: String
        var issuanceTime: Date?
        var productName: String?
    }

    struct ProductListResponse: Decodable {
        var graph: [ProductListItem]

        enum CodingKeys: String, CodingKey {
            case graph = "@graph"
        }
    }

    struct ProductResponse: Decodable {
        var id: String
        var issuanceTime: Date?
        var productText: String
        var issuingOffice: String?
    }

    // MARK: - Requests

    /// NWS rejects coordinates with more than four decimal places.
    static func pointPath(latitude: Double, longitude: Double) -> String {
        String(format: "%.4f,%.4f", latitude, longitude)
    }

    func point(latitude: Double, longitude: Double) async throws -> PointProperties {
        let url = NWSClient.baseURL.appendingPathComponent("points/\(NWSClient.pointPath(latitude: latitude, longitude: longitude))")
        return try await http.json(PointResponse.self, from: url, accept: NWSClient.geoJSON, serviceName: "NWS points", decoder: .iso8601Flexible).properties
    }

    func forecast(url: URL) async throws -> [ForecastPeriod] {
        try await http.json(ForecastResponse.self, from: url, accept: NWSClient.geoJSON, serviceName: "NWS forecast", decoder: .iso8601Flexible).properties.periods
    }

    func stations(url: URL) async throws -> [StationProperties] {
        try await http.json(StationsResponse.self, from: url, accept: NWSClient.geoJSON, serviceName: "NWS stations", decoder: .iso8601Flexible).features.map(\.properties)
    }

    func latestObservation(stationID: String) async throws -> ObservationProperties {
        let url = NWSClient.baseURL.appendingPathComponent("stations/\(stationID)/observations/latest")
        return try await http.json(ObservationResponse.self, from: url, accept: NWSClient.geoJSON, serviceName: "NWS observation", decoder: .iso8601Flexible).properties
    }

    func activeAlerts(latitude: Double, longitude: Double) async throws -> [AlertProperties] {
        var components = URLComponents(url: NWSClient.baseURL.appendingPathComponent("alerts/active"), resolvingAgainstBaseURL: false)!
        components.queryItems = [URLQueryItem(name: "point", value: NWSClient.pointPath(latitude: latitude, longitude: longitude))]
        return try await http.json(AlertsResponse.self, from: components.url!, accept: NWSClient.geoJSON, serviceName: "NWS alerts", decoder: .iso8601Flexible).features.map(\.properties)
    }

    /// Latest Area Forecast Discussion for a forecast office (for example "PHI").
    func areaForecastDiscussion(officeID: String) async throws -> ProductResponse {
        let listURL = NWSClient.baseURL.appendingPathComponent("products/types/AFD/locations/\(officeID)")
        let list = try await http.json(ProductListResponse.self, from: listURL, accept: NWSClient.ldJSON, serviceName: "NWS products", decoder: .iso8601Flexible)
        guard let latest = list.graph.first else {
            throw WeatherError.noData("forecast discussion")
        }
        let productURL = NWSClient.baseURL.appendingPathComponent("products/\(latest.id)")
        return try await http.json(ProductResponse.self, from: productURL, accept: NWSClient.ldJSON, serviceName: "NWS product", decoder: .iso8601Flexible)
    }

    // MARK: - Conversion helpers

    /// Parses NWS wind speed strings such as "5 mph" or "10 to 15 mph" into km/h (upper bound).
    static func windSpeedKph(from text: String?) -> Double? {
        guard let text else { return nil }
        let numbers = text.split(whereSeparator: { !$0.isNumber && $0 != "." }).compactMap { Double($0) }
        guard let mph = numbers.last else { return nil }
        return mph * 1.609344
    }

    static func degrees(fromCompass compass: String?) -> Double? {
        guard let compass = compass?.uppercased(), !compass.isEmpty else { return nil }
        let table: [String: Double] = [
            "N": 0, "NNE": 22.5, "NE": 45, "ENE": 67.5, "E": 90, "ESE": 112.5, "SE": 135, "SSE": 157.5,
            "S": 180, "SSW": 202.5, "SW": 225, "WSW": 247.5, "W": 270, "WNW": 292.5, "NW": 315, "NNW": 337.5,
        ]
        return table[compass]
    }

    static func celsius(_ value: Double, unit: String) -> Double {
        unit.uppercased() == "F" ? (value - 32) * 5 / 9 : value
    }

    static func celsius(_ quantity: QuantitativeValue?) -> Double? {
        guard let quantity, let value = quantity.value else { return nil }
        if quantity.unitCode?.hasSuffix("degF") == true {
            return (value - 32) * 5 / 9
        }
        return value
    }

    static func kph(_ quantity: QuantitativeValue?) -> Double? {
        guard let quantity, let value = quantity.value else { return nil }
        if quantity.unitCode?.hasSuffix("m_s-1") == true { return value * 3.6 }
        if quantity.unitCode?.hasSuffix("mi_h-1") == true { return value * 1.609344 }
        return value
    }

    static func hPa(_ quantity: QuantitativeValue?) -> Double? {
        guard let quantity, let value = quantity.value else { return nil }
        if quantity.unitCode?.hasSuffix(":Pa") == true { return value / 100 }
        return value
    }

    static func km(_ quantity: QuantitativeValue?) -> Double? {
        guard let quantity, let value = quantity.value else { return nil }
        if quantity.unitCode?.hasSuffix(":m") == true { return value / 1000 }
        return value
    }
}
