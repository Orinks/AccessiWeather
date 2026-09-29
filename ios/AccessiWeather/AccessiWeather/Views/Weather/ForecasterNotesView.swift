import SwiftUI

enum ForecasterProduct: String, CaseIterable, Identifiable {
    case afd = "AFD"
    case hwo = "HWO"
    case sps = "SPS"

    var id: String { rawValue }

    var fullName: String {
        switch self {
        case .afd: return "Area Forecast Discussion"
        case .hwo: return "Hazardous Weather Outlook"
        case .sps: return "Special Weather Statement"
        }
    }
}

struct ForecasterNotesView: View {
    @EnvironmentObject private var model: AppModel
    @EnvironmentObject private var settings: SettingsStore
    let officeID: String

    @State private var selectedProduct: ForecasterProduct = .afd
    @State private var productResponse: NWSClient.ProductResponse?
    @State private var noProduct = false
    @State private var errorMessage: String?
    @State private var productSummary: String?
    @State private var summaryError: String?
    @State private var isLoading = false
    @State private var isSummarizing = false
    @State private var summaryCache: [String: String] = [:]

    private var hasOpenRouterKey: Bool {
        !KeychainStore.read(.openRouter).isEmpty
    }

    var body: some View {
        List {
            Section {
                Picker("Product", selection: $selectedProduct) {
                    ForEach(ForecasterProduct.allCases) { product in
                        Text(product.fullName).tag(product)
                    }
                }
                .pickerStyle(.segmented)
                .accessibilityLabel("Product")
            } header: {
                SectionHeader("Forecaster Product")
            }

            if isLoading {
                ProgressView("Loading \(selectedProduct.fullName)…")
                    .accessibilityElement(children: .combine)
            } else if let errorMessage {
                ContentUnavailableView(
                    "Product Unavailable",
                    systemImage: "exclamationmark.triangle",
                    description: Text(errorMessage)
                )
            } else if noProduct {
                Text("No \(selectedProduct.fullName) is currently available from the \(officeID) office.")
                    .accessibilityElement(children: .combine)
            } else if let productResponse {
                if let productSummary {
                    Section {
                        Text(productSummary)
                            .textSelection(.enabled)
                            .accessibilityElement(children: .ignore)
                            .accessibilityLabel(productSummary)
                    } header: {
                        SectionHeader("Plain Language Summary")
                    }
                }
                if hasOpenRouterKey {
                    Section {
                        if isSummarizing {
                            ProgressView("Preparing summary…")
                                .accessibilityElement(children: .combine)
                        } else if let summaryError {
                            Text(summaryError)
                                .foregroundStyle(.secondary)
                            Button("Try Again") { Task { await explain(product: productResponse) } }
                                .accessibilityHint("Requests a new plain-language product summary")
                        } else if productSummary == nil {
                            Button("Explain This Product") { Task { await explain(product: productResponse) } }
                                .accessibilityHint("Summarizes this National Weather Service product")
                        }
                    }
                }
                Section {
                    Text(productResponse.productText)
                        .font(.body.monospaced())
                        .textSelection(.enabled)
                        .accessibilityElement(children: .ignore)
                        .accessibilityLabel(productResponse.productText)
                } header: {
                    SectionHeader(selectedProduct.fullName)
                }
            }
        }
        .navigationTitle("Forecaster Notes")
        .navigationBarTitleDisplayMode(.inline)
        .task(id: selectedProduct) {
            isLoading = true
            productResponse = nil
            noProduct = false
            errorMessage = nil
            productSummary = nil
            summaryError = nil
            do {
                productResponse = try await model.weatherService.latestProduct(
                    type: selectedProduct.rawValue,
                    officeID: officeID
                )
                noProduct = productResponse == nil
                if selectedProduct == .afd, productResponse != nil {
                    model.sounds.play(.discussionUpdate)
                }
            } catch {
                model.sounds.play(.fetchError)
                errorMessage = error.localizedDescription
            }
            isLoading = false
        }
    }

    @MainActor
    private func explain(product: NWSClient.ProductResponse) async {
        let key = KeychainStore.read(.openRouter)
        guard !key.isEmpty else {
            summaryError = "Add an OpenRouter API key in Settings > AI to explain this product."
            return
        }
        let modelName = settings.aiModel.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            ? "openrouter/free"
            : settings.aiModel
        let cacheKey = "\(product.id)|\(selectedProduct.rawValue)|\(settings.aiExplanationStyle.rawValue)|\(modelName)|\(product.productText)"
        if let cached = summaryCache[cacheKey] {
            productSummary = cached
            summaryError = nil
            return
        }
        isSummarizing = true
        summaryError = nil
        defer { isSummarizing = false }
        do {
            let response = try await OpenRouterClient().complete(
                system: "\(WeatherExplainer.defaultSystemPrompt)\n\n\(settings.aiExplanationStyle.systemInstruction)",
                user: WeatherExplainer.textProductPrompt(
                    text: product.productText,
                    productType: selectedProduct.rawValue,
                    locationName: model.report?.location.name ?? "this location",
                    style: settings.aiExplanationStyle
                ),
                model: modelName,
                key: key
            )
            let plainText = WeatherExplainer.stripMarkdown(response)
            productSummary = plainText
            summaryCache[cacheKey] = plainText
            AccessibilityNotification.Announcement("Explanation ready").post()
        } catch {
            summaryError = error.localizedDescription
        }
    }
}

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
