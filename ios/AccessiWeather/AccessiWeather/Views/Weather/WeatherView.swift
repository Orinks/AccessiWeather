import SwiftUI

struct WeatherView: View {
    @EnvironmentObject private var model: AppModel
    @EnvironmentObject private var settings: SettingsStore
    @EnvironmentObject private var locationStore: LocationStore
    @State private var showRadio = false

    var body: some View {
        NavigationStack {
            Group {
                if let location = model.selectedLocation {
                    weatherList(for: location)
                } else {
                    EmptyStateView(
                        title: "No Locations Yet",
                        systemImage: "mappin.slash",
                        description: "Add a location on the Locations tab to see its weather."
                    )
                }
            }
            .navigationTitle(model.selectedLocation?.name ?? "Weather")
            .navigationBarTitleDisplayMode(.inline)
            .navigationDestination(isPresented: $showRadio) {
                RadioView(radio: model.radio)
            }
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    locationMenu
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        showRadio = true
                    } label: {
                        Label("NOAA Weather Radio", systemImage: "radio")
                    }
                    .accessibilityHint("Opens nearby NOAA Weather Radio stations")
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        Task { await model.refresh(force: true) }
                    } label: {
                        Label("Refresh", systemImage: "arrow.clockwise")
                    }
                    .disabled(model.isLoading || model.selectedLocation == nil)
                    .accessibilityHint("Fetches the latest weather for the selected location")
                }
            }
        }
    }

    private var locationMenu: some View {
        Menu {
            ForEach(locationStore.locations) { location in
                Button {
                    model.select(location)
                } label: {
                    if location.id == model.selectedLocation?.id {
                        Label(location.name, systemImage: "checkmark")
                    } else {
                        Text(location.name)
                    }
                }
            }
        } label: {
            Label("Switch Location", systemImage: "list.bullet")
        }
        .disabled(locationStore.locations.count < 2)
        .accessibilityHint("Choose which saved location to show")
    }

    @ViewBuilder
    private func weatherList(for location: SavedLocation) -> some View {
        List {
            if let message = model.errorMessage {
                Section {
                    Label(message, systemImage: "exclamationmark.triangle")
                        .foregroundStyle(.secondary)
                        .accessibilityLabel("Error: \(message)")
                    Button("Try Again") {
                        Task { await model.refresh(force: true) }
                    }
                }
            }

            if let report = model.report {
                let formatter = WeatherFormatter(settings: settings, timeZone: report.timeZone)
                CurrentConditionsSection(report: report, formatter: formatter)
                HourlyForecastSection(report: report, formatter: formatter)
                DailyForecastSection(report: report, formatter: formatter)
                moreSection(report: report, formatter: formatter)
            } else if model.isLoading {
                Section {
                    HStack {
                        ProgressView()
                        Text("Loading weather…")
                    }
                    .accessibilityElement(children: .combine)
                }
            }
        }
        .listStyle(.insetGrouped)
        .refreshable {
            await model.refresh(force: true)
        }
        .overlay(alignment: .top) {
            if model.isLoading && model.report != nil {
                ProgressView()
                    .padding(8)
                    .background(.thinMaterial, in: Capsule())
                    .padding(.top, 4)
                    .accessibilityLabel("Refreshing weather")
            }
        }
    }

    @ViewBuilder
    private func moreSection(report: WeatherReport, formatter: WeatherFormatter) -> some View {
        Section {
            if let officeID = report.forecastOfficeID {
                NavigationLink {
                    ForecasterNotesView(officeID: officeID)
                } label: {
                    Label("Forecaster Notes", systemImage: "text.book.closed")
                }
                .accessibilityHint("Opens the National Weather Service Area Forecast Discussion")
            }
            NavigationLink {
                RadioView(radio: model.radio)
            } label: {
                Label("NOAA Weather Radio", systemImage: "radio")
            }
            .accessibilityHint("Streams the nearest NOAA Weather Radio stations")
            if model.hasOpenRouterKey {
                NavigationLink {
                    ExplainConditionsView()
                } label: {
                    Label("Explain Conditions", systemImage: "sparkles")
                }
                .accessibilityHint("Explains the current weather in plain language")
            }
        } header: {
            SectionHeader("More")
        } footer: {
            Text("Source: \(report.sourceDescription). Last updated \(formatter.time(report.fetchedAt) ?? "").")
        }
    }
}

/// Section header that VoiceOver treats as a heading for rotor navigation.
struct SectionHeader: View {
    let title: String

    init(_ title: String) {
        self.title = title
    }

    var body: some View {
        Text(title)
            .accessibilityAddTraits(.isHeader)
    }
}

/// A label/value row read by VoiceOver as one element, with expanded units when provided.
struct MeasurementRow: View {
    let label: String
    let value: String
    var spokenValue: String?

    var body: some View {
        HStack(alignment: .firstTextBaseline) {
            Text(label)
            Spacer()
            Text(value)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.trailing)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(label)
        .accessibilityValue(spokenValue ?? value)
    }
}

struct CurrentConditionsSection: View {
    @EnvironmentObject private var settings: SettingsStore
    let report: WeatherReport
    let formatter: WeatherFormatter

    var body: some View {
        let current = report.current
        Section {
            if let description = current.description {
                Text(description)
                    .font(.title2.weight(.semibold))
                    .accessibilityLabel("Currently \(description)")
            }
            if let temp = formatter.temperature(current.temperatureC) {
                MeasurementRow(label: "Temperature", value: temp, spokenValue: formatter.spokenTemperature(current.temperatureC))
            }
            if settings.showDewpoint, let dew = formatter.temperature(current.dewpointC) {
                MeasurementRow(label: "Dewpoint", value: dew, spokenValue: formatter.spokenTemperature(current.dewpointC))
            }
            if let wind = formatter.wind(speedKph: current.windSpeedKph, directionDegrees: current.windDirectionDegrees) {
                MeasurementRow(label: "Wind", value: wind, spokenValue: formatter.spokenWind(speedKph: current.windSpeedKph, directionDegrees: current.windDirectionDegrees))
            }
            if let humidity = formatter.humidity(current.humidityPercent) {
                MeasurementRow(label: "Humidity", value: humidity, spokenValue: formatter.spokenHumidity(current.humidityPercent))
            }
            if settings.showPressure, let pressure = formatter.pressure(current.pressureHpa) {
                MeasurementRow(label: "Pressure", value: pressure, spokenValue: formatter.spokenPressure(current.pressureHpa))
            }
            if settings.showVisibility, let visibility = formatter.visibility(current.visibilityKm) {
                MeasurementRow(label: "Visibility", value: visibility, spokenValue: formatter.spokenVisibility(current.visibilityKm))
            }
            if settings.showUVIndex, let uv = current.uvIndex {
                MeasurementRow(label: "UV Index", value: formatter.uvIndex(uv) ?? "", spokenValue: "\(String(format: "%.1f", uv)), \(WeatherFormatter.uvCategory(uv))")
            }
            if let sunrise = formatter.time(current.sunrise) {
                MeasurementRow(label: "Sunrise", value: sunrise)
            }
            if let sunset = formatter.time(current.sunset) {
                MeasurementRow(label: "Sunset", value: sunset)
            }
            if settings.showAirQuality, let aq = current.airQuality {
                NavigationLink {
                    AirQualityDetailView(airQuality: aq)
                } label: {
                    MeasurementRow(
                        label: "Air Quality",
                        value: "AQI \(aq.aqi) (\(aq.category))" + (aq.dominantPollutant.map { ", \($0)" } ?? ""),
                        spokenValue: "AQI \(aq.aqi), \(aq.category)" + (aq.dominantPollutant.map { ", dominant pollutant \($0)" } ?? "")
                    )
                }
                .accessibilityHint("Shows air quality advice")
            }
        } header: {
            SectionHeader("Current Conditions")
        } footer: {
            if let observed = formatter.time(current.observedAt) {
                Text("Observed at \(observed)")
            }
        }
    }
}

struct HourlyForecastSection: View {
    @EnvironmentObject private var settings: SettingsStore
    let report: WeatherReport
    let formatter: WeatherFormatter

    var body: some View {
        Section {
            let periods = Array(report.hourly.prefix(max(1, settings.hourlyForecastHours)))
            if periods.isEmpty {
                Text("No hourly forecast available.")
                    .foregroundStyle(.secondary)
            }
            ForEach(periods) { period in
                HourlyRow(period: period, formatter: formatter)
            }
        } header: {
            SectionHeader("Hourly Forecast")
        }
    }
}

struct HourlyRow: View {
    let period: HourlyPeriod
    let formatter: WeatherFormatter

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            HStack(alignment: .firstTextBaseline) {
                Text(formatter.hour(period.time))
                    .font(.headline)
                Spacer()
                Text(formatter.temperature(period.temperatureC) ?? "--")
                    .font(.headline)
            }
            Text(period.condition)
            HStack {
                if let wind = formatter.wind(speedKph: period.windSpeedKph, directionDegrees: period.windDirectionDegrees) {
                    Text("Wind \(wind)")
                }
                Spacer()
                if let precip = formatter.precipitationChance(period.precipitationChance) {
                    Text(precip)
                }
            }
            .font(.subheadline)
            .foregroundStyle(.secondary)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(spokenLabel)
    }

    private var spokenLabel: String {
        var parts: [String] = [formatter.spokenHour(period.time)]
        if let temp = formatter.spokenTemperature(period.temperatureC) { parts.append(temp) }
        parts.append(period.condition)
        if let wind = formatter.spokenWind(speedKph: period.windSpeedKph, directionDegrees: period.windDirectionDegrees) { parts.append(wind) }
        if let precip = formatter.spokenPrecipitationChance(period.precipitationChance) { parts.append(precip) }
        return parts.joined(separator: ", ")
    }
}

struct DailyForecastSection: View {
    @EnvironmentObject private var settings: SettingsStore
    let report: WeatherReport
    let formatter: WeatherFormatter

    var body: some View {
        Section {
            // NWS returns day and night as separate periods; show roughly two per day.
            let limit = report.sourceDescription.hasPrefix("National") ? settings.dailyForecastDays * 2 : settings.dailyForecastDays
            let periods = Array(report.daily.prefix(max(1, limit)))
            if periods.isEmpty {
                Text("No daily forecast available.")
                    .foregroundStyle(.secondary)
            }
            ForEach(periods) { period in
                DailyRow(period: period, formatter: formatter)
            }
        } header: {
            SectionHeader("Daily Forecast")
        }
    }
}

struct DailyRow: View {
    let period: DailyPeriod
    let formatter: WeatherFormatter

    private var temperatureText: String {
        let high = formatter.temperature(period.highC)
        let low = formatter.temperature(period.lowC)
        return [high, low].compactMap { $0 }.joined(separator: " / ")
    }

    private var windText: String? {
        if let text = period.windText, !text.isEmpty { return text }
        return formatter.wind(speedKph: period.windSpeedKph, directionDegrees: period.windDirectionDegrees)
    }

    var body: some View {
        let content = VStack(alignment: .leading, spacing: 2) {
            HStack(alignment: .firstTextBaseline) {
                Text(period.name)
                    .font(.headline)
                Spacer()
                Text(temperatureText)
                    .font(.headline)
            }
            Text(period.condition)
            HStack {
                if let wind = windText {
                    Text("Wind \(wind)")
                }
                Spacer()
                if let precip = formatter.precipitationChance(period.precipitationChance) {
                    Text(precip)
                }
            }
            .font(.subheadline)
            .foregroundStyle(.secondary)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(spokenLabel)

        if let detail = period.detailedForecast, !detail.isEmpty {
            NavigationLink {
                ScrollView {
                    Text(detail)
                        .padding()
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
                .navigationTitle(period.name)
                .navigationBarTitleDisplayMode(.inline)
            } label: {
                content
            }
            .accessibilityHint("Opens the detailed forecast")
        } else {
            content
        }
    }

    private var spokenLabel: String {
        var parts: [String] = [period.name]
        if let high = formatter.spokenTemperature(period.highC) { parts.append("high \(high)") }
        if let low = formatter.spokenTemperature(period.lowC) { parts.append(period.highC == nil ? "low \(low)" : "low \(low)") }
        parts.append(period.condition)
        if let windSpoken = formatter.spokenWind(speedKph: period.windSpeedKph, directionDegrees: period.windDirectionDegrees) {
            parts.append(windSpoken)
        } else if let wind = windText {
            parts.append("wind \(wind)")
        }
        if let precip = formatter.spokenPrecipitationChance(period.precipitationChance) { parts.append(precip) }
        return parts.joined(separator: ", ")
    }
}

struct AirQualityDetailView: View {
    let airQuality: AirQuality

    var body: some View {
        List {
            Section {
                MeasurementRow(label: "US AQI", value: "\(airQuality.aqi)")
                MeasurementRow(label: "Category", value: airQuality.category)
                if let pollutant = airQuality.dominantPollutant {
                    MeasurementRow(label: "Dominant pollutant", value: pollutant)
                }
            } header: {
                SectionHeader("Air Quality")
            }
            Section {
                Text(airQuality.advice)
            } header: {
                SectionHeader("Advice")
            }
        }
        .navigationTitle("Air Quality")
        .navigationBarTitleDisplayMode(.inline)
    }
}
