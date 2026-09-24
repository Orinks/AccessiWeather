import Foundation

/// Keeps the NOAA Weather Radio station list current from WeatherIndex.
///
/// Order of preference: a directory downloaded within `cacheTTL`, then a fresh download,
/// then the copy cached on disk from an earlier run, then the list bundled with the app.
@MainActor
final class RadioStationDirectory: ObservableObject {
    enum Source: Equatable {
        case none
        case weatherIndex(Date)
        case cached(Date)
        case bundled

        var description: String {
            switch self {
            case .none:
                return "Loading station list…"
            case .weatherIndex(let date):
                return "Station list from WeatherIndex, updated \(Self.relative(date))."
            case .cached(let date):
                return "WeatherIndex is unreachable; using the station list saved \(Self.relative(date))."
            case .bundled:
                return "WeatherIndex is unreachable; using the built-in station list, which may be out of date."
            }
        }

        private static func relative(_ date: Date) -> String {
            let formatter = RelativeDateTimeFormatter()
            formatter.unitsStyle = .full
            return formatter.localizedString(for: date, relativeTo: Date())
        }
    }

    static let cacheTTL: TimeInterval = 30 * 60
    static let retryDelay: TimeInterval = 5 * 60

    @Published private(set) var database = RadioStationDatabase(stations: [])
    @Published private(set) var source: Source = .none
    @Published private(set) var isRefreshing = false

    private let client: WeatherIndexClient
    private let cacheURL: URL
    private let bundle: Bundle
    private var lastAttempt: Date?
    private var refreshTask: Task<Void, Never>?

    init(client: WeatherIndexClient = WeatherIndexClient(), cacheURL: URL? = nil, bundle: Bundle = .main) {
        self.client = client
        self.bundle = bundle
        if let cacheURL {
            self.cacheURL = cacheURL
        } else {
            let caches = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask).first!
            let directory = caches.appendingPathComponent("AccessiWeather", isDirectory: true)
            try? FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
            self.cacheURL = directory.appendingPathComponent("noaa_radio_stations.json")
        }
        loadCachedOrBundled()
    }

    /// Stations that currently have a live feed, hiding transmitters WeatherIndex marks out of service.
    var availableStations: [RadioStation] {
        database.stations.filter { !$0.isOutOfService }
    }

    func nearest(latitude: Double, longitude: Double, limit: Int = 8) -> [NearbyStation] {
        RadioStationDatabase(stations: availableStations).nearest(latitude: latitude, longitude: longitude, limit: limit)
    }

    func station(withCallSign callSign: String) -> RadioStation? {
        database.station(withCallSign: callSign)
    }

    /// Downloads the directory unless a recent copy is already loaded (or a download just failed).
    func refreshIfStale() async {
        if case .weatherIndex(let date) = source, Date().timeIntervalSince(date) < Self.cacheTTL { return }
        if let lastAttempt, Date().timeIntervalSince(lastAttempt) < Self.retryDelay { return }
        await refresh()
    }

    func refresh() async {
        if let refreshTask {
            await refreshTask.value
            return
        }
        let task = Task { await performRefresh() }
        refreshTask = task
        await task.value
        refreshTask = nil
    }

    private func performRefresh() async {
        isRefreshing = true
        defer { isRefreshing = false }
        lastAttempt = Date()
        do {
            let result = try await client.fetchDirectory()
            database = RadioStationDatabase(stations: result.stations)
            source = .weatherIndex(Date())
            try? result.data.write(to: cacheURL, options: .atomic)
        } catch {
            if database.stations.isEmpty {
                loadCachedOrBundled()
            }
        }
    }

    private func loadCachedOrBundled() {
        if let data = try? Data(contentsOf: cacheURL),
           let stations = try? WeatherIndexClient.parse(data), !stations.isEmpty {
            let attributes = try? FileManager.default.attributesOfItem(atPath: cacheURL.path)
            let savedAt = attributes?[.modificationDate] as? Date ?? Date()
            database = RadioStationDatabase(stations: stations)
            source = .cached(savedAt)
            return
        }
        database = RadioStationDatabase.bundled(bundle: bundle)
        source = .bundled
    }
}
