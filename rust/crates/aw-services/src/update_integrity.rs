//! Checksum lookup, parsing and verification for update downloads
//! (`services/update_integrity.py`).

use std::io::Read;
use std::path::Path;

use serde_json::Value;
use sha2::Digest;

use crate::{py_strip, splitlines};

/// Name of a release asset (`asset.get("name", "")`).
pub(crate) fn asset_name(asset: &Value) -> &str {
    asset.get("name").and_then(Value::as_str).unwrap_or("")
}

pub(crate) fn assets(release: &Value) -> &[Value] {
    release
        .get("assets")
        .and_then(Value::as_array)
        .map_or(&[], Vec::as_slice)
}

/// The `<artifact>.sha256` / `.sha512` asset, else a generic checksum file.
pub fn find_checksum_asset<'a>(release: &'a Value, artifact_name: &str) -> Option<&'a Value> {
    let lower = artifact_name.to_lowercase();
    let assets = assets(release);
    for ext in [".sha256", ".sha512"] {
        let wanted = format!("{lower}{ext}");
        if let Some(asset) = assets
            .iter()
            .find(|a| asset_name(a).to_lowercase() == wanted)
        {
            return Some(asset);
        }
    }
    const GENERIC: [&str; 5] = [
        "checksums.sha256",
        "sha256sums",
        "checksums.sha512",
        "sha512sums",
        "checksums.txt",
    ];
    assets
        .iter()
        .find(|a| GENERIC.contains(&asset_name(a).to_lowercase().as_str()))
}

/// `(algorithm, lowercase hex)` for `artifact_name` from a single-hash file
/// or a BSD/GNU checksum listing.
pub fn parse_checksum_file(content: &str, artifact_name: &str) -> Option<(&'static str, String)> {
    let lines = splitlines(py_strip(content));
    let lower = artifact_name.to_lowercase();
    for line in &lines {
        let line = py_strip(line);
        if line.is_empty() {
            continue;
        }
        let (hash, rest) = match line.split_once(char::is_whitespace) {
            Some((hash, rest)) => (hash, Some(rest.trim_start())),
            None => (line, None),
        };
        let Some(algo) = algorithm_for_hash_length(hash.chars().count()) else {
            continue;
        };
        match rest {
            None if lines.len() == 1 => return Some((algo, hash.to_lowercase())),
            Some(rest) => {
                let filename = py_strip(rest.trim_start_matches('*'));
                if filename.to_lowercase() == lower {
                    return Some((algo, hash.to_lowercase()));
                }
            }
            None => {}
        }
    }
    None
}

fn algorithm_for_hash_length(len: usize) -> Option<&'static str> {
    match len {
        64 => Some("sha256"),
        128 => Some("sha512"),
        32 => Some("md5"),
        _ => None,
    }
}

/// Hash `file_path` with `algorithm` and compare against `expected_hash`.
pub fn verify_file_checksum(
    file_path: &Path,
    algorithm: &str,
    expected_hash: &str,
) -> std::io::Result<bool> {
    let mut file = std::fs::File::open(file_path)?;
    let mut buf = vec![0u8; 65536];
    let mut sha256 = sha2::Sha256::new();
    let mut sha512 = sha2::Sha512::new();
    let mut md5 = md5::Context::new();
    loop {
        let n = file.read(&mut buf)?;
        if n == 0 {
            break;
        }
        match algorithm {
            "sha256" => sha256.update(&buf[..n]),
            "sha512" => sha512.update(&buf[..n]),
            "md5" => md5.consume(&buf[..n]),
            other => {
                return Err(std::io::Error::other(format!(
                    "Unsupported hash algorithm: {other}"
                )))
            }
        }
    }
    let actual = match algorithm {
        "sha256" => hex(&sha256.finalize()),
        "sha512" => hex(&sha512.finalize()),
        _ => format!("{:x}", md5.compute()),
    };
    Ok(actual == expected_hash.to_lowercase())
}

fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn exact_checksum_asset_beats_generic_file() {
        let release = json!({"assets": [
            {"name": "checksums.txt"},
            {"name": "accessiweather-windows-x86_64.zip"},
            {"name": "ACCESSIWEATHER-WINDOWS-X86_64.ZIP.SHA256"},
        ]});
        let found = find_checksum_asset(&release, "accessiweather-windows-x86_64.zip").unwrap();
        assert_eq!(found["name"], "ACCESSIWEATHER-WINDOWS-X86_64.ZIP.SHA256");
        assert_eq!(
            find_checksum_asset(&release, "other.zip").unwrap()["name"],
            "checksums.txt"
        );
        assert!(find_checksum_asset(&json!({"assets": []}), "app.zip").is_none());
    }

    #[test]
    fn verify_accepts_matching_and_rejects_tampered_files() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("update.zip");
        std::fs::write(&path, b"hello").unwrap();
        let sha = "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824";
        assert!(verify_file_checksum(&path, "sha256", &sha.to_uppercase()).unwrap());
        assert!(!verify_file_checksum(&path, "sha256", &"0".repeat(64)).unwrap());
        assert!(verify_file_checksum(&path, "md5", "5d41402abc4b2a76b9719d911017c592").unwrap());
        assert!(verify_file_checksum(&path, "crc32", "x").is_err());
    }
}
