//! `cargo xtask <cmd>`: the build, packaging and release tooling that used to
//! be the Python scripts under `scripts/` and `installer/`.

mod changelog;
mod icons;
mod package;
mod pages;
mod streams;

use std::path::{Path, PathBuf};
use std::process::{Command, ExitCode};

use clap::{Parser, Subcommand};

type Result<T> = std::result::Result<T, Box<dyn std::error::Error>>;

#[derive(Parser)]
#[command(about = "AccessiWeather build and release tasks")]
struct Cli {
    #[command(subcommand)]
    command: Cmd,
}

#[derive(Subcommand)]
enum Cmd {
    /// Validate and extract curated changelog entries (`scripts/changelog_tools.py`).
    #[command(subcommand)]
    Changelog(changelog::Command),
    /// Print the build metadata the release build bakes in, as `KEY=value`
    /// lines for `$GITHUB_ENV` (`scripts/generate_build_meta.py`).
    BuildMeta {
        /// Build tag for nightly builds, e.g. nightly-20260201; omit for stable.
        tag: Option<String>,
    },
    /// Regenerate the app icons (`installer/create_icons.py`).
    Icons,
    /// Build the release binary and package it (`installer/build_nuitka.py`,
    /// `installer/build.py`, `installer/build_appimage.py`).
    Package {
        /// Artifacts to produce; default: every artifact of this platform.
        #[arg(value_enum)]
        artifacts: Vec<package::Artifact>,
    },
    /// Build the GitHub Pages download page (`scripts/build_pages.py`).
    Pages,
    /// Check NOAA Weather Radio stream URLs (`scripts/check_streams.py`).
    CheckStreams(streams::Args),
}

fn main() -> ExitCode {
    let result = match Cli::parse().command {
        Cmd::Changelog(cmd) => changelog::run(
            &repo_root(),
            cmd,
            &mut std::io::stdout(),
            &mut std::io::stderr(),
        ),
        Cmd::BuildMeta { tag } => build_meta(tag.as_deref()).map(|()| 0),
        Cmd::Icons => icons::generate().map(|()| 0),
        Cmd::Package { artifacts } => package::run(&artifacts).map(|()| 0),
        Cmd::Pages => pages::build().map(|()| 0),
        Cmd::CheckStreams(args) => streams::run(&args),
    };
    match result {
        Ok(code) => ExitCode::from(code),
        Err(e) => {
            eprintln!("error: {e}");
            ExitCode::FAILURE
        }
    }
}

/// The app version: the workspace version, which xtask shares.
pub(crate) const VERSION: &str = env!("CARGO_PKG_VERSION");

/// `rust/`.
pub(crate) fn rust_dir() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .expect("xtask lives in rust/xtask")
        .to_path_buf()
}

/// The repository root (holds CHANGELOG.md, docs/ and soundpacks/).
pub(crate) fn repo_root() -> PathBuf {
    rust_dir()
        .parent()
        .expect("rust/ has a parent")
        .to_path_buf()
}

/// The build tag goes into the binary through `ACCESSIWEATHER_BUILD_TAG`
/// at compile time (`aw_services::update::build_tag`); the version comes from
/// Cargo. CI appends this output to `$GITHUB_ENV` before building.
fn build_meta(tag: Option<&str>) -> Result<()> {
    let tag = tag.filter(|t| !t.is_empty());
    println!("ACCESSIWEATHER_BUILD_TAG={}", tag.unwrap_or(""));
    eprintln!("  version:   {VERSION}");
    eprintln!("  build_tag: {}", tag.unwrap_or("None"));
    Ok(())
}

/// Run `cmd`, failing unless it exits successfully.
pub(crate) fn run_checked(cmd: &mut Command) -> Result<()> {
    eprintln!("Running: {cmd:?}");
    let status = cmd
        .status()
        .map_err(|e| format!("{:?}: {e}", cmd.get_program()))?;
    if !status.success() {
        return Err(format!("{:?} failed with {status}", cmd.get_program()).into());
    }
    Ok(())
}
