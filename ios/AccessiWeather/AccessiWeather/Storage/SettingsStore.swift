import Foundation
import SwiftUI

enum TemperatureUnit: String, CaseIterable, Identifiable {
    case fahrenheit, celsius, both
    var id: String { rawValue }
    var title: String {
        switch self {
        case .fahrenheit: return "Fahrenheit"
        case .celsius: return "Celsius"
        case .both: return "Both"
        }
    }
}

enum WindSpeedUnit: String, CaseIterable, Identifiable {
    case mph, kmh, both
    var id: String { rawValue }
    var title: String {
        switch self {
        case .mph: return "Miles per hour"
        case .kmh: return "Kilometers per hour"
        case .both: return "Both"
        }
    }
}

/// User preferences backed by UserDefaults. API keys live in `KeychainStore`, not here.
@MainActor
final class SettingsStore: ObservableObject {
    private let defaults: UserDefaults

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
        temperatureUnit = TemperatureUnit(rawValue: defaults.string(forKey: "temperatureUnit") ?? "") ?? .both
        windSpeedUnit = WindSpeedUnit(rawValue: defaults.string(forKey: "windSpeedUnit") ?? "") ?? .mph
        hourlyForecastHours = defaults.object(forKey: "hourlyForecastHours") as? Int ?? 12
        dailyForecastDays = defaults.object(forKey: "dailyForecastDays") as? Int ?? 7
        use24HourTime = defaults.bool(forKey: "use24HourTime")
        showDewpoint = defaults.object(forKey: "showDewpoint") as? Bool ?? true
        showPressure = defaults.object(forKey: "showPressure") as? Bool ?? true
        showVisibility = defaults.object(forKey: "showVisibility") as? Bool ?? true
        showUVIndex = defaults.object(forKey: "showUVIndex") as? Bool ?? true
        showAirQuality = defaults.object(forKey: "showAirQuality") as? Bool ?? true
        roundValues = defaults.object(forKey: "roundValues") as? Bool ?? true
        alertNotificationsEnabled = defaults.bool(forKey: "alertNotificationsEnabled")
        notifyExtreme = defaults.object(forKey: "notifyExtreme") as? Bool ?? true
        notifySevere = defaults.object(forKey: "notifySevere") as? Bool ?? true
        notifyModerate = defaults.object(forKey: "notifyModerate") as? Bool ?? true
        notifyMinor = defaults.bool(forKey: "notifyMinor")
        weatherSource = WeatherSource(rawValue: defaults.string(forKey: "weatherSource") ?? "") ?? .automatic
        selectedLocationID = defaults.string(forKey: "selectedLocationID").flatMap(UUID.init(uuidString:))
        soundEnabled = defaults.object(forKey: "soundEnabled") as? Bool ?? true
        soundPackID = defaults.string(forKey: "soundPackID") ?? "default"
        mutedSoundEvents = Set(defaults.stringArray(forKey: "mutedSoundEvents") ?? Array(SoundEvent.defaultMuted))
        lastRadioStationCallSign = defaults.string(forKey: "lastRadioStationCallSign")
    }

    @Published var temperatureUnit: TemperatureUnit { didSet { defaults.set(temperatureUnit.rawValue, forKey: "temperatureUnit") } }
    @Published var windSpeedUnit: WindSpeedUnit { didSet { defaults.set(windSpeedUnit.rawValue, forKey: "windSpeedUnit") } }
    @Published var hourlyForecastHours: Int { didSet { defaults.set(hourlyForecastHours, forKey: "hourlyForecastHours") } }
    @Published var dailyForecastDays: Int { didSet { defaults.set(dailyForecastDays, forKey: "dailyForecastDays") } }
    @Published var use24HourTime: Bool { didSet { defaults.set(use24HourTime, forKey: "use24HourTime") } }
    @Published var showDewpoint: Bool { didSet { defaults.set(showDewpoint, forKey: "showDewpoint") } }
    @Published var showPressure: Bool { didSet { defaults.set(showPressure, forKey: "showPressure") } }
    @Published var showVisibility: Bool { didSet { defaults.set(showVisibility, forKey: "showVisibility") } }
    @Published var showUVIndex: Bool { didSet { defaults.set(showUVIndex, forKey: "showUVIndex") } }
    @Published var showAirQuality: Bool { didSet { defaults.set(showAirQuality, forKey: "showAirQuality") } }
    @Published var roundValues: Bool { didSet { defaults.set(roundValues, forKey: "roundValues") } }
    @Published var alertNotificationsEnabled: Bool { didSet { defaults.set(alertNotificationsEnabled, forKey: "alertNotificationsEnabled") } }
    @Published var notifyExtreme: Bool { didSet { defaults.set(notifyExtreme, forKey: "notifyExtreme") } }
    @Published var notifySevere: Bool { didSet { defaults.set(notifySevere, forKey: "notifySevere") } }
    @Published var notifyModerate: Bool { didSet { defaults.set(notifyModerate, forKey: "notifyModerate") } }
    @Published var notifyMinor: Bool { didSet { defaults.set(notifyMinor, forKey: "notifyMinor") } }
    @Published var weatherSource: WeatherSource { didSet { defaults.set(weatherSource.rawValue, forKey: "weatherSource") } }
    @Published var selectedLocationID: UUID? { didSet { defaults.set(selectedLocationID?.uuidString, forKey: "selectedLocationID") } }
    @Published var soundEnabled: Bool { didSet { defaults.set(soundEnabled, forKey: "soundEnabled") } }
    @Published var soundPackID: String { didSet { defaults.set(soundPackID, forKey: "soundPackID") } }
    @Published var mutedSoundEvents: Set<String> { didSet { defaults.set(Array(mutedSoundEvents).sorted(), forKey: "mutedSoundEvents") } }
    @Published var lastRadioStationCallSign: String? { didSet { defaults.set(lastRadioStationCallSign, forKey: "lastRadioStationCallSign") } }

    func isMuted(_ event: SoundEvent) -> Bool {
        mutedSoundEvents.contains(event.rawValue)
    }

    func setMuted(_ muted: Bool, for event: SoundEvent) {
        if muted { mutedSoundEvents.insert(event.rawValue) } else { mutedSoundEvents.remove(event.rawValue) }
    }

    /// True when the alert's severity is one the user asked to be notified about.
    func wantsNotification(forSeverity severity: String) -> Bool {
        switch severity.lowercased() {
        case "extreme": return notifyExtreme
        case "severe": return notifySevere
        case "moderate": return notifyModerate
        case "minor": return notifyMinor
        default: return false
        }
    }
}
