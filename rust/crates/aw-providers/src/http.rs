use std::collections::HashMap;
use std::sync::Mutex;
use std::time::Duration;

use serde::{Deserialize, Serialize};
use serde_json::Value;

pub const USER_AGENT: &str = concat!(
    "AccessiWeather/",
    env!("CARGO_PKG_VERSION"),
    " (https://github.com/Orinks/AccessiWeather; native Rust client)"
);

const CONNECT_TIMEOUT: Duration = Duration::from_secs(3);
const REQUEST_TIMEOUT: Duration = Duration::from_secs(10);
const MAX_ATTEMPTS: u32 = 3;

#[derive(Debug, Clone, thiserror::Error)]
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

impl HttpError {
    /// `utils.retry_utils.is_retryable_http_error`: transport failures and
    /// 5xx/408/409/425/429 responses are worth another attempt.
    pub fn is_retryable(&self) -> bool {
        match self {
            HttpError::Transport { .. } => true,
            HttpError::Status { status, .. } => retryable_status(*status),
            HttpError::Json { .. } | HttpError::MissingFixture(_) => false,
        }
    }
}

/// One GET exactly as the Python `httpx` call issues it: query parameters
/// and headers in the order Python builds them.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct HttpRequest {
    pub url: String,
    #[serde(default)]
    pub params: Vec<(String, String)>,
    #[serde(default)]
    pub headers: Vec<(String, String)>,
}

impl HttpRequest {
    pub fn new(url: impl Into<String>) -> Self {
        Self {
            url: url.into(),
            ..Default::default()
        }
    }

    pub fn header(mut self, name: &str, value: impl Into<String>) -> Self {
        self.headers.push((name.to_string(), value.into()));
        self
    }

    pub fn param(mut self, name: &str, value: impl Into<String>) -> Self {
        self.params.push((name.to_string(), value.into()));
        self
    }

    /// The URL with the query string appended (form-encoded like httpx).
    pub fn full_url(&self) -> String {
        if self.params.is_empty() {
            return self.url.clone();
        }
        let query = url::form_urlencoded::Serializer::new(String::new())
            .extend_pairs(&self.params)
            .finish();
        let sep = if self.url.contains('?') { '&' } else { '?' };
        format!("{}{sep}{query}", self.url)
    }
}

/// A response with its status left unchecked, like an `httpx.Response`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct HttpResponse {
    pub url: String,
    pub status: u16,
    pub body: String,
}

impl HttpResponse {
    pub fn is_success(&self) -> bool {
        (200..300).contains(&self.status)
    }

    /// `raise_for_status()`: any non-2xx status is an error.
    pub fn error_for_status(&self) -> Result<&Self, HttpError> {
        if self.is_success() {
            Ok(self)
        } else {
            Err(HttpError::Status {
                url: self.url.clone(),
                status: self.status,
            })
        }
    }

    pub fn json(&self) -> Result<Value, HttpError> {
        serde_json::from_str(&self.body).map_err(|e| HttpError::Json {
            url: self.url.clone(),
            message: e.to_string(),
        })
    }
}

/// Minimal blocking HTTP abstraction.
pub trait HttpClient: Send + Sync {
    /// JSON GET with the client's own retries and headers.
    fn get_json(&self, url: &str) -> Result<Value, HttpError>;

    /// A single GET with exactly the given headers and parameters: no
    /// retries and no status check (callers decide, as the Python code does).
    fn send(&self, req: &HttpRequest) -> Result<HttpResponse, HttpError> {
        let url = req.full_url();
        match self.get_json(&url) {
            Ok(v) => Ok(HttpResponse {
                url,
                status: 200,
                body: v.to_string(),
            }),
            Err(HttpError::Status { status, .. }) => Ok(HttpResponse {
                url,
                status,
                body: String::new(),
            }),
            Err(e) => Err(e),
        }
    }
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

    fn send(&self, req: &HttpRequest) -> Result<HttpResponse, HttpError> {
        let url = req.full_url();
        // Report the bare URL: query strings can carry API keys (AVWX).
        let transport = |e: reqwest::Error| HttpError::Transport {
            url: req.url.clone(),
            message: e.without_url().to_string(),
        };
        let mut builder = self.inner.get(&req.url).query(&req.params);
        for (name, value) in &req.headers {
            builder = builder.header(name.as_str(), value.as_str());
        }
        let resp = builder.send().map_err(transport)?;
        let status = resp.status().as_u16();
        let body = resp.text().map_err(transport)?;
        Ok(HttpResponse { url, status, body })
    }
}

#[derive(Debug, Clone)]
enum Fixture {
    Response { status: u16, body: String },
    TransportError,
}

/// Offline client that serves canned responses keyed by URL prefix (the
/// longest registered prefix of the full URL, query included, wins).
/// Used by tests and by `--smoke` runs so the app can be exercised without
/// network access.
#[derive(Default)]
pub struct FixtureClient {
    fixtures: Mutex<Vec<(String, Fixture)>>,
    pub requests: Mutex<Vec<String>>,
    sent: Mutex<Vec<HttpRequest>>,
}

impl FixtureClient {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn with(self, url_prefix: &str, body: Value) -> Self {
        self.with_response(url_prefix, 200, &body.to_string())
    }

    pub fn with_response(self, url_prefix: &str, status: u16, body: &str) -> Self {
        let fixture = Fixture::Response {
            status,
            body: body.to_string(),
        };
        self.fixtures
            .lock()
            .unwrap()
            .push((url_prefix.to_string(), fixture));
        self
    }

    /// Requests matching `url_prefix` fail as if the connection dropped.
    pub fn with_transport_error(self, url_prefix: &str) -> Self {
        self.fixtures
            .lock()
            .unwrap()
            .push((url_prefix.to_string(), Fixture::TransportError));
        self
    }

    pub fn request_log(&self) -> Vec<String> {
        self.requests.lock().unwrap().clone()
    }

    /// Every [`HttpClient::send`] call, with its headers and parameters.
    pub fn sent_requests(&self) -> Vec<HttpRequest> {
        self.sent.lock().unwrap().clone()
    }

    pub fn from_map(map: HashMap<String, Value>) -> Self {
        map.into_iter()
            .fold(Self::default(), |client, (prefix, body)| {
                client.with(&prefix, body)
            })
    }

    fn lookup(&self, url: &str) -> Result<HttpResponse, HttpError> {
        self.requests.lock().unwrap().push(url.to_string());
        let fixtures = self.fixtures.lock().unwrap();
        let fixture = fixtures
            .iter()
            .filter(|(prefix, _)| url.starts_with(prefix.as_str()))
            .max_by_key(|(prefix, _)| prefix.len())
            .map(|(_, f)| f.clone())
            .ok_or_else(|| HttpError::MissingFixture(url.to_string()))?;
        match fixture {
            Fixture::Response { status, body } => Ok(HttpResponse {
                url: url.to_string(),
                status,
                body,
            }),
            Fixture::TransportError => Err(HttpError::Transport {
                url: url.to_string(),
                message: "simulated connection failure".into(),
            }),
        }
    }
}

impl HttpClient for FixtureClient {
    fn get_json(&self, url: &str) -> Result<Value, HttpError> {
        let resp = self.lookup(url)?;
        if resp.status >= 400 {
            return Err(HttpError::Status {
                url: url.to_string(),
                status: resp.status,
            });
        }
        resp.json()
    }

    fn send(&self, req: &HttpRequest) -> Result<HttpResponse, HttpError> {
        self.sent.lock().unwrap().push(req.clone());
        self.lookup(&req.full_url())
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
