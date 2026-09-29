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
                    Text("Health guidance: \(guidance(for: category))")
                        .accessibilityElement(children: .ignore)
                        .accessibilityLabel("Health guidance: \(guidance(for: category))")
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
                if let category, let recommendations = sunSafetyRecommendations(for: category) {
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

    private func guidance(for category: String) -> String {
        switch category {
        case "Low": return "No protection needed. You can safely stay outside."
        case "Moderate": return "Seek shade during midday hours. Wear protective clothing."
        case "High": return "Reduce time in the sun between 10am and 4pm. Seek shade, wear protective clothing."
        case "Very High": return "Take extra precautions. Minimize sun exposure between 10am and 4pm."
        case "Extreme": return "Try to avoid sun exposure between 10am and 4pm. Shirt, sunscreen, and hat are essential."
        default: return "Monitor UV levels and use sun protection as needed."
        }
    }

    private func sunSafetyRecommendations(for category: String) -> [String]? {
        switch category {
        case "Low":
            return [
                "SPF 15+ sunscreen for extended outdoor activities",
                "Sunglasses on bright days",
                "No special precautions needed for most people",
            ]
        case "Moderate":
            return [
                "SPF 30+ sunscreen, reapply every 2 hours",
                "Wear sunglasses and a wide-brimmed hat",
                "Seek shade during midday hours",
                "Cover up with clothing when possible",
            ]
        case "High":
            return [
                "SPF 30+ sunscreen is essential",
                "Wear protective clothing, hat, and sunglasses",
                "Seek shade, especially during midday",
                "Limit time in direct sun between 10am-4pm",
                "Stay hydrated",
            ]
        case "Very High":
            return [
                "SPF 50+ sunscreen, reapply frequently",
                "Protective clothing, wide-brimmed hat, UV-blocking sunglasses",
                "Stay in shade whenever possible",
                "Minimize outdoor activities between 10am-4pm",
                "Extra caution for children and sensitive skin",
            ]
        case "Extreme":
            return [
                "AVOID outdoor activities between 10am-4pm if possible",
                "SPF 50+ sunscreen is critical, reapply every 1-2 hours",
                "Full protective clothing, hat, and sunglasses required",
                "Seek air-conditioned spaces",
                "Watch for signs of heat illness",
                "Extremely high risk of skin and eye damage",
            ]
        default:
            return nil
        }
    }
}
