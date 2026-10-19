import SwiftUI

/// NOAA Weather Radio: nearest stations (from the WeatherIndex directory) to the selected
/// location with Play/Stop controls.
struct RadioView: View {
    @EnvironmentObject private var model: AppModel
    @EnvironmentObject private var settings: SettingsStore
    @ObservedObject private var radio: RadioPlayer
    @ObservedObject private var directory: RadioStationDirectory

    init(radio: RadioPlayer, directory: RadioStationDirectory) {
        self.radio = radio
        self.directory = directory
    }

    private var nearby: [NearbyStation] {
        guard let location = model.selectedLocation else { return [] }
        return directory.nearest(latitude: location.latitude, longitude: location.longitude)
    }

    var body: some View {
        List {
            nowPlayingSection
            stationsSection
        }
        .listStyle(.insetGrouped)
        .navigationTitle("NOAA Weather Radio")
        .navigationBarTitleDisplayMode(.inline)
        .task { await directory.refreshIfStale() }
        .refreshable { await directory.refresh() }
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Button {
                    Task { await directory.refresh() }
                } label: {
                    Label("Refresh Stations", systemImage: "arrow.clockwise")
                }
                .disabled(directory.isRefreshing)
                .accessibilityHint("Downloads the latest station list from WeatherIndex")
            }
        }
    }

    private var nowPlayingSection: some View {
        Section {
            LabeledContent("Station", value: radio.station.map { "\($0.name), \($0.callSign)" } ?? "None selected")
                .accessibilityElement(children: .combine)
            LabeledContent("Status", value: radio.status.text)
                .accessibilityElement(children: .combine)
            if let station = radio.station {
                Button {
                    radio.toggle(station)
                } label: {
                    Label(radio.isPlaying ? "Stop" : "Play", systemImage: radio.isPlaying ? "stop.fill" : "play.fill")
                }
                .accessibilityHint(radio.isPlaying ? "Stops the radio stream" : "Starts streaming \(station.name)")
            }
        } header: {
            SectionHeader("Now Playing")
        }
    }

    private var stationsSection: some View {
        Section {
            if directory.isRefreshing && directory.database.stations.isEmpty {
                Text("Loading station list…")
                    .foregroundStyle(.secondary)
            } else if model.selectedLocation == nil {
                Text("Add a location to see nearby NOAA Weather Radio stations.")
                    .foregroundStyle(.secondary)
            } else if nearby.isEmpty {
                Text("No NOAA Weather Radio streams are available right now.")
                    .foregroundStyle(.secondary)
            }
            ForEach(nearby) { entry in
                stationRow(entry)
            }
        } header: {
            SectionHeader("Nearest Stations")
        } footer: {
            Text("\(directory.source.description) Streams are provided by volunteer relays and may be offline. Playback continues in the background and can be controlled from the Lock Screen.")
        }
    }

    private func stationRow(_ entry: NearbyStation) -> some View {
        let station = entry.station
        let isCurrent = radio.station == station
        let distance = String(format: "%.0f miles", entry.distanceMiles)
        return Button {
            radio.toggle(station)
            settings.lastRadioStationCallSign = station.callSign
        } label: {
            HStack {
                VStack(alignment: .leading) {
                    Text(station.name)
                    Text("\(station.callSign) · \(station.frequencyText) · \(distance)")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                Image(systemName: isCurrent && radio.isPlaying ? "stop.circle.fill" : "play.circle")
                    .imageScale(.large)
                    .accessibilityHidden(true)
            }
        }
        .buttonStyle(.plain)
        .accessibilityLabel("\(station.name), \(station.callSign), \(station.frequencyText), \(distance) away")
        .accessibilityValue(isCurrent ? radio.status.text : "")
        .accessibilityHint(isCurrent && radio.isPlaying ? "Stops playback" : "Plays this station")
    }
}
