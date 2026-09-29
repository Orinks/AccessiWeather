import SwiftUI

struct UVIndexDetailView: View {
    let report: WeatherReport
    let formatter: WeatherFormatter

    private var currentUVIndex: (value: Int, category: String)? {
        guard let index = report.current.uvIndex else { return nil }
        let roundedIndex = WeatherFormatter.roundedUVIndex(index)
        return (roundedIndex, WeatherFormatter.uvCategory(forRoundedIndex: roundedIndex))
    }

    private var hourlyForecast: [HourlyPeriod] {
        Array(report.hourly.filter { $0.uvIndex != nil }.prefix(12))
    }

    var body: some View {
        List {
            Section {
                if let currentUVIndex {
                    MeasurementRow(
                        label: "UV Index",
                        value: "\(currentUVIndex.value) (\(currentUVIndex.category))",
                        spokenValue: "\(currentUVIndex.value), \(currentUVIndex.category)"
                    )
                    Text("Health guidance: \(UVIndexGuidance.guidance(for: currentUVIndex.category))")
                        .accessibilityElement(children: .ignore)
                        .accessibilityLabel("Health guidance: \(UVIndexGuidance.guidance(for: currentUVIndex.category))")
                } else {
                    Text("UV index data is not available for this location.")
                        .foregroundStyle(.secondary)
                }
            } header: {
                SectionHeader("Current UV Index")
            }
            Section {
                if hourlyForecast.isEmpty {
                    Text("Hourly forecast data is not available.")
                        .foregroundStyle(.secondary)
                } else {
                    ForEach(hourlyForecast) { period in
                        let uvIndex = period.uvIndex ?? 0
                        let hour = formatter.hour(period.time)
                        let roundedIndex = WeatherFormatter.roundedUVIndex(uvIndex)
                        let category = WeatherFormatter.uvCategory(forRoundedIndex: roundedIndex)
                        Text("\(hour), UV \(roundedIndex), \(category)")
                            .accessibilityElement(children: .ignore)
                            .accessibilityLabel("\(formatter.spokenHour(period.time)), UV Index \(roundedIndex), \(category)")
                    }
                }
            } header: {
                SectionHeader("Hourly Forecast")
            }
            Section {
                if let currentUVIndex,
                   let recommendations = UVIndexGuidance.recommendations(for: currentUVIndex.category) {
                    ForEach(Array(recommendations.enumerated()), id: \.offset) { item in
                        Text(item.element)
                            .accessibilityElement(children: .ignore)
                    }
                } else {
                    Text("Sun safety recommendations are not available.")
                        .foregroundStyle(.secondary)
                }
            } header: {
                SectionHeader("Sun Safety Recommendations")
            }
        }
        .navigationTitle("UV Index")
        .navigationBarTitleDisplayMode(.inline)
    }

}
