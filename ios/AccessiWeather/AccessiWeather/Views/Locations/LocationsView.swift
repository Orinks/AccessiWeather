import SwiftUI

struct LocationsView: View {
    @EnvironmentObject private var model: AppModel
    @EnvironmentObject private var locationStore: LocationStore
    @EnvironmentObject private var settings: SettingsStore
    @ObservedObject private var tracker = CurrentLocationTracker.shared
    @State private var showingAddSheet = false

    var body: some View {
        NavigationStack {
            Group {
                if locationStore.locations.isEmpty && !settings.followCurrentLocation {
                    ContentUnavailableView {
                        Label {
                            Text("No Saved Locations")
                                .accessibilityAddTraits(.isHeader)
                        } icon: {
                            Image(systemName: "mappin.slash")
                                .accessibilityHidden(true)
                        }
                    } description: {
                        Text("Add a city, ZIP code, or your current location to get started.")
                    } actions: {
                        Button("Add Location") { showingAddSheet = true }
                            .buttonStyle(.borderedProminent)
                        Button("Follow My Current Location") { model.setFollowsCurrentLocation(true) }
                            .buttonStyle(.bordered)
                    }
                } else {
                    List {
                        currentLocationSection
                        Section {
                        ForEach(locationStore.locations) { location in
                            Button {
                                model.select(location)
                            } label: {
                                HStack {
                                    VStack(alignment: .leading) {
                                        Text(location.name)
                                            .font(.headline)
                                        Text(location.isCurrentLocation ? "Current location, \(location.coordinateDescription)" : location.coordinateDescription)
                                            .font(.caption)
                                            .foregroundStyle(.secondary)
                                    }
                                    Spacer()
                                    if location.id == model.selectedLocation?.id {
                                        Image(systemName: "checkmark")
                                            .foregroundStyle(Color.accentColor)
                                            .accessibilityHidden(true)
                                    }
                                }
                            }
                            .foregroundStyle(.primary)
                            .accessibilityLabel(location.name)
                            .accessibilityValue(
                                [
                                    location.isCurrentLocation ? "Current location" : nil,
                                    location.id == model.selectedLocation?.id ? "Selected" : nil,
                                    location.marineMode ? "Marine Mode" : nil,
                                ]
                                    .compactMap { $0 }.joined(separator: ", ")
                            )
                            .contextMenu {
                                Button(location.marineMode ? "Turn Off Marine Mode" : "Turn On Marine Mode") {
                                    toggleMarineMode(location)
                                }
                            }
                            .accessibilityAction(named: location.marineMode ? "Turn Off Marine Mode" : "Turn On Marine Mode") {
                                toggleMarineMode(location)
                            }
                            .accessibilityAddTraits(location.id == model.selectedLocation?.id ? .isSelected : [])
                            .accessibilityHint("Shows weather for this location")
                        }
                        .onDelete { offsets in
                            let removesCurrent = offsets.contains { locationStore.locations[$0].isCurrentLocation }
                            model.removeLocations(atOffsets: offsets)
                            if removesCurrent { model.setFollowsCurrentLocation(false) }
                        }
                        .onMove { source, destination in
                            locationStore.move(fromOffsets: source, toOffset: destination)
                        }
                        }
                    }
                }
            }
            .navigationTitle("Locations")
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    EditButton()
                        .disabled(locationStore.locations.isEmpty)
                        .accessibilityHint("Reorder or delete saved locations")
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        showingAddSheet = true
                    } label: {
                        Label("Add Location", systemImage: "plus")
                    }
                    .accessibilityHint("Search for a place or use your current location")
                }
            }
            .sheet(isPresented: $showingAddSheet) {
                AddLocationView()
            }
        }
    }

    private var currentLocationSection: some View {
        Section {
            Toggle("Follow my current location", isOn: Binding(
                get: { settings.followCurrentLocation },
                set: { model.setFollowsCurrentLocation($0) }
            ))
            if settings.followCurrentLocation, !tracker.updatesWhileClosed, !tracker.isDenied {
                Button("Keep Updating While AccessiWeather Is Closed") { tracker.requestAlwaysPermission() }
                    .accessibilityHint("Asks iOS to allow location access always, so alerts follow you when you travel")
            }
        } footer: {
            if tracker.isDenied, settings.followCurrentLocation {
                Text("Location access is off for AccessiWeather. Turn it on in the iPhone Settings app, under Privacy & Security, Location Services.")
            } else if tracker.updatesWhileClosed {
                Text("Your current location updates when you move about half a mile or more, even while AccessiWeather is closed.")
            } else {
                Text("Your current location updates each time you open AccessiWeather. Allow location access always to keep it updated while the app is closed.")
            }
        }
    }

    /// Marine Mode adds the nearby NWS marine zone forecast and marine alerts for US coastal locations.
    private func toggleMarineMode(_ location: SavedLocation) {
        var updated = location
        updated.marineMode.toggle()
        locationStore.update(updated)
        if location.id == model.selectedLocation?.id {
            model.select(updated)
        }
        AccessibilityNotification.Announcement(updated.marineMode ? "Marine Mode on" : "Marine Mode off").post()
    }
}
