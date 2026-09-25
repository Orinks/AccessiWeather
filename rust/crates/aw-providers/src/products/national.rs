//! National forecaster discussions (WPC, SPC, QPF, NHC, CPC) from IEM AFOS
//! text. Port of `services/national_discussion_service.py`; the AI tools and
//! the nationwide forecast handler call this.

use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use chrono::{DateTime, Datelike, Utc};

use super::iem::{AfosQuery, Iem, DEFAULT_IEM_BASE_URL};
use crate::http::HttpClient;

/// Minimum seconds between requests (`MIN_REQUEST_INTERVAL`).
pub const MIN_REQUEST_INTERVAL: Duration = Duration::from_secs(1);
/// `DEFAULT_CACHE_TTL`.
pub const DEFAULT_CACHE_TTL: Duration = Duration::from_secs(3600);

type Group = &'static [(&'static str, &'static str, &'static str)];

/// `IEM_NATIONAL_PRODUCTS`: key, AFOS PIL, title.
const WPC: Group = &[
    ("short_range", "PMDSPD", "Short Range Forecast (Days 1-3)"),
    ("medium_range", "PMDEPD", "Medium Range Forecast (Days 3-7)"),
    ("extended", "PMDET4", "Extended Forecast (Days 8-10)"),
];
const SPC: Group = &[
    ("day1", "SWODY1", "Day 1 Convective Outlook"),
    ("day2", "SWODY2", "Day 2 Convective Outlook"),
    ("day3", "SWODY3", "Day 3 Convective Outlook"),
];
const QPF: Group = &[(
    "qpf",
    "QPFPFD",
    "Quantitative Precipitation Forecast Discussion",
)];
const NHC: Group = &[
    (
        "atlantic_outlook",
        "TWOAT",
        "Atlantic Tropical Weather Outlook",
    ),
    (
        "east_pacific_outlook",
        "TWOEP",
        "East Pacific Tropical Weather Outlook",
    ),
];
const CPC: Group = &[("outlook", "PMDMRD", "CPC 6-10 & 8-14 Day Outlook")];

const OFF_SEASON_TEXT: &str =
    "NHC tropical outlooks are available during hurricane season (June-November).";

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct NationalDiscussion {
    pub key: &'static str,
    pub title: String,
    pub text: String,
}

/// `fetch_all_discussions` result; each group keeps Python's key order.
#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct NationalDiscussions {
    pub wpc: Vec<NationalDiscussion>,
    pub spc: Vec<NationalDiscussion>,
    pub qpf: Vec<NationalDiscussion>,
    pub nhc: Vec<NationalDiscussion>,
    pub cpc: Vec<NationalDiscussion>,
}

/// Look up a discussion's text by key (`result["wpc"]["short_range"]["text"]`).
pub fn text_for<'a>(group: &'a [NationalDiscussion], key: &str) -> Option<&'a str> {
    group.iter().find(|d| d.key == key).map(|d| d.text.as_str())
}

#[derive(Default)]
struct State {
    last_request: Option<Instant>,
    cache: Option<(Instant, NationalDiscussions)>,
}

pub struct NationalDiscussionService {
    http: Arc<dyn HttpClient>,
    pub iem_base: String,
    pub request_delay: Duration,
    pub cache_ttl: Duration,
    state: Mutex<State>,
}

impl NationalDiscussionService {
    pub fn new(http: Arc<dyn HttpClient>) -> Self {
        Self {
            http,
            iem_base: DEFAULT_IEM_BASE_URL.into(),
            request_delay: MIN_REQUEST_INTERVAL,
            cache_ttl: DEFAULT_CACHE_TTL,
            state: Mutex::new(State::default()),
        }
    }

    /// Sleep so requests are at least `request_delay` apart.
    fn rate_limit(&self) {
        let wait = {
            let state = self.state.lock().unwrap();
            state
                .last_request
                .and_then(|last| self.request_delay.checked_sub(last.elapsed()))
        };
        if let Some(wait) = wait.filter(|w| !w.is_zero()) {
            std::thread::sleep(wait);
        }
        self.state.lock().unwrap().last_request = Some(Instant::now());
    }

    fn fetch_group(&self, group: Group, unavailable_text: &str) -> Vec<NationalDiscussion> {
        let iem = Iem {
            http: self.http.as_ref(),
            base: &self.iem_base,
        };
        group
            .iter()
            .map(|(key, pil, title)| {
                self.rate_limit();
                let text = match iem.afos_text(pil, &AfosQuery::default()) {
                    Ok(product) => product.product_text,
                    Err(err) => format!("Error fetching {title}: {err}"),
                };
                NationalDiscussion {
                    key,
                    title: title.to_string(),
                    text: if text.is_empty() {
                        unavailable_text.to_string()
                    } else {
                        text
                    },
                }
            })
            .collect()
    }

    /// WPC short, medium and extended range discussions.
    pub fn fetch_wpc_discussions(&self) -> Vec<NationalDiscussion> {
        self.fetch_group(WPC, "Discussion not available")
    }

    /// SPC day 1-3 convective outlooks.
    pub fn fetch_spc_discussions(&self) -> Vec<NationalDiscussion> {
        self.fetch_group(SPC, "Outlook not available")
    }

    /// WPC QPF discussion.
    pub fn fetch_qpf_discussion(&self) -> Vec<NationalDiscussion> {
        self.fetch_group(QPF, "QPF discussion not available")
    }

    /// NHC Atlantic and East Pacific tropical weather outlooks.
    pub fn fetch_nhc_discussions(&self) -> Vec<NationalDiscussion> {
        self.fetch_group(NHC, "Tropical outlook not available")
    }

    /// CPC 6-10 and 8-14 day outlook discussion.
    pub fn fetch_cpc_discussions(&self) -> Vec<NationalDiscussion> {
        self.fetch_group(CPC, "CPC outlook discussion is currently unavailable.")
    }

    /// Every national discussion, cached for `cache_ttl`. NHC is only
    /// fetched during hurricane season (June-November, UTC).
    pub fn fetch_all_discussions(&self, force_refresh: bool) -> NationalDiscussions {
        self.fetch_all_discussions_at(force_refresh, Utc::now())
    }

    pub fn fetch_all_discussions_at(
        &self,
        force_refresh: bool,
        now: DateTime<Utc>,
    ) -> NationalDiscussions {
        if !force_refresh {
            if let Some((at, cached)) = &self.state.lock().unwrap().cache {
                if at.elapsed() < self.cache_ttl {
                    return cached.clone();
                }
            }
        }
        let mut result = NationalDiscussions {
            wpc: self.fetch_wpc_discussions(),
            spc: self.fetch_spc_discussions(),
            qpf: self.fetch_qpf_discussion(),
            nhc: Vec::new(),
            cpc: self.fetch_cpc_discussions(),
        };
        result.nhc = if is_hurricane_season(now) {
            self.fetch_nhc_discussions()
        } else {
            NHC.iter()
                .map(|(key, _, title)| NationalDiscussion {
                    key,
                    title: title.to_string(),
                    text: OFF_SEASON_TEXT.to_string(),
                })
                .collect()
        };
        self.state.lock().unwrap().cache = Some((Instant::now(), result.clone()));
        result
    }
}

/// Atlantic hurricane season: June through November.
pub fn is_hurricane_season(now: DateTime<Utc>) -> bool {
    (6..=11).contains(&now.month())
}
