import Foundation
import SwiftUI

/// Weather Assistant chat with live weather tools, after Rust `aw_ai::assistant` and `aw_ai::tools`.
enum WeatherAssistantTools {
    static let maxContextMessages = 40
    static let maxToolRounds = 5

    static let systemPrompt = """
    You are Weather Assistant, a friendly and knowledgeable weather assistant built into AccessiWeather. You help users understand weather conditions in plain, accessible language optimized for screen reader users.

    You have access to live weather tools that can fetch current conditions, forecasts, and active alerts for any location. The available tools are:
    - get_current_weather: Get current weather conditions for a location
    - get_forecast: Get the weather forecast for a location
    - get_hourly_forecast: Get hourly forecast (great for specific time questions)
    - get_alerts: Get active weather alerts for a location
    - search_location: Search for a location by name or ZIP code
    - list_locations: Show all saved locations
    - get_area_forecast_discussion: Local NWS forecaster's detailed discussion
    - get_wpc_discussion: National WPC short range forecast discussion
    - get_spc_outlook: Storm Prediction Center severe weather outlook

    Use the provided tools to fetch weather data when users ask about specific locations or conditions not in the current context. You can call multiple tools if needed to give a complete answer. Use search_location when a place name is ambiguous.

    Guidelines:
    - Be conversational and helpful
    - Explain weather in practical terms (what to wear, activity suitability, etc.)
    - Avoid visual-only descriptions
    - When referencing data, use the weather context provided
    - For live weather requests, fetch the requested data before answering; never finish with a promise to check later
    - After tool results arrive, answer using those results and their observation times
    - A failed alert lookup means alerts are unknown, not that there are no alerts
    - Keep responses concise but thorough
    - Respond in plain text only — no markdown formatting
    - Do not repeat information the user can already see

    IMPORTANT: Respond in plain text. No bold, italic, headers, or bullet markers.
    """

    static func welcome(locationName: String?) -> String {
        "Welcome to Weather Assistant! I can help you understand the weather conditions for \(locationName ?? "your area"). Ask me anything about the current weather, forecast, what to wear, or how conditions might affect your plans."
    }

    private static func tool(_ name: String, _ description: String, location: String? = nil) -> [String: Any] {
        var parameters: [String: Any] = ["type": "object", "properties": [String: Any]()]
        if let location {
            parameters["properties"] = ["location": ["type": "string", "description": location]]
            parameters["required"] = ["location"]
        }
        return ["type": "function", "function": ["name": name, "description": description, "parameters": parameters]]
    }

    static let definitions: [[String: Any]] = [
        tool("get_current_weather", "Get current weather conditions for a location.", location: "The location to get weather for, e.g. 'New York, NY' or '10001'."),
        tool("get_forecast", "Get the weather forecast for a location.", location: "The location to get the forecast for, e.g. 'New York, NY' or '10001'."),
        tool("get_hourly_forecast", "Get the hourly forecast for a location. Great for questions about a specific time today or tomorrow.", location: "The location to get the hourly forecast for."),
        tool("get_alerts", "Get active weather alerts for a location.", location: "The location to get weather alerts for, e.g. 'New York, NY' or '10001'."),
        tool("search_location", "Search for a location by name or ZIP code and return matching places with coordinates.", location: "Place name or ZIP code to search for."),
        tool("list_locations", "List the user's saved locations."),
        tool("get_area_forecast_discussion", "Get the Area Forecast Discussion (AFD) for a location. This is a detailed technical forecast discussion written by local NWS forecasters. Great for understanding the reasoning behind the forecast.", location: "Location to get the AFD for, e.g. 'New York, NY'."),
        tool("get_wpc_discussion", "Get the Weather Prediction Center (WPC) Short Range Forecast Discussion. A nationwide weather discussion covering the next 1-3 days. Covers major weather systems, precipitation patterns, and significant weather events across the US."),
        tool("get_spc_outlook", "Get the Storm Prediction Center (SPC) Day 1 Convective Outlook discussion. Covers severe weather risks including tornadoes, large hail, and damaging winds. Explains the meteorological reasoning behind severe weather risk areas."),
    ]

    static func fahrenheit(_ celsius: Double?) -> String {
        celsius.map { "\(Int((($0 * 9 / 5) + 32).rounded()))°F" } ?? "unknown"
    }

    static func mph(_ kph: Double?) -> String? {
        kph.map { "\(Int(($0 / 1.609344).rounded())) mph" }
    }

    /// `build_weather_context` for the report the user is viewing.
    static func context(_ report: WeatherReport?) -> String {
        guard let report else { return "No weather data currently loaded." }
        var parts = ["Location: \(report.location.name) (\(report.location.latitude), \(report.location.longitude))"]
        parts.append(current(report))
        if !report.daily.isEmpty {
            parts.append("\nForecast:")
            parts += report.daily.prefix(6).map(dailyLine)
        }
        if !report.alerts.isEmpty {
            parts.append("\nActive Alerts:")
            parts += report.alerts.prefix(5).map { "  - \($0.event) (Severity: \($0.severity))" }
        }
        return parts.joined(separator: "\n")
    }

    static func current(_ report: WeatherReport) -> String {
        let c = report.current
        var lines = ["Temperature: \(fahrenheit(c.temperatureC))"]
        if let description = c.description, !description.isEmpty { lines.append("Conditions: \(description)") }
        if let humidity = c.humidityPercent { lines.append("Humidity: \(Int(humidity.rounded()))%") }
        if let wind = mph(c.windSpeedKph) {
            lines.append("Wind: \(wind)" + (c.windDirectionDegrees.map { " from \(Int($0.rounded())) degrees" } ?? ""))
        }
        if let pressure = c.pressureHpa { lines.append(String(format: "Pressure: %.2f inHg", pressure * 0.02953)) }
        if let visibility = c.visibilityKm { lines.append(String(format: "Visibility: %.1f miles", visibility / 1.609344)) }
        if let uv = c.uvIndex { lines.append("UV Index: \(Int(uv.rounded()))") }
        if let aqi = c.airQuality { lines.append("Air quality: AQI \(aqi.aqi), \(aqi.category)") }
        if let observed = c.observedAt { lines.append("Observed: \(observed.formatted(date: .abbreviated, time: .shortened))") }
        return lines.joined(separator: "\n")
    }

    static func dailyLine(_ period: DailyPeriod) -> String {
        let temperature = period.isDaytime ? (period.highC ?? period.lowC) : (period.lowC ?? period.highC)
        var line = "  \(period.name): \(fahrenheit(temperature)), \(period.condition)"
        if let chance = period.precipitationChance { line += ", \(chance)% chance of precipitation" }
        return line
    }

    static func hourlyLine(_ period: HourlyPeriod, timeZone: TimeZone) -> String {
        let formatter = DateFormatter()
        formatter.timeZone = timeZone
        formatter.dateFormat = "EEE h a"
        var line = "  \(formatter.string(from: period.time)): \(fahrenheit(period.temperatureC)), \(period.condition)"
        if let chance = period.precipitationChance { line += ", \(chance)% precipitation" }
        if let wind = mph(period.windSpeedKph) { line += ", wind \(wind)" }
        return line
    }

    static func alertsText(_ report: WeatherReport) -> String {
        guard report.alertsAreCurrent else { return "Weather alerts could not be checked. Alert status is unknown." }
        guard !report.alerts.isEmpty else { return "No active weather alerts for \(report.location.name)." }
        return "Active alerts for \(report.location.name):\n" + report.alerts.prefix(10).map { alert in
            var text = "- \(alert.event) (Severity: \(alert.severity))"
            if let headline = alert.headline { text += "\n  \(headline)" }
            if let instruction = alert.instruction { text += "\n  Instructions: \(instruction)" }
            return text
        }.joined(separator: "\n")
    }

    static func truncated(_ text: String) -> String {
        text.count > 3000 ? String(text.prefix(3000)) + "\n\n[Truncated — full discussion is longer]" : text
    }
}

@MainActor
final class WeatherAssistant: ObservableObject {
    struct Entry: Identifiable, Equatable {
        let id = UUID()
        var speaker: String
        var text: String
        var time = Date()
    }

    @Published private(set) var entries: [Entry] = []
    @Published private(set) var isThinking = false
    private var history: [[String: Any]] = []
    private let model: AppModel
    private let client = OpenRouterClient()

    init(model: AppModel) {
        self.model = model
        clear()
    }

    func clear() {
        history = []
        entries = [Entry(speaker: "Weather Assistant", text: WeatherAssistantTools.welcome(locationName: model.selectedLocation?.name))]
    }

    /// Sends a question; returns it back when the request failed so the caller can restore the input.
    func send(_ question: String) async -> String? {
        let text = question.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, !isThinking else { return nil }
        let key = KeychainStore.read(.openRouter)
        entries.append(Entry(speaker: "You", text: text))
        guard !key.isEmpty else {
            entries.append(Entry(speaker: "Weather Assistant", text: "Add an OpenRouter API key in Settings > AI to use Weather Assistant."))
            return text
        }
        isThinking = true
        defer { isThinking = false }
        history.append(["role": "user", "content": text])
        do {
            let answer = try await respond(key: key)
            history.append(["role": "assistant", "content": answer])
            if history.count > WeatherAssistantTools.maxContextMessages {
                history.removeFirst(history.count - WeatherAssistantTools.maxContextMessages)
            }
            entries.append(Entry(speaker: "Weather Assistant", text: answer))
            AccessibilityNotification.Announcement("Weather Assistant: \(answer)").post()
            return nil
        } catch {
            history.removeLast()
            let message = "Sorry, I couldn't respond: \(error.localizedDescription)"
            entries.append(Entry(speaker: "Weather Assistant", text: message))
            AccessibilityNotification.Announcement("Weather Assistant: \(message) Your question is restored in the input for editing.").post()
            return text
        }
    }

    private func respond(key: String) async throws -> String {
        let system = WeatherAssistantTools.systemPrompt + "\n\nCurrent weather context:\n" + WeatherAssistantTools.context(model.report)
        var messages: [[String: Any]] = [["role": "system", "content": system]] + history
        for _ in 0...WeatherAssistantTools.maxToolRounds {
            let body: [String: Any] = ["model": model.settings.aiModel, "messages": messages, "max_tokens": 2000, "tools": WeatherAssistantTools.definitions]
            let reply = try await client.chat(body: body, key: key)
            let calls = reply["tool_calls"] as? [[String: Any]] ?? []
            if calls.isEmpty {
                let content = WeatherExplainer.stripMarkdown((reply["content"] as? String ?? "").trimmingCharacters(in: .whitespacesAndNewlines))
                guard !content.isEmpty else {
                    throw WeatherError.unsupported("Received an empty response. Try again or switch models in Settings.")
                }
                return content
            }
            messages.append(["role": "assistant", "content": reply["content"] as? String ?? "", "tool_calls": calls])
            for call in calls {
                let function = call["function"] as? [String: Any] ?? [:]
                let arguments = (function["arguments"] as? String)
                    .flatMap { try? JSONSerialization.jsonObject(with: Data($0.utf8)) as? [String: Any] } ?? [:]
                let result = await execute(function["name"] as? String ?? "", location: arguments["location"] as? String)
                messages.append(["role": "tool", "tool_call_id": call["id"] as? String ?? "", "content": result])
            }
        }
        throw WeatherError.unsupported("The assistant could not finish its weather lookup. Please try a simpler question.")
    }

    private func resolve(_ query: String?) async throws -> SavedLocation {
        let query = (query ?? "").trimmingCharacters(in: .whitespaces)
        let saved = model.locationStore.locations
        if query.isEmpty, let selected = model.selectedLocation { return selected }
        if let match = saved.first(where: { $0.name.caseInsensitiveCompare(query) == .orderedSame }) { return match }
        guard let result = try await GeocodingClient().search(query, limit: 1).first else {
            throw WeatherError.unsupported("Could not find location '\(query)'.")
        }
        return SavedLocation(name: result.shortName, latitude: result.latitude, longitude: result.longitude)
    }

    private func report(_ query: String?) async throws -> WeatherReport {
        try await model.weatherService.report(
            for: try await resolve(query),
            source: model.settings.weatherSource,
            pirateWeatherKey: KeychainStore.read(.pirateWeather)
        )
    }

    func execute(_ name: String, location: String?) async -> String {
        do {
            switch name {
            case "get_current_weather":
                let report = try await report(location)
                return "Current weather for \(report.location.name):\n" + WeatherAssistantTools.current(report)
            case "get_forecast":
                let report = try await report(location)
                return "Forecast for \(report.location.name):\n" + report.daily.prefix(14).map(WeatherAssistantTools.dailyLine).joined(separator: "\n")
            case "get_hourly_forecast":
                let report = try await report(location)
                return "Hourly forecast for \(report.location.name):\n" + report.hourly.prefix(24)
                    .map { WeatherAssistantTools.hourlyLine($0, timeZone: report.timeZone) }.joined(separator: "\n")
            case "get_alerts":
                guard let report = try? await report(location) else {
                    return "Weather alerts could not be checked. Alert status is unknown."
                }
                return WeatherAssistantTools.alertsText(report)
            case "search_location":
                let results = try await GeocodingClient().search(location ?? "", limit: 5)
                guard !results.isEmpty else { return "No locations found for '\(location ?? "")'." }
                return results.map { "- \($0.displayName) (\($0.latitude), \($0.longitude))" }.joined(separator: "\n")
            case "list_locations":
                let names = model.locationStore.locations.map(\.name)
                guard !names.isEmpty else { return "No saved locations." }
                let selected = model.selectedLocation?.name
                return "Saved locations:\n" + names.map { "- \($0)" + ($0 == selected ? " (current)" : "") }.joined(separator: "\n")
            case "get_area_forecast_discussion":
                let report = try await report(location)
                guard let office = report.forecastOfficeID,
                      let product = try await model.weatherService.latestProduct(type: "AFD", officeID: office) else {
                    return "No Area Forecast Discussion is available for \(report.location.name)."
                }
                return "Area Forecast Discussion for \(report.location.name):\n" + WeatherAssistantTools.truncated(product.productText)
            case "get_wpc_discussion":
                return "WPC Short Range Forecast Discussion:\n" + WeatherAssistantTools.truncated(try await IEMClient().latestText(pil: "PMDSPD"))
            case "get_spc_outlook":
                return "SPC Day 1 Convective Outlook:\n" + WeatherAssistantTools.truncated(try await IEMClient().latestText(pil: "SWODY1"))
            default:
                return "Error: this tool call is not available for this request."
            }
        } catch {
            return "Error fetching weather data: \(error.localizedDescription)"
        }
    }
}
