//! Ordering of saved locations for user-facing lists. Ported from
//! `accessiweather.location_sorting`.

use std::cmp::Ordering;

use crate::location::Location;

pub const LOCATION_SORT_ALPHABETICAL: &str = "alphabetical";
pub const LOCATION_SORT_MANUAL: &str = "manual";
pub const LOCATION_SORT_NEAREST_CURRENT: &str = "nearest_current";

/// `normalize_location_sort_order`: anything unknown means alphabetical.
pub fn normalize_location_sort_order(value: Option<&str>) -> &'static str {
    match value {
        Some(LOCATION_SORT_MANUAL) => LOCATION_SORT_MANUAL,
        Some(LOCATION_SORT_NEAREST_CURRENT) => LOCATION_SORT_NEAREST_CURRENT,
        _ => LOCATION_SORT_ALPHABETICAL,
    }
}

/// `location_name_sort_key`: case-insensitive, ties broken by the raw name.
fn name_order(a: &Location, b: &Location) -> Ordering {
    // ponytail: to_lowercase stands in for Python's casefold (differs only
    // for a few non-ASCII letters such as ß).
    (a.name.to_lowercase(), &a.name).cmp(&(b.name.to_lowercase(), &b.name))
}

/// `sort_locations_for_display`.
pub fn sort_locations_for_display(
    locations: &[Location],
    sort_order: Option<&str>,
    anchor: Option<&Location>,
) -> Vec<Location> {
    let order = normalize_location_sort_order(sort_order);
    let mut sorted = locations.to_vec();
    if order == LOCATION_SORT_MANUAL {
        return sorted;
    }
    sorted.sort_by(name_order);
    if let (LOCATION_SORT_NEAREST_CURRENT, Some(anchor)) = (order, anchor) {
        sorted.sort_by(|a, b| {
            distance_miles(anchor, a)
                .total_cmp(&distance_miles(anchor, b))
                .then_with(|| name_order(a, b))
        });
    }
    sorted
}

/// Great-circle distance in miles (`_distance_miles`).
fn distance_miles(first: &Location, second: &Location) -> f64 {
    const EARTH_RADIUS_MILES: f64 = 3958.7613;
    let lat1 = first.latitude.to_radians();
    let lat2 = second.latitude.to_radians();
    let delta_lat = (second.latitude - first.latitude).to_radians();
    let delta_lon = (second.longitude - first.longitude).to_radians();
    let a =
        (delta_lat / 2.0).sin().powi(2) + lat1.cos() * lat2.cos() * (delta_lon / 2.0).sin().powi(2);
    let c = 2.0 * a.sqrt().atan2((1.0 - a).max(0.0).sqrt());
    EARTH_RADIUS_MILES * c
}
