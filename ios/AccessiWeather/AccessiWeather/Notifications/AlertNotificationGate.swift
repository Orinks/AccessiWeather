import CryptoKit
import Foundation

/// Why an alert is being notified, mirroring the desktop alert manager's reasons.
enum AlertNoticeReason: String, Codable, Equatable {
    case new
    case updated
    case escalated
}

struct AlertNotice: Equatable {
    var alert: WeatherAlert
    var locationID: UUID
    var locationName: String
    var reason: AlertNoticeReason
}

struct AlertGateSettings: Equatable {
    var notificationsEnabled: Bool
    var notifiedSeverities: Set<String>
    var globalCooldownMinutes: Double = 5
    var maxNotificationsPerHour: Double = 10
}

/// Decides which alerts to notify about, ported from the desktop `AlertManager.process_alerts`:
/// notify on a new alert, on changed content (headline, description, severity, urgency,
/// instruction), and call it an escalation when severity rises above anything seen for that alert.
/// A token bucket caps notifications per hour and a global cooldown spaces out refresh batches.
/// Blocked alerts are not recorded, so the next check notifies them. State is Codable so it
/// survives relaunches and background wake-ups.
struct AlertNotificationGate: Codable, Equatable {
    static let retentionDays: Double = 7
    static let historyLimit = 15

    struct AlertState: Codable, Equatable {
        var firstSeen: Date
        var lastNotified: Date?
        var notificationCount: Int
        var hashes: [String]
        var maxSeverityPriority: Int
    }

    var alerts: [String: AlertState] = [:]
    var lastGlobalNotification: Date?
    var rateLimitTokens: Double?
    var rateLimitLastRefill: Date?

    static func severityPriority(_ severity: String) -> Int {
        switch severity.lowercased() {
        case "minor": return 2
        case "moderate": return 3
        case "severe": return 4
        case "extreme": return 5
        default: return 1
        }
    }

    static func contentHash(_ alert: WeatherAlert) -> String {
        let parts = [
            alert.event,
            alert.description ?? "",
            alert.severity,
            alert.urgency ?? "",
            alert.headline ?? "",
            alert.instruction ?? "",
        ]
        let digest = SHA256.hash(data: Data(parts.joined(separator: "|").utf8))
        return digest.map { String(format: "%02x", $0) }.joined()
    }

    private mutating func takeToken(_ settings: AlertGateSettings, now: Date) -> Bool {
        let capacity = max(1, settings.maxNotificationsPerHour)
        let last = rateLimitLastRefill ?? now
        let elapsed = max(0, now.timeIntervalSince(last))
        var tokens = min(capacity, (rateLimitTokens ?? capacity) + elapsed * capacity / 3600)
        rateLimitLastRefill = now
        guard tokens >= 1 else {
            rateLimitTokens = tokens
            return false
        }
        tokens -= 1
        rateLimitTokens = tokens
        return true
    }

    private func globalCooldownActive(_ settings: AlertGateSettings, now: Date) -> Bool {
        guard let last = lastGlobalNotification else { return false }
        return now.timeIntervalSince(last) <= settings.globalCooldownMinutes * 60
    }

    private mutating func canNotifyNow(_ settings: AlertGateSettings, now: Date) -> Bool {
        takeToken(settings, now: now) && !globalCooldownActive(settings, now: now)
    }

    /// Returns the alerts to notify about across every checked location, and records them.
    mutating func process(
        _ batches: [(location: SavedLocation, alerts: [WeatherAlert])],
        settings: AlertGateSettings,
        now: Date = Date()
    ) -> [AlertNotice] {
        var notices: [AlertNotice] = []
        var seenThisBatch: Set<String> = []
        for batch in batches {
            for alert in batch.alerts {
                guard settings.notificationsEnabled,
                      settings.notifiedSeverities.contains(alert.severity.lowercased()),
                      alert.expires.map({ $0 >= now }) ?? true,
                      seenThisBatch.insert(alert.id).inserted else { continue }
                let hash = Self.contentHash(alert)
                let priority = Self.severityPriority(alert.severity)
                var reason: AlertNoticeReason
                if var state = alerts[alert.id] {
                    guard state.hashes.last != hash else { continue }
                    guard canNotifyNow(settings, now: now) else { continue }
                    reason = priority > state.maxSeverityPriority ? .escalated : .updated
                    state.hashes.append(hash)
                    if state.hashes.count > Self.historyLimit {
                        state.hashes.removeFirst(state.hashes.count - Self.historyLimit)
                    }
                    state.maxSeverityPriority = max(state.maxSeverityPriority, priority)
                    alerts[alert.id] = state
                } else {
                    guard canNotifyNow(settings, now: now) else { continue }
                    reason = .new
                    alerts[alert.id] = AlertState(
                        firstSeen: now,
                        lastNotified: nil,
                        notificationCount: 0,
                        hashes: [hash],
                        maxSeverityPriority: priority
                    )
                }
                alerts[alert.id]?.lastNotified = now
                alerts[alert.id]?.notificationCount += 1
                notices.append(AlertNotice(
                    alert: alert,
                    locationID: batch.location.id,
                    locationName: batch.location.name,
                    reason: reason
                ))
            }
        }
        if !notices.isEmpty {
            lastGlobalNotification = now
        }
        let cutoff = now.addingTimeInterval(-Self.retentionDays * 86_400)
        alerts = alerts.filter { $0.value.firstSeen >= cutoff }
        return notices
    }
}
