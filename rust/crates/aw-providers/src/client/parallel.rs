//! Parallel multi-source fetch. Port of
//! `accessiweather/weather_client_parallel.py` (`ParallelFetchCoordinator`).

use std::sync::mpsc;
use std::time::{Duration, Instant};

use aw_core::model::SourceData;
use chrono::{DateTime, Utc};

use super::sources::SourceResult;

/// One source's fetch; returns the source's data (its `source`,
/// `fetch_time` and `success` fields are filled in by the coordinator).
pub type SourceFetch = Box<dyn FnOnce() -> SourceResult<SourceData> + Send + 'static>;

/// Runs source fetches concurrently, each bounded by `timeout`. A source that
/// fails or times out becomes an unsuccessful `SourceData` instead of
/// failing the whole fetch.
#[derive(Debug, Clone, Copy)]
pub struct ParallelFetchCoordinator {
    pub timeout: Duration,
}

impl ParallelFetchCoordinator {
    pub fn new(timeout_seconds: f64) -> Self {
        Self {
            timeout: Duration::from_secs_f64(timeout_seconds.max(0.0)),
        }
    }

    /// Results come back in the order of `fetches`. A timed-out fetch keeps
    /// running on its own thread; its late result is dropped.
    pub fn fetch_all(
        &self,
        fetches: Vec<(String, SourceFetch)>,
        now: DateTime<Utc>,
    ) -> Vec<SourceData> {
        let (tx, rx) = mpsc::channel();
        let names: Vec<String> = fetches.iter().map(|(name, _)| name.clone()).collect();
        for (index, (name, fetch)) in fetches.into_iter().enumerate() {
            let thread_tx = tx.clone();
            let spawned = std::thread::Builder::new()
                .name(format!("aw-fetch-{name}"))
                .spawn(move || {
                    let _ = thread_tx.send((index, fetch()));
                });
            if let Err(e) = spawned {
                let _ = tx.send((index, Err(super::SourceError::new(e.to_string()))));
            }
        }
        drop(tx);

        let deadline = Instant::now() + self.timeout;
        let mut results: Vec<Option<SourceResult<SourceData>>> =
            names.iter().map(|_| None).collect();
        while results.iter().any(Option::is_none) {
            match rx.recv_timeout(deadline.saturating_duration_since(Instant::now())) {
                Ok((index, result)) => results[index] = Some(result),
                Err(_) => break,
            }
        }

        let fetch_time = now.fixed_offset();
        names
            .into_iter()
            .zip(results)
            .map(|(name, result)| match result {
                Some(Ok(data)) => SourceData {
                    source: name,
                    fetch_time,
                    success: true,
                    error: None,
                    ..data
                },
                Some(Err(e)) => {
                    tracing::warn!("Source {name} failed: {e}");
                    failed(name, fetch_time, e.to_string())
                }
                None => {
                    tracing::warn!("Source {name} timed out after {:?}", self.timeout);
                    failed(name, fetch_time, "Request timed out".into())
                }
            })
            .collect()
    }
}

fn failed(source: String, fetch_time: aw_core::model::Timestamp, error: String) -> SourceData {
    SourceData {
        fetch_time,
        success: false,
        error: Some(error),
        ..SourceData::new(source)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::client::SourceError;
    use aw_core::model::CurrentConditions;

    fn ok(temp: f64) -> SourceFetch {
        Box::new(move || {
            Ok(SourceData {
                current: Some(CurrentConditions {
                    temperature_f: Some(temp),
                    ..Default::default()
                }),
                ..SourceData::new("")
            })
        })
    }

    #[test]
    fn results_keep_order_and_mark_failures() {
        let coordinator = ParallelFetchCoordinator::new(5.0);
        let fetches: Vec<(String, SourceFetch)> = vec![
            ("nws".into(), ok(70.0)),
            (
                "openmeteo".into(),
                Box::new(|| Err(SourceError::new("boom"))),
            ),
            ("pirateweather".into(), ok(72.0)),
        ];
        let results = coordinator.fetch_all(fetches, Utc::now());
        let names: Vec<&str> = results.iter().map(|s| s.source.as_str()).collect();
        assert_eq!(names, ["nws", "openmeteo", "pirateweather"]);
        assert!(results[0].success && results[2].success);
        assert!(!results[1].success);
        assert_eq!(results[1].error.as_deref(), Some("boom"));
        assert!(results[1].current.is_none());
    }

    #[test]
    fn slow_source_times_out() {
        let coordinator = ParallelFetchCoordinator::new(0.05);
        let slow: SourceFetch = Box::new(|| {
            std::thread::sleep(Duration::from_millis(500));
            Ok(SourceData::new(""))
        });
        let results = coordinator.fetch_all(
            vec![("nws".into(), slow), ("openmeteo".into(), ok(1.0))],
            Utc::now(),
        );
        assert!(!results[0].success);
        assert_eq!(results[0].error.as_deref(), Some("Request timed out"));
        assert!(results[1].success);
    }

    #[test]
    fn nothing_to_fetch() {
        assert!(ParallelFetchCoordinator::new(1.0)
            .fetch_all(Vec::new(), Utc::now())
            .is_empty());
    }
}
