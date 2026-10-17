import SwiftUI

struct AviationWeatherView: View {
    @EnvironmentObject private var model: AppModel
    @EnvironmentObject private var settings: SettingsStore
    let report: WeatherReport

    @State private var icao: String
    @State private var weather: AviationWeather?
    @State private var errorMessage: String?
    @State private var isLoading = false

    init(report: WeatherReport) {
        self.report = report
        let stationID = report.observationStationID ?? ""
        _icao = State(initialValue: ICAOCodeValidation.error(for: stationID) == nil
            ? ICAOCodeValidation.normalized(stationID)
            : "")
    }

    private var formatter: WeatherFormatter {
        WeatherFormatter(settings: settings, timeZone: report.timeZone)
    }

    var body: some View {
        List {
            Section {
                TextField("ICAO code", text: $icao)
                    .textInputAutocapitalization(.characters)
                    .autocorrectionDisabled()
                    .accessibilityLabel("ICAO airport code")
                Button {
                    Task { await fetchWeather() }
                } label: {
                    Label("Get", systemImage: "airplane")
                }
                .foregroundStyle(.primary)
                .disabled(isLoading)
                .accessibilityLabel("Get Aviation Weather")
                .accessibilityHint("Fetches current METAR observations and TAF forecasts for this airport")
            } header: {
                SectionHeader("Airport")
            }

            if isLoading {
                Section {
                    ProgressView("Loading aviation weather…")
                        .accessibilityElement(children: .combine)
                }
            }

            if let errorMessage {
                Section {
                    Text(errorMessage)
                        .foregroundStyle(.primary)
                        .accessibilityLabel(errorMessage)
                } header: {
                    SectionHeader("Aviation Weather")
                }
            }

            if let weather {
                Section {
                    if let observation = weather.metars.first {
                        metarRows(observation)
                    } else {
                        Text(weather.metarError ?? "No METAR available for \(ICAOCodeValidation.normalized(icao)).")
                            .accessibilityElement(children: .ignore)
                    }
                } header: {
                    SectionHeader("Current Observation (METAR)")
                }

                Section {
                    if weather.tafs.isEmpty {
                        Text(weather.tafError ?? "No TAF available for \(ICAOCodeValidation.normalized(icao)).")
                            .accessibilityElement(children: .ignore)
                    } else {
                        ForEach(Array(weather.tafs.enumerated()), id: \.offset) { item in
                            tafRows(item.element)
                        }
                    }
                } header: {
                    SectionHeader("Terminal Aerodrome Forecast (TAF)")
                }
            }
        }
        .navigationTitle("Aviation Weather")
        .navigationBarTitleDisplayMode(.inline)
    }

    private func fetchWeather() async {
        let code = ICAOCodeValidation.normalized(icao)
        guard let validationError = ICAOCodeValidation.error(for: code) else {
            errorMessage = nil
            isLoading = true
            defer { isLoading = false }
            do {
                weather = try await model.weatherService.aviationWeather(icao: code)
            } catch {
                errorMessage = error.localizedDescription
            }
            return
        }
        weather = nil
        errorMessage = validationError
    }

    @ViewBuilder
    private func metarRows(_ observation: METARObservation) -> some View {
        if let raw = observation.rawOb {
            MeasurementRow(label: "Raw METAR", value: raw)
        }
        if let date = observation.observationDate, let time = formatter.time(date) {
            MeasurementRow(label: "Observation time", value: time)
        }
        if let wind = AviationWeatherFormatting.wind(
            direction: observation.wdir,
            speed: observation.wspd,
            gust: observation.wgst
        ) {
            MeasurementRow(label: "Wind", value: wind)
        }
        if let visibility = AviationWeatherFormatting.visibility(observation.visib) {
            MeasurementRow(label: "Visibility", value: visibility)
        }
        if let clouds = AviationWeatherFormatting.clouds(observation.clouds) {
            MeasurementRow(label: "Clouds", value: clouds)
        }
        if let temperature = formatter.temperature(observation.temperature?.number) {
            MeasurementRow(
                label: "Temperature",
                value: temperature,
                spokenValue: formatter.spokenTemperature(observation.temperature?.number)
            )
        }
        if let dewpoint = formatter.temperature(observation.dewpoint?.number) {
            MeasurementRow(
                label: "Dewpoint",
                value: dewpoint,
                spokenValue: formatter.spokenTemperature(observation.dewpoint?.number)
            )
        }
        if let pressure = formatter.pressure(AviationWeatherFormatting.altimeterHectopascals(observation.altim)) {
            MeasurementRow(label: "Altimeter", value: pressure)
        }
        if let weather = observation.wxString, !weather.isEmpty {
            MeasurementRow(label: "Weather", value: weather)
        }
    }

    @ViewBuilder
    private func tafRows(_ taf: TAFProduct) -> some View {
        if let raw = taf.rawTAF {
            MeasurementRow(label: "Raw TAF", value: raw)
        }
        ForEach(Array((taf.fcsts ?? []).enumerated()), id: \.offset) { item in
            forecastRow(item.element)
        }
    }

    private func forecastRow(_ forecast: TAFForecast) -> some View {
        let start = forecast.startDate.map(formatter.hour) ?? "Unknown time"
        let end = forecast.endDate.map(formatter.hour) ?? "Unknown time"
        var details: [String] = []
        if let wind = AviationWeatherFormatting.wind(
            direction: forecast.wdir,
            speed: forecast.wspd,
            gust: forecast.wgst
        ) {
            details.append("wind \(wind)")
        }
        if let visibility = AviationWeatherFormatting.visibility(forecast.visib) {
            details.append("visibility \(visibility)")
        }
        if let clouds = AviationWeatherFormatting.clouds(forecast.clouds) {
            details.append("clouds \(clouds)")
        }
        if let weather = forecast.wxString, !weather.isEmpty {
            details.append("weather \(weather)")
        }
        let change = forecast.fcstChange.map { "\($0), " } ?? ""
        let detailText = details.isEmpty ? "Forecast details unavailable." : details.joined(separator: ", ")
        let row = "\(change)From \(start) to \(end): \(detailText)"
        return Text(row)
            .fixedSize(horizontal: false, vertical: true)
            .accessibilityElement(children: .ignore)
            .accessibilityLabel(row)
    }
}
