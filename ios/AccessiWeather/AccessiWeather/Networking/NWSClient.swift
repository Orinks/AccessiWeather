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
        var geocode: AlertSAMECodes?
        var eventCode: AlertSAMECodes?
    }

    struct AlertSAMECodes: Decodable {
        var same: [String]?

        enum CodingKeys: String, CodingKey {
            case same = "SAME"
        }
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

    /// Marine Mode: the nearest marine zone's forecast and that zone's active alerts.
    func marine(latitude: Double, longitude: Double) async throws -> (forecast: MarineForecast?, alerts: [AlertProperties])? {
        var zonesURL = URLComponents(url: NWSClient.baseURL.appendingPathComponent("zones"), resolvingAgainstBaseURL: false)!
        zonesURL.queryItems = [
            URLQueryItem(name: "type", value: "marine"),
            URLQueryItem(name: "point", value: NWSClient.pointPath(latitude: latitude, longitude: longitude)),
        ]
        let zonesData = try await http.data(from: zonesURL.url!, accept: NWSClient.geoJSON, serviceName: "NWS marine zones")
        guard let zones = try JSONSerialization.jsonObject(with: zonesData) as? [String: Any],
              let zone = MarineForecast.zone(from: zones) else { return nil }
        let forecastURL = NWSClient.baseURL.appendingPathComponent("zones/marine/\(zone.id)/forecast")
        let forecastData = try await http.data(from: forecastURL, accept: NWSClient.geoJSON, serviceName: "NWS marine forecast")
        guard let forecast = try JSONSerialization.jsonObject(with: forecastData) as? [String: Any], !forecast.isEmpty else { return nil }
        let summary = MarineForecast.build(zoneID: zone.id, zoneName: zone.name, forecast: forecast)
        var alertsURL = URLComponents(url: NWSClient.baseURL.appendingPathComponent("alerts/active"), resolvingAgainstBaseURL: false)!
        alertsURL.queryItems = [URLQueryItem(name: "zone", value: zone.id), URLQueryItem(name: "status", value: "actual")]
        let alerts = (try? await http.json(AlertsResponse.self, from: alertsURL.url!, accept: NWSClient.geoJSON, serviceName: "NWS marine alerts", decoder: .iso8601Flexible).features.map(\.properties)) ?? []
        return (summary.hasData ? summary : nil, alerts)
    }

    static func weatherAlert(from alert: AlertProperties) -> WeatherAlert {
        WeatherAlert(
            id: alert.id,
            event: alert.event,
            severity: alert.severity ?? "Unknown",
            urgency: alert.urgency,
            certainty: alert.certainty,
            headline: alert.headline,
            description: alert.description,
            instruction: alert.instruction,
            areaDescription: alert.areaDesc,
            sender: alert.senderName,
            effective: alert.effective,
            expires: alert.expires,
            sameCountyCodes: normalizedSAMECountyCodes(alert.geocode?.same ?? []),
            sameEventCodes: normalizedSAMEEventCodes(alert.eventCode?.same ?? [])
        )
    }

    static func normalizedSAMECountyCodes(_ values: [String]) -> [String] {
        var seen: Set<String> = []
        return values.compactMap { value in
            guard let code = WeatherIndexClient.normalizeSameCode(value),
                  seen.insert(code).inserted else {
                return nil
            }
            return code
        }
    }

    static func normalizedSAMEEventCodes(_ values: [String]) -> [String] {
        var seen: Set<String> = []
        return values.compactMap { value in
            let code = value.trimmingCharacters(in: .whitespacesAndNewlines).uppercased()
            guard !code.isEmpty, code != "NWS", seen.insert(code).inserted else { return nil }
            return code
        }
    }

    func latestProduct(type: String, officeID: String) async throws -> ProductResponse? {
        guard let latest = try await productList(type: type, officeID: officeID).first else { return nil }
        return try await product(id: latest.id)
    }

    func productList(type: String, officeID: String) async throws -> [ProductListItem] {
        let listURL = NWSClient.baseURL.appendingPathComponent("products/types/\(type)/locations/\(officeID)")
        return try await http.json(ProductListResponse.self, from: listURL, accept: NWSClient.ldJSON, serviceName: "NWS products", decoder: .iso8601Flexible).graph
    }

    func product(id: String) async throws -> ProductResponse {
        let productURL = NWSClient.baseURL.appendingPathComponent("products/\(id)")
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
