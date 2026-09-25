//! Sharing a pack with the community (`services/pack_submission_service.py`,
//! `services/github_backend_client.py`, `utils/url_validation.py`).
//!
//! The pack is zipped and uploaded to the AccessiWeather backend
//! (`https://soundpack-backend.fly.dev` unless `github_backend_url` is set),
//! which opens the pull request on `orinks/accessiweather-soundpacks`. As in
//! Python, the client holds no GitHub credentials; the unused
//! `github_app_*` settings stay untouched.
//!
//! Not ported (unreachable in Python): the backend's `/share-pack` and
//! `/health` calls, `submit_pack_anonymous`, PR title/body and branch-name
//! builders.

use std::io::Cursor;
use std::net::{IpAddr, Ipv4Addr, Ipv6Addr, ToSocketAddrs};
use std::path::Path;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::Duration;

use serde_json::{Map, Value};

use crate::http::{retry, Body, Http, HttpError, Request, ReqwestHttp};
use crate::pack::validate_sound_pack;
use crate::py::{py_repr_str, py_str, py_truthy};

pub const DEFAULT_BACKEND_URL: &str = "https://soundpack-backend.fly.dev";
const TIMEOUT: Duration = Duration::from_secs(30);

/// `get_github_backend_url`: the `github_backend_url` setting, or the default.
pub fn backend_url_from_setting(setting: &str) -> String {
    match setting.trim() {
        "" => DEFAULT_BACKEND_URL.into(),
        url => url.into(),
    }
}

/// `SSRFError`.
#[derive(Debug, Clone, thiserror::Error, PartialEq)]
#[error("{0}")]
pub struct SsrfError(pub String);

fn in_v4(addr: Ipv4Addr, net: [u8; 4], prefix: u32) -> bool {
    let mask = if prefix == 0 {
        0
    } else {
        u32::MAX << (32 - prefix)
    };
    u32::from(addr) & mask == u32::from(Ipv4Addr::from(net)) & mask
}

fn in_v6(addr: Ipv6Addr, net: [u16; 8], prefix: u32) -> bool {
    let mask = if prefix == 0 {
        0
    } else {
        u128::MAX << (128 - prefix)
    };
    u128::from(addr) & mask == u128::from(Ipv6Addr::from(net)) & mask
}

/// Python's `is_private or is_loopback or is_link_local or is_reserved`
/// (Python 3.12 address tables).
fn is_internal(ip: IpAddr) -> bool {
    match ip {
        IpAddr::V4(a) => {
            const PRIVATE: &[([u8; 4], u32)] = &[
                ([0, 0, 0, 0], 8),
                ([10, 0, 0, 0], 8),
                ([127, 0, 0, 0], 8),
                ([169, 254, 0, 0], 16),
                ([172, 16, 0, 0], 12),
                ([192, 0, 0, 0], 24),
                ([192, 0, 0, 170], 31),
                ([192, 0, 2, 0], 24),
                ([192, 168, 0, 0], 16),
                ([198, 18, 0, 0], 15),
                ([198, 51, 100, 0], 24),
                ([203, 0, 113, 0], 24),
                ([240, 0, 0, 0], 4),
                ([255, 255, 255, 255], 32),
            ];
            let exception = a == Ipv4Addr::new(192, 0, 0, 9) || a == Ipv4Addr::new(192, 0, 0, 10);
            PRIVATE.iter().any(|(net, p)| in_v4(a, *net, *p)) && !exception
        }
        IpAddr::V6(a) => {
            if let Some(v4) = a.to_ipv4_mapped() {
                return is_internal(IpAddr::V4(v4));
            }
            const PRIVATE: &[([u16; 8], u32)] = &[
                ([0, 0, 0, 0, 0, 0, 0, 1], 128),
                ([0; 8], 128),
                ([0x64, 0xff9b, 1, 0, 0, 0, 0, 0], 48),
                ([0x100, 0, 0, 0, 0, 0, 0, 0], 64),
                ([0x2001, 0, 0, 0, 0, 0, 0, 0], 23),
                ([0x2001, 0xdb8, 0, 0, 0, 0, 0, 0], 32),
                ([0x2002, 0, 0, 0, 0, 0, 0, 0], 16),
                ([0xfc00, 0, 0, 0, 0, 0, 0, 0], 7),
                ([0xfe80, 0, 0, 0, 0, 0, 0, 0], 10),
            ];
            const PRIVATE_EXCEPTIONS: &[([u16; 8], u32)] = &[
                ([0x2001, 1, 0, 0, 0, 0, 0, 1], 128),
                ([0x2001, 1, 0, 0, 0, 0, 0, 2], 128),
                ([0x2001, 3, 0, 0, 0, 0, 0, 0], 32),
                ([0x2001, 4, 0x112, 0, 0, 0, 0, 0], 48),
                ([0x2001, 0x20, 0, 0, 0, 0, 0, 0], 28),
                ([0x2001, 0x30, 0, 0, 0, 0, 0, 0], 28),
            ];
            const RESERVED: &[([u16; 8], u32)] = &[
                ([0; 8], 8),
                ([0x100, 0, 0, 0, 0, 0, 0, 0], 8),
                ([0x200, 0, 0, 0, 0, 0, 0, 0], 7),
                ([0x400, 0, 0, 0, 0, 0, 0, 0], 6),
                ([0x800, 0, 0, 0, 0, 0, 0, 0], 5),
                ([0x1000, 0, 0, 0, 0, 0, 0, 0], 4),
                ([0x4000, 0, 0, 0, 0, 0, 0, 0], 3),
                ([0x6000, 0, 0, 0, 0, 0, 0, 0], 3),
                ([0x8000, 0, 0, 0, 0, 0, 0, 0], 3),
                ([0xa000, 0, 0, 0, 0, 0, 0, 0], 3),
                ([0xc000, 0, 0, 0, 0, 0, 0, 0], 3),
                ([0xe000, 0, 0, 0, 0, 0, 0, 0], 4),
                ([0xf000, 0, 0, 0, 0, 0, 0, 0], 5),
                ([0xf800, 0, 0, 0, 0, 0, 0, 0], 6),
                ([0xfe00, 0, 0, 0, 0, 0, 0, 0], 9),
            ];
            let any = |list: &[([u16; 8], u32)]| list.iter().any(|(n, p)| in_v6(a, *n, *p));
            (any(PRIVATE) && !any(PRIVATE_EXCEPTIONS)) || any(RESERVED)
        }
    }
}

/// `validate_backend_url`: HTTPS only, and never localhost or an address
/// (literal or resolved) in a private/internal range.
pub fn validate_backend_url(url: &str) -> Result<String, SsrfError> {
    let url = url.trim();
    if url.is_empty() {
        return Err(SsrfError("URL must not be empty".into()));
    }
    let scheme = match url.split_once(':') {
        Some((s, _))
            if s.starts_with(|c: char| c.is_ascii_alphabetic())
                && s.chars()
                    .all(|c| c.is_ascii_alphanumeric() || "+-.".contains(c)) =>
        {
            s.to_lowercase()
        }
        _ => String::new(),
    };
    if scheme != "https" {
        return Err(SsrfError(format!(
            "Only HTTPS URLs are allowed, got scheme: {}",
            py_repr_str(&scheme)
        )));
    }
    let host = url::Url::parse(url).ok().and_then(|u| {
        u.host().map(|h| match h {
            url::Host::Domain(d) => d.to_lowercase(),
            url::Host::Ipv4(a) => a.to_string(),
            url::Host::Ipv6(a) => a.to_string(),
        })
    });
    let Some(host) = host.filter(|h| !h.is_empty()) else {
        return Err(SsrfError("URL must have a valid hostname".into()));
    };
    if ["localhost", "127.0.0.1", "::1", "0.0.0.0"].contains(&host.as_str()) {
        return Err(SsrfError(format!(
            "Localhost URLs are not allowed: {}",
            py_repr_str(&host)
        )));
    }
    let resolves_internal = |ip: IpAddr| {
        SsrfError(format!(
            "Hostname {} resolves to private/internal address {ip}",
            py_repr_str(&host)
        ))
    };
    // Python's "Private/internal IP addresses are not allowed" error is a
    // ValueError caught by its own `except ValueError`, so internal IP
    // literals get the "resolves to" message.
    if let Ok(ip) = host.parse::<IpAddr>() {
        return if is_internal(ip) {
            Err(resolves_internal(ip))
        } else {
            Ok(url.to_string())
        };
    }
    // Unresolvable hosts are allowed; the request fails later anyway.
    if let Ok(addrs) = (host.as_str(), 0).to_socket_addrs() {
        if let Some(addr) = addrs.into_iter().find(|a| is_internal(a.ip())) {
            return Err(resolves_internal(addr.ip()));
        }
    }
    Ok(url.to_string())
}

#[derive(Debug, thiserror::Error, PartialEq)]
pub enum SubmitError {
    #[error("{0}")]
    Ssrf(#[from] SsrfError),
    /// Python `RuntimeError`, with its message.
    #[error("{0}")]
    Runtime(String),
    #[error("Operation cancelled by user")]
    Cancelled,
}

/// `GitHubBackendClient`.
pub struct GitHubBackendClient {
    pub backend_url: String,
    pub user_agent: String,
    http: Arc<dyn Http>,
}

impl GitHubBackendClient {
    pub fn new(
        backend_url: &str,
        user_agent: Option<&str>,
        http: Arc<dyn Http>,
    ) -> Result<Self, SsrfError> {
        validate_backend_url(backend_url)?;
        Ok(Self {
            backend_url: backend_url.trim_end_matches('/').to_string(),
            user_agent: user_agent
                .map(str::to_string)
                .unwrap_or_else(|| format!("AccessiWeather/{}", aw_core::VERSION)),
            http,
        })
    }

    /// `upload_zip`: POST the ZIP to `/upload-zip` (field `zip_file`) and
    /// return the backend's JSON (`html_url` is the new pull request).
    /// Retried once after 2 s on any failure but cancellation.
    pub fn upload_zip(
        &self,
        zip_bytes: &[u8],
        filename: &str,
        cancel: &AtomicBool,
    ) -> Result<Value, SubmitError> {
        retry(
            2,
            Duration::from_secs(2),
            |e: &SubmitError| matches!(e, SubmitError::Runtime(_)),
            || self.upload_zip_once(zip_bytes, filename, cancel),
        )
    }

    fn upload_zip_once(
        &self,
        zip_bytes: &[u8],
        filename: &str,
        cancel: &AtomicBool,
    ) -> Result<Value, SubmitError> {
        if cancel.load(Ordering::SeqCst) {
            return Err(SubmitError::Cancelled);
        }
        let url = format!("{}/upload-zip", self.backend_url);
        tracing::debug!("Uploading soundpack ZIP to backend: {url}");
        let response = self.http.send(Request {
            method: "POST",
            url,
            headers: vec![("User-Agent", self.user_agent.clone())],
            body: Body::Multipart {
                field: "zip_file".into(),
                filename: filename.into(),
                bytes: zip_bytes.to_vec(),
                content_type: "application/zip".into(),
            },
            timeout: Some(TIMEOUT),
        });
        // Python wraps every non-network failure, its own HTTP-status error
        // included, as "Unexpected error communicating with backend: ...".
        let unexpected = |e: String| {
            SubmitError::Runtime(format!("Unexpected error communicating with backend: {e}"))
        };
        let response = match response {
            Ok(r) => r,
            Err(HttpError::Timeout(_)) => {
                return Err(SubmitError::Runtime(format!(
                    "Backend service timeout after {:.1}s",
                    TIMEOUT.as_secs_f64()
                )))
            }
            Err(HttpError::Request(e)) => {
                return Err(SubmitError::Runtime(format!(
                    "Failed to connect to backend service: {e}"
                )))
            }
        };
        if cancel.load(Ordering::SeqCst) {
            return Err(SubmitError::Cancelled);
        }
        let status = response.status;
        let text = response.text().map_err(|e| unexpected(e.to_string()))?;
        if status >= 400 {
            let detail = match serde_json::from_str::<Value>(&text) {
                Ok(Value::Object(obj)) => obj.get("detail").map(py_str).unwrap_or(text),
                _ => text,
            };
            return Err(unexpected(format!(
                "Backend service error (HTTP {status}): {detail}"
            )));
        }
        serde_json::from_str(&text).map_err(|e| unexpected(e.to_string()))
    }
}

/// `_sanitize_id`: lower-case, spaces to hyphens, only `[a-z0-9-]`.
fn sanitize_id(text: &str) -> String {
    let s: String = text
        .trim()
        .to_lowercase()
        .replace(' ', "-")
        .chars()
        .filter(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || *c == '-')
        .collect();
    if s.is_empty() {
        "pack".into()
    } else {
        s
    }
}

/// `_derive_pack_id`: `name-author` (author omitted when blank or
/// "unknown"), sanitized. The upload is named `{pack_id}.zip`.
pub fn derive_pack_id(pack_path: &Path, meta: &Map<String, Value>) -> String {
    let dir_name = pack_path
        .file_name()
        .map(|n| n.to_string_lossy().into_owned())
        .unwrap_or_default();
    let name = meta
        .get("name")
        .filter(|v| py_truthy(v))
        .map(py_str)
        .unwrap_or(if dir_name.is_empty() {
            "pack".into()
        } else {
            dir_name
        });
    let name = name.trim();
    let author = meta
        .get("author")
        .filter(|v| py_truthy(v))
        .map(py_str)
        .unwrap_or_default();
    let author = author.trim();
    let pack_id = if !author.is_empty() && author.to_lowercase() != "unknown" {
        format!("{name}-{author}")
    } else {
        name.to_string()
    };
    sanitize_id(&pack_id)
}

/// `PackSubmissionService`.
pub struct PackSubmissionService {
    backend_url: String,
    user_agent: Option<String>,
    http: Arc<dyn Http>,
}

impl PackSubmissionService {
    /// `backend_url`: [`backend_url_from_setting`] of `github_backend_url`.
    pub fn new(backend_url: &str) -> Result<Self, HttpError> {
        Ok(Self::with_http(
            backend_url,
            Arc::new(ReqwestHttp::new(TIMEOUT)?),
        ))
    }

    pub fn with_http(backend_url: &str, http: Arc<dyn Http>) -> Self {
        Self {
            backend_url: backend_url.into(),
            user_agent: None,
            http,
        }
    }

    /// `submit_pack`: validate, zip and upload the pack; returns the pull
    /// request URL. `progress(percent, status)` returns false to cancel.
    pub fn submit_pack(
        &self,
        pack_path: &Path,
        pack_meta: &Map<String, Value>,
        progress: &mut dyn FnMut(f64, &str) -> bool,
        cancel: &AtomicBool,
    ) -> Result<String, SubmitError> {
        let mut report = |pct: f64, status: &str| {
            if progress(pct, status) {
                Ok(())
            } else {
                cancel.store(true, Ordering::SeqCst);
                Err(SubmitError::Cancelled)
            }
        };
        report(5.0, "Checking prerequisites...")?;
        report(7.0, "Connecting to backend service...")?;
        let client = GitHubBackendClient::new(
            &self.backend_url,
            self.user_agent.as_deref(),
            Arc::clone(&self.http),
        )?;
        report(10.0, "Validating sound pack...")?;
        let (ok, msg) = validate_sound_pack(pack_path);
        if !ok {
            return Err(SubmitError::Runtime(format!(
                "Sound pack validation failed for {}: {msg}",
                pack_path.display()
            )));
        }
        report(15.0, "Preparing pack submission...")?;
        let pack_id = derive_pack_id(pack_path, pack_meta);
        report(20.0, "Packaging sound pack...")?;
        let zip_bytes = crate::manager::zip_dir(pack_path, Cursor::new(Vec::new()))
            .map_err(SubmitError::Runtime)?
            .into_inner();
        report(70.0, "Uploading pack to backend...")?;
        let pr_data = client.upload_zip(&zip_bytes, &format!("{pack_id}.zip"), cancel)?;
        let pr_url = pr_data.get("html_url").map(py_str).unwrap_or_default();
        report(100.0, &format!("Pull request created: {pr_url}"))?;
        Ok(pr_url)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::http::fake::FakeHttp;

    fn client(fake: FakeHttp) -> (GitHubBackendClient, Arc<FakeHttp>) {
        let fake = Arc::new(fake);
        let client = GitHubBackendClient::new("https://203.0.114.1/", None, fake.clone()).unwrap();
        (client, fake)
    }

    #[test]
    fn client_strips_slash_and_rejects_internal_urls() {
        let (c, _) = client(FakeHttp::default());
        assert_eq!(c.backend_url, "https://203.0.114.1");
        assert!(c.user_agent.starts_with("AccessiWeather/"));
        for bad in [
            "http://example.com",
            "https://localhost",
            "https://10.0.0.5",
            "https://[::1]/",
        ] {
            assert!(
                GitHubBackendClient::new(bad, None, Arc::new(FakeHttp::default())).is_err(),
                "{bad}"
            );
        }
    }

    #[test]
    fn upload_errors_match_python() {
        let url = "https://203.0.114.1/upload-zip";
        let cancel = AtomicBool::new(false);
        let (c, fake) =
            client(FakeHttp::default().route(url, 200, r#"{"pr_url": "https://github.com/pr/1"}"#));
        assert_eq!(
            c.upload_zip(b"zip", "p.zip", &cancel).unwrap(),
            serde_json::json!({"pr_url": "https://github.com/pr/1"})
        );
        let log = fake.log.lock().unwrap();
        let (field, name, _, ctype) = log[0].multipart.clone().unwrap();
        assert_eq!(
            (field.as_str(), name.as_str(), ctype.as_str()),
            ("zip_file", "p.zip", "application/zip")
        );

        let (c, fake) = client(FakeHttp::default().route(url, 500, r#"{"detail": "boom"}"#));
        let err = c
            .upload_zip(b"zip", "p.zip", &cancel)
            .unwrap_err()
            .to_string();
        assert_eq!(
            err,
            "Unexpected error communicating with backend: Backend service error (HTTP 500): boom"
        );
        assert_eq!(fake.urls().len(), 2, "retried once");

        let (c, _) = client(FakeHttp::default().route(url, 502, "Bad Gateway"));
        assert!(c
            .upload_zip(b"", "p.zip", &cancel)
            .unwrap_err()
            .to_string()
            .ends_with("(HTTP 502): Bad Gateway"));

        let (c, _) = client(FakeHttp::default().fail(url, HttpError::Timeout("t".into())));
        assert_eq!(
            c.upload_zip(b"", "p.zip", &cancel).unwrap_err().to_string(),
            "Backend service timeout after 30.0s"
        );

        let (c, _) = client(FakeHttp::default().fail(url, HttpError::Request("refused".into())));
        assert_eq!(
            c.upload_zip(b"", "p.zip", &cancel).unwrap_err().to_string(),
            "Failed to connect to backend service: refused"
        );

        let (c, fake) = client(FakeHttp::default());
        assert_eq!(
            c.upload_zip(b"", "p.zip", &AtomicBool::new(true)),
            Err(SubmitError::Cancelled)
        );
        assert!(fake.urls().is_empty());
    }
}
