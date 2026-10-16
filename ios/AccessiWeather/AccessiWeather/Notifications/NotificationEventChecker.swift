import CryptoKit
import Foundation

struct NotificationEvent: Equatable {
    var kind: String
    var title: String
    var body: String
}

struct EventNotificationSettings: Equatable {
    var discussionUpdates: Bool
    var hazardousWeatherOutlook: Bool
    var specialWeatherStatements: Bool
    var precipitationStart: Bool
    var precipitationStop: Bool
}

/// Text product and minute-by-minute precipitation change detection, ported from the desktop
/// `NotificationEventManager`. Every check stores a baseline the first time it sees a value and
/// never notifies on that first sighting.
struct NotificationEventState: Codable, Equatable {
    var discussionIssuance: Date?
    var discussionText: String?
    var hwoIssuance: Date?
    var hwoHash: String?
    var hwoText: String?
    var spsProductIDs: [String]?
    var minutelySignature: String?
    var lastHWONotified: Date?
    var lastSPSNotified: Date?

    static let productRateLimit: TimeInterval = 30 * 60
    static let transitionLeadMinutes = 10
    static let wetIntensityThreshold = 0.01

    mutating func checkDiscussion(issuance: Date?, text: String?, locationName: String, enabled: Bool) -> NotificationEvent? {
        guard let issuance else { return nil }
        guard let last = discussionIssuance else {
            discussionIssuance = issuance
            discussionText = text
            return nil
        }
        guard issuance > last else {
            discussionText = text
            return nil
        }
        let summary = Self.summarizeChange(previous: discussionText, current: text)
        discussionIssuance = issuance
        discussionText = text
        guard enabled else { return nil }
        if summary == nil, Self.isNoChangeSummary(Self.section(text ?? "", start: ".WHAT HAS CHANGED")) {
            return nil
        }
        var body = "The Area Forecast Discussion for \(locationName) was updated by the National Weather Service."
        if let summary, !summary.isEmpty { body += " \(summary)" }
        return NotificationEvent(kind: "discussion_update", title: "Forecast Discussion Updated", body: body)
    }

    mutating func checkHWO(issuance: Date?, text: String, officeID: String, enabled: Bool, now: Date = Date()) -> NotificationEvent? {
        let hash = Self.sha256(text.trimmingCharacters(in: .whitespacesAndNewlines))
        guard hwoIssuance != nil || hwoHash != nil else {
            hwoIssuance = issuance
            hwoHash = hash
            hwoText = text
            return nil
        }
        if hwoIssuance == issuance && hwoHash == hash { return nil }
        let previous = hwoText
        hwoIssuance = issuance
        hwoHash = hash
        hwoText = text
        guard enabled, lastHWONotified.map({ now.timeIntervalSince($0) >= Self.productRateLimit }) ?? true else { return nil }
        lastHWONotified = now
        let summary = Self.summarizeChange(previous: previous, current: text)?.trimmingCharacters(in: .whitespaces)
        let body = (summary?.count ?? 0) > 20
            ? summary!
            : "Hazardous Weather Outlook updated for \(officeID). Open Forecaster Notes to read it."
        return NotificationEvent(kind: "hwo_update", title: "Hazardous Weather Outlook Updated", body: body)
    }

    /// `productIDs` are the office's current SPS product IDs, newest first. `textFor` loads one.
    mutating func checkSPS(
        productIDs: [String],
        coveredByAlert: Bool,
        enabled: Bool,
        now: Date = Date(),
        textFor: (String) async -> String?
    ) async -> NotificationEvent? {
        guard let known = spsProductIDs else {
            spsProductIDs = productIDs
            return nil
        }
        let current = Set(productIDs)
        let kept = known.filter { current.contains($0) }
        let fresh = productIDs.filter { !kept.contains($0) }
        spsProductIDs = kept + fresh
        guard let newest = fresh.first, enabled, !coveredByAlert,
              lastSPSNotified.map({ now.timeIntervalSince($0) >= Self.productRateLimit }) ?? true,
              let text = await textFor(newest) else { return nil }
        lastSPSNotified = now
        return NotificationEvent(kind: "sps_issued", title: "Special Weather Statement", body: Self.spsBody(text))
    }

    mutating func checkMinutely(_ points: [MinutelyPoint]?, locationName: String, settings: EventNotificationSettings, now: Date = Date()) -> NotificationEvent? {
        guard let points = points?.filter({ $0.time.addingTimeInterval(60) > now }), let first = points.first else { return nil }
        let wetNow = Self.isWet(first)
        let changeIndex = points.firstIndex { Self.isWet($0) != wetNow }
        guard let changeIndex else {
            minutelySignature = "none"
            return nil
        }
        let change = points[changeIndex]
        let starting = !wetNow
        let type = starting ? "starting" : "stopping"
        let precipType = (starting ? change : first).precipitationType
        let signature = "\(type):\(precipType ?? "")"
        let minutes = max(1, Int((change.time.timeIntervalSince(now) / 60).rounded()))
        if minutes > Self.transitionLeadMinutes { return nil }
        guard let last = minutelySignature else {
            minutelySignature = signature
            return nil
        }
        guard last != signature else { return nil }
        minutelySignature = signature
        guard starting ? settings.precipitationStart : settings.precipitationStop else { return nil }
        let unit = minutes == 1 ? "minute" : "minutes"
        let title = "\(Self.precipitationLabel(precipType)) \(type) in \(minutes) \(unit)"
        return NotificationEvent(kind: starting ? "minutely_precipitation_start" : "minutely_precipitation_stop", title: title, body: "\(title) for \(locationName).")
    }

    // MARK: - Helpers

    static func isWet(_ point: MinutelyPoint) -> Bool {
        if let intensity = point.precipitationIntensity { return intensity >= wetIntensityThreshold }
        return (point.precipitationProbability ?? 0) >= 0.5
    }

    static func precipitationLabel(_ type: String?) -> String {
        switch type?.lowercased() {
        case "rain": return "Rain"
        case "snow": return "Snow"
        case "sleet": return "Sleet"
        case "hail": return "Hail"
        default: return "Precipitation"
        }
    }

    static func sha256(_ text: String) -> String {
        SHA256.hash(data: Data(text.utf8)).map { String(format: "%02x", $0) }.joined()
    }

    static func section(_ text: String, start: String) -> String? {
        var inSection = false
        var body: [String] = []
        for line in text.components(separatedBy: .newlines) {
            let stripped = line.trimmingCharacters(in: .whitespaces)
            if !inSection {
                if stripped.uppercased().hasPrefix(start.uppercased()) { inSection = true }
                continue
            }
            if stripped.hasPrefix(".") || stripped.hasPrefix("&&") { break }
            if !stripped.isEmpty { body.append(stripped) }
        }
        guard inSection, !body.isEmpty else { return nil }
        return body.joined(separator: " ")
    }

    static func normalized(_ text: String?) -> String {
        (text ?? "").split(whereSeparator: \.isWhitespace).joined(separator: " ")
            .lowercased().trimmingCharacters(in: CharacterSet(charactersIn: " .!"))
    }

    static func isNoChangeSummary(_ text: String?) -> Bool {
        [
            "no change", "no changes", "no significant change", "no significant changes",
            "no significant changes made to forecast", "no significant changes made to the forecast",
        ].contains(normalized(text))
    }

    static func truncated(_ text: String, _ limit: Int = 300) -> String {
        text.count > limit ? String(text.prefix(limit)) : text
    }

    /// `summarize_discussion_change`: the "What has changed" section, else changed key messages,
    /// else the first line that wasn't in the previous text.
    static func summarizeChange(previous: String?, current: String?) -> String? {
        guard let current, !current.isEmpty else { return nil }
        let whatChanged = section(current, start: ".WHAT HAS CHANGED")
        let noChanges = isNoChangeSummary(whatChanged)
        if let whatChanged, !noChanges { return truncated(whatChanged) }
        if let keyMessages = section(current, start: ".KEY MESSAGES") {
            let previousMessages = section(previous ?? "", start: ".KEY MESSAGES")
            if previousMessages.map({ normalized($0) != normalized(keyMessages) }) ?? true {
                return truncated(keyMessages)
            }
            if noChanges { return nil }
        }
        if noChanges { return nil }
        let previousLines = Set((previous ?? "").components(separatedBy: .newlines)
            .map { $0.trimmingCharacters(in: .whitespaces) }
            .filter { !$0.isEmpty && !$0.hasPrefix("$") })
        return current.components(separatedBy: .newlines)
            .map { $0.trimmingCharacters(in: .whitespaces) }
            .first { !$0.isEmpty && !$0.hasPrefix("$") && !previousLines.contains($0) }
            .map { truncated($0) }
    }

    /// The statement's first prose paragraph after the header block, at most 160 characters.
    static func spsBody(_ text: String) -> String {
        let paragraphs = text.components(separatedBy: "\n\n")
            .map { $0.split(whereSeparator: \.isNewline).joined(separator: " ").trimmingCharacters(in: .whitespaces) }
            .filter { paragraph in
                let letters = paragraph.filter(\.isLetter)
                return letters.count > 40 && letters.contains(where: \.isLowercase)
            }
        let body = paragraphs.first ?? "A Special Weather Statement was issued. Open Forecaster Notes to read it."
        return body.count > 160 ? String(body.prefix(157)) + "..." : body
    }
}
