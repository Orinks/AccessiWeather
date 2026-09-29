import SwiftUI

enum PrecipitationTimelineText {
    static func summary(_ points: [MinutelyPoint]) -> String {
        guard let firstWet = points.firstIndex(where: \.isWet) else {
            return "No precipitation expected in the next hour."
        }
        if firstWet == 0,
           let firstDry = points[firstWet...].firstIndex(where: { !$0.isWet }) {
            return "Rain ending in about \(firstDry) minutes."
        }
        return "Rain starting in about \(firstWet) minutes."
    }

    static func condition(_ point: MinutelyPoint) -> String {
        guard point.isWet else { return "Dry" }
        switch point.precipitationType?.lowercased() {
        case "rain": return "Rain"
        case "snow": return "Snow"
        case "sleet": return "Sleet"
        default: return "Precipitation"
        }
    }

    static func row(_ point: MinutelyPoint, offset: Int, timeZone: TimeZone) -> String {
        let formatter = DateFormatter()
        formatter.timeZone = timeZone
        formatter.dateStyle = .none
        formatter.timeStyle = .short
        let time = formatter.string(from: point.time)
        var parts = [offset == 0 ? "Now" : String(format: "+%02dm", offset), time, condition(point)]
        if let probability = point.precipitationProbability, probability > 0 {
            parts.append("\(Int((probability * 100).rounded()))% chance")
        }
        if let intensity = point.precipitationIntensity, intensity > 0 {
            parts.append(String(format: "%.3f mm/h", intensity))
        }
        return parts.joined(separator: ", ")
    }
}

struct PrecipitationTimelineView: View {
    @EnvironmentObject private var model: AppModel
    @State private var points: [MinutelyPoint] = []
    @State private var isLoading = true
    @State private var unavailable = false

    var body: some View {
        List {
            if isLoading {
                ProgressView("Loading precipitation timeline…")
                    .accessibilityElement(children: .combine)
            } else if unavailable {
                Text("Minutely precipitation data is not available for this location yet.")
                    .foregroundStyle(.secondary)
            } else {
                Section {
                    Text(PrecipitationTimelineText.summary(points))
                        .accessibilityElement(children: .ignore)
                        .accessibilityLabel(PrecipitationTimelineText.summary(points))
                } header: {
                    SectionHeader("Summary")
                }
                Section {
                    ForEach(Array(points.enumerated()), id: \.element.id) { offset, point in
                        Text(PrecipitationTimelineText.row(point, offset: offset, timeZone: timeZone))
                            .accessibilityElement(children: .ignore)
                            .accessibilityLabel(PrecipitationTimelineText.row(point, offset: offset, timeZone: timeZone))
                    }
                } header: {
                    SectionHeader("Minute-by-minute timeline")
                }
            }
        }
        .navigationTitle("Precipitation Timeline")
        .navigationBarTitleDisplayMode(.inline)
        .task { await load() }
    }

    private var timeZone: TimeZone {
        model.report?.timeZone ?? .current
    }

    @MainActor
    private func load() async {
        guard let location = model.selectedLocation,
              !KeychainStore.read(.pirateWeather).isEmpty else {
            points = []
            unavailable = true
            isLoading = false
            return
        }
        if let report = model.report,
           report.sourceDescription == "Pirate Weather",
           let minutely = report.minutely {
            points = minutely
            unavailable = false
            isLoading = false
            return
        }
        do {
            let report = try await model.weatherService.report(
                for: location,
                source: .pirateWeather,
                pirateWeatherKey: KeychainStore.read(.pirateWeather)
            )
            points = report.minutely ?? []
            unavailable = points.isEmpty
        } catch {
            points = []
            unavailable = true
        }
        isLoading = false
    }
}
