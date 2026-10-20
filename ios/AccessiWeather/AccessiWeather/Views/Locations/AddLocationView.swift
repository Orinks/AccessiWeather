import CoreLocation
import SwiftUI

struct AddLocationView: View {
    @EnvironmentObject private var model: AppModel
    @Environment(\.dismiss) private var dismiss

    @State private var query = ""
    @State private var results: [GeocodingResult] = []
    @State private var isSearching = false
    @State private var statusMessage: String?
    @StateObject private var locationFinder = CurrentLocationFinder()

    private let geocoder = GeocodingClient()

    var body: some View {
        NavigationStack {
            List {
                Section {
                    HStack {
                        TextField("City, ZIP code, or address", text: $query)
                            .textInputAutocapitalization(.words)
                            .autocorrectionDisabled()
                            .submitLabel(.search)
                            .onSubmit { Task { await search() } }
                            .accessibilityLabel("Search for a location")
                            .accessibilityHint("Enter a city, ZIP or postal code, or US street address")
                        Button {
                            Task { await search() }
                        } label: {
                            Label("Search", systemImage: "magnifyingglass")
                                .labelStyle(.iconOnly)
                        }
                        .disabled(query.trimmingCharacters(in: .whitespaces).isEmpty || isSearching)
                        .accessibilityLabel("Search")
                    }
                    Button {
                        Task { await useCurrentLocation() }
                    } label: {
                        Label("Use Current Location", systemImage: "location")
                    }
                    .disabled(locationFinder.isLocating)
                    .accessibilityHint("Finds your position and looks up its place name")
                } header: {
                    SectionHeader("Find a Location")
                } footer: {
                    Text("Examples: London, New York, 10001, or 123 Main St, Carrollton, TX")
                }

                Section {
                    if isSearching || locationFinder.isLocating {
                        HStack {
                            ProgressView()
                            Text(locationFinder.isLocating ? "Finding your location…" : "Searching…")
                        }
                        .accessibilityElement(children: .combine)
                    } else if let statusMessage {
                        Text(statusMessage)
                            .foregroundStyle(.secondary)
                    } else if results.isEmpty {
                        Text("Search results will appear here.")
                            .foregroundStyle(.secondary)
                    }
                    ForEach(results) { result in
                        Button {
                            save(result)
                        } label: {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(result.shortName)
                                    .font(.headline)
                                Text(result.displayName)
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                        }
                        .foregroundStyle(.primary)
                        .accessibilityElement(children: .ignore)
                        .accessibilityLabel(result.displayName)
                        .accessibilityHint("Saves this location")
                    }
                } header: {
                    SectionHeader("Search Results")
                }
            }
            .navigationTitle("Add Location")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
            }
        }
    }

    private func search() async {
        let trimmed = query.trimmingCharacters(in: .whitespaces)
        guard !trimmed.isEmpty else { return }
        isSearching = true
        statusMessage = nil
        defer { isSearching = false }
        do {
            results = try await geocoder.search(trimmed)
            if results.isEmpty {
                statusMessage = "No places matched \"\(trimmed)\"."
            }
            AccessibilityNotification.Announcement(results.isEmpty ? "No results" : "\(results.count) results found").post()
        } catch {
            results = []
            statusMessage = "Search failed: \(error.localizedDescription)"
        }
    }

    private func useCurrentLocation() async {
        statusMessage = nil
        do {
            let coordinate = try await locationFinder.currentCoordinate()
            let place = try? await geocoder.reverse(latitude: coordinate.latitude, longitude: coordinate.longitude)
            let name = place?.shortName ?? String(format: "%.3f, %.3f", coordinate.latitude, coordinate.longitude)
            let result = GeocodingResult(
                id: "current",
                displayName: place?.displayName ?? name,
                shortName: name,
                latitude: coordinate.latitude,
                longitude: coordinate.longitude
            )
            results = [result]
            AccessibilityNotification.Announcement("Found \(name). Select it to save.").post()
        } catch {
            statusMessage = error.localizedDescription
        }
    }

    private func save(_ result: GeocodingResult) {
        model.addLocation(SavedLocation(name: result.shortName, latitude: result.latitude, longitude: result.longitude))
        AccessibilityNotification.Announcement("Saved \(result.shortName)").post()
        dismiss()
    }
}

/// One-shot CoreLocation wrapper exposing the device position as an async call.
@MainActor
final class CurrentLocationFinder: NSObject, ObservableObject, CLLocationManagerDelegate {
    @Published private(set) var isLocating = false

    private let manager = CLLocationManager()
    private var continuation: CheckedContinuation<CLLocationCoordinate2D, Error>?

    enum LocationError: LocalizedError {
        case denied
        case unavailable

        var errorDescription: String? {
            switch self {
            case .denied: return "Location access is turned off. Allow it for AccessiWeather in the Settings app, or search for a place instead."
            case .unavailable: return "Your location could not be determined. Try again or search for a place instead."
            }
        }
    }

    override init() {
        super.init()
        manager.delegate = self
        manager.desiredAccuracy = kCLLocationAccuracyKilometer
    }

    func currentCoordinate() async throws -> CLLocationCoordinate2D {
        if let continuation {
            continuation.resume(throwing: LocationError.unavailable)
            self.continuation = nil
        }
        isLocating = true
        defer { isLocating = false }
        return try await withCheckedThrowingContinuation { continuation in
            self.continuation = continuation
            switch manager.authorizationStatus {
            case .notDetermined:
                manager.requestWhenInUseAuthorization()
            case .denied, .restricted:
                finish(.failure(LocationError.denied))
            default:
                manager.requestLocation()
            }
        }
    }

    private func finish(_ result: Result<CLLocationCoordinate2D, Error>) {
        guard let continuation else { return }
        self.continuation = nil
        continuation.resume(with: result)
    }

    nonisolated func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        let status = manager.authorizationStatus
        Task { @MainActor in
            guard continuation != nil else { return }
            switch status {
            case .authorizedAlways, .authorizedWhenInUse:
                self.manager.requestLocation()
            case .denied, .restricted:
                finish(.failure(LocationError.denied))
            default:
                break
            }
        }
    }

    nonisolated func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        let coordinate = locations.last?.coordinate
        Task { @MainActor in
            if let coordinate {
                finish(.success(coordinate))
            } else {
                finish(.failure(LocationError.unavailable))
            }
        }
    }

    nonisolated func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        Task { @MainActor in
            finish(.failure(LocationError.unavailable))
        }
    }
}
