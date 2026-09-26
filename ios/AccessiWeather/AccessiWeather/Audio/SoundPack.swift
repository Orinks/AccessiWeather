import Foundation

/// A sound event the app can play. Raw values match the desktop app's `pack.json` keys.
enum SoundEvent: String, CaseIterable, Identifiable {
    case dataUpdated = "data_updated"
    case fetchError = "fetch_error"
    case discussionUpdate = "discussion_update"
    case alertUpdated = "alert_updated"
    case extreme
    case severe
    case moderate
    case minor
    case unknown

    var id: String { rawValue }

    var title: String {
        switch self {
        case .dataUpdated: return "Weather refresh completed"
        case .fetchError: return "Weather refresh failed"
        case .discussionUpdate: return "Forecast discussion updated"
        case .alertUpdated: return "Weather alert updated"
        case .extreme: return "Extreme severity alert"
        case .severe: return "Severe severity alert"
        case .moderate: return "Moderate severity alert"
        case .minor: return "Minor severity alert"
        case .unknown: return "Unknown severity alert"
        }
    }

    static let appEvents: [SoundEvent] = [.dataUpdated, .fetchError, .discussionUpdate, .alertUpdated]
    static let alertEvents: [SoundEvent] = [.extreme, .severe, .moderate, .minor, .unknown]

    /// Same default as the desktop app's `DEFAULT_MUTED_SOUND_EVENTS`.
    static let defaultMuted: Set<String> = [SoundEvent.dataUpdated.rawValue]

    static func forSeverity(_ severity: String) -> SoundEvent {
        SoundEvent(rawValue: severity.lowercased()) ?? .unknown
    }
}

/// A bundled sound pack in the desktop `soundpacks/<id>/pack.json` format.
struct SoundPack: Identifiable, Hashable {
    let id: String
    let name: String
    let author: String
    let description: String
    let version: String
    let directory: URL
    let sounds: [String: String]

    private struct Manifest: Decodable {
        let name: String
        let author: String?
        let description: String?
        let version: String?
        let sounds: [String: String]
    }

    init?(directory: URL) {
        let manifestURL = directory.appendingPathComponent("pack.json")
        guard let data = try? Data(contentsOf: manifestURL),
              let manifest = try? JSONDecoder().decode(Manifest.self, from: data) else { return nil }
        id = directory.lastPathComponent
        name = manifest.name
        author = manifest.author ?? ""
        description = manifest.description ?? ""
        version = manifest.version ?? ""
        self.directory = directory
        sounds = manifest.sounds
    }

    /// Resolves the clip for an event, falling back through the desktop app's generic keys.
    func url(for event: SoundEvent) -> URL? {
        let fallbacks: [String]
        switch event {
        case .dataUpdated: fallbacks = ["success", "notify"]
        case .fetchError: fallbacks = ["error", "alert"]
        case .discussionUpdate, .alertUpdated: fallbacks = ["notify"]
        case .extreme, .severe: fallbacks = ["warning", "alert"]
        case .moderate: fallbacks = ["watch", "alert"]
        case .minor: fallbacks = ["advisory", "notify"]
        case .unknown: fallbacks = ["notify", "alert"]
        }
        for key in [event.rawValue] + fallbacks {
            if let file = sounds[key] {
                let url = directory.appendingPathComponent(file)
                if FileManager.default.fileExists(atPath: url.path) { return url }
            }
        }
        return nil
    }

    /// All packs bundled under `Resources/SoundPacks`, sorted with "default" first.
    static func bundledPacks(bundle: Bundle = .main) -> [SoundPack] {
        guard let root = bundle.url(forResource: "SoundPacks", withExtension: nil),
              let children = try? FileManager.default.contentsOfDirectory(at: root, includingPropertiesForKeys: nil) else {
            return []
        }
        return children.compactMap(SoundPack.init(directory:)).sorted {
            if $0.id == "default" { return true }
            if $1.id == "default" { return false }
            return $0.name.localizedCaseInsensitiveCompare($1.name) == .orderedAscending
        }
    }
}
