import SwiftUI

struct SettingsView: View {
    @EnvironmentObject private var model: AppModel
    @EnvironmentObject private var settings: SettingsStore

    @State private var pirateWeatherKey = KeychainStore.read(.pirateWeather)
    @State private var airNowKey = KeychainStore.read(.airNow)
    @State private var avwxKey = KeychainStore.read(.avwx)
    @State private var openRouterKey = KeychainStore.read(.openRouter)
    @State private var notificationPermissionDenied = false

    private var appVersion: String {
        let version = Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "0.0"
        let build = Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "0"
        return "\(version) (\(build))"
    }

    var body: some View {
        NavigationStack {
            Form {
                unitsSection
                forecastSection
                displaySection
                alertsSection
                soundsSection
                dataSourcesSection
                aboutSection
            }
            .navigationTitle("Settings")
            .onChange(of: settings.weatherSource) { _, _ in
                Task { await model.refresh(force: true) }
            }
            .alert("Notifications Are Off", isPresented: $notificationPermissionDenied) {
                Button("OK", role: .cancel) {}
            } message: {
                Text("Allow notifications for AccessiWeather in the Settings app to be told about new weather alerts.")
            }
        }
    }

    private var unitsSection: some View {
        Section {
            Picker("Temperature", selection: $settings.temperatureUnit) {
                ForEach(TemperatureUnit.allCases) { unit in
                    Text(unit.title).tag(unit)
                }
            }
            Picker("Wind speed", selection: $settings.windSpeedUnit) {
                ForEach(WindSpeedUnit.allCases) { unit in
                    Text(unit.title).tag(unit)
                }
            }
        } header: {
            SectionHeader("Units")
        }
    }

    private var forecastSection: some View {
        Section {
            Stepper(value: $settings.hourlyForecastHours, in: 1...48) {
                LabeledContent("Hourly forecast hours", value: "\(settings.hourlyForecastHours)")
            }
            .accessibilityValue("\(settings.hourlyForecastHours) hours")
            Stepper(value: $settings.dailyForecastDays, in: 1...14) {
                LabeledContent("Daily forecast days", value: "\(settings.dailyForecastDays)")
            }
            .accessibilityValue("\(settings.dailyForecastDays) days")
            Toggle("24-hour time", isOn: $settings.use24HourTime)
        } header: {
            SectionHeader("Forecast")
        }
    }

    private var displaySection: some View {
        Section {
            Toggle("Show dewpoint", isOn: $settings.showDewpoint)
            Toggle("Show pressure", isOn: $settings.showPressure)
            Toggle("Show visibility", isOn: $settings.showVisibility)
            Toggle("Show UV index", isOn: $settings.showUVIndex)
            Toggle("Show air quality", isOn: $settings.showAirQuality)
            Toggle("Round values to whole numbers", isOn: $settings.roundValues)
        } header: {
            SectionHeader("Display")
        }
    }

    private var alertsSection: some View {
        Section {
            Toggle("Notify me about new alerts", isOn: $settings.alertNotificationsEnabled)
                .onChange(of: settings.alertNotificationsEnabled) { _, enabled in
                    guard enabled else { return }
                    Task {
                        let granted = await model.requestNotificationPermission()
                        if !granted {
                            settings.alertNotificationsEnabled = false
                            notificationPermissionDenied = true
                        }
                    }
                }
            Group {
                Toggle("Extreme alerts", isOn: $settings.notifyExtreme)
                Toggle("Severe alerts", isOn: $settings.notifySevere)
                Toggle("Moderate alerts", isOn: $settings.notifyModerate)
                Toggle("Minor alerts", isOn: $settings.notifyMinor)
            }
            .disabled(!settings.alertNotificationsEnabled)
        } header: {
            SectionHeader("Alerts")
        } footer: {
            Text("Notifications play the selected sound pack's alert cue when Sounds are on. Alerts are checked whenever weather is refreshed.")
        }
    }

    private var soundsSection: some View {
        Section {
            Toggle("Play sounds", isOn: $settings.soundEnabled)
            ForEach(model.sounds.packs) { pack in
                soundPackRow(pack)
            }
            NavigationLink {
                SoundEventsView()
            } label: {
                LabeledContent("Muted events", value: "\(settings.mutedSoundEvents.count)")
            }
            .accessibilityHint("Choose which events play a sound")
            .disabled(!settings.soundEnabled)
        } header: {
            SectionHeader("Sounds")
        } footer: {
            Text("Sounds mix with VoiceOver and follow the silent switch. Notification sounds come from the selected pack; iOS only allows notification clips shorter than 30 seconds.")
        }
    }

    private func soundPackRow(_ pack: SoundPack) -> some View {
        let isSelected = settings.soundPackID == pack.id
        return HStack {
            Button {
                settings.soundPackID = pack.id
            } label: {
                HStack {
                    VStack(alignment: .leading) {
                        Text(pack.name)
                        if !pack.description.isEmpty {
                            Text(pack.description)
                                .font(.footnote)
                                .foregroundStyle(.secondary)
                        }
                    }
                    Spacer()
                    if isSelected {
                        Image(systemName: "checkmark")
                            .accessibilityHidden(true)
                    }
                }
            }
            .buttonStyle(.plain)
            .accessibilityLabel("\(pack.name) sound pack")
            .accessibilityValue(isSelected ? "Selected" : "")
            .accessibilityHint("Uses this pack for app sounds and alert notifications")
            .accessibilityAddTraits(isSelected ? [.isSelected] : [])
            Button {
                model.sounds.preview(pack)
            } label: {
                Image(systemName: "play.circle")
                    .imageScale(.large)
            }
            .buttonStyle(.borderless)
            .accessibilityLabel("Preview \(pack.name)")
            .accessibilityHint("Plays this pack's alert sound")
        }
    }

    private var dataSourcesSection: some View {
        Section {
            Picker("Weather source", selection: $settings.weatherSource) {
                ForEach(WeatherSource.allCases) { source in
                    Text(source.displayName).tag(source)
                }
            }
            apiKeyField("Pirate Weather API key", text: $pirateWeatherKey, key: .pirateWeather)
            apiKeyField("AirNow API key", text: $airNowKey, key: .airNow)
            apiKeyField("AVWX API key", text: $avwxKey, key: .avwx)
            apiKeyField("OpenRouter API key", text: $openRouterKey, key: .openRouter)
        } header: {
            SectionHeader("Data Sources")
        } footer: {
            Text("Automatic uses the National Weather Service inside the United States and Open-Meteo elsewhere. API keys are stored in the iOS Keychain. Pirate Weather, AirNow, AVWX, and OpenRouter features are coming in a later version.")
        }
    }

    private func apiKeyField(_ title: String, text: Binding<String>, key: KeychainStore.Key) -> some View {
        SecureField(title, text: text)
            .textContentType(.password)
            .autocorrectionDisabled()
            .textInputAutocapitalization(.never)
            .accessibilityLabel(title)
            .accessibilityHint("Stored securely in the Keychain")
            .onChange(of: text.wrappedValue) { _, newValue in
                KeychainStore.write(newValue, for: key)
                if key == .openRouter {
                    model.refreshKeyStatus()
                }
            }
    }

    private var aboutSection: some View {
        Section {
            LabeledContent("Version", value: appVersion)
            Link(destination: URL(string: "https://github.com/Orinks/AccessiWeather/blob/main/docs/user_manual.md")!) {
                Label("User Manual", systemImage: "book")
            }
            .accessibilityHint("Opens the user manual in Safari")
            Link(destination: URL(string: "https://github.com/Orinks/AccessiWeather")!) {
                Label("AccessiWeather on GitHub", systemImage: "link")
            }
            .accessibilityHint("Opens the project page in Safari")
            Link(destination: URL(string: "https://github.com/Orinks/AccessiWeather/issues/new")!) {
                Label("Report an Issue", systemImage: "exclamationmark.bubble")
            }
            .accessibilityHint("Opens a new GitHub issue in Safari")
        } header: {
            SectionHeader("About")
        } footer: {
            Text("Weather data from the National Weather Service and Open-Meteo. Geocoding by OpenStreetMap Nominatim.")
        }
    }
}
