import SwiftUI

/// NOAA Weather Radio: nearest stations to the selected location with Play/Stop controls.
struct RadioView: View {
    @EnvironmentObject private var model: AppModel
    @EnvironmentObject private var settings: SettingsStore
    @ObservedObject private var radio: RadioPlayer

    private let database = RadioStationDatabase()

    init(radio: RadioPlayer) {
        self.radio = radio
    }

    private var nearby: [NearbyStation] {
        guard let location = model.selectedLocation else { return [] }
        return database.nearest(latitude: location.latitude, longitude: location.longitude)
    }

    var body: some View {
        List {
            nowPlayingSection
            stationsSection
        }
        .listStyle(.insetGrouped)
        .navigationTitle("NOAA Weather Radio")
        .navigationBarTitleDisplayMode(.inline)
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
            if nearby.isEmpty {
                Text("Add a location to see nearby NOAA Weather Radio stations.")
                    .foregroundStyle(.secondary)
            }
            ForEach(nearby) { entry in
                stationRow(entry)
            }
        } header: {
            SectionHeader("Nearest Stations")
        } footer: {
            Text("Streams are provided by volunteer relays and may be offline. Playback continues in the background and can be controlled from the Lock Screen. Stations with no stream fall back to Broadcastify.")
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
