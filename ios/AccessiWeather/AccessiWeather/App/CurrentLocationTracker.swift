import CoreLocation
import UIKit

/// Follows the device for the current location: significant-change monitoring with Always permission, which iOS
/// delivers even after relaunching a closed app, otherwise one fix each time the app opens.
@MainActor
final class CurrentLocationTracker: NSObject, ObservableObject, CLLocationManagerDelegate {
    static let shared = CurrentLocationTracker()
    /// Moves shorter than this keep the current location where it is.
    static let minimumMoveMeters: CLLocationDistance = 800

    @Published private(set) var authorizationStatus: CLAuthorizationStatus
    var onLocation: ((CLLocation) -> Void)?
    private let manager: CLLocationManager
    private var isFollowing = false

    override init() {
        let manager = CLLocationManager()
        self.manager = manager
        authorizationStatus = manager.authorizationStatus
        super.init()
        manager.delegate = self
        manager.desiredAccuracy = kCLLocationAccuracyKilometer
    }

    var updatesWhileClosed: Bool { authorizationStatus == .authorizedAlways }
    var isDenied: Bool { authorizationStatus == .denied || authorizationStatus == .restricted }

    func follow() {
        isFollowing = true
        switch manager.authorizationStatus {
        case .notDetermined:
            manager.requestWhenInUseAuthorization()
        case .authorizedAlways:
            manager.startMonitoringSignificantLocationChanges()
            manager.requestLocation()
        case .authorizedWhenInUse:
            manager.requestLocation()
        default:
            break
        }
    }

    func stop() {
        isFollowing = false
        manager.stopMonitoringSignificantLocationChanges()
    }

    func requestAlwaysPermission() {
        manager.requestAlwaysAuthorization()
    }

    nonisolated func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        let status = manager.authorizationStatus
        Task { @MainActor in
            self.authorizationStatus = status
            if self.isFollowing, status != .notDetermined { self.follow() }
        }
    }

    nonisolated func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard let last = locations.last else { return }
        Task { @MainActor in self.onLocation?(last) }
    }

    nonisolated func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {}
}

extension AppModel {
    static let shared = AppModel()

    var currentLocation: SavedLocation? { locationStore.locations.first { $0.isCurrentLocation } }

    func startFollowingCurrentLocation() {
        CurrentLocationTracker.shared.onLocation = { [weak self] location in
            Task { await self?.currentLocationMoved(to: location) }
        }
        updateCurrentLocation()
    }

    func updateCurrentLocation() {
        guard settings.followCurrentLocation else { return }
        CurrentLocationTracker.shared.follow()
    }

    func setFollowsCurrentLocation(_ on: Bool) {
        settings.followCurrentLocation = on
        if on {
            CurrentLocationTracker.shared.follow()
        } else {
            CurrentLocationTracker.shared.stop()
            if let index = locationStore.locations.firstIndex(where: \.isCurrentLocation) {
                removeLocations(atOffsets: IndexSet(integer: index))
            }
        }
    }

    /// Moves the current location (rounded to about 1 km) and tells the push server, which notifies Extreme and
    /// Severe alerts already active there.
    func currentLocationMoved(to location: CLLocation) async {
        guard settings.followCurrentLocation else { return }
        if let current = currentLocation,
           CLLocation(latitude: current.latitude, longitude: current.longitude).distance(from: location)
            < CurrentLocationTracker.minimumMoveMeters {
            return
        }
        let application = UIApplication.shared
        let background = application.beginBackgroundTask(withName: "Current location")
        defer { application.endBackgroundTask(background) }
        let latitude = (location.coordinate.latitude * 100).rounded() / 100
        let longitude = (location.coordinate.longitude * 100).rounded() / 100
        let place = try? await GeocodingClient().reverse(latitude: latitude, longitude: longitude)
        let name = place?.shortName ?? String(format: "%.2f, %.2f", latitude, longitude)
        guard var current = currentLocation else {
            var created = SavedLocation(name: name, latitude: latitude, longitude: longitude)
            created.isCurrentLocation = true
            locationStore.insertFirst(created)
            select(created)
            return
        }
        current.name = name
        current.latitude = latitude
        current.longitude = longitude
        locationStore.update(current)
        if current.id == selectedLocation?.id, application.applicationState == .active {
            report = nil
            await refresh(announce: false)
        } else {
            await syncPush()
        }
    }
}
