import Foundation

/// Fetches and merges weather data. Automatic mode uses NWS inside the United States and Open-Meteo elsewhere;
/// Open-Meteo always supplies air quality, UV, sunrise and sunset because NWS does not offer them.
actor WeatherService {
    static let cacheLifetime: TimeInterval = 5 * 60

    private let nws: NWSClient
    private let openMeteo: OpenMeteoClient
    private let pirateWeather: PirateWeatherClient

    private struct CacheEntry {
        var report: WeatherReport
        var storedAt: Date
    }

    private var reportCache: [String: CacheEntry] = [:]
    private var productCache: [String: (product: NWSClient.ProductResponse?, storedAt: Date)] = [:]

    init(
        nws: NWSClient = NWSClient(),
        openMeteo: OpenMeteoClient = OpenMeteoClient(),
        pirateWeather: PirateWeatherClient = PirateWeatherClient()
    ) {
        self.nws = nws
        self.openMeteo = openMeteo
        self.pirateWeather = pirateWeather
    }

    private func cacheKey(_ location: SavedLocation, source: WeatherSource) -> String {
        "\(source.rawValue)|\(NWSClient.pointPath(latitude: location.latitude, longitude: location.longitude))"
    }

    func invalidate(location: SavedLocation) {
        for source in WeatherSource.allCases {
            reportCache[cacheKey(location, source: source)] = nil
        }
    }

    func report(
        for location: SavedLocation,
        source: WeatherSource,
        forceRefresh: Bool = false,
        pirateWeatherKey: String = ""
    ) async throws -> WeatherReport {
        let key = cacheKey(location, source: source)
        if !forceRefresh, let entry = reportCache[key], Date().timeIntervalSince(entry.storedAt) < WeatherService.cacheLifetime {
            return entry.report
        }

        let resolved: WeatherSource
        switch source {
        case .automatic:
            resolved = location.isInUnitedStates ? .nws : .openMeteo
        case .nws:
            guard location.isInUnitedStates else {
                throw WeatherError.unsupported("The National Weather Service only covers United States locations. Choose Automatic or Open-Meteo in Settings for this location.")
            }
            resolved = .nws
        case .openMeteo:
            resolved = .openMeteo
        case .pirateWeather:
            guard !pirateWeatherKey.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
                throw WeatherError.unsupported("Add a Pirate Weather API key in Settings to use Pirate Weather.")
            }
            resolved = .pirateWeather
        }

        var report: WeatherReport
        switch resolved {
        case .nws:
            report = try await fetchNWS(location: location)
        case .pirateWeather:
            let response = try await pirateWeather.forecast(
                latitude: location.latitude,
                longitude: location.longitude,
                key: pirateWeatherKey
            )
            report = PirateWeatherClient.report(from: response, location: location)
        default:
            report = try await fetchOpenMeteo(location: location)
        }

        if resolved == .nws {
            // Supplement NWS with Open-Meteo extras. Failures here are not fatal.
            if let extras = try? await openMeteo.forecast(latitude: location.latitude, longitude: location.longitude, days: 1) {
                WeatherService.applyOpenMeteoExtras(extras, to: &report)
            }
        }
        if let aq = try? await openMeteo.airQuality(latitude: location.latitude, longitude: location.longitude),
           let current = aq.current, let aqi = current.us_aqi {
            let timeZone = aq.timezone.flatMap(TimeZone.init(identifier:)) ?? report.timeZone
            let now = Date()
            var hourly: [AirQualityHour] = []
            if let responseHourly = aq.hourly {
                for index in responseHourly.time.indices {
                    guard let time = OpenMeteoClient.date(from: responseHourly.time[index], in: timeZone),
                          time.addingTimeInterval(3600) > now,
                          let hourlyAQI = responseHourly.us_aqi?[safe: index] ?? nil else {
                        continue
                    }
                    hourly.append(AirQualityHour(time: time, aqi: hourlyAQI))
                }
            }
            report.current.airQuality = AirQuality(
                aqi: aqi,
                dominantPollutant: OpenMeteoClient.dominantPollutant(current),
                pollutantLevels: AirQualityPollutantLevels(
                    pm25: current.pm2_5,
                    pm10: current.pm10,
                    ozone: current.ozone
                ),
                hourly: Array(hourly.prefix(12))
            )
        }

        reportCache[key] = CacheEntry(report: report, storedAt: Date())
        return report
    }

    func latestProduct(type: String, officeID: String) async throws -> NWSClient.ProductResponse? {
        let key = "\(type.uppercased())|\(officeID.uppercased())"
        if let cached = productCache[key], Date().timeIntervalSince(cached.storedAt) < WeatherService.cacheLifetime {
            return cached.product
        }
        let product = try await nws.latestProduct(type: type, officeID: officeID)
        productCache[key] = (product, Date())
        return product
    }

    func history(for report: WeatherReport, temperatureUnit: TemperatureUnit) async throws -> WeatherHistory {
        let response = try await openMeteo.history(
            latitude: report.location.latitude,
            longitude: report.location.longitude
        )
        guard let daily = response.daily else {
            throw WeatherError.noData("weather history")
        }
        let timeZone = TimeZone(identifier: response.timezone) ?? report.timeZone
        let todayFormatter = DateFormatter()
        todayFormatter.locale = Locale(identifier: "en_US_POSIX")
        todayFormatter.timeZone = timeZone
        todayFormatter.dateFormat = "yyyy-MM-dd"
        let today = todayFormatter.string(from: Date())
        let days = daily.time.indices.compactMap { index -> WeatherHistoryDay? in
            let dateString = daily.time[index]
            guard dateString < today,
                  let date = OpenMeteoClient.date(from: dateString, in: timeZone) else {
                return nil
            }
            return WeatherHistoryDay(
                date: date,
                highC: daily.temperature_2m_max[safe: index] ?? nil,
                lowC: daily.temperature_2m_min[safe: index] ?? nil,
                meanC: daily.temperature_2m_mean?[safe: index] ?? nil,
                condition: OpenMeteoClient.condition(forCode: daily.weather_code[safe: index] ?? nil)
            )
        }
        let calendar = Calendar(identifier: .gregorian)
        var localCalendar = calendar
        localCalendar.timeZone = timeZone
        let now = Date()
        func day(from date: Date, daysAgo: Int) -> WeatherHistoryDay? {
            guard let target = localCalendar.date(byAdding: .day, value: -daysAgo, to: localCalendar.startOfDay(for: date)) else {
                return nil
            }
            return days.first { localCalendar.isDate($0.date, inSameDayAs: target) }
        }
        return WeatherHistory(
            days: days.sorted { $0.date > $1.date },
            yesterdayComparison: WeatherHistory.comparison(
                currentTemperatureC: report.current.temperatureC,
                currentCondition: report.current.description,
                historicalDay: day(from: now, daysAgo: 1),
                daysAgo: 1,
                unit: temperatureUnit
            ),
            lastWeekComparison: WeatherHistory.comparison(
                currentTemperatureC: report.current.temperatureC,
                currentCondition: report.current.description,
                historicalDay: day(from: now, daysAgo: 7),
                daysAgo: 7,
                unit: temperatureUnit
            )
        )
    }

    // MARK: - NWS

    private func fetchNWS(location: SavedLocation) async throws -> WeatherReport {
        let point = try await nws.point(latitude: location.latitude, longitude: location.longitude)
        guard let forecastURL = point.forecast, let hourlyURL = point.forecastHourly else {
            throw WeatherError.noData("NWS forecast")
        }
        let timeZone = point.timeZone.flatMap(TimeZone.init(identifier:)) ?? .current

        async let dailyTask = nws.forecast(url: forecastURL)
        async let hourlyTask = nws.forecast(url: hourlyURL)
        async let alertsTask = nws.activeAlerts(latitude: location.latitude, longitude: location.longitude)
        async let observationTask: NWSClient.ObservationProperties? = {
            guard let stationsURL = point.observationStations else { return nil }
            let stations = try await nws.stations(url: stationsURL)
            for station in stations.prefix(3) {
                if let observation = try? await nws.latestObservation(stationID: station.stationIdentifier),
                   observation.temperature?.value != nil || observation.textDescription != nil {
                    return observation
                }
            }
            return nil
        }()

        let dailyPeriods = try await dailyTask
        let hourlyPeriods = try await hourlyTask
        let alerts = (try? await alertsTask) ?? []
        let observation = try? await observationTask

        let now = Date()
        let hourly: [HourlyPeriod] = hourlyPeriods
            .filter { $0.endTime > now }
            .map { period in
                HourlyPeriod(
                    time: period.startTime,
                    temperatureC: NWSClient.celsius(period.temperature, unit: period.temperatureUnit),
                    condition: period.shortForecast,
                    windSpeedKph: NWSClient.windSpeedKph(from: period.windSpeed),
                    windDirectionDegrees: NWSClient.degrees(fromCompass: period.windDirection),
                    precipitationChance: period.probabilityOfPrecipitation?.value.map { Int($0.rounded()) }
                )
            }

        let daily: [DailyPeriod] = dailyPeriods.map { period in
            let temperature = NWSClient.celsius(period.temperature, unit: period.temperatureUnit)
            return DailyPeriod(
                id: "nws-\(period.number)",
                name: period.name,
                date: period.startTime,
                isDaytime: period.isDaytime,
                highC: period.isDaytime ? temperature : nil,
                lowC: period.isDaytime ? nil : temperature,
                condition: period.shortForecast,
                detailedForecast: period.detailedForecast,
                windSpeedKph: NWSClient.windSpeedKph(from: period.windSpeed),
                windDirectionDegrees: NWSClient.degrees(fromCompass: period.windDirection),
                windText: [period.windDirection, period.windSpeed].compactMap { $0 }.joined(separator: " "),
                precipitationChance: period.probabilityOfPrecipitation?.value.map { Int($0.rounded()) }
            )
        }

        var current = CurrentConditions()
        if let observation {
            current.description = observation.textDescription
            current.temperatureC = NWSClient.celsius(observation.temperature)
            current.dewpointC = NWSClient.celsius(observation.dewpoint)
            current.humidityPercent = observation.relativeHumidity?.value
            current.windSpeedKph = NWSClient.kph(observation.windSpeed)
            current.windDirectionDegrees = observation.windDirection?.value
            current.pressureHpa = NWSClient.hPa(observation.barometricPressure)
            current.visibilityKm = NWSClient.km(observation.visibility)
            current.observedAt = observation.timestamp
        }
        if current.description == nil, let first = hourly.first {
            current.description = first.condition
            current.temperatureC = current.temperatureC ?? first.temperatureC
        }

        let mappedAlerts = alerts.map { alert in
            WeatherAlert(
                id: alert.id,
                event: alert.event,
                severity: alert.severity ?? "Unknown",
                urgency: alert.urgency,
                certainty: alert.certainty,
                headline: alert.headline,
                description: alert.description,
                instruction: alert.instruction,
                areaDescription: alert.areaDesc,
                sender: alert.senderName,
                effective: alert.effective,
                expires: alert.expires
            )
        }

        return WeatherReport(
            location: location,
            current: current,
            hourly: hourly,
            daily: daily,
            alerts: mappedAlerts,
            sourceDescription: "National Weather Service",
            timeZone: timeZone,
            fetchedAt: Date(),
            forecastOfficeID: point.cwa ?? point.gridId
        )
    }

    // MARK: - Open-Meteo

    private func fetchOpenMeteo(location: SavedLocation) async throws -> WeatherReport {
        let response = try await openMeteo.forecast(latitude: location.latitude, longitude: location.longitude, days: 7)
        let timeZone = TimeZone(identifier: response.timezone) ?? .current

        var current = CurrentConditions()
        if let c = response.current {
            current.description = OpenMeteoClient.condition(forCode: c.weather_code)
            current.temperatureC = c.temperature_2m
            current.dewpointC = c.dew_point_2m
            current.humidityPercent = c.relative_humidity_2m
            current.windSpeedKph = c.wind_speed_10m
            current.windDirectionDegrees = c.wind_direction_10m
            current.pressureHpa = c.surface_pressure
            current.observedAt = OpenMeteoClient.date(from: c.time, in: timeZone)
        }

        var hourly: [HourlyPeriod] = []
        let now = Date()
        if let h = response.hourly {
            for index in h.time.indices {
                guard let time = OpenMeteoClient.date(from: h.time[index], in: timeZone), time.addingTimeInterval(3600) > now else { continue }
                hourly.append(HourlyPeriod(
                    time: time,
                    temperatureC: h.temperature_2m[safe: index] ?? nil,
                    condition: OpenMeteoClient.condition(forCode: h.weather_code[safe: index] ?? nil),
                    windSpeedKph: h.wind_speed_10m?[safe: index] ?? nil,
                    windDirectionDegrees: h.wind_direction_10m?[safe: index] ?? nil,
                    precipitationChance: h.precipitation_probability?[safe: index] ?? nil,
                    uvIndex: h.uv_index?[safe: index] ?? nil
                ))
            }
        }

        var daily: [DailyPeriod] = []
        if let d = response.daily {
            let formatter = DateFormatter()
            formatter.timeZone = timeZone
            formatter.dateFormat = "EEEE"
            for index in d.time.indices {
                guard let date = OpenMeteoClient.date(from: d.time[index], in: timeZone) else { continue }
                let isToday = Calendar.current.isDate(date, inSameDayAs: now)
                let windKph = d.wind_speed_10m_max?[safe: index] ?? nil
                let windDeg = d.wind_direction_10m_dominant?[safe: index] ?? nil
                daily.append(DailyPeriod(
                    id: "om-\(d.time[index])",
                    name: isToday ? "Today" : formatter.string(from: date),
                    date: date,
                    isDaytime: true,
                    highC: d.temperature_2m_max[safe: index] ?? nil,
                    lowC: d.temperature_2m_min[safe: index] ?? nil,
                    condition: OpenMeteoClient.condition(forCode: d.weather_code[safe: index] ?? nil),
                    detailedForecast: nil,
                    windSpeedKph: windKph,
                    windDirectionDegrees: windDeg,
                    windText: nil,
                    precipitationChance: d.precipitation_probability_max?[safe: index] ?? nil
                ))
            }
        }

        var report = WeatherReport(
            location: location,
            current: current,
            hourly: hourly,
            daily: daily,
            alerts: [],
            sourceDescription: "Open-Meteo",
            timeZone: timeZone,
            fetchedAt: Date(),
            forecastOfficeID: nil
        )
        WeatherService.applyOpenMeteoExtras(response, to: &report)
        return report
    }

    /// Copies UV, visibility, sunrise and sunset from an Open-Meteo response into the report.
    private static func applyOpenMeteoExtras(_ response: OpenMeteoClient.ForecastResponse, to report: inout WeatherReport) {
        let timeZone = TimeZone(identifier: response.timezone) ?? report.timeZone
        let now = Date()
        if let h = response.hourly {
            // Pick the hourly row covering the current hour.
            var bestIndex: Int?
            for index in h.time.indices {
                guard let time = OpenMeteoClient.date(from: h.time[index], in: timeZone) else { continue }
                if time <= now { bestIndex = index } else { break }
            }
            if let index = bestIndex {
                if report.current.uvIndex == nil { report.current.uvIndex = h.uv_index?[safe: index] ?? nil }
                if report.current.visibilityKm == nil, let meters = h.visibility?[safe: index] ?? nil {
                    report.current.visibilityKm = meters / 1000
                }
            }
            for index in report.hourly.indices {
                guard let sourceIndex = h.time.indices.first(where: { sourceIndex in
                    guard let date = OpenMeteoClient.date(from: h.time[sourceIndex], in: timeZone) else { return false }
                    return abs(date.timeIntervalSince(report.hourly[index].time)) < 1800
                }) else {
                    continue
                }
                report.hourly[index].uvIndex = h.uv_index?[safe: sourceIndex] ?? nil
            }
        }
        if let d = response.daily, let sunrise = d.sunrise?.first, let sunset = d.sunset?.first {
            report.current.sunrise = OpenMeteoClient.date(from: sunrise, in: timeZone)
            report.current.sunset = OpenMeteoClient.date(from: sunset, in: timeZone)
        }
    }
}

extension Array {
    subscript(safe index: Int) -> Element? {
        indices.contains(index) ? self[index] : nil
    }
}
