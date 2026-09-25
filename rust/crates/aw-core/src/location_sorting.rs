//! Saved-location ordering, ported from `accessiweather.location_sorting`.

use crate::location::Location;
use crate::py::casefold;

pub const LOCATION_SORT_ALPHABETICAL: &str = "alphabetical";
pub const LOCATION_SORT_MANUAL: &str = "manual";
pub const LOCATION_SORT_NEAREST_CURRENT: &str = "nearest_current";

/// A supported sort order; anything unknown means alphabetical.
pub fn normalize_location_sort_order(value: &str) -> &'static str {
    match value {
        LOCATION_SORT_MANUAL => LOCATION_SORT_MANUAL,
        LOCATION_SORT_NEAREST_CURRENT => LOCATION_SORT_NEAREST_CURRENT,
        _ => LOCATION_SORT_ALPHABETICAL,
    }
}

/// Stable, case-insensitive sort key for saved locations.
pub fn location_name_sort_key(location: &Location) -> (String, String) {
    (casefold(&location.name), location.name.clone())
}

/// Sort saved locations for user-facing lists.
pub fn sort_locations_for_display(
    locations: &[Location],
    sort_order: &str,
    anchor: Option<&Location>,
) -> Vec<Location> {
    let order = normalize_location_sort_order(sort_order);
    let mut sorted = locations.to_vec();
    if order == LOCATION_SORT_MANUAL {
        return sorted;
    }
    sorted.sort_by_cached_key(location_name_sort_key);
    let Some(anchor) = anchor.filter(|_| order == LOCATION_SORT_NEAREST_CURRENT) else {
        return sorted;
    };
    let mut keyed: Vec<(f64, (String, String), Location)> = sorted
        .into_iter()
        .map(|l| (distance_miles(anchor, &l), location_name_sort_key(&l), l))
        .collect();
    keyed.sort_by(|a, b| a.0.total_cmp(&b.0).then_with(|| a.1.cmp(&b.1)));
    keyed.into_iter().map(|(_, _, l)| l).collect()
}

/// Great-circle distance in miles (mean Earth radius 3958.7613 mi).
fn distance_miles(first: &Location, second: &Location) -> f64 {
    let earth_radius_miles = 3958.7613;
    let lat1 = first.latitude.to_radians();
    let lat2 = second.latitude.to_radians();
    let delta_lat = (second.latitude - first.latitude).to_radians();
    let delta_lon = (second.longitude - first.longitude).to_radians();
    let a =
        (delta_lat / 2.0).sin().powi(2) + lat1.cos() * lat2.cos() * (delta_lon / 2.0).sin().powi(2);
    let c = 2.0 * a.sqrt().atan2((1.0 - a).max(0.0).sqrt());
    earth_radius_miles * c
}

#[cfg(test)]
mod tests {
    use super::*;

    fn names(v: &[Location]) -> Vec<&str> {
        v.iter().map(|l| l.name.as_str()).collect()
    }

    #[test]
    fn alphabetical_is_case_insensitive_and_default() {
        let locs = vec![
            Location::new("beta", 0.0, 0.0),
            Location::new("Alpha", 0.0, 0.0),
            Location::new("alpha", 0.0, 0.0),
        ];
        let sorted = sort_locations_for_display(&locs, "bogus", None);
        assert_eq!(names(&sorted), ["Alpha", "alpha", "beta"]);
    }

    #[test]
    fn manual_keeps_order() {
        let locs = vec![Location::new("b", 0.0, 0.0), Location::new("a", 0.0, 0.0)];
        assert_eq!(
            names(&sort_locations_for_display(&locs, "manual", None)),
            ["b", "a"]
        );
    }

    #[test]
    fn nearest_current_orders_by_distance_then_name() {
        let home = Location::new("Home", 40.0, -75.0);
        let locs = vec![
            Location::new("Far", 34.0, -118.0),
            Location::new("Near", 40.1, -75.1),
            Location::new("Home", 40.0, -75.0),
        ];
        let sorted = sort_locations_for_display(&locs, "nearest_current", Some(&home));
        assert_eq!(names(&sorted), ["Home", "Near", "Far"]);
        let sorted = sort_locations_for_display(&locs, "nearest_current", None);
        assert_eq!(names(&sorted), ["Far", "Home", "Near"]);
    }
}
