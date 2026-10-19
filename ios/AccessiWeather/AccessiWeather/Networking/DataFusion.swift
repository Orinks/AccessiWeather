import Foundation

/// Automatic mode's fusion of NWS, Open-Meteo and Pirate Weather, after Rust `aw_core::fusion`.
/// Current conditions merge field by field in source priority; daily and hourly forecasts each come
/// from one source so period times stay consistent.
enum DataFusion {
    enum Source: String {
        case nws, openMeteo, pirateWeather
    }

    /// `SourcePriorityConfig` defaults.
    static func priority(isUS: Bool) -> [Source] {
        isUS ? [.nws, .openMeteo, .pirateWeather] : [.openMeteo, .pirateWeather]
    }

    static func merge(
        location: SavedLocation,
        nws: WeatherReport?,
        openMeteo: WeatherReport?,
        pirateWeather: WeatherReport?
    ) -> WeatherReport? {
        let isUS = location.isInUnitedStates
        let reports: [Source: WeatherReport] = [.nws: nws, .openMeteo: openMeteo, .pirateWeather: pirateWeather]
            .compactMapValues { $0 }
        let ordered = priority(isUS: isUS).compactMap { source in reports[source].map { (source, $0) } }
        guard let primary = ordered.first?.1 else { return nil }

        func first<T>(_ value: (WeatherReport) -> T?) -> T? {
            for (_, report) in ordered {
                if let found = value(report) { return found }
            }
            return nil
        }
        let windSource = ordered.first { $0.1.current.windSpeedKph != nil }?.1
        let description = first { report -> String? in
            guard let text = report.current.description?.trimmingCharacters(in: .whitespacesAndNewlines),
                  !missingConditionText.contains(text.lowercased()) else { return nil }
            return text
        }
        let current = CurrentConditions(
            description: description,
            temperatureC: first { $0.current.temperatureC },
            dewpointC: first { $0.current.dewpointC },
            humidityPercent: first { $0.current.humidityPercent },
            windSpeedKph: windSource?.current.windSpeedKph,
            windDirectionDegrees: windSource?.current.windDirectionDegrees ?? first { $0.current.windDirectionDegrees },
            pressureHpa: first { $0.current.pressureHpa },
            visibilityKm: first { $0.current.visibilityKm },
            uvIndex: first { $0.current.uvIndex },
            sunrise: first { $0.current.sunrise },
            sunset: first { $0.current.sunset },
            airQuality: first { $0.current.airQuality },
            observedAt: first { $0.current.observedAt }
        )

        let daily = ordered.first { !$0.1.daily.isEmpty }?.1
        let hourlySource = ordered.first { !$0.1.hourly.isEmpty }?.1
        var hourly = hourlySource?.hourly ?? []
        if let openMeteo, hourlySource?.sourceDescription != openMeteo.sourceDescription {
            for index in hourly.indices where hourly[index].uvIndex == nil {
                hourly[index].uvIndex = openMeteo.hourly.first {
                    abs($0.time.timeIntervalSince(hourly[index].time)) < 1800
                }?.uvIndex
            }
        }

        // NWS is authoritative for US alerts; Pirate Weather's alerts cover the rest of the world.
        let alertReport = isUS ? (nws ?? pirateWeather) : pirateWeather
        return WeatherReport(
            location: location,
            current: current,
            hourly: hourly,
            daily: daily?.daily ?? [],
            alerts: alertReport?.alerts ?? [],
            sourceDescription: "Automatic: " + ordered.map(\.1.sourceDescription).joined(separator: ", "),
            timeZone: (hourlySource ?? primary).timeZone,
            fetchedAt: Date(),
            forecastOfficeID: nws?.forecastOfficeID,
            observationStationID: nws?.observationStationID,
            alertsAreCurrent: alertReport?.alertsAreCurrent ?? false,
            minutely: pirateWeather?.minutely,
            marine: nws?.marine
        )
    }

    static let missingConditionText: Set<String> = [
        "", "n/a", "na", "none", "not available", "null", "unavailable", "unknown", "--",
    ]
}
