//! Update check and download against a local HTTP server
//! (Python's `test_simple_update.py` / `test_update_checksum_verification.py`).

use std::io::{Read, Write};
use std::net::TcpListener;

use aw_services::update::{UpdateError, UpdateInfo, UpdateService};
use serde_json::{json, Value};
use sha2::Digest;

/// Serves `(path, status, body)` routes, one connection per request.
fn serve(routes: Vec<(String, u16, Vec<u8>)>) -> String {
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let base = format!("http://{}", listener.local_addr().unwrap());
    std::thread::spawn(move || {
        for stream in listener.incoming() {
            let Ok(mut stream) = stream else { continue };
            let mut request = Vec::new();
            let mut buf = [0u8; 1024];
            while !request.windows(4).any(|w| w == b"\r\n\r\n") {
                match stream.read(&mut buf) {
                    Ok(0) | Err(_) => break,
                    Ok(n) => request.extend_from_slice(&buf[..n]),
                }
            }
            let text = String::from_utf8_lossy(&request);
            let path = text.split_whitespace().nth(1).unwrap_or("").to_string();
            let (status, body) = routes
                .iter()
                .find(|(p, _, _)| *p == path)
                .map_or((404, Vec::new()), |(_, s, b)| (*s, b.clone()));
            let _ = write!(
                stream,
                "HTTP/1.1 {status} X\r\nContent-Length: {}\r\nConnection: close\r\n\r\n",
                body.len()
            );
            let _ = stream.write_all(&body);
        }
    });
    base
}

fn sha256(bytes: &[u8]) -> String {
    sha2::Sha256::digest(bytes)
        .iter()
        .map(|b| format!("{b:02x}"))
        .collect()
}

fn info(base: &str, release: Option<Value>) -> UpdateInfo {
    UpdateInfo {
        version: "1.0.0".into(),
        download_url: format!("{base}/update.zip"),
        artifact_name: "update.zip".into(),
        release_notes: "Test release".into(),
        commit_hash: None,
        is_nightly: false,
        is_prerelease: false,
        release,
    }
}

fn release_with_checksum(base: &str) -> Value {
    json!({"assets": [
        {"name": "update.zip", "browser_download_url": format!("{base}/update.zip")},
        {"name": "update.zip.sha256", "browser_download_url": format!("{base}/update.zip.sha256")},
    ]})
}

fn download(
    base: &str,
    release: Option<Value>,
) -> (
    Result<std::path::PathBuf, UpdateError>,
    tempfile::TempDir,
    Vec<(u64, u64)>,
) {
    let dir = tempfile::tempdir().unwrap();
    let mut progress = Vec::new();
    let result =
        UpdateService::new()
            .unwrap()
            .download_update(&info(base, release), dir.path(), |d, t| {
                progress.push((d, t))
            });
    (result, dir, progress)
}

fn checksum_error(result: Result<std::path::PathBuf, UpdateError>) -> String {
    match result {
        Err(UpdateError::Checksum(msg)) => msg,
        other => panic!("expected a checksum error, got {other:?}"),
    }
}

#[test]
fn valid_artifact_is_kept_and_reports_progress() {
    let artifact = vec![b'x'; 100];
    let base = serve(vec![
        ("/update.zip".into(), 200, artifact.clone()),
        (
            "/update.zip.sha256".into(),
            200,
            format!("{}  update.zip", sha256(&artifact)).into_bytes(),
        ),
    ]);
    let (result, dir, progress) = download(&base, Some(release_with_checksum(&base)));
    let path = result.unwrap();
    assert_eq!(path, dir.path().join("update.zip"));
    assert_eq!(std::fs::read(&path).unwrap(), artifact);
    assert_eq!(progress.last(), Some(&(100, 100)));
}

#[test]
fn tampered_artifact_is_deleted() {
    let base = serve(vec![
        ("/update.zip".into(), 200, b"tampered".to_vec()),
        (
            "/update.zip.sha256".into(),
            200,
            format!("{}  update.zip", "0".repeat(64)).into_bytes(),
        ),
    ]);
    let (result, dir, _) = download(&base, Some(release_with_checksum(&base)));
    let msg = checksum_error(result);
    assert!(msg.starts_with("Checksum verification failed for update.zip. Expected sha256:"));
    assert!(msg.ends_with("The downloaded file may be corrupted or tampered with."));
    assert!(!dir.path().join("update.zip").exists());
}

#[test]
fn release_without_checksum_asset_is_allowed() {
    let base = serve(vec![("/update.zip".into(), 200, b"abc".to_vec())]);
    let release = json!({"assets": [{"name": "update.zip"}]});
    let (result, _dir, _) = download(&base, Some(release));
    assert_eq!(std::fs::read(result.unwrap()).unwrap(), b"abc");
}

#[test]
fn verification_failures_fail_closed() {
    let base = serve(vec![
        ("/update.zip".into(), 200, b"abc".to_vec()),
        (
            "/other.sha256".into(),
            200,
            format!("{}  other.zip", "0".repeat(64)).into_bytes(),
        ),
    ]);
    let cases = [
        (
            None,
            "Cannot verify update.zip: no release metadata available. Refusing to install an unverified update.",
        ),
        (
            Some(json!({"assets": [{"name": "update.zip.sha256"}]})),
            "Checksum asset for update.zip has no download URL; cannot verify integrity.",
        ),
        (
            Some(json!({"assets": [{"name": "update.zip.sha256", "browser_download_url": format!("{base}/missing")}]})),
            "Failed to download checksum file for update.zip; cannot verify integrity.",
        ),
        (
            Some(json!({"assets": [{"name": "checksums.txt", "browser_download_url": format!("{base}/other.sha256")}]})),
            "Could not find a checksum for update.zip in the published checksum file; cannot verify integrity.",
        ),
    ];
    for (release, expected) in cases {
        let (result, dir, _) = download(&base, release);
        assert_eq!(checksum_error(result), expected);
        assert!(!dir.path().join("update.zip").exists());
    }
}

#[test]
fn check_for_updates_reads_the_releases_api() {
    let artifact = match std::env::consts::OS {
        "windows" => "AccessiWeather-nightly-20260925-windows-portable.zip",
        "macos" => "AccessiWeather-nightly-20260925-macOS.dmg",
        _ => "AccessiWeather-nightly-20260925-linux-x86_64.AppImage",
    };
    let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../testdata/services/github_releases.json");
    let mut releases: Vec<Value> =
        serde_json::from_str(&std::fs::read_to_string(path).unwrap()).unwrap();
    releases[0]["assets"].as_array_mut().unwrap().push(json!({
        "name": "AccessiWeather-nightly-20260925-macOS.dmg",
        "browser_download_url": "https://example.test/a"
    }));
    let base = serve(vec![(
        "/releases".into(),
        200,
        serde_json::to_vec(&releases).unwrap(),
    )]);
    let service = UpdateService::with_releases_url(&format!("{base}/releases")).unwrap();
    let update = service
        .check_for_updates("0.10.1", Some("20260924"), "nightly", true)
        .unwrap()
        .unwrap();
    assert_eq!(update.version, "20260925");
    assert!(update.is_nightly && update.is_prerelease);
    assert_eq!(update.artifact_name, artifact);
    assert!(service
        .check_for_updates("0.10.1", None, "stable", true)
        .unwrap()
        .is_none());
    assert!(UpdateService::with_releases_url(&format!("{base}/nope"))
        .unwrap()
        .check_for_updates("0.10.1", None, "stable", true)
        .is_err());
}
