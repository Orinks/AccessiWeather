import Foundation
import UserNotifications

struct AlertOpenRequest: Equatable {
    var alertID: String
    var locationID: UUID
}

/// The notification center delegate. Shows banners while the app is open and turns a tapped
/// alert notification into an `AlertOpenRequest` that the root view routes to the alert details.
/// Installed at launch so taps that cold-start the app aren't lost.
@MainActor
final class NotificationRouter: NSObject, ObservableObject, UNUserNotificationCenterDelegate {
    static let shared = NotificationRouter()

    static let alertIDKey = "alertID"
    static let locationIDKey = "locationID"

    @Published var pendingAlert: AlertOpenRequest?

    func install() {
        UNUserNotificationCenter.current().delegate = self
    }

    nonisolated func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification
    ) async -> UNNotificationPresentationOptions {
        [.banner, .list, .sound]
    }

    nonisolated func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        didReceive response: UNNotificationResponse
    ) async {
        let info = response.notification.request.content.userInfo
        guard response.actionIdentifier == UNNotificationDefaultActionIdentifier,
              let alertID = info[Self.alertIDKey] as? String,
              let locationID = (info[Self.locationIDKey] as? String).flatMap(UUID.init(uuidString:)) else { return }
        await MainActor.run {
            pendingAlert = AlertOpenRequest(alertID: alertID, locationID: locationID)
        }
    }
}

/// Alert gate and per-location event baselines, saved as JSON in Application Support so
/// relaunches and background wake-ups don't repeat notifications.
struct NotificationState: Codable, Equatable {
    var alerts = AlertNotificationGate()
    var events: [UUID: NotificationEventState] = [:]

    static var defaultURL: URL {
        let support = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
        return support.appendingPathComponent("AccessiWeather", isDirectory: true)
            .appendingPathComponent("notification_state.json")
    }

    static func load(from url: URL = defaultURL) -> NotificationState {
        guard let data = try? Data(contentsOf: url),
              let state = try? JSONDecoder().decode(NotificationState.self, from: data) else { return NotificationState() }
        return state
    }

    func save(to url: URL = defaultURL) {
        try? FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        guard let data = try? JSONEncoder().encode(self) else { return }
        try? data.write(to: url, options: [.atomic, .completeFileProtectionUntilFirstUserAuthentication])
    }
}
