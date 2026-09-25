use std::collections::HashMap;
use std::sync::Mutex;
use std::time::Duration;

use serde_json::Value;

pub const USER_AGENT: &str = concat!(
    "AccessiWeather/",
    env!("CARGO_PKG_VERSION"),
    " (https://github.com/Orinks/AccessiWeather; native Rust client)"
);

const CONNECT_TIMEOUT: Duration = Duration::from_secs(3);
const REQUEST_TIMEOUT: Duration = Duration::from_secs(10);
const MAX_ATTEMPTS: u32 = 3;

#[derive(Debug, thiserror::Error)]
pub enum HttpError {
    #[error("request to {url} failed: {message}")]
    Transport { url: String, message: String },
    #[error("{url} returned HTTP {status}")]
    Status { url: String, status: u16 },
    #[error("{url} returned invalid JSON: {message}")]
    Json { url: String, message: String },
    #[error("no fixture registered for {0}")]
    MissingFixture(String),
}

/// Minimal blocking JSON GET abstraction.
pub trait HttpClient: Send + Sync {
    fn get_json(&self, url: &str) -> Result<Value, HttpError>;
}

/// Production client with a shared `reqwest` connection pool, retries with
/// exponential backoff for transient failures and NWS-friendly headers.
pub struct ReqwestClient {
    inner: reqwest::blocking::Client,
}

impl ReqwestClient {
    pub fn new() -> Result<Self, HttpError> {
        let inner = reqwest::blocking::Client::builder()
            .user_agent(USER_AGENT)
            .connect_timeout(CONNECT_TIMEOUT)
            .timeout(REQUEST_TIMEOUT)
            .gzip(true)
            .build()
            .map_err(|e| HttpError::Transport {
                url: String::new(),
                message: e.to_string(),
            })?;
        Ok(Self { inner })
    }
}

fn retryable_status(status: u16) -> bool {
    matches!(status, 408 | 409 | 425 | 429) || status >= 500
}

impl HttpClient for ReqwestClient {
    fn get_json(&self, url: &str) -> Result<Value, HttpError> {
        let mut last = None;
        for attempt in 0..MAX_ATTEMPTS {
            if attempt > 0 {
                std::thread::sleep(Duration::from_millis(250 * (1 << attempt)));
            }
            let result = self
                .inner
                .get(url)
                .header("Accept", "application/geo+json, application/json")
                .send();
            match result {
                Ok(resp) => {
                    let status = resp.status().as_u16();
                    if status >= 400 {
                        let err = HttpError::Status {
                            url: url.to_string(),
                            status,
                        };
                        if retryable_status(status) {
                            tracing::warn!("{err}; retrying");
                            last = Some(err);
                            continue;
                        }
                        return Err(err);
                    }
                    return resp.json::<Value>().map_err(|e| HttpError::Json {
                        url: url.to_string(),
                        message: e.to_string(),
                    });
                }
                Err(e) => {
                    let err = HttpError::Transport {
                        url: url.to_string(),
                        message: e.to_string(),
                    };
                    if e.is_timeout() || e.is_connect() || e.is_request() {
                        tracing::warn!("{err}; retrying");
                        last = Some(err);
                        continue;
                    }
                    return Err(err);
                }
            }
        }
        Err(last.unwrap_or_else(|| HttpError::Transport {
            url: url.to_string(),
            message: "retries exhausted".into(),
        }))
    }
}

/// Offline client that serves canned responses keyed by URL prefix.
/// Used by tests and by `--smoke` runs so the app can be exercised without
/// network access.
#[derive(Default)]
pub struct FixtureClient {
    fixtures: Mutex<Vec<(String, Value)>>,
    pub requests: Mutex<Vec<String>>,
}

impl FixtureClient {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn with(self, url_prefix: &str, body: Value) -> Self {
        self.fixtures
            .lock()
            .unwrap()
            .push((url_prefix.to_string(), body));
        self
    }

    pub fn request_log(&self) -> Vec<String> {
        self.requests.lock().unwrap().clone()
    }

    pub fn from_map(map: HashMap<String, Value>) -> Self {
        Self {
            fixtures: Mutex::new(map.into_iter().collect()),
            requests: Mutex::new(Vec::new()),
        }
    }
}

impl HttpClient for FixtureClient {
    fn get_json(&self, url: &str) -> Result<Value, HttpError> {
        self.requests.lock().unwrap().push(url.to_string());
        let fixtures = self.fixtures.lock().unwrap();
        fixtures
            .iter()
            .filter(|(prefix, _)| url.starts_with(prefix.as_str()))
            .max_by_key(|(prefix, _)| prefix.len())
            .map(|(_, body)| body.clone())
            .ok_or_else(|| HttpError::MissingFixture(url.to_string()))
    }
}

/// Fetch and deserialize JSON into a typed struct.
pub fn get_typed<T: serde::de::DeserializeOwned>(
    client: &dyn HttpClient,
    url: &str,
) -> Result<T, HttpError> {
    let value = client.get_json(url)?;
    serde_json::from_value(value).map_err(|e| HttpError::Json {
        url: url.to_string(),
        message: e.to_string(),
    })
}
