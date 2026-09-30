import Foundation

/// Minimal URLSession wrapper that adds the AccessiWeather User-Agent and decodes JSON.
struct HTTPClient {
    static let userAgent = "AccessiWeather-iOS (github.com/Orinks/AccessiWeather)"

    static let shared = HTTPClient()

    private let session: URLSession

    init(session: URLSession? = nil) {
        if let session {
            self.session = session
        } else {
            let config = URLSessionConfiguration.default
            config.timeoutIntervalForRequest = 20
            config.timeoutIntervalForResource = 40
            config.httpAdditionalHeaders = ["User-Agent": HTTPClient.userAgent]
            self.session = URLSession(configuration: config)
        }
    }

    func data(from url: URL, accept: String? = nil, serviceName: String) async throws -> Data {
        var request = URLRequest(url: url)
        request.setValue(HTTPClient.userAgent, forHTTPHeaderField: "User-Agent")
        if let accept {
            request.setValue(accept, forHTTPHeaderField: "Accept")
        }
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw WeatherError.invalidResponse(serviceName)
        }
        guard (200..<300).contains(http.statusCode) else {
            throw WeatherError.httpStatus(http.statusCode, serviceName)
        }
        return data
    }

    func json<T: Decodable>(_ type: T.Type, from url: URL, accept: String? = nil, serviceName: String, decoder: JSONDecoder = JSONDecoder()) async throws -> T {
        let data = try await data(from: url, accept: accept, serviceName: serviceName)
        do {
            return try decoder.decode(type, from: data)
        } catch {
            throw WeatherError.invalidResponse(serviceName)
        }
    }
}

extension JSONDecoder {
    /// Decoder that accepts ISO 8601 timestamps with or without fractional seconds and with offsets.
    static let iso8601Flexible: JSONDecoder = {
        let decoder = JSONDecoder()
        let withFraction = ISO8601DateFormatter()
        withFraction.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        let plain = ISO8601DateFormatter()
        plain.formatOptions = [.withInternetDateTime]
        decoder.dateDecodingStrategy = .custom { decoder in
            let container = try decoder.singleValueContainer()
            let string = try container.decode(String.self)
            if let date = withFraction.date(from: string) ?? plain.date(from: string) {
                return date
            }
            throw DecodingError.dataCorruptedError(in: container, debugDescription: "Unrecognized date \(string)")
        }
        return decoder
    }()
}
