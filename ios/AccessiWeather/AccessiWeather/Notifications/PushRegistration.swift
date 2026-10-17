import CryptoKit
import Foundation
import UIKit

/// Registers this device with the AccessiWeather push server, which pushes NWS alerts while the app is closed.
@MainActor
final class PushRegistration {
    static let shared = PushRegistration()
    static let tokenKey = "pushDeviceToken"
    static let signatureKey = "pushRegistrationSignature"
    static let syncedAtKey = "pushRegistrationSyncedAt"
    static let maxLocations = 20

    private let defaults: UserDefaults
    var onTokenChange: (() -> Void)?

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
    }

    var serverURL: URL? {
        guard let value = Bundle.main.object(forInfoDictionaryKey: "AWPushServerURL") as? String,
              !value.isEmpty else { return nil }
        return URL(string: value)
    }

    var deviceToken: String? { defaults.string(forKey: Self.tokenKey) }

    /// True while the server holds this device's locations; the app then leaves alert and event checks to it.
    var isActive: Bool { serverURL != nil && defaults.string(forKey: Self.signatureKey) != nil }

    static var environment: String {
        #if DEBUG
        "sandbox"
        #else
        "production"
        #endif
    }

    func requestToken() {
        guard serverURL != nil else { return }
        UIApplication.shared.registerForRemoteNotifications()
    }

    func didReceive(token: Data) {
        let hex = token.map { String(format: "%02x", $0) }.joined()
        guard hex != deviceToken else { return }
        defaults.set(hex, forKey: Self.tokenKey)
        defaults.removeObject(forKey: Self.signatureKey)
        onTokenChange?()
    }

    static func body(
        token: String,
        enabled: Bool,
        severities: [String],
        notifyUnknown: Bool,
        events: EventNotificationSettings,
        pirateWeatherKey: String,
        locations: [SavedLocation]
    ) -> [String: Any] {
        [
            "token": token,
            "environment": environment,
            "enabled": enabled,
            "severities": severities,
            "notifyUnknown": notifyUnknown,
            "events": [
                "discussion": events.discussionUpdates,
                "hwo": events.hazardousWeatherOutlook,
                "sps": events.specialWeatherStatements,
                "precip_start": events.precipitationStart,
                "precip_stop": events.precipitationStop,
            ],
            "pirateWeatherKey": pirateWeatherKey.trimmingCharacters(in: .whitespacesAndNewlines),
            "locations": locations.prefix(maxLocations).map {
                [
                    "id": $0.id.uuidString,
                    "name": $0.name,
                    "latitude": $0.latitude,
                    "longitude": $0.longitude,
                    "current": $0.isCurrentLocation,
                ] as [String: Any]
            },
        ]
    }

    /// Sends alert settings and locations when they changed, or once a day so the server keeps the device.
    func sync(
        enabled: Bool,
        severities: [String],
        notifyUnknown: Bool,
        events: EventNotificationSettings,
        pirateWeatherKey: String,
        locations: [SavedLocation]
    ) async {
        guard let serverURL, let token = deviceToken else { return }
        let body = Self.body(
            token: token, enabled: enabled, severities: severities, notifyUnknown: notifyUnknown,
            events: events, pirateWeatherKey: pirateWeatherKey, locations: locations
        )
        guard let data = try? JSONSerialization.data(withJSONObject: body, options: .sortedKeys) else { return }
        let signature = SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
        let syncedAt = defaults.object(forKey: Self.syncedAtKey) as? Date ?? .distantPast
        let registers = enabled && !((body["locations"] as? [Any])?.isEmpty ?? true)
        if registers, defaults.string(forKey: Self.signatureKey) == signature, Date().timeIntervalSince(syncedAt) < 86_400 { return }
        if !registers, defaults.string(forKey: Self.signatureKey) == nil, defaults.object(forKey: Self.syncedAtKey) != nil { return }

        var request = URLRequest(url: serverURL.appendingPathComponent("v1/devices"), timeoutInterval: 20)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = data
        guard let (_, response) = try? await URLSession.shared.data(for: request),
              (response as? HTTPURLResponse)?.statusCode == 200 else { return }
        defaults.set(Date(), forKey: Self.syncedAtKey)
        if registers {
            defaults.set(signature, forKey: Self.signatureKey)
        } else {
            defaults.removeObject(forKey: Self.signatureKey)
        }
    }
}

final class AppDelegate: NSObject, UIApplicationDelegate {
    func application(
        _ application: UIApplication,
        didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil
    ) -> Bool {
        // iOS relaunches the app in the background after significant moves; the tracker must be running to get them.
        AppModel.shared.startFollowingCurrentLocation()
        return true
    }

    func application(_ application: UIApplication, didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data) {
        Task { @MainActor in PushRegistration.shared.didReceive(token: deviceToken) }
    }

    func application(_ application: UIApplication, didFailToRegisterForRemoteNotificationsWithError error: Error) {}
}
