import SwiftUI

/// Shows the NWS Area Forecast Discussion for the current forecast office.
struct ForecasterNotesView: View {
    @EnvironmentObject private var model: AppModel
    let officeID: String

    @State private var text: String?
    @State private var errorMessage: String?

    var body: some View {
        ScrollView {
            if let text {
                Text(text)
                    .font(.body.monospaced())
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding()
                    .textSelection(.enabled)
            } else if let errorMessage {
                ContentUnavailableView("Discussion Unavailable", systemImage: "exclamationmark.triangle", description: Text(errorMessage))
            } else {
                ProgressView("Loading forecast discussion…")
                    .padding()
            }
        }
        .navigationTitle("Forecaster Notes")
        .navigationBarTitleDisplayMode(.inline)
        .task {
            do {
                text = try await model.weatherService.forecastDiscussion(officeID: officeID)
                model.sounds.play(.discussionUpdate)
            } catch {
                model.sounds.play(.fetchError)
                errorMessage = error.localizedDescription
            }
        }
    }
}

/// Placeholder until the AI explanation feature is ported.
struct ExplainConditionsView: View {
    @EnvironmentObject private var model: AppModel
    @EnvironmentObject private var settings: SettingsStore
    @State private var explanation: String?
    @State private var errorMessage: String?
    @State private var isLoading = false

    var body: some View {
        List {
            Section {
                if isLoading {
                    ProgressView("Preparing your explanation…")
                        .accessibilityElement(children: .combine)
                } else if let explanation {
                    Text(explanation)
                        .textSelection(.enabled)
                        .accessibilityElement(children: .ignore)
                        .accessibilityLabel(explanation)
                } else if let errorMessage {
                    Text(errorMessage)
                        .foregroundStyle(.secondary)
                    Button("Try Again") { Task { await explain() } }
                        .accessibilityHint("Requests a new weather explanation")
                } else {
                    Button("Explain") { Task { await explain() } }
                        .accessibilityHint("Requests a plain-language explanation of the current weather")
                }
            } header: {
                SectionHeader("Weather Explanation")
            }
        }
        .navigationTitle("Explain Conditions")
        .navigationBarTitleDisplayMode(.inline)
    }

    @MainActor
    private func explain() async {
        guard let report = model.report else {
            errorMessage = "Weather data is not available yet. Refresh and try again."
            return
        }
        let key = KeychainStore.read(.openRouter)
        guard !key.isEmpty else {
            errorMessage = "Add an OpenRouter API key in Settings > AI to explain weather."
            return
        }
        let modelName = settings.aiModel.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            ? "openrouter/free"
            : settings.aiModel
        if let cached = WeatherExplanationCache.shared.value(
            locationID: report.location.id,
            fetchedAt: report.fetchedAt,
            style: settings.aiExplanationStyle,
            model: modelName
        ) {
            explanation = cached
            errorMessage = nil
            return
        }
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        do {
            let formatter = WeatherFormatter(settings: settings, timeZone: report.timeZone)
            let messages = WeatherExplainer.messages(
                report: report,
                style: settings.aiExplanationStyle,
                formatter: formatter
            )
            let response = try await OpenRouterClient().complete(
                system: messages[0].content,
                user: messages[1].content,
                model: modelName,
                key: key
            )
            let plainText = WeatherExplainer.stripMarkdown(response)
            explanation = plainText
            WeatherExplanationCache.shared.store(
                plainText,
                locationID: report.location.id,
                fetchedAt: report.fetchedAt,
                style: settings.aiExplanationStyle,
                model: modelName
            )
            AccessibilityNotification.Announcement("Explanation ready").post()
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}
