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

impl HttpError {
    /// Python's `is_retryable_http_error`: timeouts, transport failures,
    /// 408/409/425/429 and 5xx responses.
    pub fn is_retryable(&self) -> bool {
        match self {
            HttpError::Transport { .. } => true,
            HttpError::Status { status, .. } => {
                *status >= 500 || matches!(status, 408 | 409 | 425 | 429)
            }
            _ => false,
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

/// Minimal blocking JSON GET abstraction.
pub trait HttpClient: Send + Sync {
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
                request = request.header("Accept", "application/geo+json, application/json");
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

/// A canned fixture response.
#[derive(Debug, Clone)]
enum Canned {
    Body(Value),
    Status(u16),
    Transport(String),
}

/// Offline client that serves canned responses keyed by URL prefix.
/// Used by tests and by `--smoke` runs so the app can be exercised without
/// network access.
#[derive(Default)]
pub struct FixtureClient {
    fixtures: Mutex<Vec<(String, Canned)>>,
    pub requests: Mutex<Vec<String>>,
    /// Explicit headers sent with each request (empty for plain `get_json`).
    pub headers: Mutex<Vec<Vec<(String, String)>>>,
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

    pub fn from_map(map: HashMap<String, Value>) -> Self {
        Self {
            fixtures: Mutex::new(map.into_iter().map(|(k, v)| (k, Canned::Body(v))).collect()),
            ..Self::default()
        }
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
        self.requests.lock().unwrap().push(url.to_string());
        self.headers.lock().unwrap().push(
            headers
                .iter()
                .map(|(k, v)| (k.to_string(), v.to_string()))
                .collect(),
        );
        let fixtures = self.fixtures.lock().unwrap();
        let canned = fixtures
            .iter()
            .filter(|(prefix, _)| url.starts_with(prefix.as_str()))
            .max_by_key(|(prefix, _)| prefix.len())
            .map(|(_, canned)| canned.clone())
            .ok_or_else(|| HttpError::MissingFixture(url.to_string()))?;
        match canned {
            Canned::Body(body) => Ok(body),
            Canned::Status(status) => Err(HttpError::Status {
                url: url.to_string(),
                status,
            }),
            Canned::Transport(message) => Err(HttpError::Transport {
                url: url.to_string(),
                message,
            }),
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
}
