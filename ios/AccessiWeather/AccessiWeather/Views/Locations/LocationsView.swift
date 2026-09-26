import SwiftUI

struct LocationsView: View {
    @EnvironmentObject private var model: AppModel
    @EnvironmentObject private var locationStore: LocationStore
    @State private var showingAddSheet = false

    var body: some View {
        NavigationStack {
            Group {
                if locationStore.locations.isEmpty {
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
                    }
                } else {
                    List {
                        ForEach(locationStore.locations) { location in
                            Button {
                                model.select(location)
                            } label: {
                                HStack {
                                    VStack(alignment: .leading) {
                                        Text(location.name)
                                            .font(.headline)
                                        Text(location.coordinateDescription)
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
                            .accessibilityValue(location.id == model.selectedLocation?.id ? "Selected" : "")
                            .accessibilityAddTraits(location.id == model.selectedLocation?.id ? .isSelected : [])
                            .accessibilityHint("Shows weather for this location")
                        }
                        .onDelete { offsets in
                            model.removeLocations(atOffsets: offsets)
                        }
                        .onMove { source, destination in
                            locationStore.move(fromOffsets: source, toOffset: destination)
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
}
