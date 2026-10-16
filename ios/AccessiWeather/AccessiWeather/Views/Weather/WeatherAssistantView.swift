import SwiftUI

struct WeatherAssistantView: View {
    @StateObject private var assistant: WeatherAssistant
    @State private var question = ""
    @FocusState private var inputFocused: Bool

    init(model: AppModel) {
        _assistant = StateObject(wrappedValue: WeatherAssistant(model: model))
    }

    var body: some View {
        List {
            Section {
                ForEach(assistant.entries) { entry in
                    VStack(alignment: .leading, spacing: 4) {
                        Text("\(entry.speaker), \(entry.time.formatted(date: .omitted, time: .shortened))")
                            .font(.caption)
                        Text(entry.text)
                            .textSelection(.enabled)
                    }
                    .accessibilityElement(children: .combine)
                    .accessibilityLabel("\(entry.speaker): \(entry.text)")
                }
                if assistant.isThinking {
                    ProgressView("Weather Assistant is thinking…")
                        .accessibilityElement(children: .combine)
                }
            } header: {
                SectionHeader("Conversation")
            }

            Section {
                TextField("Ask about the weather", text: $question, axis: .vertical)
                    .focused($inputFocused)
                    .accessibilityLabel("Message")
                    .accessibilityHint("Type a weather question, then choose Send")
                Button {
                    let text = question
                    question = ""
                    Task {
                        if let restored = await assistant.send(text) { question = restored }
                    }
                } label: {
                    Label("Send", systemImage: "paperplane")
                }
                .disabled(assistant.isThinking || question.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                .accessibilityHint("Sends your question to Weather Assistant")
                Button(role: .destructive) {
                    assistant.clear()
                    AccessibilityNotification.Announcement("Conversation cleared").post()
                } label: {
                    Label("Clear Conversation", systemImage: "trash")
                }
                .disabled(assistant.isThinking)
            } header: {
                SectionHeader("Ask")
            }
        }
        .navigationTitle("Weather Assistant")
        .navigationBarTitleDisplayMode(.inline)
    }
}
