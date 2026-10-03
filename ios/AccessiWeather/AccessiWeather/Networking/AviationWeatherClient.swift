import Foundation

struct AviationWeatherClient {
    private let http: HTTPClient

    init(http: HTTPClient = .shared) {
        self.http = http
    }

    func metars(icao: String) async throws -> [METARObservation] {
        try await http.json(
            [METARObservation].self,
            from: url(product: "metar", icao: icao),
            serviceName: "Aviation Weather METAR"
        )
    }

    func tafs(icao: String) async throws -> [TAFProduct] {
        try await http.json(
            [TAFProduct].self,
            from: url(product: "taf", icao: icao),
            serviceName: "Aviation Weather TAF"
        )
    }

    private func url(product: String, icao: String) -> URL {
        var components = URLComponents(string: "https://aviationweather.gov/api/data/\(product)")!
        components.queryItems = [
            .init(name: "ids", value: icao),
            .init(name: "format", value: "json"),
        ]
        return components.url!
    }
}
