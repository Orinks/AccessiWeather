import Foundation

/// Saved locations persisted as JSON in Application Support.
@MainActor
final class LocationStore: ObservableObject {
    @Published private(set) var locations: [SavedLocation] = []

    private let fileURL: URL

    init(fileURL: URL? = nil) {
        if let fileURL {
            self.fileURL = fileURL
        } else {
            let support = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
            let directory = support.appendingPathComponent("AccessiWeather", isDirectory: true)
            try? FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
            self.fileURL = directory.appendingPathComponent("locations.json")
        }
        load()
    }

    func location(withID id: UUID?) -> SavedLocation? {
        guard let id else { return nil }
        return locations.first { $0.id == id }
    }

    func add(_ location: SavedLocation) {
        locations.append(location)
        save()
    }

    func update(_ location: SavedLocation) {
        guard let index = locations.firstIndex(where: { $0.id == location.id }) else { return }
        locations[index] = location
        save()
    }

    func remove(atOffsets offsets: IndexSet) {
        locations.remove(atOffsets: offsets)
        save()
    }

    func remove(_ location: SavedLocation) {
        locations.removeAll { $0.id == location.id }
        save()
    }

    func move(fromOffsets source: IndexSet, toOffset destination: Int) {
        locations.move(fromOffsets: source, toOffset: destination)
        save()
    }

    private func load() {
        guard let data = try? Data(contentsOf: fileURL) else { return }
        locations = (try? JSONDecoder().decode([SavedLocation].self, from: data)) ?? []
    }

    private func save() {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        guard let data = try? encoder.encode(locations) else { return }
        try? data.write(to: fileURL, options: .atomic)
    }
}
