//! The Report Issue dialog's logic (`ui/dialogs/report_issue_dialog.py`):
//! issue types, the system info block and the pre-filled GitHub URL.

pub const GITHUB_REPO: &str = "Orinks/AccessiWeather";
pub const ISSUE_URL: &str = "https://github.com/Orinks/AccessiWeather/issues/new";
/// Choices of the "Issue Type:" list; the first is selected.
pub const ISSUE_TYPES: [&str; 2] = ["Bug Report", "Feature Request"];
pub const TITLE_REQUIRED_TITLE: &str = "Title Required";
pub const TITLE_REQUIRED: &str = "Please enter a title for the issue.";

/// The auto-collected block. Python's third line is its interpreter
/// version; the Rust edition names itself there instead.
pub fn format_system_info(
    app_version: &str,
    os_system: &str,
    os_release: &str,
    runtime: (&str, &str),
) -> String {
    format!(
        "- App Version: {app_version}\n- OS: {os_system} {os_release}\n- {}: {}",
        runtime.0, runtime.1
    )
}

/// System info for this machine.
pub fn system_info() -> String {
    format_system_info(
        env!("CARGO_PKG_VERSION"),
        os_system(),
        &os_release(),
        ("Edition", "Rust"),
    )
}

/// `platform.system()`.
pub fn os_system() -> &'static str {
    match std::env::consts::OS {
        "windows" => "Windows",
        "macos" => "Darwin",
        "linux" => "Linux",
        other => other,
    }
}

/// `platform.release()`: "10"/"11" on Windows, the kernel release elsewhere.
pub fn os_release() -> String {
    #[cfg(windows)]
    {
        let build = crate::startup::machine_registry_string(
            r"SOFTWARE\Microsoft\Windows NT\CurrentVersion",
            "CurrentBuildNumber",
        )
        .and_then(|b| b.parse::<u32>().ok())
        .unwrap_or(0);
        if build >= 22000 { "11" } else { "10" }.to_string()
    }
    #[cfg(not(windows))]
    {
        std::process::Command::new("uname")
            .arg("-r")
            .output()
            .map(|o| String::from_utf8_lossy(&o.stdout).trim().to_string())
            .unwrap_or_default()
    }
}

/// The new-issue URL, or the "Title Required" message when the title is blank.
/// `issue_type` is the selected index of [`ISSUE_TYPES`].
pub fn build_issue_url(
    issue_type: usize,
    title: &str,
    description: &str,
    system_info: &str,
) -> Result<String, &'static str> {
    let title = crate::py_strip(title);
    if title.is_empty() {
        return Err(TITLE_REQUIRED);
    }
    let description = crate::py_strip(description);
    let mut body_parts = Vec::new();
    if !description.is_empty() {
        body_parts.push(description);
    }
    body_parts.extend(["\n---\n**System Information:**\n```", system_info, "```"]);
    let body = body_parts.join("\n");
    let label = if issue_type == 0 {
        "bug"
    } else {
        "enhancement"
    };
    Ok(format!(
        "{ISSUE_URL}?{}",
        crate::urlencode(&[("title", title), ("body", &body), ("labels", label)])
    ))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn url_is_prefilled_and_encoded() {
        let info = format_system_info("1.0", "Windows", "11", ("Edition", "Rust"));
        assert_eq!(
            info,
            "- App Version: 1.0\n- OS: Windows 11\n- Edition: Rust"
        );
        let url = build_issue_url(0, " Test & Title ", "", &info).unwrap();
        assert!(url.starts_with(
            "https://github.com/Orinks/AccessiWeather/issues/new?title=Test+%26+Title&body=%0A---"
        ));
        assert!(url.ends_with("&labels=bug"));
        assert!(build_issue_url(1, "x", "d", "i")
            .unwrap()
            .ends_with("labels=enhancement"));
        assert_eq!(build_issue_url(0, "  ", "d", "i"), Err(TITLE_REQUIRED));
        assert!(system_info().contains(env!("CARGO_PKG_VERSION")));
    }
}
