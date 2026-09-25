//! Lightweight notification poll: alerts, AFD issuance and minutely
//! precipitation only. Port of `accessiweather/weather_client_notification.py`.

use std::collections::HashSet;

use aw_core::alert_aggregator::AlertAggregator;
use aw_core::alert_lifecycle::diff_alerts;
use aw_core::model::{Location, WeatherAlerts, WeatherData};

use super::sources::SourceResult;
use super::{joined, location_key, WeatherClient};

impl WeatherClient {
    /// `get_notification_event_data`: the data the alert/discussion/risk
    /// notifications need, with an alert lifecycle diff against the previous
    /// poll or refresh for this location.
    pub fn get_notification_event_data(&self, location: &Location) -> WeatherData {
        tracing::info!("Fetching notification event data for {}", location.name);
        let mut weather = WeatherData::new(location.clone());
        if let Err(e) = self.notification_poll(location, &mut weather) {
            tracing::error!(
                "Failed to fetch notification event data for {}: {e}",
                location.name
            );
            if weather.alerts.is_none() {
                weather.alerts = Some(WeatherAlerts::default());
            }
        }
        weather
    }

    fn notification_poll(
        &self,
        location: &Location,
        weather: &mut WeatherData,
    ) -> SourceResult<()> {
        let source = self.data_source.as_str();
        let nws_like = matches!(source, "auto" | "nws");
        let pirate_like = matches!(source, "auto" | "pirateweather");
        let pirate = self.sources.pirate_weather.clone().filter(|_| pirate_like);

        if nws_like && self.is_us(location) {
            // Discussion-only so a forecast outage cannot hide AFD updates.
            let radius = &self.settings.alert_radius_type;
            let (discussion, alerts) = std::thread::scope(|scope| {
                let discussion = scope.spawn(|| self.sources.nws.get_discussion_only(location));
                let alerts = scope.spawn(|| self.sources.nws.get_alerts(location, radius));
                (joined(discussion), joined(alerts))
            });
            let (discussion, issuance) = discussion?;
            let alerts = alerts?;
            weather.discussion = discussion;
            weather.discussion_issuance_time = issuance;
            weather.alerts = Some(alerts.unwrap_or_default());
        } else if let Some(pirate) = &pirate {
            let units = self.pirate_units(location);
            let (current, alerts) = std::thread::scope(|scope| {
                let current = scope.spawn(|| pirate.get_current_conditions(location, units));
                let alerts = scope.spawn(|| pirate.get_alerts(location, units));
                (joined(current), joined(alerts))
            });
            weather.current = current?;
            weather.alerts = Some(alerts?.unwrap_or_default());
        } else {
            // Open-Meteo has no alerts.
            weather.alerts = Some(WeatherAlerts::default());
        }

        // Minutely data only when the user wants precipitation notifications,
        // and no more often than the polling cadence allows.
        let settings = &self.settings;
        let wants_minutely = settings.notify_minutely_precipitation_start
            || settings.notify_minutely_precipitation_stop
            || settings.notify_precipitation_likelihood;
        if let Some(pirate) = &pirate {
            if wants_minutely && self.should_fetch_minutely_precipitation(location) {
                weather.minutely_precipitation =
                    pirate.get_minutely(location, self.pirate_units(location));
                let now = self.now();
                self.state()
                    .last_minutely_poll
                    .insert(location_key(location), now);
            }
        }

        // The full auto refresh stores aggregated alerts; store the same
        // shape here or the two paths would diff as phantom changes.
        if source == "auto" {
            if let Some(alerts) = &weather.alerts {
                weather.alerts =
                    Some(AlertAggregator::default().aggregate_alerts(Some(alerts), None));
            }
        }

        let key = location_key(location);
        let previous = self.state().previous_alerts.get(&key).cloned();
        let cancel_ids: HashSet<String> = if nws_like {
            self.sources.nws.fetch_cancel_references(15)
        } else {
            HashSet::new()
        };
        weather.alert_lifecycle_diff = Some(diff_alerts(
            previous.as_ref(),
            weather.alerts.as_ref(),
            Some(&cancel_ids),
            self.now(),
        ));
        if let Some(alerts) = &weather.alerts {
            self.state().previous_alerts.insert(key, alerts.clone());
        }
        Ok(())
    }
}
