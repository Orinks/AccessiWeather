import SwiftUI

struct WeatherHistoryView: View {
    @EnvironmentObject private var model: AppModel
    @EnvironmentObject private var settings: SettingsStore
    let report: WeatherReport

    @State private var history: WeatherHistory?
    @State private var errorMessage: String?
    @State private var isLoading = true

    private var formatter: WeatherFormatter {
        WeatherFormatter(settings: settings, timeZone: report.timeZone)
    }

    var body: some View {
        List {
            Section {
                if let history {
                    if let yesterday = history.yesterdayComparison {
                        Text(yesterday)
                            .foregroundStyle(.primary)
                            .accessibilityElement(children: .ignore)
                            .accessibilityLabel(yesterday)
                    } else {
                        Text("Comparison with yesterday is unavailable.")
                            .foregroundStyle(.primary)
                    }
                    if let lastWeek = history.lastWeekComparison {
                        Text(lastWeek)
                            .foregroundStyle(.primary)
                            .accessibilityElement(children: .ignore)
                            .accessibilityLabel(lastWeek)
                    } else {
                        Text("Comparison with last week is unavailable.")
                            .foregroundStyle(.primary)
                    }
                } else if let errorMessage {
                    Text(errorMessage)
                        .foregroundStyle(.primary)
                } else {
                    ProgressView("Loading weather history…")
                        .foregroundStyle(.primary)
                        .accessibilityElement(children: .combine)
                }
            } header: {
                SectionHeader("Compared to Previous Days")
            }

            Section {
                if let history {
                    ForEach(history.days) { day in
                        historyRow(day)
                    }
                } else if isLoading {
                    ProgressView("Loading the last 7 days…")
                        .foregroundStyle(.primary)
                        .accessibilityElement(children: .combine)
                }
            } header: {
                SectionHeader("Last 7 Days")
            }
        }
        .navigationTitle("Weather History")
        .navigationBarTitleDisplayMode(.inline)
        .task {
            do {
                history = try await model.weatherService.history(
                    for: report,
                    temperatureUnit: settings.temperatureUnit
                )
            } catch {
                errorMessage = error.localizedDescription
            }
            isLoading = false
        }
    }

    private func historyRow(_ day: WeatherHistoryDay) -> some View {
        let dateFormatter = DateFormatter()
        dateFormatter.locale = Locale(identifier: "en_US")
        dateFormatter.timeZone = report.timeZone
        dateFormatter.dateFormat = "EEEE, MMM d"
        let date = dateFormatter.string(from: day.date)
        let high = formatter.temperature(day.highC) ?? "Unknown"
        let low = formatter.temperature(day.lowC) ?? "Unknown"
        let spokenHigh = formatter.spokenTemperature(day.highC) ?? "unknown"
        let spokenLow = formatter.spokenTemperature(day.lowC) ?? "unknown"
        return Text("\(date): high \(high), low \(low), \(day.condition)")
            .accessibilityElement(children: .ignore)
            .accessibilityLabel("\(date): high \(spokenHigh), low \(spokenLow), \(day.condition)")
    }
}
