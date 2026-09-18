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
            } catch {
                errorMessage = error.localizedDescription
            }
        }
    }
}

/// Placeholder until the AI explanation feature is ported.
struct ExplainConditionsView: View {
    var body: some View {
        ContentUnavailableView(
            "Explain Conditions",
            systemImage: "sparkles",
            description: Text("Plain-language weather explanations require an OpenRouter API key and are not available in this version of the iOS app yet.")
        )
        .navigationTitle("Explain Conditions")
        .navigationBarTitleDisplayMode(.inline)
    }
}
