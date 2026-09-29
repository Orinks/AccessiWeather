import Foundation

struct OpenRouterClient {
    static let endpoint = URL(string: "https://openrouter.ai/api/v1/chat/completions")!
    private let session: URLSession

    init(session: URLSession = .shared) {
        self.session = session
    }

    struct Message: Encodable, Equatable {
        var role: String
        var content: String
    }

    private struct RequestBody: Encodable {
        var model: String
        var messages: [Message]
        var max_tokens: Int
    }

    private struct ResponseBody: Decodable {
        var choices: [Choice]?

        struct Choice: Decodable {
            var message: MessageContent?
        }

        struct MessageContent: Decodable {
            var content: String?
        }
    }

    func complete(system: String, user: String, model: String, key: String) async throws -> String {
        var request = URLRequest(url: Self.endpoint)
        request.httpMethod = "POST"
        request.setValue("Bearer \(key)", forHTTPHeaderField: "Authorization")
        request.setValue("https://accessiweather.orinks.net", forHTTPHeaderField: "HTTP-Referer")
        request.setValue("AccessiWeather", forHTTPHeaderField: "X-Title")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(
            RequestBody(
                model: model,
                messages: [Message(role: "system", content: system), Message(role: "user", content: user)],
                max_tokens: 4000
            )
        )
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw WeatherError.invalidResponse("OpenRouter")
        }
        guard (200..<300).contains(http.statusCode) else {
            throw WeatherError.unsupported(Self.errorMessage(status: http.statusCode))
        }
        let decoded = try JSONDecoder().decode(ResponseBody.self, from: data)
        guard let content = decoded.choices?.first?.message?.content?.trimmingCharacters(in: .whitespacesAndNewlines),
              !content.isEmpty else {
            throw WeatherError.unsupported("The AI model returned an empty response. Try again or choose another model in Settings > AI.")
        }
        return content
    }

    static func errorMessage(status: Int) -> String {
        switch status {
        case 401:
            return "Your OpenRouter API key is invalid. Please check Settings > AI and verify your API key. Get a free key at: openrouter.ai/keys"
        case 402:
            return "Your OpenRouter account has no funds. Add credits at openrouter.ai/credits or switch to a free model in Settings > AI."
        default:
            return "The AI service returned status \(status)."
        }
    }
}
