//! `scripts/build_pages.py`: the download page (`index.html` from
//! `docs/index.template.html`), `docs/download-links.md` and `.nojekyll`,
//! built from the repository's GitHub releases. Reads `GITHUB_REPOSITORY`
//! and `GITHUB_TOKEN`; writes into the repository root.
//!
//! `scripts/pages_utils.py` is not ported: nothing uses it since the
//! `update-pages.yml` workflow it served was removed.

use chrono::{DateTime, Utc};
use serde_json::{json, Value};

use crate::Result;

pub fn build() -> Result<()> {
    let repo = std::env::var("GITHUB_REPOSITORY").map_err(|_| "GITHUB_REPOSITORY is not set")?;
    let token = std::env::var("GITHUB_TOKEN").unwrap_or_default();
    let client = reqwest::blocking::Client::builder()
        .user_agent("AccessiWeather-Pages")
        .build()?;
    let github = |req: reqwest::blocking::RequestBuilder| {
        req.header("Accept", "application/vnd.github+json")
            .header("Authorization", format!("Bearer {token}"))
            .header("X-GitHub-Api-Version", "2022-11-28")
    };
    let releases: Vec<Value> = github(client.get(format!(
        "https://api.github.com/repos/{repo}/releases?per_page=100"
    )))
    .send()?
    .error_for_status()?
    .json()?;
    let render_markdown = |text: &str| {
        github(client.post("https://api.github.com/markdown"))
            .json(&json!({"text": text, "mode": "gfm", "context": repo}))
            .send()
            .and_then(|r| r.error_for_status())
            .and_then(|r| r.text())
            .unwrap_or_else(|_| format!("<pre>{}</pre>", html_escape(text)))
    };

    let root = crate::repo_root();
    let template = std::fs::read_to_string(root.join("docs/index.template.html"))?;
    let page = render(&template, &releases, &repo, Utc::now(), render_markdown);
    std::fs::write(root.join("index.html"), page.index)?;
    std::fs::write(root.join("docs/download-links.md"), page.download_links)?;
    std::fs::write(root.join(".nojekyll"), "")?;
    Ok(())
}

pub struct Page {
    pub index: String,
    pub download_links: String,
}

/// The page for `releases`; `markdown` renders release notes to HTML.
pub fn render(
    template: &str,
    releases: &[Value],
    repo: &str,
    now: DateTime<Utc>,
    markdown: impl Fn(&str) -> String,
) -> Page {
    let releases_url = format!("https://github.com/{repo}/releases");
    let render_notes = |release: Option<&Value>, missing: &str| {
        match release
            .map(|r| str_field(r, "body"))
            .filter(|b| !b.is_empty())
        {
            // A blank body renders to nothing, like build_pages.render_markdown.
            Some(body) if body.trim().is_empty() => String::new(),
            Some(body) => markdown(body),
            None => format!("<p>{missing} <a href=\"{releases_url}\">View releases</a></p>"),
        }
    };
    let stable = latest_release(releases, false);
    let prerelease = latest_release(releases, true);
    let tag = |r: Option<&Value>, default: &str| {
        r.and_then(|r| r.get("tag_name")?.as_str())
            .unwrap_or(default)
            .trim_start_matches('v')
            .to_string()
    };
    let field =
        |r: Option<&Value>, key: &str| r.map(|r| str_field(r, key)).unwrap_or("").to_string();

    let main_version = tag(stable, "Latest Release");
    let main_date = format_date(stable.and_then(|r| r.get("published_at")?.as_str()));
    let main = asset_info(stable, &releases_url);
    let dev_version = tag(prerelease, "Development");
    let dev_date = format_date(prerelease.and_then(|r| r.get("published_at")?.as_str()));
    let dev = asset_info(prerelease, &releases_url);
    let dev_release_url = prerelease
        .and_then(|r| r.get("html_url")?.as_str())
        .unwrap_or(&releases_url)
        .to_string();
    let last_updated = now.format("%Y-%m-%d %H:%M UTC").to_string();
    let has = |r: Option<&Value>| if r.is_some() { "true" } else { "false" };

    let substitutions = [
        ("MAIN_VERSION", main_version.clone()),
        ("MAIN_DATE", main_date.clone()),
        ("MAIN_COMMIT", field(stable, "target_commitish")),
        ("MAIN_INSTALLER_URL", main.installer.0.clone()),
        ("MAIN_PORTABLE_URL", main.portable.0.clone()),
        ("MAIN_MACOS_INSTALLER_URL", main.macos.0.clone()),
        (
            "MAIN_INSTALLER_DOWNLOADS",
            format_downloads(main.installer.1),
        ),
        ("MAIN_PORTABLE_DOWNLOADS", format_downloads(main.portable.1)),
        ("MAIN_MACOS_DOWNLOADS", format_downloads(main.macos.1)),
        ("MAIN_TOTAL_DOWNLOADS", format_downloads(main.total)),
        ("MAIN_HAS_RELEASE", has(stable).into()),
        (
            "MAIN_RELEASE_NOTES",
            render_notes(stable, "No stable release available."),
        ),
        ("DEV_VERSION", dev_version.clone()),
        ("DEV_DATE", dev_date.clone()),
        ("DEV_COMMIT", field(prerelease, "target_commitish")),
        ("DEV_RELEASE_URL", dev_release_url),
        ("DEV_INSTALLER_URL", dev.installer.0.clone()),
        ("DEV_PORTABLE_URL", dev.portable.0.clone()),
        ("DEV_MACOS_INSTALLER_URL", dev.macos.0.clone()),
        ("DEV_INSTALLER_DOWNLOADS", format_downloads(dev.installer.1)),
        ("DEV_PORTABLE_DOWNLOADS", format_downloads(dev.portable.1)),
        ("DEV_MACOS_DOWNLOADS", format_downloads(dev.macos.1)),
        ("DEV_TOTAL_DOWNLOADS", format_downloads(dev.total)),
        ("DEV_HAS_RELEASE", has(prerelease).into()),
        (
            "DEV_RELEASE_NOTES",
            render_notes(prerelease, "No pre-release available."),
        ),
        ("LAST_UPDATED", last_updated.clone()),
    ];
    let mut index = template.to_string();
    for (key, value) in substitutions {
        index = index.replace(&format!("{{{{{key}}}}}"), &value);
    }
    let download_links = format!(
        "# AccessiWeather Download Links\n\n\
         All downloads are on GitHub: {releases_url}\n\n\
         ## Build Info\n\n\
         - Main version: {main_version}\n\
         - Main date: {main_date}\n\
         - Dev version: {dev_version}\n\
         - Dev date: {dev_date}\n\
         - Last updated: {last_updated}\n"
    );
    Page {
        index,
        download_links,
    }
}

fn str_field<'a>(value: &'a Value, key: &str) -> &'a str {
    value.get(key).and_then(Value::as_str).unwrap_or("")
}

/// Python truthiness of a JSON value.
fn truthy(value: Option<&Value>) -> bool {
    match value {
        None | Some(Value::Null) => false,
        Some(Value::Bool(b)) => *b,
        Some(Value::Number(n)) => n.as_f64() != Some(0.0),
        Some(Value::String(s)) => !s.is_empty(),
        Some(Value::Array(a)) => !a.is_empty(),
        Some(Value::Object(o)) => !o.is_empty(),
    }
}

/// The newest non-draft release whose `prerelease` equals `prerelease` (the
/// API lists newest first; a missing flag counts as false).
fn latest_release(releases: &[Value], prerelease: bool) -> Option<&Value> {
    let flag_is = |v: Option<&Value>| match v {
        None => !prerelease,
        Some(Value::Bool(b)) => *b == prerelease,
        Some(Value::Number(n)) => n.as_f64() == Some(if prerelease { 1.0 } else { 0.0 }),
        _ => false,
    };
    releases
        .iter()
        .filter(|r| !truthy(r.get("draft")))
        .find(|r| flag_is(r.get("prerelease")))
}

/// An ISO date as `YYYY-MM-DD HH:MM UTC`; "N/A" when missing, the input
/// itself when unparseable.
fn format_date(date: Option<&str>) -> String {
    let Some(date) = date.filter(|d| !d.is_empty()) else {
        return "N/A".into();
    };
    DateTime::parse_from_rfc3339(&date.replace('Z', "+00:00"))
        .map(|d| d.format("%Y-%m-%d %H:%M UTC").to_string())
        .unwrap_or_else(|_| date.to_string())
}

/// `(url, downloads)` per download button, and the release's total downloads.
struct Assets {
    installer: (String, u64),
    portable: (String, u64),
    macos: (String, u64),
    total: u64,
}

fn asset_info(release: Option<&Value>, releases_url: &str) -> Assets {
    let mut info = Assets {
        installer: (releases_url.into(), 0),
        portable: (releases_url.into(), 0),
        macos: (releases_url.into(), 0),
        total: 0,
    };
    let Some(release) = release else { return info };
    let release_url = release
        .get("html_url")
        .and_then(Value::as_str)
        .unwrap_or(releases_url);
    let assets = release.get("assets").and_then(Value::as_array);
    for asset in assets.into_iter().flatten() {
        let name = str_field(asset, "name").to_lowercase();
        let url = asset
            .get("browser_download_url")
            .and_then(Value::as_str)
            .unwrap_or(release_url)
            .to_string();
        let downloads = asset
            .get("download_count")
            .and_then(Value::as_u64)
            .unwrap_or(0);
        info.total += downloads;
        if name.ends_with(".msi") || name.contains("setup") && name.ends_with(".exe") {
            info.installer = (url, downloads);
        } else if name.contains("portable") && name.ends_with(".zip") {
            info.portable = (url, downloads);
        } else if name.ends_with(".dmg") {
            info.macos = (url, downloads);
        }
    }
    info
}

/// A count with thousands separators (`f"{count:,}"`).
fn format_downloads(count: u64) -> String {
    let digits = count.to_string();
    let mut out = String::new();
    for (i, c) in digits.chars().enumerate() {
        if i > 0 && (digits.len() - i).is_multiple_of(3) {
            out.push(',');
        }
        out.push(c);
    }
    out
}

/// Python's `html.escape` (quotes included).
pub fn html_escape(text: &str) -> String {
    text.replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
        .replace('\'', "&#x27;")
}

#[cfg(test)]
mod tests {
    //! Golden parity with `scripts/build_pages.py`, recorded by
    //! `rust/tools/golden/pages.py` with a fixed clock and a stand-in
    //! Markdown renderer.

    use chrono::TimeZone;

    use super::*;

    #[test]
    fn matches_python_build_pages() {
        let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("../testdata/golden/pages/cases.json");
        let golden: Value = serde_json::from_str(&std::fs::read_to_string(path).unwrap()).unwrap();
        let now = Utc.with_ymd_and_hms(2026, 9, 25, 12, 34, 56).unwrap();
        for case in golden["cases"].as_array().unwrap() {
            let repo = case["repo"].as_str().unwrap();
            let template = if case["full_template"].as_bool().unwrap() {
                &golden["template"]
            } else {
                &golden["compact_template"]
            };
            let page = render(
                template.as_str().unwrap(),
                case["releases"].as_array().unwrap(),
                repo,
                now,
                |text| format!("<div data-repo=\"{repo}\">{}</div>", html_escape(text)),
            );
            let name = case["name"].as_str().unwrap();
            assert_eq!(page.index, case["index"].as_str().unwrap(), "{name}");
            assert_eq!(
                page.download_links,
                case["download_links"].as_str().unwrap(),
                "{name}"
            );
        }
        assert_eq!(format_downloads(1234567), "1,234,567");
        assert_eq!(format_downloads(999), "999");
    }
}
