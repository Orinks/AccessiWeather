//! Community sound packs from GitHub (`services/community_soundpack_models.py`,
//! `services/community_soundpack_service.py`) and the pure parts of the
//! Browse Community Sound Packs dialog (`ui/dialogs/community_packs_dialog.py`).
//!
//! Packs come from, in order: a curated `index.json` in the repo root, zip
//! assets of GitHub releases, or the `packs/` folders of the repository
//! (the layout `Orinks/accessiweather-soundpacks` actually uses). Blocking:
//! call from a worker thread.

use std::fs;
use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use base64::Engine;
use serde::Serialize;
use serde_json::{Map, Value};

use crate::http::{retry, sleep, Http, HttpError, Request, ReqwestHttp, Response};
use crate::installer::contained_path;
use crate::py::{get_str, get_str_or, py_repr_str, py_str};

pub const COMMUNITY_REPO_OWNER: &str = "orinks";
pub const COMMUNITY_REPO_NAME: &str = "accessiweather-soundpacks";
const USER_AGENT: &str = "AccessiWeather-CommunityPacks/1.0";
const TIMEOUT: Duration = Duration::from_secs(30);
const CACHE_DURATION: Duration = Duration::from_secs(300);

/// `CommunityPack` (field names match the Python dataclass).
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct CommunityPack {
    pub name: String,
    pub author: String,
    pub description: String,
    pub version: String,
    pub download_url: String,
    pub file_size: Option<i64>,
    pub repository_url: String,
    pub release_tag: String,
    pub download_count: Option<i64>,
    pub created_date: Option<String>,
    pub preview_image_url: Option<String>,
    pub repo_path: Option<String>,
    pub tree_sha: Option<String>,
    #[serde(rename = "ref")]
    pub git_ref: Option<String>,
}

impl std::fmt::Display for CommunityPack {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{} {} by {}", self.name, self.version, self.author)
    }
}

fn mb(bytes: f64) -> String {
    format!("{:.1}", bytes / (1024.0 * 1024.0))
}

impl CommunityPack {
    /// `_pack_key`: stable key for the list's client data.
    pub fn key(&self) -> String {
        format!("{}|{}|{}", self.name, self.author, self.version)
    }

    /// List entry: `"{name} v{version} by {author} ({size} MB)"` or `(?)`.
    pub fn list_label(&self) -> String {
        let size = match self.file_size {
            Some(s) if s != 0 => format!("{} MB", mb(s as f64)),
            _ => "?".into(),
        };
        format!(
            "{} v{} by {} ({size})",
            self.name, self.version, self.author
        )
    }

    /// Details panel: name, `Author: ...`, `Version: ...`, `Size: ...`,
    /// description text.
    pub fn detail_labels(&self) -> [String; 5] {
        let size = match self.file_size {
            Some(s) if s != 0 => format!("Size: {} MB", mb(s as f64)),
            _ => "Size: Unknown".into(),
        };
        let description = if self.description.is_empty() {
            "No description provided.".to_string()
        } else {
            self.description.clone()
        };
        [
            self.name.clone(),
            format!("Author: {}", self.author),
            format!("Version: {}", self.version),
            size,
            description,
        ]
    }

    /// "Download & Install" is enabled when the pack has a source.
    pub fn installable(&self) -> bool {
        !self.download_url.is_empty() || self.repo_path.as_deref().is_some_and(|p| !p.is_empty())
    }

    /// `download_pack`'s file name stem: `"{name}-{version}"`, spaces as `_`.
    /// It is also the folder the pack is installed into.
    pub fn download_stem(&self) -> String {
        format!("{}-{}", self.name, self.version).replace(' ', "_")
    }
}

/// `_populate_list` filter: case-insensitive match on name or author.
pub fn filter_packs<'a>(packs: &'a [CommunityPack], filter_text: &str) -> Vec<&'a CommunityPack> {
    let ft = filter_text.trim().to_lowercase();
    packs
        .iter()
        .filter(|p| {
            ft.is_empty()
                || p.name.to_lowercase().contains(&ft)
                || p.author.to_lowercase().contains(&ft)
        })
        .collect()
}

/// Download progress detail: `"1.2 MB of 3.4 MB"` or `"1.2 MB downloaded"`.
pub fn progress_detail(downloaded: u64, total: u64) -> String {
    if total > 0 {
        format!("{} MB of {} MB", mb(downloaded as f64), mb(total as f64))
    } else {
        format!("{} MB downloaded", mb(downloaded as f64))
    }
}

#[derive(Debug, thiserror::Error)]
pub enum CommunityError {
    #[error("{0}")]
    Http(#[from] HttpError),
    /// Python `RuntimeError`, with its message.
    #[error("{0}")]
    Runtime(String),
    /// The progress callback asked to stop.
    #[error("Download cancelled by callback")]
    Cancelled,
    #[error("{0}")]
    Io(#[from] std::io::Error),
}

impl CommunityError {
    /// Default `async_retry_with_backoff` policy: network errors and `OSError`.
    fn retryable_default(&self) -> bool {
        matches!(self, Self::Http(_) | Self::Io(_))
    }

    /// `retryable_exceptions=(RuntimeError,)` (network errors still count).
    fn retryable_runtime(&self) -> bool {
        matches!(self, Self::Http(_) | Self::Runtime(_))
    }
}

fn opt_i64(obj: &Map<String, Value>, key: &str) -> Option<i64> {
    obj.get(key).and_then(Value::as_i64)
}

fn opt_str(obj: &Map<String, Value>, key: &str) -> Option<String> {
    obj.get(key).filter(|v| !v.is_null()).map(py_str)
}

/// Packs listed in a curated `index.json`.
pub fn parse_index(index: &Value, owner: &str, repo: &str) -> Vec<CommunityPack> {
    let entries = index.get("packs").and_then(Value::as_array);
    entries
        .into_iter()
        .flatten()
        .filter_map(Value::as_object)
        .map(|e| CommunityPack {
            name: get_str_or(e, "name", &get_str_or(e, "id", "unknown")),
            author: get_str(e, "author", "Unknown"),
            description: get_str(e, "description", ""),
            version: get_str(e, "version", "1.0"),
            download_url: get_str(e, "download_url", ""),
            file_size: opt_i64(e, "file_size"),
            repository_url: get_str_or(
                e,
                "homepage",
                &format!("https://github.com/{owner}/{repo}"),
            ),
            release_tag: get_str(e, "release_tag", ""),
            download_count: opt_i64(e, "download_count"),
            created_date: opt_str(e, "created_date"),
            preview_image_url: opt_str(e, "preview_image_url"),
            repo_path: None,
            tree_sha: None,
            git_ref: Some("main".into()),
        })
        .collect()
}

/// One pack per `.zip` asset of each release.
pub fn parse_releases(releases: &Value, owner: &str, repo: &str) -> Vec<CommunityPack> {
    let mut packs = Vec::new();
    for release in releases
        .as_array()
        .into_iter()
        .flatten()
        .filter_map(Value::as_object)
    {
        let tag = get_str_or(release, "tag_name", "");
        let body = get_str_or(release, "body", "");
        let author = release
            .get("author")
            .and_then(Value::as_object)
            .map(|a| get_str(a, "login", "Unknown"))
            .unwrap_or_else(|| "Unknown".into());
        let html_url = get_str_or(
            release,
            "html_url",
            &format!("https://github.com/{owner}/{repo}/releases"),
        );
        let version = match tag.trim_start_matches('v') {
            "" => "1.0".to_string(),
            v => v.to_string(),
        };
        let assets = release.get("assets").and_then(Value::as_array);
        for asset in assets.into_iter().flatten().filter_map(Value::as_object) {
            let name = get_str_or(asset, "name", "");
            if !name.to_lowercase().ends_with(".zip") {
                continue;
            }
            let pack_name = match name.rfind(".zip") {
                Some(i) => name[..i].to_string(),
                None => name.clone(),
            };
            packs.push(CommunityPack {
                name: pack_name,
                author: author.clone(),
                description: body.trim().to_string(),
                version: version.clone(),
                download_url: opt_str(asset, "browser_download_url").unwrap_or_default(),
                file_size: opt_i64(asset, "size"),
                repository_url: html_url.clone(),
                release_tag: tag.clone(),
                download_count: opt_i64(asset, "download_count"),
                created_date: opt_str(release, "published_at"),
                preview_image_url: None,
                repo_path: None,
                tree_sha: None,
                git_ref: Some("main".into()),
            });
        }
    }
    packs
}

fn blob_size_total(tree: &[Value]) -> i64 {
    tree.iter()
        .filter(|item| item.get("type").and_then(Value::as_str) == Some("blob"))
        .map(|item| item.get("size").and_then(Value::as_i64).unwrap_or(0))
        .sum()
}

/// `CommunitySoundPackService`.
pub struct CommunitySoundPackService {
    http: Arc<dyn Http>,
    pub repo_owner: String,
    pub repo_name: String,
    cache: Mutex<Option<(Instant, Vec<CommunityPack>)>>,
}

impl CommunitySoundPackService {
    /// Service for `orinks/accessiweather-soundpacks` over HTTPS.
    pub fn new() -> Result<Self, HttpError> {
        Ok(Self::with_http(
            Arc::new(ReqwestHttp::new(TIMEOUT)?),
            COMMUNITY_REPO_OWNER,
            COMMUNITY_REPO_NAME,
        ))
    }

    pub fn with_http(http: Arc<dyn Http>, repo_owner: &str, repo_name: &str) -> Self {
        Self {
            http,
            repo_owner: repo_owner.into(),
            repo_name: repo_name.into(),
            cache: Mutex::new(None),
        }
    }

    fn get(&self, url: &str, timeout: Option<Duration>) -> Result<Response, HttpError> {
        self.http.send(Request::get(
            url,
            &[
                ("User-Agent", USER_AGENT),
                ("Accept", "application/vnd.github+json"),
            ],
            timeout,
        ))
    }

    fn get_json(&self, url: &str) -> Result<(u16, Result<Value, String>), HttpError> {
        let response = self.get(url, Some(TIMEOUT))?;
        let status = response.status;
        Ok((status, response.json()?))
    }

    /// `fetch_available_packs`: cached for five minutes unless `force_refresh`.
    pub fn fetch_available_packs(
        &self,
        force_refresh: bool,
    ) -> Result<Vec<CommunityPack>, CommunityError> {
        if !force_refresh {
            if let Some((at, packs)) = &*self.cache.lock().unwrap_or_else(|e| e.into_inner()) {
                if at.elapsed() < CACHE_DURATION {
                    return Ok(packs.clone());
                }
            }
        }
        let packs = retry(
            3,
            Duration::from_secs(1),
            CommunityError::retryable_default,
            || self.fetch_uncached(),
        )?;
        *self.cache.lock().unwrap_or_else(|e| e.into_inner()) =
            Some((Instant::now(), packs.clone()));
        Ok(packs)
    }

    fn fetch_uncached(&self) -> Result<Vec<CommunityPack>, CommunityError> {
        let (owner, repo) = (&self.repo_owner, &self.repo_name);
        let mut packs = Vec::new();

        let url = format!("https://api.github.com/repos/{owner}/{repo}/contents/index.json");
        match self.get_json(&url) {
            Ok((200, Ok(data))) => {
                if let Some(content) = data.get("content").map(py_str).filter(|c| !c.is_empty()) {
                    match decode_index(&content) {
                        Ok(index) => packs = parse_index(&index, owner, repo),
                        Err(e) => tracing::warn!("Failed to parse curated index.json: {e}"),
                    }
                }
            }
            Ok((200, Err(e))) => tracing::info!("Curated index.json not available or failed: {e}"),
            Ok(_) => {}
            Err(e) => {
                tracing::info!("Curated index.json not available or failed: {e}");
                return Err(e.into());
            }
        }

        if packs.is_empty() {
            let url = format!("https://api.github.com/repos/{owner}/{repo}/releases?per_page=50");
            match self.get_json(&url) {
                Ok((200, Ok(releases))) => packs = parse_releases(&releases, owner, repo),
                Ok((200, Err(e))) => tracing::error!("Failed to fetch releases: {e}"),
                Ok((403, _)) => {
                    tracing::warn!("GitHub API rate limit reached while fetching releases.")
                }
                Ok((status, _)) => tracing::warn!("Unexpected GitHub API status: {status}"),
                Err(e) => {
                    tracing::error!("Failed to fetch releases: {e}");
                    return Err(e.into());
                }
            }
        }

        if packs.is_empty() {
            match retry(
                2,
                Duration::from_secs(1),
                CommunityError::retryable_default,
                || self.fetch_repo_directory_packs(),
            ) {
                Ok(found) => packs = found,
                Err(e) => {
                    tracing::error!("Failed to discover packs from repository contents: {e}");
                    if matches!(e, CommunityError::Http(_)) {
                        return Err(e);
                    }
                }
            }
        }
        Ok(packs)
    }

    /// `_fetch_repo_directory_packs`: one pack per folder under `packs/`.
    fn fetch_repo_directory_packs(&self) -> Result<Vec<CommunityPack>, CommunityError> {
        let (owner, repo, git_ref) = (&self.repo_owner, &self.repo_name, "main");
        let url =
            format!("https://api.github.com/repos/{owner}/{repo}/contents/packs?ref={git_ref}");
        let (status, entries) = self.get_json(&url)?;
        if status != 200 {
            tracing::debug!("Repository contents fallback unavailable (status {status})");
            return Ok(Vec::new());
        }
        let entries = entries.map_err(CommunityError::Runtime)?;
        let mut packs = Vec::new();
        for entry in entries
            .as_array()
            .into_iter()
            .flatten()
            .filter_map(Value::as_object)
        {
            if entry.get("type").and_then(Value::as_str) != Some("dir") {
                continue;
            }
            let dir_name = get_str_or(entry, "name", "unknown");
            let repo_path = get_str_or(entry, "path", &format!("packs/{dir_name}"));
            let tree_sha = opt_str(entry, "sha");
            let pack_json_url = format!(
                "https://raw.githubusercontent.com/{owner}/{repo}/{git_ref}/{repo_path}/pack.json"
            );
            let meta = match self.get_json(&pack_json_url) {
                Ok((200, Ok(Value::Object(meta)))) => meta,
                Ok((200, _)) => {
                    tracing::debug!("Skipping pack {dir_name}: failed to parse pack.json");
                    continue;
                }
                Ok(_) => {
                    tracing::debug!("Skipping pack {dir_name}: pack.json not found");
                    continue;
                }
                Err(e) => {
                    tracing::debug!("Skipping pack {dir_name}: failed to parse pack.json ({e})");
                    continue;
                }
            };
            let total_size = retry(
                2,
                Duration::from_secs(1),
                CommunityError::retryable_default,
                || self.calculate_tree_size(tree_sha.as_deref()),
            )?;
            packs.push(CommunityPack {
                name: get_str_or(&meta, "name", &dir_name),
                author: get_str(&meta, "author", "Unknown"),
                description: get_str(&meta, "description", ""),
                version: get_str(&meta, "version", "1.0"),
                download_url: String::new(),
                file_size: total_size,
                repository_url: format!(
                    "https://github.com/{owner}/{repo}/tree/{git_ref}/{repo_path}"
                ),
                release_tag: git_ref.into(),
                download_count: None,
                created_date: None,
                preview_image_url: opt_str(&meta, "preview_image_url"),
                repo_path: Some(repo_path),
                tree_sha,
                git_ref: Some(git_ref.into()),
            });
        }
        Ok(packs)
    }

    fn tree_url(&self, sha: &str) -> String {
        format!(
            "https://api.github.com/repos/{}/{}/git/trees/{sha}?recursive=1",
            self.repo_owner, self.repo_name
        )
    }

    /// `_calculate_tree_size`: total bytes of the folder's files.
    fn calculate_tree_size(&self, tree_sha: Option<&str>) -> Result<Option<i64>, CommunityError> {
        let Some(sha) = tree_sha.filter(|s| !s.is_empty()) else {
            return Ok(None);
        };
        let (status, data) = self.get_json(&self.tree_url(sha))?;
        if status != 200 {
            return Ok(None);
        }
        Ok(data.ok().map(|d| {
            blob_size_total(
                d.get("tree")
                    .and_then(Value::as_array)
                    .map_or(&[], Vec::as_slice),
            )
        }))
    }

    /// `download_pack`: save the pack as a ZIP in `dest_dir` (as
    /// `{name}-{version}.zip`, then `_2`, `_3`... when taken) and return its
    /// path. `progress(percent, downloaded, total)` returns false to cancel.
    pub fn download_pack(
        &self,
        pack: &CommunityPack,
        dest_dir: &Path,
        progress: &mut dyn FnMut(f64, u64, u64) -> bool,
    ) -> Result<PathBuf, CommunityError> {
        fs::create_dir_all(dest_dir)?;
        let base = pack.download_stem();
        let mut final_path = dest_dir.join(format!("{base}.zip"));
        if final_path.exists() {
            let mut i = 2;
            while dest_dir.join(format!("{base}_{i}.zip")).exists() {
                i += 1;
            }
            final_path = dest_dir.join(format!("{base}_{i}.zip"));
        }
        if !pack.download_url.is_empty() {
            return self.download_from_url(pack, &final_path, progress, 2);
        }
        if pack.repo_path.as_deref().is_some_and(|p| !p.is_empty()) {
            return retry(
                2,
                Duration::from_secs(1),
                CommunityError::retryable_runtime,
                || self.download_repo_pack(pack, &final_path, progress),
            );
        }
        Err(CommunityError::Runtime(format!(
            "Pack {} has no download source",
            pack.name
        )))
    }

    fn download_from_url(
        &self,
        pack: &CommunityPack,
        final_path: &Path,
        progress: &mut dyn FnMut(f64, u64, u64) -> bool,
        max_retries: u32,
    ) -> Result<PathBuf, CommunityError> {
        let parent = final_path.parent().unwrap_or(Path::new("."));
        let mut last_error = String::new();
        for attempt in 1..=max_retries + 1 {
            let result = (|| -> Result<(), CommunityError> {
                let response = self.get(&pack.download_url, None)?;
                if response.status != 200 {
                    return Err(CommunityError::Runtime(format!(
                        "Download failed with status {}",
                        response.status
                    )));
                }
                let total = response.content_length.unwrap_or(0);
                let mut tmp = tempfile::Builder::new()
                    .suffix(".zip")
                    .tempfile_in(parent)?;
                copy_with_progress(response.body, tmp.as_file_mut(), total, progress)?;
                tmp.persist(final_path).map_err(|e| e.error)?;
                Ok(())
            })();
            match result {
                Ok(()) => return Ok(final_path.to_path_buf()),
                Err(CommunityError::Cancelled) => {
                    let _ = fs::remove_file(final_path);
                    return Err(CommunityError::Cancelled);
                }
                Err(e) => {
                    tracing::warn!("Download attempt {attempt} failed: {e}");
                    last_error = e.to_string();
                    sleep(Duration::from_secs(u64::from((2 * attempt).min(5))));
                }
            }
        }
        Err(CommunityError::Runtime(format!(
            "Failed to download {}: {last_error}",
            pack.name
        )))
    }

    /// `_fetch_tree_entries`.
    fn fetch_tree_entries(&self, pack: &CommunityPack) -> Result<Vec<Value>, CommunityError> {
        let Some(sha) = pack.tree_sha.as_deref().filter(|s| !s.is_empty()) else {
            return Ok(Vec::new());
        };
        let (status, data) = self.get_json(&self.tree_url(sha))?;
        if status != 200 {
            tracing::error!(
                "Failed to fetch tree {sha} for pack {} (status {status})",
                pack.name
            );
            return Err(CommunityError::Runtime(format!(
                "Tree fetch failed with status {status}"
            )));
        }
        let data = data.map_err(CommunityError::Runtime)?;
        Ok(data
            .get("tree")
            .and_then(Value::as_array)
            .cloned()
            .unwrap_or_default())
    }

    /// `_download_repo_pack`: fetch every file of the pack folder and zip it.
    fn download_repo_pack(
        &self,
        pack: &CommunityPack,
        final_path: &Path,
        progress: &mut dyn FnMut(f64, u64, u64) -> bool,
    ) -> Result<PathBuf, CommunityError> {
        let git_ref = pack
            .git_ref
            .as_deref()
            .filter(|r| !r.is_empty())
            .unwrap_or("main");
        let tree = retry(
            2,
            Duration::from_secs(1),
            CommunityError::retryable_runtime,
            || self.fetch_tree_entries(pack),
        )?;
        if tree.is_empty() {
            return Err(CommunityError::Runtime(format!(
                "No files found for {}",
                pack.name
            )));
        }
        let total = blob_size_total(&tree) as u64;
        let parent = final_path.parent().unwrap_or(Path::new("."));
        let staging = tempfile::Builder::new()
            .prefix("aw_pack_")
            .tempdir_in(parent)?;
        let mut downloaded = 0u64;
        let result = (|| -> Result<(), CommunityError> {
            for item in &tree {
                if item.get("type").and_then(Value::as_str) != Some("blob") {
                    continue;
                }
                let rel_path = item
                    .as_object()
                    .map(|o| get_str_or(o, "path", ""))
                    .unwrap_or_default();
                let target = contained_path(staging.path(), &rel_path).ok_or_else(|| {
                    CommunityError::Runtime(format!(
                        "Unsafe path in repository tree: {}",
                        py_repr_str(&rel_path)
                    ))
                })?;
                if let Some(dir) = target.parent() {
                    fs::create_dir_all(dir)?;
                }
                let raw_url = format!(
                    "https://raw.githubusercontent.com/{}/{}/{git_ref}/{}/{rel_path}",
                    self.repo_owner,
                    self.repo_name,
                    pack.repo_path.as_deref().unwrap_or_default()
                );
                let response = self.get(&raw_url, None)?;
                if response.status != 200 {
                    return Err(CommunityError::Runtime(format!(
                        "Failed to download {rel_path} (status {})",
                        response.status
                    )));
                }
                let mut file = fs::File::create(&target)?;
                let mut offset_progress = |_: f64, done: u64, _: u64| {
                    let now = downloaded + done;
                    let pct = if total > 0 {
                        now as f64 / total as f64 * 100.0
                    } else {
                        0.0
                    };
                    progress(pct, now, total)
                };
                downloaded +=
                    copy_with_progress(response.body, &mut file, 0, &mut offset_progress)?;
            }
            let file = fs::File::create(final_path)?;
            crate::manager::zip_dir(staging.path(), file).map_err(CommunityError::Runtime)?;
            Ok(())
        })();
        if let Err(e) = result {
            if !matches!(e, CommunityError::Cancelled) {
                let _ = fs::remove_file(final_path);
            }
            return Err(e);
        }
        Ok(final_path.to_path_buf())
    }
}

fn decode_index(content_b64: &str) -> Result<Value, String> {
    // GitHub wraps base64 content in newlines; Python's b64decode skips them.
    let compact: String = content_b64.chars().filter(|c| !c.is_whitespace()).collect();
    let bytes = base64::engine::general_purpose::STANDARD
        .decode(compact)
        .map_err(|e| e.to_string())?;
    let text = String::from_utf8(bytes).map_err(|e| e.to_string())?;
    serde_json::from_str(&text).map_err(|e| e.to_string())
}

/// Stream `body` into `out` in 64 KiB chunks, reporting after each chunk.
/// Returns the bytes copied.
fn copy_with_progress(
    mut body: Box<dyn Read + Send>,
    out: &mut dyn Write,
    total: u64,
    progress: &mut dyn FnMut(f64, u64, u64) -> bool,
) -> Result<u64, CommunityError> {
    let mut buf = vec![0u8; 65536];
    let mut downloaded = 0u64;
    loop {
        let n = body
            .read(&mut buf)
            .map_err(|e| CommunityError::Http(HttpError::Request(e.to_string())))?;
        if n == 0 {
            break;
        }
        out.write_all(&buf[..n])?;
        downloaded += n as u64;
        let pct = if total > 0 {
            downloaded as f64 / total as f64 * 100.0
        } else {
            0.0
        };
        if !progress(pct, downloaded, total) {
            return Err(CommunityError::Cancelled);
        }
    }
    out.flush()?;
    Ok(downloaded)
}
