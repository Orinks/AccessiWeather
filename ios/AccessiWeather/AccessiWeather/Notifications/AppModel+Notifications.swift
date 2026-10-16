import BackgroundTasks
import Foundation
import SwiftUI
import UserNotifications

enum BackgroundRefresh {
    static let taskIdentifier = "net.orinks.AccessiWeather.refresh"
    /// iOS rarely wakes apps more often than this, whatever we ask for.
    static let minimumMinutes = 15

    static func schedule(afterMinutes minutes: Int) {
        let request = BGAppRefreshTaskRequest(identifier: taskIdentifier)
        request.earliestBeginDate = Date(timeIntervalSinceNow: Double(max(minimumMinutes, minutes)) * 60)
        try? BGTaskScheduler.shared.submit(request)
    }
}

extension AppModel {
    // MARK: - Lifecycle

    /// Refreshes on the user's update interval while the app is in the foreground.
    func startAutoRefresh() {
        autoRefreshTask?.cancel()
        let interval = TimeInterval(max(5, settings.updateIntervalMinutes)) * 60
        if let report, Date().timeIntervalSince(report.fetchedAt) >= interval, !isLoading {
            Task { await refresh(announce: false) }
        }
        autoRefreshTask = Task { [weak self] in
            while !Task.isCancelled {
                let minutes = self?.settings.updateIntervalMinutes ?? 10
                try? await Task.sleep(for: .seconds(Double(max(5, minutes)) * 60))
                guard !Task.isCancelled, let self else { return }
                if !self.isLoading {
                    await self.refresh(announce: false)
                }
            }
        }
    }

    func didEnterBackground() {
        autoRefreshTask?.cancel()
        autoRefreshTask = nil
        if settings.anyNotificationsEnabled {
            BackgroundRefresh.schedule(afterMinutes: settings.updateIntervalMinutes)
        }
    }

    /// Runs when iOS wakes the app for Background App Refresh.
    func handleBackgroundRefresh() async {
        guard settings.anyNotificationsEnabled else { return }
        BackgroundRefresh.schedule(afterMinutes: settings.updateIntervalMinutes)
        _ = await checkAlerts(selectedReport: nil)
        if let location = selectedLocation {
            await checkEvents(for: location, report: nil)
        }
    }

    /// Selects the notified alert's location, refreshes if needed and asks the Alerts tab to open it.
    func openAlert(_ request: AlertOpenRequest) async {
        if selectedLocation?.id != request.locationID, let location = locationStore.location(withID: request.locationID) {
            settings.selectedLocationID = location.id
            report = nil
        }
        if report?.location.id != request.locationID || !(report?.alerts.contains { $0.id == request.alertID } ?? false) {
            await refresh(announce: false)
        }
        alertToOpen = request
    }

    // MARK: - Checks

    private func notificationsAuthorized() async -> Bool {
        let status = await UNUserNotificationCenter.current().notificationSettings().authorizationStatus
        return status == .authorized || status == .provisional || status == .ephemeral
    }

    /// Checks alerts for every saved location (reusing the selected location's fresh report) and
    /// posts notifications for new, updated and escalated alerts. Returns the selected location's
    /// notified alert IDs.
    func checkAlerts(selectedReport: WeatherReport?) async -> Set<String> {
        guard settings.alertNotificationsEnabled, await notificationsAuthorized() else { return [] }
        let service = weatherService
        let others = locationStore.locations.filter { $0.id != selectedReport?.location.id }
        var fetched: [UUID: [WeatherAlert]] = [:]
        await withTaskGroup(of: (UUID, [WeatherAlert]?).self) { group in
            for location in others {
                group.addTask { (location.id, try? await service.activeAlerts(for: location)) }
            }
            for await (id, alerts) in group {
                fetched[id] = alerts
            }
        }
        var batches: [(location: SavedLocation, alerts: [WeatherAlert])] = []
        if let selectedReport, selectedReport.alertsAreCurrent {
            batches.append((selectedReport.location, selectedReport.alerts))
        }
        for location in others {
            if let alerts = fetched[location.id] ?? nil {
                batches.append((location, alerts))
            }
        }
        let notices = notificationState.alerts.process(batches, settings: settings.alertGateSettings)
        notificationState.save(to: notificationStateURL)
        for notice in notices {
            await post(notice)
        }
        return Set(notices.filter { $0.locationID == selectedReport?.location.id }.map(\.alert.id))
    }

    /// Forecast product and precipitation event notifications for one location.
    func checkEvents(for location: SavedLocation, report: WeatherReport?) async {
        let wanted = settings.eventNotificationSettings
        let wantsProducts = wanted.discussionUpdates || wanted.hazardousWeatherOutlook || wanted.specialWeatherStatements
        let wantsMinutely = wanted.precipitationStart || wanted.precipitationStop
        guard wantsProducts || wantsMinutely, await notificationsAuthorized() else { return }
        let service = weatherService
        var state = notificationState.events[location.id] ?? NotificationEventState()
        var events: [NotificationEvent] = []

        var office = report?.forecastOfficeID
        if office == nil, wantsProducts, location.isInUnitedStates {
            office = try? await service.forecastOfficeID(for: location)
        }
        if wantsProducts, location.isInUnitedStates, let office {
            if wanted.discussionUpdates,
               let latest = try? await service.productItems(type: "AFD", officeID: office).first,
               latest.issuanceTime != state.discussionIssuance {
                let text = try? await service.product(id: latest.id).productText
                if let event = state.checkDiscussion(issuance: latest.issuanceTime, text: text, locationName: location.name, enabled: true) {
                    events.append(event)
                }
            }
            if wanted.hazardousWeatherOutlook,
               let latest = try? await service.productItems(type: "HWO", officeID: office).first,
               latest.issuanceTime != state.hwoIssuance || state.hwoHash == nil,
               let text = try? await service.product(id: latest.id).productText,
               let event = state.checkHWO(issuance: latest.issuanceTime, text: text, officeID: office, enabled: true) {
                events.append(event)
            }
            if wanted.specialWeatherStatements,
               let items = try? await service.productItems(type: "SPS", officeID: office) {
                var alerts = report?.alerts ?? []
                if report == nil {
                    alerts = (try? await service.activeAlerts(for: location)) ?? []
                }
                let covered = alerts.contains { $0.event.caseInsensitiveCompare("Special Weather Statement") == .orderedSame }
                if let event = await state.checkSPS(
                    productIDs: items.prefix(10).map(\.id),
                    coveredByAlert: covered,
                    enabled: true,
                    textFor: { id in try? await service.product(id: id).productText }
                ) {
                    events.append(event)
                }
            }
        }

        let pirateKey = KeychainStore.read(.pirateWeather)
        if wantsMinutely, !pirateKey.isEmpty {
            var points = report?.minutely
            if points == nil {
                points = (try? await service.minutely(for: location, pirateWeatherKey: pirateKey)) ?? nil
            }
            if let event = state.checkMinutely(points, locationName: location.name, settings: wanted) {
                events.append(event)
            }
        }

        notificationState.events[location.id] = state
        notificationState.save(to: notificationStateURL)
        for event in events {
            await post(event, location: location)
        }
    }

    // MARK: - Posting

    private func post(_ notice: AlertNotice) async {
        let alert = notice.alert
        let content = UNMutableNotificationContent()
        switch notice.reason {
        case .new: content.title = "\(alert.severity) alert: \(alert.event)"
        case .updated: content.title = "Updated alert: \(alert.event)"
        case .escalated: content.title = "Escalated to \(alert.severity): \(alert.event)"
        }
        content.subtitle = notice.locationName
        content.body = alert.headline ?? alert.areaDescription ?? notice.locationName
        content.threadIdentifier = notice.locationID.uuidString
        content.userInfo = [
            NotificationRouter.alertIDKey: alert.id,
            NotificationRouter.locationIDKey: notice.locationID.uuidString,
        ]
        if let name = sounds.notificationSoundName(forSeverity: alert.severity) {
            content.sound = UNNotificationSound(named: UNNotificationSoundName(name))
        } else {
            content.sound = .default
        }
        let request = UNNotificationRequest(identifier: "alert-\(alert.id)", content: content, trigger: nil)
        try? await UNUserNotificationCenter.current().add(request)
    }

    private func post(_ event: NotificationEvent, location: SavedLocation) async {
        let content = UNMutableNotificationContent()
        content.title = event.title
        content.subtitle = location.name
        content.body = event.body
        content.threadIdentifier = location.id.uuidString
        content.sound = .default
        let request = UNNotificationRequest(identifier: "\(event.kind)-\(location.id.uuidString)", content: content, trigger: nil)
        try? await UNUserNotificationCenter.current().add(request)
    }
}
