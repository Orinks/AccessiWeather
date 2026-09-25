//! One-time "Use my current location" detection, ported from
//! `accessiweather.current_location`. Windows uses Windows Location Services
//! (WinRT `Geolocator`); other platforms report "unsupported" (see the port
//! notes: the macOS CoreLocation provider is not implemented yet).

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
                message: "Current location detected. Review the editable name before saving.".into(),
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
    #[cfg(not(windows))]
    {
        Box::new(UnsupportedLocationProvider)
    }
}

#[cfg(windows)]
pub use windows_provider::WindowsLocationProvider;

#[cfg(windows)]
mod windows_provider {
    use std::sync::mpsc;
    use std::time::Duration;

    use windows::Devices::Geolocation::{GeolocationAccessStatus, Geolocator, PositionAccuracy};
    use windows_future::IAsyncOperation;

    use super::{CurrentCoordinates, CurrentLocationProvider, DetectError, LocationDetectionStatus};

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
        let r = CurrentLocationService::new(Box::new(UnsupportedLocationProvider)).detect_once(DEFAULT_TIMEOUT);
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
        assert_eq!(r.message, "Current location detection timed out. You can still search manually.");
        let r = service(Err(DetectError::Failed("boom".into()))).detect_once(DEFAULT_TIMEOUT);
        assert_eq!(r.status, LocationDetectionStatus::Unavailable);
        assert_eq!(r.message, "Current location is unavailable. You can still search manually.");
        let denied = DetectError::Known(LocationDetectionStatus::Denied, "no".into());
        assert_eq!(service(Err(denied)).detect_once(DEFAULT_TIMEOUT).message, "no");
    }

    #[test]
    fn coordinates_become_an_editable_location() {
        let coords = CurrentCoordinates { latitude: 40.7128, longitude: -74.006, accuracy_meters: Some(25.0) };
        let r = service(Ok(coords)).detect_once(DEFAULT_TIMEOUT);
        assert_eq!(r.status, LocationDetectionStatus::Success);
        assert_eq!(r.message, "Current location detected. Review the editable name before saving.");
        let location = r.location.unwrap();
        assert_eq!(location.name, "Current Location (40.7128, -74.0060)");
        assert_eq!(location.country_code.as_deref(), Some("US"));

        let toronto = CurrentCoordinates { latitude: 43.65, longitude: -79.38, accuracy_meters: None };
        assert_eq!(location_from_coordinates(toronto, None).country_code, None);
    }
}
