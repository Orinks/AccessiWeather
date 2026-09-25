//! The HTTP calls behind community packs and pack sharing, behind a small
//! trait so tests can serve canned responses.

use std::io::Read;
use std::time::Duration;

use serde_json::Value;

pub struct Request {
    pub method: &'static str,
    pub url: String,
    pub headers: Vec<(&'static str, String)>,
    pub body: Body,
    /// Whole-request timeout; `None` for streamed downloads, which only get
    /// the connect timeout (httpx's timeout is per read, not total).
    pub timeout: Option<Duration>,
}

impl Request {
    pub fn get(
        url: impl Into<String>,
        headers: &[(&'static str, &str)],
        timeout: Option<Duration>,
    ) -> Self {
        Self {
            method: "GET",
            url: url.into(),
            headers: headers.iter().map(|(k, v)| (*k, v.to_string())).collect(),
            body: Body::Empty,
            timeout,
        }
    }
}

pub enum Body {
    Empty,
    /// One multipart file field.
    Multipart {
        field: String,
        filename: String,
        bytes: Vec<u8>,
        content_type: String,
    },
}

pub struct Response {
    pub status: u16,
    pub content_length: Option<u64>,
    pub body: Box<dyn Read + Send>,
}

impl Response {
    pub fn bytes(mut self) -> Result<Vec<u8>, HttpError> {
        let mut out = Vec::new();
        self.body
            .read_to_end(&mut out)
            .map_err(|e| HttpError::Request(e.to_string()))?;
        Ok(out)
    }

    pub fn text(self) -> Result<String, HttpError> {
        Ok(String::from_utf8_lossy(&self.bytes()?).into_owned())
    }

    /// The body as JSON (`Err` carries the parse error text).
    pub fn json(self) -> Result<Result<Value, String>, HttpError> {
        let bytes = self.bytes()?;
        Ok(serde_json::from_slice(&bytes).map_err(|e| e.to_string()))
    }
}

/// httpx's `TimeoutException` and other `RequestError`s.
#[derive(Debug, Clone, thiserror::Error, PartialEq)]
pub enum HttpError {
    #[error("{0}")]
    Timeout(String),
    #[error("{0}")]
    Request(String),
}

pub trait Http: Send + Sync {
    fn send(&self, request: Request) -> Result<Response, HttpError>;
}

/// Production transport. Like httpx's default client it does not follow
/// redirects.
pub struct ReqwestHttp {
    client: reqwest::blocking::Client,
}

impl ReqwestHttp {
    pub fn new(connect_timeout: Duration) -> Result<Self, HttpError> {
        let client = reqwest::blocking::Client::builder()
            .connect_timeout(connect_timeout)
            .redirect(reqwest::redirect::Policy::none())
            .timeout(None)
            .build()
            .map_err(map_err)?;
        Ok(Self { client })
    }
}

fn map_err(e: reqwest::Error) -> HttpError {
    if e.is_timeout() {
        HttpError::Timeout(e.to_string())
    } else {
        HttpError::Request(e.to_string())
    }
}

impl Http for ReqwestHttp {
    fn send(&self, request: Request) -> Result<Response, HttpError> {
        let method = reqwest::Method::from_bytes(request.method.as_bytes())
            .map_err(|e| HttpError::Request(e.to_string()))?;
        let mut builder = self.client.request(method, &request.url);
        for (name, value) in &request.headers {
            builder = builder.header(*name, value);
        }
        if let Some(timeout) = request.timeout {
            builder = builder.timeout(timeout);
        }
        builder = match request.body {
            Body::Empty => builder,
            Body::Multipart {
                field,
                filename,
                bytes,
                content_type,
            } => {
                let part = reqwest::blocking::multipart::Part::bytes(bytes)
                    .file_name(filename)
                    .mime_str(&content_type)
                    .map_err(map_err)?;
                builder.multipart(reqwest::blocking::multipart::Form::new().part(field, part))
            }
        };
        let response = builder.send().map_err(map_err)?;
        Ok(Response {
            status: response.status().as_u16(),
            content_length: response.content_length(),
            body: Box::new(response),
        })
    }
}

/// `async_retry_with_backoff` without jitter: up to `attempts` tries,
/// sleeping `base_delay * 2^(n-1)` between them while `retryable(err)`.
pub(crate) fn retry<T, E: std::fmt::Display>(
    attempts: u32,
    base_delay: Duration,
    retryable: impl Fn(&E) -> bool,
    mut f: impl FnMut() -> Result<T, E>,
) -> Result<T, E> {
    let mut attempt = 1;
    loop {
        match f() {
            Ok(v) => return Ok(v),
            Err(e) if attempt < attempts && retryable(&e) => {
                let delay = base_delay * 2u32.pow(attempt - 1);
                tracing::warn!(
                    "Attempt {attempt}/{attempts} failed with {e}. Retrying in {delay:?}"
                );
                sleep(delay);
                attempt += 1;
            }
            Err(e) => return Err(e),
        }
    }
}

pub(crate) fn sleep(delay: Duration) {
    if !cfg!(test) {
        std::thread::sleep(delay);
    }
}

#[cfg(test)]
pub(crate) mod fake {
    //! Canned responses keyed by URL, recording every request.
    use super::*;
    use std::sync::Mutex;

    pub struct Recorded {
        pub method: &'static str,
        pub url: String,
        pub headers: Vec<(&'static str, String)>,
        pub multipart: Option<(String, String, Vec<u8>, String)>,
    }

    type Route = (String, Result<(u16, Vec<u8>), HttpError>);

    #[derive(Default)]
    pub struct FakeHttp {
        pub routes: Mutex<Vec<Route>>,
        pub log: Mutex<Vec<Recorded>>,
    }

    impl FakeHttp {
        pub fn route(self, url: &str, status: u16, body: impl Into<Vec<u8>>) -> Self {
            self.routes
                .lock()
                .unwrap()
                .push((url.to_string(), Ok((status, body.into()))));
            self
        }

        pub fn fail(self, url: &str, err: HttpError) -> Self {
            self.routes
                .lock()
                .unwrap()
                .push((url.to_string(), Err(err)));
            self
        }

        pub fn urls(&self) -> Vec<String> {
            self.log
                .lock()
                .unwrap()
                .iter()
                .map(|r| r.url.clone())
                .collect()
        }
    }

    impl Http for FakeHttp {
        fn send(&self, request: Request) -> Result<Response, HttpError> {
            let multipart = match request.body {
                Body::Empty => None,
                Body::Multipart {
                    field,
                    filename,
                    bytes,
                    content_type,
                } => Some((field, filename, bytes, content_type)),
            };
            self.log.lock().unwrap().push(Recorded {
                method: request.method,
                url: request.url.clone(),
                headers: request.headers,
                multipart,
            });
            let routes = self.routes.lock().unwrap();
            let (_, result) = routes
                .iter()
                .find(|(url, _)| *url == request.url)
                .unwrap_or_else(|| panic!("no fake route for {}", request.url));
            let (status, body) = result.clone()?;
            Ok(Response {
                status,
                content_length: Some(body.len() as u64),
                body: Box::new(std::io::Cursor::new(body)),
            })
        }
    }
}
