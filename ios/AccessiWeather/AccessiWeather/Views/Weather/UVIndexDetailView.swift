import SwiftUI

struct UVIndexDetailView: View {
    let report: WeatherReport
    let formatter: WeatherFormatter

    private var category: String? {
        report.current.uvIndex.map(WeatherFormatter.uvCategory)
    }

    private var hourlyForecast: [HourlyPeriod] {
        Array(report.hourly.filter { $0.uvIndex != nil }.prefix(12))
    }

    var body: some View {
        List {
            Section {
                if let uvIndex = report.current.uvIndex, let category {
                    MeasurementRow(
                        label: "UV Index",
                        value: "\(Int(uvIndex.rounded())) (\(category))",
                        spokenValue: "\(Int(uvIndex.rounded())), \(category)"
                    )
                    Text("Health guidance: \(UVIndexGuidance.guidance(for: category))")
                        .accessibilityElement(children: .ignore)
                        .accessibilityLabel("Health guidance: \(UVIndexGuidance.guidance(for: category))")
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
                        let category = WeatherFormatter.uvCategory(uvIndex)
                        Text("\(hour), UV \(Int(uvIndex.rounded())), \(category)")
                            .accessibilityElement(children: .ignore)
                            .accessibilityLabel("\(formatter.spokenHour(period.time)), UV Index \(Int(uvIndex.rounded())), \(category)")
                    }
                }
            } header: {
                SectionHeader("Hourly Forecast")
            }
            Section {
                if let category, let recommendations = UVIndexGuidance.recommendations(for: category) {
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
