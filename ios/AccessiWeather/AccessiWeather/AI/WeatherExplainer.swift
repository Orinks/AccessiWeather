import Foundation

enum ExplanationStyle: String, CaseIterable, Identifiable {
    case brief = "Brief"
    case standard = "Standard"
    case detailed = "Detailed"

    var id: String { rawValue }

    var systemInstruction: String {
        switch self {
        case .brief: return "Keep your response to 1-2 sentences."
        case .standard: return "Provide a 3-4 sentence explanation."
        case .detailed: return "Provide a comprehensive paragraph with context about how the weather might affect daily activities."
        }
    }

    var productInstruction: String {
        switch self {
        case .brief: return "Provide a 2-3 sentence summary of the key points."
        case .standard: return "Provide a clear 1-2 paragraph summary."
        case .detailed: return "Provide a comprehensive summary covering all major points from the discussion, organized by topic."
        }
    }
}

enum WeatherExplainer {
    static let defaultSystemPrompt = """
    You are a helpful weather assistant that explains weather information in plain, accessible language. Your explanations should be easy to understand for screen reader users and people who prefer audio descriptions. Use only the information provided in the request. Do not invent missing details, hazards, records, dates, locations, or forecast impacts. If something is unclear or not provided, say so plainly.

    Avoid visual-only descriptions. When useful, explain what the weather information means for comfort, travel, planning, or safety, but only when supported by the provided text or data.

    IMPORTANT: Do NOT repeat the location name, date, time, or timezone in your response unless it is necessary for clarity. The user already sees this information. Jump straight into the explanation.

    IMPORTANT: Respond in plain text only. Do NOT use markdown formatting such as bold (**text**), italic (*text*), headers (#), bullet points, or any other markdown syntax. Use simple paragraph text.
    """

    static let closingSentence = "Provide a natural language explanation of the current conditions and what to expect over the coming days for someone planning their activities."

    static func messages(
        report: WeatherReport,
        style: ExplanationStyle,
        formatter: WeatherFormatter
    ) -> [OpenRouterClient.Message] {
        let system = "\(defaultSystemPrompt)\n\n\(style.systemInstruction)"
        let dateFormatter = DateFormatter()
        dateFormatter.locale = Locale(identifier: "en_US")
        dateFormatter.timeZone = report.timeZone
        dateFormatter.dateStyle = .medium
        dateFormatter.timeStyle = .short
        let humidity = formatter.humidity(report.current.humidityPercent) ?? "Unknown"

        var lines = [
            "Weather information to explain:",
            "Location: \(report.location.name)",
            "Local Time: \(dateFormatter.string(from: report.fetchedAt)) (\(report.timeZone.identifier))",
            "Temperature: \(formatter.temperature(report.current.temperatureC) ?? "Unknown")",
            "Conditions: \(report.current.description ?? "Unknown")",
            "Humidity: \(humidity)",
            "Wind: \(formatter.wind(speedKph: report.current.windSpeedKph, directionDegrees: report.current.windDirectionDegrees) ?? "Unknown")",
            "Visibility: \(formatter.visibility(report.current.visibilityKm) ?? "Unknown")",
            "Pressure: \(formatter.pressure(report.current.pressureHpa) ?? "Unknown")",
            "Active Alerts:",
        ]
        lines += report.alerts.map { "- \($0.event) (Severity: \($0.severity))" }
        lines.append("\nUpcoming Forecast:")
        lines += report.daily.prefix(6).map { period in
            let high = formatter.temperature(period.highC) ?? "Unknown"
            let low = formatter.temperature(period.lowC) ?? "Unknown"
            return "- \(period.name): \(high)/\(low), \(period.condition)"
        }
        lines.append("\n\(closingSentence)")
        return [
            OpenRouterClient.Message(role: "system", content: system),
            OpenRouterClient.Message(role: "user", content: lines.joined(separator: "\n")),
        ]
    }

    static func textProductPrompt(
        text: String,
        productType: String,
        locationName: String,
        style: ExplanationStyle
    ) -> String {
        let label = productType.isEmpty ? "unknown type" : productType
        return "Please explain this National Weather Service text product (\(label)) for \(locationName) in plain language:\n\n\(text)\n\n\(style.productInstruction)"
    }

    static func stripMarkdown(_ text: String) -> String {
        let replacements: [(String, String)] = [
            (#"\*\*(.+?)\*\*"#, "$1"),
            (#"\*(.+?)\*"#, "$1"),
            (#"__(.+?)__"#, "$1"),
            (#"_(.+?)_"#, "$1"),
            (#"(?m)^#{1,6}\s+"#, ""),
            (#"```[\s\S]*?```"#, ""),
            (#"`(.+?)`"#, "$1"),
            (#"\[(.+?)\]\(.+?\)"#, "$1"),
            (#"(?m)^\s*[-*+]\s+"#, ""),
            (#"\n{3,}"#, "\n\n"),
        ]
        let result = replacements.reduce(text) { output, rule in
            guard let regex = try? NSRegularExpression(pattern: rule.0) else { return output }
            let range = NSRange(output.startIndex..<output.endIndex, in: output)
            return regex.stringByReplacingMatches(in: output, range: range, withTemplate: rule.1)
        }
        return result.trimmingCharacters(in: .whitespacesAndNewlines)
    }
}

@MainActor
final class WeatherExplanationCache {
    static let shared = WeatherExplanationCache()
    private var values: [String: String] = [:]

    func value(locationID: UUID, fetchedAt: Date, style: ExplanationStyle, model: String) -> String? {
        values[key(locationID: locationID, fetchedAt: fetchedAt, style: style, model: model)]
    }

    func store(_ text: String, locationID: UUID, fetchedAt: Date, style: ExplanationStyle, model: String) {
        values[key(locationID: locationID, fetchedAt: fetchedAt, style: style, model: model)] = text
    }

    private func key(locationID: UUID, fetchedAt: Date, style: ExplanationStyle, model: String) -> String {
        "\(locationID.uuidString)|\(fetchedAt.timeIntervalSince1970)|\(style.rawValue)|\(model)"
    }
}
