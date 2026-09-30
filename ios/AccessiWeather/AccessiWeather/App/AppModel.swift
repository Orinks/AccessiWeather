import Foundation
import SwiftUI
import UserNotifications

/// Shared app state: the selected location, its latest report, and loading/error status.
@MainActor
final class AppModel: ObservableObject {
    let settings: SettingsStore
    let locationStore: LocationStore
    let weatherService: WeatherService

    @Published private(set) var report: WeatherReport?
    @Published private(set) var isLoading = false
    @Published private(set) var errorMessage: String?
    @Published var hasOpenRouterKey = !KeychainStore.read(.openRouter).isEmpty

    private var notifiedAlertIDs: Set<String> = []

    init(settings: SettingsStore? = nil, locationStore: LocationStore? = nil, weatherService: WeatherService = WeatherService()) {
        self.settings = settings ?? SettingsStore()
        self.locationStore = locationStore ?? LocationStore()
        self.weatherService = weatherService
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
            let fresh = try await weatherService.report(for: location, source: settings.weatherSource, forceRefresh: force)
            report = fresh
            if announce {
                let summary = fresh.current.description.map { ", \($0)" } ?? ""
                AccessibilityNotification.Announcement("Weather updated for \(location.name)\(summary)").post()
            }
            await scheduleAlertNotifications(for: fresh)
        } catch {
            errorMessage = error.localizedDescription
            if announce {
                AccessibilityNotification.Announcement("Weather update failed. \(error.localizedDescription)").post()
            }
        }
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
            content.sound = .default
            let request = UNNotificationRequest(identifier: alert.id, content: content, trigger: nil)
            try? await center.add(request)
        }
    }
}
