import SwiftUI

/// The latest WPC, CPC, NHC and SPC national text products, like the desktop National Products dialog.
struct NationalProductsView: View {
    @EnvironmentObject private var model: AppModel
    @EnvironmentObject private var settings: SettingsStore

    @State private var selected: NationalProduct = .wpcShortRange
    @State private var text: String?
    @State private var errorMessage: String?
    @State private var isLoading = false
    @State private var summary: String?
    @State private var summaryError: String?
    @State private var isSummarizing = false

    var body: some View {
        List {
            Section {
                Picker("Product", selection: $selected) {
                    ForEach(NationalProduct.allCases) { product in
                        Text(product.label).tag(product)
                    }
                }
            } header: {
                SectionHeader("National Product")
            }

            if isLoading {
                ProgressView("Loading \(selected.label)…")
                    .accessibilityElement(children: .combine)
            } else if let errorMessage {
                ContentUnavailableView(
                    "Product Unavailable",
                    systemImage: "exclamationmark.triangle",
                    description: Text(errorMessage)
                )
            } else if let text {
                if let summary {
                    Section {
                        Text(summary)
                            .textSelection(.enabled)
                            .accessibilityElement(children: .ignore)
                            .accessibilityLabel(summary)
                    } header: {
                        SectionHeader("Plain Language Summary")
                    }
                }
                if model.hasOpenRouterKey {
                    Section {
                        if isSummarizing {
                            ProgressView("Preparing summary…")
                                .accessibilityElement(children: .combine)
                        } else if let summaryError {
                            Text(summaryError)
                                .foregroundStyle(.secondary)
                            Button("Try Again") { Task { await explain(text: text, product: selected) } }
                                .accessibilityHint("Requests a new plain-language product summary")
                        } else if summary == nil {
                            Button("Explain This Product") { Task { await explain(text: text, product: selected) } }
                                .accessibilityHint("Summarizes this national product")
                        }
                    }
                }
                Section {
                    Text(text)
                        .font(.body.monospaced())
                        .textSelection(.enabled)
                        .accessibilityElement(children: .ignore)
                        .accessibilityLabel(text)
                } header: {
                    SectionHeader(selected.label)
                }
            }
        }
        .navigationTitle("National Products")
        .navigationBarTitleDisplayMode(.inline)
        .task(id: selected) {
            isLoading = true
            text = nil
            errorMessage = nil
            summary = nil
            summaryError = nil
            isSummarizing = false
            do {
                text = try await IEMClient().latestText(pil: selected.rawValue)
            } catch is CancellationError {
                return
            } catch {
                model.sounds.play(.fetchError)
                errorMessage = error.localizedDescription
            }
            isLoading = false
        }
    }

    @MainActor
    private func explain(text: String, product: NationalProduct) async {
        let key = KeychainStore.read(.openRouter)
        guard !key.isEmpty else {
            summaryError = "Add an OpenRouter API key in Settings > AI to explain this product."
            return
        }
        let modelName = settings.aiModel.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            ? "openrouter/free"
            : settings.aiModel
        isSummarizing = true
        summaryError = nil
        defer { if selected == product { isSummarizing = false } }
        do {
            let response = try await OpenRouterClient().complete(
                system: "\(WeatherExplainer.defaultSystemPrompt)\n\n\(settings.aiExplanationStyle.systemInstruction)",
                user: WeatherExplainer.textProductPrompt(
                    text: text,
                    productType: product.rawValue,
                    locationName: "the United States",
                    style: settings.aiExplanationStyle
                ),
                model: modelName,
                key: key
            )
            guard selected == product else { return }
            summary = WeatherExplainer.stripMarkdown(response)
            AccessibilityNotification.Announcement("Explanation ready").post()
        } catch {
            guard selected == product else { return }
            summaryError = error.localizedDescription
        }
    }
}
