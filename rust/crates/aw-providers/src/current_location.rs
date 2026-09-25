//! One-time "Use my current location" detection, ported from
//! `accessiweather.current_location`. Windows uses Windows Location Services
//! (WinRT `Geolocator`), macOS uses CoreLocation; other platforms report
//! "unsupported".

use std::time::Duration;

use aw_core::location::is_us_location;
use aw_core::model::Location;

/// Outcome of a one-time current-location request.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LocationDetectionStatus {
    Success,
    Denied,
    Timeout,
    Unavailable,
    Unsupported,
}

impl LocationDetectionStatus {
    pub fn value(self) -> &'static str {
        match self {
            Self::Success => "success",
            Self::Denied => "denied",
            Self::Timeout => "timeout",
            Self::Unavailable => "unavailable",
            Self::Unsupported => "unsupported",
        }
    }
}

/// Coordinates returned by a native location provider.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct CurrentCoordinates {
    pub latitude: f64,
    pub longitude: f64,
    pub accuracy_meters: Option<f64>,
}

/// Normalized result for the UI.
#[derive(Debug, Clone, PartialEq)]
pub struct CurrentLocationResult {
    pub status: LocationDetectionStatus,
    pub message: String,
    pub coordinates: Option<CurrentCoordinates>,
    pub location: Option<Location>,
}

/// Provider failure: an expected outcome with its user-facing message, a
/// bare timeout, or anything else.
#[derive(Debug, Clone, PartialEq)]
pub enum DetectError {
    Known(LocationDetectionStatus, String),
    Timeout,
    Failed(String),
}

pub trait CurrentLocationProvider: Send + Sync {
    fn detect(&self, timeout: Duration) -> Result<CurrentCoordinates, DetectError>;
}

pub const DEFAULT_TIMEOUT: Duration = Duration::from_secs(15);

/// The editable location a manual save would create for the coordinates.
pub fn location_from_coordinates(coordinates: CurrentCoordinates, name: Option<&str>) -> Location {
    let label = match name.filter(|n| !n.is_empty()) {
        Some(n) => n.to_string(),
        None => format!(
            "Current Location ({:.4}, {:.4})",
            coordinates.latitude, coordinates.longitude
        ),
    };
    let mut location = Location::new(label, coordinates.latitude, coordinates.longitude);
    if is_us_location(&location) {
        location.country_code = Some("US".into());
    }
    location
}

/// Facade that normalizes native provider outcomes for the UI.
pub struct CurrentLocationService {
    provider: Box<dyn CurrentLocationProvider>,
}

impl Default for CurrentLocationService {
    fn default() -> Self {
        Self::new(native_provider())
    }
}

impl CurrentLocationService {
    pub fn new(provider: Box<dyn CurrentLocationProvider>) -> Self {
        Self { provider }
    }

    /// Run one user-initiated location request (blocking; call off the UI thread).
    pub fn detect_once(&self, timeout: Duration) -> CurrentLocationResult {
        let failure = |status, message: &str| CurrentLocationResult {
            status,
            message: message.to_string(),
            coordinates: None,
            location: None,
        };
        match self.provider.detect(timeout) {
            Ok(coordinates) => CurrentLocationResult {
                status: LocationDetectionStatus::Success,
                message: "Current location detected. Review the editable name before saving."
                    .into(),
                coordinates: Some(coordinates),
                location: Some(location_from_coordinates(coordinates, None)),
            },
            Err(DetectError::Known(status, message)) => failure(status, &message),
            Err(DetectError::Timeout) => failure(
                LocationDetectionStatus::Timeout,
                "Current location detection timed out. You can still search manually.",
            ),
            Err(DetectError::Failed(reason)) => {
                tracing::debug!("Current location detection failed unexpectedly: {reason}");
                failure(
                    LocationDetectionStatus::Unavailable,
                    "Current location is unavailable. You can still search manually.",
                )
            }
        }
    }
}

/// Provider used where native location detection is not implemented.
pub struct UnsupportedLocationProvider;

impl CurrentLocationProvider for UnsupportedLocationProvider {
    fn detect(&self, _timeout: Duration) -> Result<CurrentCoordinates, DetectError> {
        Err(DetectError::Known(
            LocationDetectionStatus::Unsupported,
            "Current location detection is not supported on this platform. You can still search manually."
                .into(),
        ))
    }
}

/// The provider for this platform.
pub fn native_provider() -> Box<dyn CurrentLocationProvider> {
    #[cfg(windows)]
    {
        Box::new(windows_provider::WindowsLocationProvider)
    }
    #[cfg(target_os = "macos")]
    {
        Box::new(macos_provider::MacOSLocationProvider)
    }
    #[cfg(not(any(windows, target_os = "macos")))]
    {
        Box::new(UnsupportedLocationProvider)
    }
}

#[cfg(windows)]
pub use windows_provider::WindowsLocationProvider;

#[cfg(target_os = "macos")]
pub use macos_provider::MacOSLocationProvider;

/// Platform-independent half of `MacOSLocationProvider`: what each delegate
/// callback means for the one-shot request, and the run-loop wait.
#[cfg(any(target_os = "macos", test))]
mod core_location {
    use std::time::{Duration, Instant};

    use super::{CurrentCoordinates, DetectError, LocationDetectionStatus};

    pub const TIMEOUT_MESSAGE: &str =
        "macOS location detection timed out. You can still search manually.";

    /// Longest stretch the run loop runs before the outcome is checked again.
    pub const SLICE: Duration = Duration::from_millis(100);

    /// A `CLLocationManagerDelegate` callback.
    #[derive(Debug, Clone, Copy, PartialEq)]
    pub enum Event {
        Located {
            latitude: f64,
            longitude: f64,
            horizontal_accuracy: f64,
        },
        Failed,
        /// Raw `CLAuthorizationStatus`.
        Authorization(i32),
    }

    /// Python's `_LocationDelegate`: the request's outcome for a callback,
    /// `None` to keep waiting.
    pub fn outcome(event: Event) -> Option<Result<CurrentCoordinates, DetectError>> {
        match event {
            Event::Located {
                latitude,
                longitude,
                horizontal_accuracy,
            } => Some(Ok(CurrentCoordinates {
                latitude,
                longitude,
                // CoreLocation reports a negative accuracy when it is unknown.
                accuracy_meters: (horizontal_accuracy >= 0.0).then_some(horizontal_accuracy),
            })),
            Event::Failed => Some(Err(DetectError::Known(
                LocationDetectionStatus::Unavailable,
                "macOS could not detect your current location. You can still search manually."
                    .into(),
            ))),
            // kCLAuthorizationStatusRestricted, kCLAuthorizationStatusDenied
            Event::Authorization(1 | 2) => Some(Err(DetectError::Known(
                LocationDetectionStatus::Denied,
                "Location permission was denied. You can still search manually.".into(),
            ))),
            Event::Authorization(_) => None,
        }
    }

    /// Run the run loop in slices until `outcome` yields, or `None` once
    /// `timeout` has passed.
    pub fn pump_until<T>(
        timeout: Duration,
        mut run_slice: impl FnMut(Duration),
        mut outcome: impl FnMut() -> Option<T>,
    ) -> Option<T> {
        let deadline = Instant::now() + timeout;
        loop {
            if let Some(found) = outcome() {
                return Some(found);
            }
            let left = deadline.saturating_duration_since(Instant::now());
            if left.is_zero() {
                return None;
            }
            run_slice(left.min(SLICE));
        }
    }
}

#[cfg(target_os = "macos")]
mod macos_provider {
    use std::cell::RefCell;
    use std::time::Duration;

    use objc2::rc::{autoreleasepool, Retained};
    use objc2::runtime::ProtocolObject;
    use objc2::{define_class, msg_send, AnyThread, DefinedClass};
    use objc2_core_location::{CLLocation, CLLocationManager, CLLocationManagerDelegate};
    use objc2_foundation::{
        NSArray, NSDate, NSDefaultRunLoopMode, NSError, NSObject, NSObjectProtocol, NSPort,
        NSRunLoop,
    };

    use super::core_location::{outcome, pump_until, Event, TIMEOUT_MESSAGE};
    use super::{
        CurrentCoordinates, CurrentLocationProvider, DetectError, LocationDetectionStatus,
    };

    /// One-shot CoreLocation provider.
    pub struct MacOSLocationProvider;

    struct DelegateIvars {
        outcome: RefCell<Option<Result<CurrentCoordinates, DetectError>>>,
    }

    define_class!(
        // SAFETY: NSObject has no subclassing requirements and the class
        // does not implement Drop.
        #[unsafe(super(NSObject))]
        #[name = "AccessiWeatherLocationDelegate"]
        #[ivars = DelegateIvars]
        struct LocationDelegate;

        unsafe impl NSObjectProtocol for LocationDelegate {}

        unsafe impl CLLocationManagerDelegate for LocationDelegate {
            #[unsafe(method(locationManager:didUpdateLocations:))]
            fn did_update_locations(
                &self,
                manager: &CLLocationManager,
                locations: &NSArray<CLLocation>,
            ) {
                if let Some(latest) = locations.lastObject() {
                    // SAFETY: plain property reads on a location CoreLocation handed us.
                    let (coordinate, accuracy) =
                        unsafe { (latest.coordinate(), latest.horizontalAccuracy()) };
                    self.record(Event::Located {
                        latitude: coordinate.latitude,
                        longitude: coordinate.longitude,
                        horizontal_accuracy: accuracy,
                    });
                }
                // SAFETY: called on the manager's own run-loop thread.
                unsafe { manager.stopUpdatingLocation() };
            }

            #[unsafe(method(locationManager:didFailWithError:))]
            fn did_fail(&self, manager: &CLLocationManager, _error: &NSError) {
                self.record(Event::Failed);
                // SAFETY: as above.
                unsafe { manager.stopUpdatingLocation() };
            }

            #[unsafe(method(locationManagerDidChangeAuthorization:))]
            fn did_change_authorization(&self, manager: &CLLocationManager) {
                // SAFETY: as above.
                let status = unsafe { manager.authorizationStatus() };
                self.record(Event::Authorization(status.0));
            }
        }
    );

    impl LocationDelegate {
        fn new() -> Retained<Self> {
            let this = Self::alloc().set_ivars(DelegateIvars {
                outcome: RefCell::new(None),
            });
            // SAFETY: NSObject's designated initializer.
            unsafe { msg_send![super(this), init] }
        }

        /// The first decisive callback wins, like Python's `future.done()` guard.
        fn record(&self, event: Event) {
            let mut slot = self.ivars().outcome.borrow_mut();
            if slot.is_none() {
                *slot = outcome(event);
            }
        }
    }

    impl CurrentLocationProvider for MacOSLocationProvider {
        fn detect(&self, timeout: Duration) -> Result<CurrentCoordinates, DetectError> {
            autoreleasepool(|_| {
                // CoreLocation calls the delegate on the run loop of the thread
                // that created the manager, so create it here and run this
                // thread's run loop until the answer arrives.
                let delegate = LocationDelegate::new();
                let run_loop = NSRunLoop::currentRunLoop();
                // A worker thread's run loop has no input sources, so
                // `runUntilDate:` would return at once and spin; a port keeps
                // it waiting between callbacks.
                let keep_alive = NSPort::port();
                // SAFETY: CLLocationManager may be used from any thread with
                // a run loop; the delegate (held weakly by the manager) lives
                // until after it is cleared below.
                let manager = unsafe {
                    let manager = CLLocationManager::new();
                    manager.setDelegate(Some(ProtocolObject::from_ref(&*delegate)));
                    manager.requestWhenInUseAuthorization();
                    manager.requestLocation();
                    run_loop.addPort_forMode(&keep_alive, NSDefaultRunLoopMode);
                    manager
                };
                let result = pump_until(
                    timeout,
                    |slice| {
                        run_loop.runUntilDate(&NSDate::dateWithTimeIntervalSinceNow(
                            slice.as_secs_f64(),
                        ))
                    },
                    || delegate.ivars().outcome.borrow_mut().take(),
                );
                // SAFETY: same thread and objects as above.
                unsafe {
                    run_loop.removePort_forMode(&keep_alive, NSDefaultRunLoopMode);
                    manager.stopUpdatingLocation();
                    manager.setDelegate(None);
                }
                result.unwrap_or_else(|| {
                    Err(DetectError::Known(
                        LocationDetectionStatus::Timeout,
                        TIMEOUT_MESSAGE.into(),
                    ))
                })
            })
        }
    }
}

#[cfg(windows)]
mod windows_provider {
    use std::sync::mpsc;
    use std::time::Duration;

    use windows::Devices::Geolocation::{GeolocationAccessStatus, Geolocator, PositionAccuracy};
    use windows_future::IAsyncOperation;

    use super::{
        CurrentCoordinates, CurrentLocationProvider, DetectError, LocationDetectionStatus,
    };

    /// One-shot Windows Location Services provider.
    pub struct WindowsLocationProvider;

    fn failed(e: windows::core::Error) -> DetectError {
        DetectError::Failed(e.to_string())
    }

    /// Wait for a WinRT operation, cancelling it on timeout (`None`).
    fn wait<T>(op: IAsyncOperation<T>, timeout: Duration) -> Result<Option<T>, DetectError>
    where
        T: windows::core::RuntimeType + Send + 'static,
    {
        let (tx, rx) = mpsc::channel();
        op.when(move |result| {
            let _ = tx.send(result);
        })
        .map_err(failed)?;
        match rx.recv_timeout(timeout) {
            Ok(result) => result.map(Some).map_err(failed),
            Err(_) => {
                let _ = op.Cancel();
                Ok(None)
            }
        }
    }

    impl CurrentLocationProvider for WindowsLocationProvider {
        fn detect(&self, timeout: Duration) -> Result<CurrentCoordinates, DetectError> {
            let access = wait(Geolocator::RequestAccessAsync().map_err(failed)?, timeout)?
                .ok_or_else(|| {
                    DetectError::Known(
                        LocationDetectionStatus::Timeout,
                        "Windows Location Services did not respond. You can still search manually."
                            .into(),
                    )
                })?;
            if access != GeolocationAccessStatus::Allowed {
                return Err(DetectError::Known(
                    LocationDetectionStatus::Denied,
                    "Location permission was denied. You can still search manually.".into(),
                ));
            }

            let locator = Geolocator::new().map_err(failed)?;
            locator
                .SetDesiredAccuracy(PositionAccuracy::Default)
                .map_err(failed)?;
            let position = wait(locator.GetGeopositionAsync().map_err(failed)?, timeout)?
                .ok_or_else(|| {
                    DetectError::Known(
                        LocationDetectionStatus::Timeout,
                        "Windows Location Services timed out. You can still search manually."
                            .into(),
                    )
                })?;

            let no_coordinates = || {
                DetectError::Known(
                    LocationDetectionStatus::Unavailable,
                    "Windows Location Services returned no coordinates. You can still search manually."
                        .into(),
                )
            };
            let coordinate = position.Coordinate().map_err(|_| no_coordinates())?;
            let point = coordinate
                .Point()
                .and_then(|p| p.Position())
                .map_err(|_| no_coordinates())?;
            Ok(CurrentCoordinates {
                latitude: point.Latitude,
                longitude: point.Longitude,
                accuracy_meters: coordinate.Accuracy().ok(),
            })
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    struct Fixed(Result<CurrentCoordinates, DetectError>);

    impl CurrentLocationProvider for Fixed {
        fn detect(&self, _timeout: Duration) -> Result<CurrentCoordinates, DetectError> {
            self.0.clone()
        }
    }

    fn service(result: Result<CurrentCoordinates, DetectError>) -> CurrentLocationService {
        CurrentLocationService::new(Box::new(Fixed(result)))
    }

    #[test]
    fn unsupported_provider_reports_manual_fallback() {
        let r = CurrentLocationService::new(Box::new(UnsupportedLocationProvider))
            .detect_once(DEFAULT_TIMEOUT);
        assert_eq!(r.status, LocationDetectionStatus::Unsupported);
        assert_eq!(
            r.message,
            "Current location detection is not supported on this platform. You can still search manually."
        );
    }

    #[test]
    fn failures_are_normalized() {
        let r = service(Err(DetectError::Timeout)).detect_once(DEFAULT_TIMEOUT);
        assert_eq!(r.status, LocationDetectionStatus::Timeout);
        assert_eq!(
            r.message,
            "Current location detection timed out. You can still search manually."
        );
        let r = service(Err(DetectError::Failed("boom".into()))).detect_once(DEFAULT_TIMEOUT);
        assert_eq!(r.status, LocationDetectionStatus::Unavailable);
        assert_eq!(
            r.message,
            "Current location is unavailable. You can still search manually."
        );
        let denied = DetectError::Known(LocationDetectionStatus::Denied, "no".into());
        assert_eq!(
            service(Err(denied)).detect_once(DEFAULT_TIMEOUT).message,
            "no"
        );
    }

    #[test]
    fn coordinates_become_an_editable_location() {
        let coords = CurrentCoordinates {
            latitude: 40.7128,
            longitude: -74.006,
            accuracy_meters: Some(25.0),
        };
        let r = service(Ok(coords)).detect_once(DEFAULT_TIMEOUT);
        assert_eq!(r.status, LocationDetectionStatus::Success);
        assert_eq!(
            r.message,
            "Current location detected. Review the editable name before saving."
        );
        let location = r.location.unwrap();
        assert_eq!(location.name, "Current Location (40.7128, -74.0060)");
        assert_eq!(location.country_code.as_deref(), Some("US"));

        let toronto = CurrentCoordinates {
            latitude: 43.65,
            longitude: -79.38,
            accuracy_meters: None,
        };
        assert_eq!(location_from_coordinates(toronto, None).country_code, None);
    }

    #[test]
    fn core_location_callbacks_map_like_python() {
        use core_location::{outcome, Event};
        let located = |horizontal_accuracy| Event::Located {
            latitude: 39.9526,
            longitude: -75.1652,
            horizontal_accuracy,
        };
        let coords = outcome(located(15.0)).unwrap().unwrap();
        assert_eq!((coords.latitude, coords.longitude), (39.9526, -75.1652));
        assert_eq!(coords.accuracy_meters, Some(15.0));
        let unknown = outcome(located(-1.0)).unwrap().unwrap();
        assert_eq!(unknown.accuracy_meters, None);

        assert_eq!(
            outcome(Event::Failed),
            Some(Err(DetectError::Known(
                LocationDetectionStatus::Unavailable,
                "macOS could not detect your current location. You can still search manually."
                    .into()
            )))
        );
        let denied = Some(Err(DetectError::Known(
            LocationDetectionStatus::Denied,
            "Location permission was denied. You can still search manually.".into(),
        )));
        // Restricted and Denied refuse; NotDetermined and the granted states keep waiting.
        assert_eq!(outcome(Event::Authorization(1)), denied);
        assert_eq!(outcome(Event::Authorization(2)), denied);
        for waiting in [0, 3, 4] {
            assert_eq!(outcome(Event::Authorization(waiting)), None);
        }
    }

    #[test]
    fn core_location_wait_stops_at_the_answer_or_the_timeout() {
        use core_location::{pump_until, SLICE};
        use std::time::Instant;

        let slices = std::cell::Cell::new(0);
        let found = pump_until(
            DEFAULT_TIMEOUT,
            |_| slices.set(slices.get() + 1),
            || (slices.get() == 3).then_some("x"),
        );
        assert_eq!((found, slices.get()), (Some("x"), 3));

        let timeout = Duration::from_millis(120);
        let start = Instant::now();
        let mut longest = Duration::ZERO;
        let never = pump_until(
            timeout,
            |slice| {
                longest = longest.max(slice);
                std::thread::sleep(slice);
            },
            || None::<()>,
        );
        assert_eq!(never, None);
        assert!(start.elapsed() >= timeout);
        assert!(longest <= SLICE);
        assert_eq!(
            core_location::TIMEOUT_MESSAGE,
            "macOS location detection timed out. You can still search manually."
        );
    }
}
