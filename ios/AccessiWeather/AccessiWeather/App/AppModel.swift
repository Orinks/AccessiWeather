import Foundation
import Combine
import SwiftUI
import UserNotifications

/// Shared app state: the selected location, its latest report, and loading/error status.
@MainActor
final class AppModel: ObservableObject {
    let settings: SettingsStore
    let locationStore: LocationStore
    let weatherService: WeatherService
    let sounds: SoundManager
    let radio: RadioPlayer
    let radioStations: RadioStationDirectory
    let eventLog: EventLog

    @Published private(set) var report: WeatherReport?
    @Published private(set) var isLoading = false
    @Published private(set) var errorMessage: String?
    @Published var hasOpenRouterKey = !KeychainStore.read(.openRouter).isEmpty

    private var notifiedAlertIDs: Set<String> = []
    private var previousAlertsByLocation: [UUID: [String: WeatherAlert]] = [:]
    private var autoTunePlaybackOwnership: RadioAutoTunePlaybackOwnership?
    private var autoTuneStopTask: Task<Void, Never>?
    private var radioGenerationCancellable: AnyCancellable?
    private var radioAutoTuneSettingCancellable: AnyCancellable?

    init(
        settings: SettingsStore? = nil,
        locationStore: LocationStore? = nil,
        weatherService: WeatherService = WeatherService(),
        eventLog: EventLog? = nil
    ) {
        self.settings = settings ?? SettingsStore()
        self.locationStore = locationStore ?? LocationStore()
        self.weatherService = weatherService
        sounds = SoundManager(settings: self.settings)
        radio = RadioPlayer()
        radioStations = RadioStationDirectory()
        self.eventLog = eventLog ?? EventLog()
        radioGenerationCancellable = radio.$playbackGeneration
            .dropFirst()
            .sink { [weak self] generation in
                Task { @MainActor in self?.radioPlaybackGenerationDidChange(generation) }
            }
        radioAutoTuneSettingCancellable = self.settings.$radioAutoTuneEnabled
            .dropFirst()
            .sink { [weak self] enabled in
                guard !enabled else { return }
                Task { @MainActor in self?.stopAutoTunedPlaybackIfOwned() }
            }
    }

    var selectedLocation: SavedLocation? {
        locationStore.location(withID: settings.selectedLocationID) ?? locationStore.locations.first
    }

    func select(_ location: SavedLocation) {
        settings.selectedLocationID = location.id
        report = nil
        errorMessage = nil
        Task { await refresh() }
    }

    func addLocation(_ location: SavedLocation) {
        locationStore.add(location)
        if locationStore.locations.count == 1 || settings.selectedLocationID == nil {
            select(location)
        }
    }

    func removeLocations(atOffsets offsets: IndexSet) {
        let removedIDs = offsets.map { locationStore.locations[$0].id }
        locationStore.remove(atOffsets: offsets)
        if let selected = settings.selectedLocationID, removedIDs.contains(selected) {
            settings.selectedLocationID = locationStore.locations.first?.id
            report = nil
            if selectedLocation != nil { Task { await refresh() } }
        }
    }

    func refreshKeyStatus() {
        hasOpenRouterKey = !KeychainStore.read(.openRouter).isEmpty
    }

    func recordDiscussionIssuance(_ issuanceTime: Date, officeID: String, locationName: String) {
        let key = "lastAFDIssuanceTime.\(officeID.uppercased())"
        let defaults = UserDefaults.standard
        if let previous = defaults.object(forKey: key) as? Date, previous != issuanceTime {
            eventLog.record(
                kind: .discussionUpdated,
                locationName: locationName,
                title: "Area Forecast Discussion",
                detail: "A new discussion was issued by the \(officeID) office."
            )
        }
        defaults.set(issuanceTime, forKey: key)
    }

    /// Fetches weather for the selected location. Announces completion to VoiceOver.
    func refresh(force: Bool = false, announce: Bool = true) async {
        guard let location = selectedLocation else {
            report = nil
            return
        }
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        do {
            let fresh = try await weatherService.report(
                for: location,
                source: settings.weatherSource,
                forceRefresh: force,
                pirateWeatherKey: KeychainStore.read(.pirateWeather)
            )
            if fresh.alertsAreCurrent,
               let ownership = autoTunePlaybackOwnership,
               ownership.locationID == location.id,
               !fresh.alerts.contains(where: { $0.id == ownership.alertID }) {
                stopAutoTunedPlaybackIfOwned()
            }
            let hadReport = report?.location.id == location.id
            let previousAlerts = previousAlertsByLocation[location.id].map { Array($0.values) }
                ?? (hadReport ? report?.alerts ?? [] : [])
            let changes = fresh.alertsAreCurrent
                ? EventLog.diff(previous: previousAlerts, current: fresh.alerts)
                : AlertChanges(new: [], updated: [], ended: [])
            let newAlertIDs = Set(changes.new.map(\.id))
            var alertToTune: WeatherAlert?
            var stationToTune: RadioStation?
            let tunableAlerts = changes.new.filter {
                ["extreme", "severe"].contains($0.severity.lowercased()) && $0.wouldWakeSAMERadio
            }
            if hadReport, settings.radioAutoTuneEnabled, !radio.isPlaying, !tunableAlerts.isEmpty {
                let sameCountyCodes = Array(Set(tunableAlerts.flatMap(\.sameCountyCodes))).sorted()
                if let coverage = await radioStations.nearestCoveringStation(
                    latitude: location.latitude,
                    longitude: location.longitude,
                    sameCountyCodes: sameCountyCodes
                ) {
                    alertToTune = tunableAlerts.first {
                        !Set($0.sameCountyCodes).isDisjoint(with: coverage.matchedCountyCodes)
                    }
                    if alertToTune != nil {
                        stationToTune = coverage.station
                    }
                }
            }
            var additionalDetails: [String: String] = [:]
            if let alertToTune, let stationToTune {
                additionalDetails[alertToTune.id] = "NOAA Weather Radio tuned to \(stationToTune.callSign)."
            }
            if fresh.alertsAreCurrent {
                _ = eventLog.recordAlertChanges(
                    previous: previousAlerts,
                    current: fresh.alerts,
                    locationName: location.name,
                    additionalDetails: additionalDetails
                )
                previousAlertsByLocation[location.id] = Dictionary(
                    uniqueKeysWithValues: fresh.alerts.map { ($0.id, $0) }
                )
            }
            report = fresh
            if hadReport, let strongest = fresh.alerts.first(where: { newAlertIDs.contains($0.id) }) {
                sounds.play(SoundEvent.forSeverity(strongest.severity))
            } else {
                sounds.play(.dataUpdated)
            }
            if let alertToTune, let stationToTune {
                radio.play(stationToTune)
                startAutoTuneStopTimer(
                    alertID: alertToTune.id,
                    locationID: location.id,
                    durationMinutes: settings.radioAutoTuneDurationMinutes
                )
                AccessibilityNotification.Announcement(
                    "Tuning NOAA Weather Radio \(stationToTune.callSign) for \(alertToTune.event)"
                ).post()
            }
            if announce {
                let summary = fresh.current.description.map { ", \($0)" } ?? ""
                AccessibilityNotification.Announcement("Weather updated for \(location.name)\(summary)").post()
            }
            await scheduleAlertNotifications(for: fresh)
        } catch {
            errorMessage = error.localizedDescription
            sounds.play(.fetchError)
            if announce {
                AccessibilityNotification.Announcement("Weather update failed. \(error.localizedDescription)").post()
            }
        }
    }

    private func startAutoTuneStopTimer(alertID: String, locationID: UUID, durationMinutes: Int) {
        autoTuneStopTask?.cancel()
        let ownership = RadioAutoTunePlaybackOwnership(
            generation: radio.playbackGeneration,
            alertID: alertID,
            locationID: locationID
        )
        autoTunePlaybackOwnership = ownership
        autoTuneStopTask = Task { [weak self] in
            do {
                try await Task.sleep(nanoseconds: UInt64(durationMinutes) * 60 * 1_000_000_000)
            } catch {
                return
            }
            guard let self, self.autoTunePlaybackOwnership == ownership else { return }
            self.stopAutoTunedPlaybackIfOwned()
        }
    }

    private func stopAutoTunedPlaybackIfOwned() {
        guard let ownership = autoTunePlaybackOwnership else {
            autoTuneStopTask?.cancel()
            autoTuneStopTask = nil
            return
        }
        autoTuneStopTask?.cancel()
        autoTuneStopTask = nil
        autoTunePlaybackOwnership = nil
        if ownership.ownsPlayback(generation: radio.playbackGeneration) {
            radio.stop()
        }
    }

    private func radioPlaybackGenerationDidChange(_ generation: Int) {
        guard let ownership = autoTunePlaybackOwnership,
              !ownership.ownsPlayback(generation: generation) else {
            return
        }
        autoTuneStopTask?.cancel()
        autoTuneStopTask = nil
        autoTunePlaybackOwnership = nil
    }

    // MARK: - Notifications

    func requestNotificationPermission() async -> Bool {
        let center = UNUserNotificationCenter.current()
        do {
            return try await center.requestAuthorization(options: [.alert, .sound, .badge])
        } catch {
            return false
        }
    }

    private func scheduleAlertNotifications(for report: WeatherReport) async {
        guard settings.alertNotificationsEnabled else { return }
        let center = UNUserNotificationCenter.current()
        let status = await center.notificationSettings().authorizationStatus
        guard status == .authorized || status == .provisional else { return }
        for alert in report.alerts where !notifiedAlertIDs.contains(alert.id) && settings.wantsNotification(forSeverity: alert.severity) {
            notifiedAlertIDs.insert(alert.id)
            let content = UNMutableNotificationContent()
            content.title = "\(alert.severity) alert: \(alert.event)"
            content.body = alert.headline ?? alert.areaDescription ?? report.location.name
            if let name = sounds.notificationSoundName(forSeverity: alert.severity) {
                content.sound = UNNotificationSound(named: UNNotificationSoundName(name))
            } else {
                content.sound = .default
            }
            let request = UNNotificationRequest(identifier: alert.id, content: content, trigger: nil)
            try? await center.add(request)
        }
    }
}

struct RadioAutoTunePlaybackOwnership: Equatable {
    let generation: Int
    let alertID: String
    let locationID: UUID

    func ownsPlayback(generation currentGeneration: Int) -> Bool {
        generation == currentGeneration
    }
}
