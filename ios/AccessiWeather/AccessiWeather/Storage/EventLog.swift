import Foundation
import SwiftUI

enum EventKind: String, Codable, Hashable {
    case newAlert
    case updatedAlert
    case alertEnded
    case discussionUpdated

    var spokenName: String {
        switch self {
        case .newAlert: return "New alert"
        case .updatedAlert: return "Updated alert"
        case .alertEnded: return "Alert ended"
        case .discussionUpdated: return "Discussion updated"
        }
    }
}

struct EventLogEntry: Codable, Equatable, Identifiable {
    var id: UUID
    var date: Date
    var locationName: String
    var kind: EventKind
    var title: String
    var detail: String

    var accessibleSummary: String {
        let formatter = DateFormatter()
        formatter.locale = .current
        formatter.timeZone = .current
        formatter.dateStyle = .none
        formatter.timeStyle = .short
        return "\(kind.spokenName), \(title), \(locationName), \(formatter.string(from: date))"
    }
}

struct AlertChanges: Equatable {
    var new: [WeatherAlert]
    var updated: [WeatherAlert]
    var ended: [WeatherAlert]
}

@MainActor
final class EventLog: ObservableObject {
    static let maximumEntries = 200

    @Published private(set) var entries: [EventLogEntry] = []
    private let fileURL: URL

    init(fileURL: URL? = nil) {
        if let fileURL {
            self.fileURL = fileURL
        } else {
            let support = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
            let directory = support.appendingPathComponent("AccessiWeather", isDirectory: true)
            try? FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
            self.fileURL = directory.appendingPathComponent("events.json")
        }
        load()
    }

    static func diff(previous: [WeatherAlert], current: [WeatherAlert]) -> AlertChanges {
        let previousByID = Dictionary(uniqueKeysWithValues: previous.map { ($0.id, $0) })
        let currentByID = Dictionary(uniqueKeysWithValues: current.map { ($0.id, $0) })
        let new = current.filter { previousByID[$0.id] == nil }
        let updated = current.filter { alert in
            guard let old = previousByID[alert.id] else { return false }
            return old.headline != alert.headline || old.expires != alert.expires
        }
        let ended = previousByID.keys
            .filter { currentByID[$0] == nil }
            .sorted()
            .compactMap { previousByID[$0] }
        return AlertChanges(new: new, updated: updated, ended: ended)
    }

    func recordAlertChanges(
        previous: [WeatherAlert],
        current: [WeatherAlert],
        locationName: String,
        additionalDetails: [String: String] = [:]
    ) -> AlertChanges {
        let changes = Self.diff(previous: previous, current: current)
        for alert in changes.new {
            let detail = [alert.headline ?? alert.description, additionalDetails[alert.id]]
                .compactMap { $0 }
                .filter { !$0.isEmpty }
                .joined(separator: " ")
            record(kind: .newAlert, locationName: locationName, title: alert.event, detail: detail)
        }
        for alert in changes.updated {
            var fields: [String] = []
            if let old = previous.first(where: { $0.id == alert.id }),
               old.headline != alert.headline {
                fields.append("The alert headline changed.")
            }
            if let old = previous.first(where: { $0.id == alert.id }),
               old.expires != alert.expires {
                fields.append("The alert expiration time changed.")
            }
            record(
                kind: .updatedAlert,
                locationName: locationName,
                title: alert.event,
                detail: fields.joined(separator: " ")
            )
        }
        for alert in changes.ended {
            record(
                kind: .alertEnded,
                locationName: locationName,
                title: alert.event,
                detail: "This alert is no longer active."
            )
        }
        return changes
    }

    func record(kind: EventKind, locationName: String, title: String, detail: String) {
        let entry = EventLogEntry(
            id: UUID(),
            date: Date(),
            locationName: locationName,
            kind: kind,
            title: title,
            detail: detail
        )
        entries.insert(entry, at: 0)
        if entries.count > Self.maximumEntries {
            entries.removeLast(entries.count - Self.maximumEntries)
        }
        save()
    }

    func clear() {
        entries = []
        save()
    }

    private func load() {
        guard let data = try? Data(contentsOf: fileURL),
              let decoded = try? JSONDecoder().decode([EventLogEntry].self, from: data) else {
            return
        }
        entries = Array(decoded.sorted { $0.date > $1.date }.prefix(Self.maximumEntries))
    }

    private func save() {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        guard let data = try? encoder.encode(entries) else { return }
        try? data.write(to: fileURL, options: .atomic)
    }
}
