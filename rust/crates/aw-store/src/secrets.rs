//! API keys and other secrets, stored exactly where the Python app keeps
//! them so both editions share one set of keys.
//!
//! * Installed: the system keyring, service `accessiweather`, username = the
//!   setting name (`accessiweather.config.secure_storage`). On Windows this
//!   follows python-keyring's Credential Manager layout: the most recently
//!   written key sits under target `accessiweather`, older ones under
//!   `<name>@accessiweather`.
//! * Portable: an encrypted `api-keys.keys` bundle beside the config
//!   (`accessiweather.config.portable_secrets`), whose passphrase is cached in
//!   the keyring under `portable_bundle_passphrase`.

use std::collections::BTreeMap;
use std::path::Path;

use aw_core::settings::AppSettings;
use base64::engine::general_purpose::{STANDARD, URL_SAFE};
use base64::Engine;
use serde_json::{json, Value};

pub const SERVICE_NAME: &str = "accessiweather";
pub const PORTABLE_PASSPHRASE_KEY: &str = "portable_bundle_passphrase";
pub const BUNDLE_FILE_NAMES: [&str; 2] = ["api-keys.keys", "api-keys.awkeys"];

/// API keys that travel in the portable bundle.
pub const API_KEY_NAMES: [&str; 5] = [
    "pirate_weather_api_key",
    "airnow_api_key",
    "openrouter_api_key",
    "venice_api_key",
    "avwx_api_key",
];

const BUNDLE_VERSION: i64 = 1;
const KDF_ITERATIONS: u32 = 390_000;
const SALT_SIZE: usize = 16;

#[derive(Debug, thiserror::Error)]
pub enum SecretsError {
    #[error("Passphrase is required")]
    NoPassphrase,
    #[error("Invalid passphrase or corrupted bundle")]
    InvalidToken,
    #[error("Invalid encrypted bundle: {0}")]
    Invalid(String),
    #[error("I/O error: {0}")]
    Io(#[from] std::io::Error),
}

/// Read a secret from the system keyring.
pub fn get_password(name: &str) -> Option<String> {
    backend::get(SERVICE_NAME, name)
}

/// Store a secret; an empty value deletes it, as in Python.
pub fn set_password(name: &str, value: &str) -> bool {
    if value.is_empty() {
        return delete_password(name);
    }
    let ok = backend::set(SERVICE_NAME, name, value);
    if !ok {
        tracing::error!("Failed to store credential for {name}");
    }
    ok
}

/// Delete a secret; succeeds when it did not exist.
pub fn delete_password(name: &str) -> bool {
    backend::delete(SERVICE_NAME, name)
}

/// Mutable access to the API key fields of the settings by name.
pub fn api_key_mut<'a>(settings: &'a mut AppSettings, name: &str) -> Option<&'a mut String> {
    Some(match name {
        "pirate_weather_api_key" => &mut settings.pirate_weather_api_key,
        "airnow_api_key" => &mut settings.airnow_api_key,
        "openrouter_api_key" => &mut settings.openrouter_api_key,
        "venice_api_key" => &mut settings.venice_api_key,
        "avwx_api_key" => &mut settings.avwx_api_key,
        _ => return None,
    })
}

/// Fill the API key fields from the keyring (installed mode). A key still
/// present in a legacy config file is moved into the keyring.
pub fn load_into(settings: &mut AppSettings) {
    let mut present = Vec::new();
    let mut missing = Vec::new();
    for name in API_KEY_NAMES {
        let field = api_key_mut(settings, name).expect("known key");
        let legacy = std::mem::take(field);
        let stored = get_password(name).unwrap_or_default();
        *field = if stored.is_empty() && !legacy.trim().is_empty() {
            set_password(name, legacy.trim());
            legacy.trim().to_string()
        } else {
            stored
        };
        if field.is_empty() {
            missing.push(name);
        } else {
            present.push(name);
        }
    }
    if !present.is_empty() {
        tracing::info!("Keyring keys loaded: {}", present.join(", "));
    }
    if !missing.is_empty() {
        tracing::info!("Keyring keys not set: {}", missing.join(", "));
    }
}

/// The API keys currently set in `settings`.
pub fn collect(settings: &mut AppSettings) -> BTreeMap<String, String> {
    API_KEY_NAMES
        .iter()
        .filter_map(|name| {
            let value = api_key_mut(settings, name)?.trim().to_string();
            (!value.is_empty()).then(|| (name.to_string(), value))
        })
        .collect()
}

/// Encrypt `secrets` into the bundle envelope (Fernet over PBKDF2-SHA256).
pub fn encrypt_bundle(
    secrets: &BTreeMap<String, String>,
    passphrase: &str,
) -> Result<Value, SecretsError> {
    if passphrase.is_empty() {
        return Err(SecretsError::NoPassphrase);
    }
    let mut salt = [0u8; SALT_SIZE];
    getrandom::getrandom(&mut salt).map_err(|e| SecretsError::Invalid(e.to_string()))?;
    let fernet = fernet_for(passphrase, &salt, KDF_ITERATIONS)?;
    let payload = serde_json::to_vec(secrets).map_err(|e| SecretsError::Invalid(e.to_string()))?;
    Ok(json!({
        "version": BUNDLE_VERSION,
        "cipher": "fernet",
        "kdf": {
            "name": "pbkdf2-sha256",
            "iterations": KDF_ITERATIONS,
            "salt": STANDARD.encode(salt),
        },
        "token": fernet.encrypt(&payload),
    }))
}

/// Decrypt a bundle envelope written by either edition.
pub fn decrypt_bundle(
    envelope: &Value,
    passphrase: &str,
) -> Result<BTreeMap<String, String>, SecretsError> {
    if passphrase.is_empty() {
        return Err(SecretsError::NoPassphrase);
    }
    if envelope.get("version").and_then(Value::as_i64) != Some(BUNDLE_VERSION) {
        return Err(SecretsError::Invalid(format!(
            "Unsupported encrypted bundle version: {}",
            envelope.get("version").unwrap_or(&Value::Null)
        )));
    }
    let kdf = envelope
        .get("kdf")
        .filter(|k| k.is_object())
        .ok_or_else(|| SecretsError::Invalid("Invalid encrypted bundle metadata".into()))?;
    let salt = kdf
        .get("salt")
        .and_then(Value::as_str)
        .and_then(|s| STANDARD.decode(s).ok())
        .ok_or_else(|| SecretsError::Invalid("bad salt".into()))?;
    let iterations = kdf
        .get("iterations")
        .and_then(Value::as_u64)
        .map_or(KDF_ITERATIONS, |i| i as u32);
    let token = envelope
        .get("token")
        .and_then(Value::as_str)
        .ok_or_else(|| SecretsError::Invalid("missing token".into()))?;
    let payload = fernet_for(passphrase, &salt, iterations)?
        .decrypt(token)
        .map_err(|_| SecretsError::InvalidToken)?;
    let data: Value =
        serde_json::from_slice(&payload).map_err(|e| SecretsError::Invalid(e.to_string()))?;
    let obj = data
        .as_object()
        .ok_or_else(|| SecretsError::Invalid("Invalid decrypted bundle payload".into()))?;
    Ok(obj
        .iter()
        .filter_map(|(k, v)| Some((k.clone(), v.as_str()?.to_string())))
        .collect())
}

fn fernet_for(
    passphrase: &str,
    salt: &[u8],
    iterations: u32,
) -> Result<fernet::Fernet, SecretsError> {
    let mut key = [0u8; 32];
    pbkdf2::pbkdf2_hmac::<sha2::Sha256>(passphrase.as_bytes(), salt, iterations, &mut key);
    fernet::Fernet::new(&URL_SAFE.encode(key))
        .ok_or_else(|| SecretsError::Invalid("could not derive key".into()))
}

/// Read and decrypt a bundle file.
pub fn read_bundle(
    path: &Path,
    passphrase: &str,
) -> Result<BTreeMap<String, String>, SecretsError> {
    let text = std::fs::read_to_string(path)?;
    let envelope: Value =
        serde_json::from_str(&text).map_err(|e| SecretsError::Invalid(e.to_string()))?;
    decrypt_bundle(&envelope, passphrase)
}

/// Encrypt and write a bundle file (pretty-printed like Python's `indent=2`).
pub fn write_bundle(
    path: &Path,
    secrets: &BTreeMap<String, String>,
    passphrase: &str,
) -> Result<(), SecretsError> {
    let envelope = encrypt_bundle(secrets, passphrase)?;
    let text = serde_json::to_string_pretty(&envelope).expect("serialisable envelope");
    crate::write_atomic(path, text.as_bytes()).map_err(|e| SecretsError::Invalid(e.to_string()))
}

/// The existing portable bundle in `config_dir`, if any.
pub fn find_bundle(config_dir: &Path) -> Option<std::path::PathBuf> {
    BUNDLE_FILE_NAMES
        .iter()
        .map(|name| config_dir.join(name))
        .find(|p| p.exists())
}

/// Copy decrypted bundle keys into the in-memory settings.
pub fn apply(settings: &mut AppSettings, secrets: &BTreeMap<String, String>) {
    for (name, value) in secrets {
        if let Some(field) = api_key_mut(settings, name) {
            *field = value.clone();
        }
    }
}

#[cfg(windows)]
mod backend {
    //! python-keyring's `WinVaultKeyring` layout on the Credential Manager.

    use std::ptr::null_mut;
    use windows_sys::Win32::Security::Credentials::{
        CredDeleteW, CredFree, CredReadW, CredWriteW, CREDENTIALW, CRED_PERSIST_ENTERPRISE,
        CRED_TYPE_GENERIC,
    };

    struct Cred {
        user: String,
        secret: String,
    }

    fn wide(s: &str) -> Vec<u16> {
        s.encode_utf16().chain(Some(0)).collect()
    }

    fn from_wide(p: *const u16) -> String {
        if p.is_null() {
            return String::new();
        }
        let mut len = 0;
        // SAFETY: Credential Manager strings are NUL-terminated.
        unsafe {
            while *p.add(len) != 0 {
                len += 1;
            }
            String::from_utf16_lossy(std::slice::from_raw_parts(p, len))
        }
    }

    /// python-keyring writes UTF-16-LE and falls back to UTF-8 on read.
    fn decode(blob: &[u8]) -> String {
        if blob.len().is_multiple_of(2) {
            let units: Vec<u16> = blob
                .as_chunks::<2>()
                .0
                .iter()
                .map(|c| u16::from_le_bytes(*c))
                .collect();
            if let Ok(s) = String::from_utf16(&units) {
                return s;
            }
        }
        String::from_utf8_lossy(blob).into_owned()
    }

    fn read(target: &str) -> Option<Cred> {
        let target = wide(target);
        let mut p: *mut CREDENTIALW = null_mut();
        // SAFETY: valid NUL-terminated target; `p` is freed with CredFree.
        unsafe {
            if CredReadW(target.as_ptr(), CRED_TYPE_GENERIC, 0, &mut p) == 0 {
                return None;
            }
            let c = &*p;
            let blob = if c.CredentialBlob.is_null() {
                &[][..]
            } else {
                std::slice::from_raw_parts(c.CredentialBlob, c.CredentialBlobSize as usize)
            };
            let cred = Cred {
                user: from_wide(c.UserName),
                secret: decode(blob),
            };
            CredFree(p as *const _);
            Some(cred)
        }
    }

    fn write(target: &str, user: &str, secret: &str) -> bool {
        let mut target = wide(target);
        let mut user = wide(user);
        let mut comment = wide("Stored using python-keyring");
        let mut blob: Vec<u8> = secret.encode_utf16().flat_map(u16::to_le_bytes).collect();
        let cred = CREDENTIALW {
            Flags: 0,
            Type: CRED_TYPE_GENERIC,
            TargetName: target.as_mut_ptr(),
            Comment: comment.as_mut_ptr(),
            LastWritten: unsafe { std::mem::zeroed() },
            CredentialBlobSize: blob.len() as u32,
            CredentialBlob: blob.as_mut_ptr(),
            Persist: CRED_PERSIST_ENTERPRISE,
            AttributeCount: 0,
            Attributes: null_mut(),
            TargetAlias: null_mut(),
            UserName: user.as_mut_ptr(),
        };
        // SAFETY: every pointer in `cred` outlives the call.
        unsafe { CredWriteW(&cred, 0) != 0 }
    }

    fn remove(target: &str) -> bool {
        let target = wide(target);
        // SAFETY: valid NUL-terminated target.
        unsafe { CredDeleteW(target.as_ptr(), CRED_TYPE_GENERIC, 0) != 0 }
    }

    fn compound(service: &str, user: &str) -> String {
        format!("{user}@{service}")
    }

    pub fn get(service: &str, user: &str) -> Option<String> {
        match read(service) {
            Some(c) if c.user == user => Some(c.secret),
            _ => read(&compound(service, user)).map(|c| c.secret),
        }
    }

    pub fn set(service: &str, user: &str, secret: &str) -> bool {
        // Like python-keyring: move whoever holds the plain service target to
        // its compound name, then take the service target.
        if let Some(existing) = read(service) {
            if existing.user != user
                && !write(
                    &compound(service, &existing.user),
                    &existing.user,
                    &existing.secret,
                )
            {
                return false;
            }
        }
        write(service, user, secret)
    }

    pub fn delete(service: &str, user: &str) -> bool {
        let mut ok = true;
        for target in [service.to_string(), compound(service, user)] {
            if read(&target).is_some_and(|c| c.user == user) {
                ok &= remove(&target);
            }
        }
        ok
    }
}

#[cfg(not(windows))]
mod backend {
    //! Keychain / Secret Service with python-keyring's service and username.

    fn entry(service: &str, user: &str) -> Option<keyring::Entry> {
        keyring::Entry::new(service, user)
            .inspect_err(|e| tracing::warn!("keyring unavailable: {e}"))
            .ok()
    }

    pub fn get(service: &str, user: &str) -> Option<String> {
        entry(service, user)?.get_password().ok()
    }

    pub fn set(service: &str, user: &str, secret: &str) -> bool {
        entry(service, user).is_some_and(|e| e.set_password(secret).is_ok())
    }

    pub fn delete(service: &str, user: &str) -> bool {
        match entry(service, user).map(|e| e.delete_credential()) {
            Some(Ok(())) | Some(Err(keyring::Error::NoEntry)) => true,
            Some(Err(e)) => {
                tracing::error!("Failed to delete credential for {user}: {e}");
                false
            }
            None => true,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bundle_round_trips_and_rejects_wrong_passphrase() {
        let secrets = BTreeMap::from([("pirate_weather_api_key".to_string(), "abc".to_string())]);
        let envelope = encrypt_bundle(&secrets, "hunter2").unwrap();
        assert_eq!(envelope["kdf"]["name"], "pbkdf2-sha256");
        assert_eq!(decrypt_bundle(&envelope, "hunter2").unwrap(), secrets);
        assert!(matches!(
            decrypt_bundle(&envelope, "nope"),
            Err(SecretsError::InvalidToken)
        ));
    }

    /// Envelope produced by the Python app's `encrypt_secret_bundle`
    /// (passphrase "pass", 1000 iterations to keep the test fast).
    #[test]
    fn decrypts_python_bundle() {
        let envelope = json!({
            "version": 1,
            "cipher": "fernet",
            "kdf": {"name": "pbkdf2-sha256", "iterations": 1000, "salt": "AAECAwQFBgcICQoLDA0ODw=="},
            "token": PYTHON_TOKEN,
        });
        let secrets = decrypt_bundle(&envelope, "pass").unwrap();
        assert_eq!(secrets["openrouter_api_key"], "sk-test");
    }

    const PYTHON_TOKEN: &str = "gAAAAABqtk2-_OIojw2yoSuFbFYkUqlCVYgAP9XxtC5Y6hqsqmmBGic5nCl5RFtvEI7kZAxdbpva2m7kCf-gigeYUmj0HG05U0EG6NpfVm8pdH6FYYZgyZIETPm1qVNvxdzHYnExrAUO";

    #[cfg(windows)]
    #[test]
    fn credential_manager_matches_python_keyring_layout() {
        let service = format!("accessiweather-test-{}", std::process::id());
        assert!(backend::set(&service, "a_key", "one"));
        assert!(backend::set(&service, "b_key", "two"));
        // "b_key" now holds the plain target; "a_key" moved to its compound name.
        assert_eq!(backend::get(&service, "a_key").as_deref(), Some("one"));
        assert_eq!(backend::get(&service, "b_key").as_deref(), Some("two"));
        assert!(backend::set(&service, "a_key", "three"));
        assert_eq!(backend::get(&service, "a_key").as_deref(), Some("three"));
        assert_eq!(backend::get(&service, "b_key").as_deref(), Some("two"));
        for user in ["a_key", "b_key"] {
            assert!(backend::delete(&service, user));
            assert!(backend::get(&service, user).is_none());
        }
    }
}
