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
const JSON_ACCEPT: &str = "application/geo+json, application/json";

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
    /// Python's `is_retryable_http_error`: timeouts, transport failures,
    /// 408/409/425/429 and 5xx responses.
    pub fn is_retryable(&self) -> bool {
        match self {
            HttpError::Transport { .. } => true,
            HttpError::Status { status, .. } => retryable_status(*status),
            HttpError::Json { .. } | HttpError::MissingFixture(_) => false,
        }
    }

    pub fn status(&self) -> Option<u16> {
        match self {
            HttpError::Status { status, .. } => Some(*status),
            _ => None,
        }
    }

    /// Whether a transport failure was a timeout (reqwest reports these as
    /// "operation timed out").
    pub fn is_timeout(&self) -> bool {
        matches!(self, HttpError::Transport { message, .. } if message.contains("timed out"))
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

    /// GET with explicit request headers (User-Agent, Accept) the Python
    /// client sends. Clients that cannot set headers fall back to `get_json`.
    fn get_json_with_headers(
        &self,
        url: &str,
        headers: &[(&str, &str)],
    ) -> Result<Value, HttpError> {
        let _ = headers;
        self.get_json(url)
    }

    /// GET a plain-text body (IEM AFOS text products).
    fn get_text(&self, url: &str) -> Result<String, HttpError> {
        let resp = self.send(&HttpRequest::new(url))?;
        resp.error_for_status()?;
        Ok(resp.body)
    }

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

/// Mask `key=`/`api_key=` query values (the AirNow key travels in the URL)
/// so retry logs never carry credentials.
pub fn redact_secrets(text: &str) -> String {
    static KEY_PARAM: std::sync::LazyLock<regex::Regex> = std::sync::LazyLock::new(|| {
        regex::Regex::new(r"(?i)\b((?:api_?)?key=)[^&\s)]+").expect("valid redaction regex")
    });
    KEY_PARAM.replace_all(text, "${1}***").into_owned()
}

/// Percent-encode like httpx query params: everything except `A-Za-z0-9_.-~`.
pub fn py_quote(text: &str) -> String {
    let mut out = String::with_capacity(text.len());
    for byte in text.bytes() {
        if byte.is_ascii_alphanumeric() || matches!(byte, b'_' | b'.' | b'-' | b'~') {
            out.push(byte as char);
        } else {
            out.push_str(&format!("%{byte:02X}"));
        }
    }
    out
}

/// `base?k=v&...` with params in order, encoded as httpx does.
pub fn build_url(base: &str, params: &[(&str, String)]) -> String {
    if params.is_empty() {
        return base.to_string();
    }
    let query: Vec<String> = params
        .iter()
        .map(|(k, v)| format!("{}={}", py_quote(k), py_quote(v)))
        .collect();
    format!("{base}?{}", query.join("&"))
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

    /// GET with retries on transient failures; `accept` applies unless the
    /// caller passes its own Accept header.
    fn get_with_retry(
        &self,
        url: &str,
        headers: &[(&str, &str)],
        accept: &str,
    ) -> Result<reqwest::blocking::Response, HttpError> {
        let mut last = None;
        for attempt in 0..MAX_ATTEMPTS {
            if attempt > 0 {
                std::thread::sleep(Duration::from_millis(250 * (1 << attempt)));
            }
            let mut request = self.inner.get(url);
            if !headers
                .iter()
                .any(|(k, _)| k.eq_ignore_ascii_case("accept"))
            {
                request = request.header("Accept", accept);
            }
            for (name, value) in headers {
                request = request.header(*name, *value);
            }
            match request.send() {
                Ok(resp) => {
                    let status = resp.status().as_u16();
                    if status >= 400 {
                        let err = HttpError::Status {
                            url: url.to_string(),
                            status,
                        };
                        if retryable_status(status) {
                            tracing::warn!("{}; retrying", redact_secrets(&err.to_string()));
                            last = Some(err);
                            continue;
                        }
                        return Err(err);
                    }
                    return Ok(resp);
                }
                Err(e) => {
                    let err = HttpError::Transport {
                        url: url.to_string(),
                        message: e.to_string(),
                    };
                    if e.is_timeout() || e.is_connect() || e.is_request() {
                        tracing::warn!("{}; retrying", redact_secrets(&err.to_string()));
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

fn retryable_status(status: u16) -> bool {
    matches!(status, 408 | 409 | 425 | 429) || status >= 500
}

impl HttpClient for ReqwestClient {
    fn get_json(&self, url: &str) -> Result<Value, HttpError> {
        self.get_json_with_headers(url, &[])
    }

    fn get_json_with_headers(
        &self,
        url: &str,
        headers: &[(&str, &str)],
    ) -> Result<Value, HttpError> {
        self.get_with_retry(url, headers, JSON_ACCEPT)?
            .json::<Value>()
            .map_err(|e| HttpError::Json {
                url: url.to_string(),
                message: e.to_string(),
            })
    }

    fn get_text(&self, url: &str) -> Result<String, HttpError> {
        self.get_with_retry(url, &[], "*/*")?
            .text()
            .map_err(|e| HttpError::Transport {
                url: url.to_string(),
                message: e.to_string(),
            })
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

/// A canned fixture response.
#[derive(Debug, Clone)]
enum Canned {
    /// 200 with a JSON body (a JSON string is served verbatim by `get_text`).
    Body(Value),
    /// Any status with a raw body.
    Raw {
        status: u16,
        body: String,
    },
    /// An error status with no body.
    Status(u16),
    Transport(String),
}

/// Offline client that serves canned responses keyed by URL prefix (the
/// longest registered prefix of the full URL, query included, wins).
/// Used by tests and by `--smoke` runs so the app can be exercised without
/// network access.
#[derive(Default)]
pub struct FixtureClient {
    fixtures: Mutex<Vec<(String, Canned)>>,
    pub requests: Mutex<Vec<String>>,
    /// Explicit headers sent with each `get_json_with_headers` call.
    pub headers: Mutex<Vec<Vec<(String, String)>>>,
    sent: Mutex<Vec<HttpRequest>>,
}

impl FixtureClient {
    pub fn new() -> Self {
        Self::default()
    }

    fn push(self, url_prefix: &str, canned: Canned) -> Self {
        self.fixtures
            .lock()
            .unwrap()
            .push((url_prefix.to_string(), canned));
        self
    }

    pub fn with(self, url_prefix: &str, body: Value) -> Self {
        self.push(url_prefix, Canned::Body(body))
    }

    /// Answer matching URLs with `status` and a raw `body`.
    pub fn with_response(self, url_prefix: &str, status: u16, body: &str) -> Self {
        self.push(
            url_prefix,
            Canned::Raw {
                status,
                body: body.to_string(),
            },
        )
    }

    /// Answer matching URLs with an HTTP error status.
    pub fn with_status(self, url_prefix: &str, status: u16) -> Self {
        self.push(url_prefix, Canned::Status(status))
    }

    /// Fail matching URLs with a transport error carrying `message`.
    pub fn with_transport_error(self, url_prefix: &str, message: &str) -> Self {
        self.push(url_prefix, Canned::Transport(message.to_string()))
    }

    pub fn request_log(&self) -> Vec<String> {
        self.requests.lock().unwrap().clone()
    }

    pub fn header_log(&self) -> Vec<Vec<(String, String)>> {
        self.headers.lock().unwrap().clone()
    }

    /// Every [`HttpClient::send`] call, with its headers and parameters.
    pub fn sent_requests(&self) -> Vec<HttpRequest> {
        self.sent.lock().unwrap().clone()
    }

    pub fn from_map(map: HashMap<String, Value>) -> Self {
        Self {
            fixtures: Mutex::new(map.into_iter().map(|(k, v)| (k, Canned::Body(v))).collect()),
            ..Self::default()
        }
    }

    fn lookup(&self, url: &str) -> Result<Canned, HttpError> {
        self.requests.lock().unwrap().push(url.to_string());
        let fixtures = self.fixtures.lock().unwrap();
        fixtures
            .iter()
            .filter(|(prefix, _)| url.starts_with(prefix.as_str()))
            .max_by_key(|(prefix, _)| prefix.len())
            .map(|(_, canned)| canned.clone())
            .ok_or_else(|| HttpError::MissingFixture(url.to_string()))
    }
}

impl HttpClient for FixtureClient {
    fn get_json(&self, url: &str) -> Result<Value, HttpError> {
        self.get_json_with_headers(url, &[])
    }

    fn get_json_with_headers(
        &self,
        url: &str,
        headers: &[(&str, &str)],
    ) -> Result<Value, HttpError> {
        self.headers.lock().unwrap().push(
            headers
                .iter()
                .map(|(k, v)| (k.to_string(), v.to_string()))
                .collect(),
        );
        let url_owned = url.to_string();
        match self.lookup(url)? {
            Canned::Body(body) => Ok(body),
            Canned::Raw { status, body } if status < 400 => HttpResponse {
                url: url_owned,
                status,
                body,
            }
            .json(),
            Canned::Raw { status, .. } | Canned::Status(status) => Err(HttpError::Status {
                url: url_owned,
                status,
            }),
            Canned::Transport(message) => Err(HttpError::Transport {
                url: url_owned,
                message,
            }),
        }
    }

    /// String fixtures are served verbatim; anything else as its JSON text.
    fn get_text(&self, url: &str) -> Result<String, HttpError> {
        match self.lookup(url)? {
            Canned::Body(Value::String(text)) => Ok(text),
            Canned::Body(other) => Ok(other.to_string()),
            Canned::Raw { status, body } if status < 400 => Ok(body),
            Canned::Raw { status, .. } | Canned::Status(status) => Err(HttpError::Status {
                url: url.to_string(),
                status,
            }),
            Canned::Transport(message) => Err(HttpError::Transport {
                url: url.to_string(),
                message,
            }),
        }
    }

    fn send(&self, req: &HttpRequest) -> Result<HttpResponse, HttpError> {
        self.sent.lock().unwrap().push(req.clone());
        let url = req.full_url();
        match self.lookup(&url)? {
            Canned::Body(body) => Ok(HttpResponse {
                url,
                status: 200,
                body: body.to_string(),
            }),
            Canned::Raw { status, body } => Ok(HttpResponse { url, status, body }),
            Canned::Status(status) => Ok(HttpResponse {
                url,
                status,
                body: String::new(),
            }),
            Canned::Transport(message) => Err(HttpError::Transport { url, message }),
        }
    }
}

/// Python's `async_retry_with_backoff(max_attempts, base_delay)`: retryable
/// failures are tried again after `base_delay`, doubling each time.
pub fn retry_with_backoff<T>(
    max_attempts: u32,
    base_delay: Duration,
    mut attempt: impl FnMut() -> Result<T, HttpError>,
) -> Result<T, HttpError> {
    let mut n = 1;
    loop {
        match attempt() {
            Err(e) if e.is_retryable() && n < max_attempts => {
                let delay = base_delay * 2u32.pow(n - 1);
                tracing::warn!("Attempt {n}/{max_attempts} failed with {e}. Retrying in {delay:?}");
                std::thread::sleep(delay);
                n += 1;
            }
            other => return other,
        }
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn quote_matches_httpx() {
        assert_eq!(
            py_quote("Zürich/ß ~*'()!, NY"),
            "Z%C3%BCrich%2F%C3%9F%20~%2A%27%28%29%21%2C%20NY"
        );
        assert_eq!(
            build_url(
                "https://x.test/s",
                &[("name", "New York".into()), ("count", "5".into())]
            ),
            "https://x.test/s?name=New%20York&count=5"
        );
    }

    #[test]
    fn secrets_are_redacted_from_logged_urls() {
        assert_eq!(
            redact_secrets("request to https://a.test/?format=json&API_KEY=abc123&x=1 failed"),
            "request to https://a.test/?format=json&API_KEY=***&x=1 failed"
        );
    }

    #[test]
    fn fixture_statuses_and_headers() {
        let http = FixtureClient::new()
            .with("https://a.test/", serde_json::json!({"ok": true}))
            .with_status("https://a.test/missing", 404);
        assert!(http
            .get_json_with_headers("https://a.test/x", &[("User-Agent", "UA")])
            .is_ok());
        let err = http.get_json("https://a.test/missing/1").unwrap_err();
        assert_eq!(err.status(), Some(404));
        assert!(!err.is_retryable());
        assert_eq!(
            http.header_log()[0],
            vec![("User-Agent".to_string(), "UA".to_string())]
        );
    }

    #[test]
    fn fixture_text_and_raw_responses() {
        let http = FixtureClient::new()
            .with("https://t.test/afos", Value::String("RAW TEXT".into()))
            .with_response("https://t.test/raw", 503, "busy");
        assert_eq!(http.get_text("https://t.test/afos").unwrap(), "RAW TEXT");
        let resp = http.send(&HttpRequest::new("https://t.test/raw")).unwrap();
        assert_eq!((resp.status, resp.body.as_str()), (503, "busy"));
        assert_eq!(
            http.get_text("https://t.test/raw").unwrap_err().status(),
            Some(503)
        );
    }
}
