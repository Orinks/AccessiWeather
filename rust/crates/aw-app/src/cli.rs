//! Command line (`main.py`): Python's flags plus the Rust-only
//! `--offline`, `--smoke`, `--check`, `--print-paths` and `--version`.
//! A Windows toast click passes one extra `accessiweather-toast:...` token.

use std::ffi::OsString;
use std::path::PathBuf;

use aw_services::activation::ActivationRequest;
use clap::error::ErrorKind;
use clap::{CommandFactory, Parser};

#[derive(Parser, Debug, Clone)]
#[command(
    name = "accessiweather",
    version,
    about = "AccessiWeather - Accessible Weather Application"
)]
pub struct Args {
    /// Custom configuration directory path
    #[arg(long, value_name = "CONFIG_DIR")]
    pub config_dir: Option<PathBuf>,

    /// Run in portable mode (config stored in app directory)
    #[arg(long)]
    pub portable: bool,

    /// Enable debug logging
    #[arg(long)]
    pub debug: bool,

    /// Fake version for testing updates (e.g., '0.1.0')
    #[arg(long, value_name = "FAKE_VERSION")]
    pub fake_version: Option<String>,

    /// Fake nightly tag for testing updates (e.g., 'nightly-20250101')
    #[arg(long, value_name = "FAKE_NIGHTLY")]
    pub fake_nightly: Option<String>,

    /// Force the onboarding wizard to run even if it has already been shown
    #[arg(long)]
    pub wizard: bool,

    /// Mark this launch as an update restart
    #[arg(long)]
    pub updated: bool,

    /// Mark this launch as an automatic startup launch
    #[arg(long = "startup")]
    pub startup_launch: bool,

    /// Print the resolved configuration paths and exit.
    #[arg(long)]
    pub print_paths: bool,

    /// Open the UI with recorded offline data, run for a moment and exit 0
    /// if everything initialised. Used by CI and packaging checks.
    #[arg(long)]
    pub smoke: bool,

    /// Headless self-check (no window): load config, run the presenter on
    /// fixture data, exit 0 on success.
    #[arg(long)]
    pub check: bool,

    /// Use bundled offline fixtures instead of live weather services.
    #[arg(long)]
    pub offline: bool,

    /// Verbose logging.
    #[arg(short, long)]
    pub verbose: bool,

    /// Windows toast activation token (accessiweather-toast:...).
    #[arg(hide = true)]
    pub activation_tokens: Vec<String>,

    /// The request carried by the first activation token.
    #[arg(skip)]
    pub activation_request: Option<ActivationRequest>,
}

impl Args {
    pub fn parse_args() -> Self {
        Self::parse_from_os(std::env::args_os()).unwrap_or_else(|e| e.exit())
    }

    /// `parse_args`: extra arguments must all be valid toast tokens.
    pub fn parse_from_os<I, T>(argv: I) -> Result<Self, clap::Error>
    where
        I: IntoIterator<Item = T>,
        T: Into<OsString> + Clone,
    {
        let mut args = Self::try_parse_from(argv)?;
        let unknown: Vec<&str> = args
            .activation_tokens
            .iter()
            .filter(|t| ActivationRequest::from_argv(&[t.as_str()]).is_none())
            .map(String::as_str)
            .collect();
        if !unknown.is_empty() {
            return Err(Self::command().error(
                ErrorKind::UnknownArgument,
                format!("unrecognized arguments: {}", unknown.join(" ")),
            ));
        }
        args.activation_request = ActivationRequest::from_argv(&args.activation_tokens);
        Ok(args)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn parse(argv: &[&str]) -> Result<Args, clap::Error> {
        Args::parse_from_os(std::iter::once("accessiweather").chain(argv.iter().copied()))
    }

    #[test]
    fn python_flags_parse() {
        let args = parse(&[
            "--config-dir",
            "C:\\cfg",
            "--portable",
            "--debug",
            "--fake-version",
            "0.1.0",
            "--fake-nightly",
            "nightly-20250101",
            "--wizard",
            "--updated",
            "--startup",
        ])
        .unwrap();
        assert_eq!(args.config_dir, Some(PathBuf::from("C:\\cfg")));
        assert!(args.portable && args.debug && args.wizard && args.updated && args.startup_launch);
        assert_eq!(args.fake_version.as_deref(), Some("0.1.0"));
        assert_eq!(args.fake_nightly.as_deref(), Some("nightly-20250101"));
        assert_eq!(args.activation_request, None);
    }

    #[test]
    fn toast_tokens_become_the_activation_request() {
        let args = parse(&[
            "--startup",
            "accessiweather-toast:kind=alert_details&alert_id=urn%3A1",
        ])
        .unwrap();
        assert_eq!(
            args.activation_request,
            ActivationRequest::new("alert_details", Some("urn:1".into()))
        );
        assert!(parse(&["accessiweather-toast:kind=discussion"])
            .unwrap()
            .activation_request
            .is_some());
    }

    #[test]
    fn anything_else_is_rejected_like_argparse() {
        for bad in [
            &["stray"][..],
            &["accessiweather-toast:kind=bogus"],
            &["accessiweather-toast:kind=alert_details"],
            &["--bogus"],
        ] {
            assert!(parse(bad).is_err(), "{bad:?}");
        }
        let err = parse(&["accessiweather-toast:kind=discussion", "junk"]).unwrap_err();
        assert!(err.to_string().contains("unrecognized arguments: junk"));
    }

    #[test]
    fn rust_only_flags_still_parse() {
        let args = parse(&["--offline", "--smoke", "--check", "--print-paths", "-v"]).unwrap();
        assert!(args.offline && args.smoke && args.check && args.print_paths && args.verbose);
    }
}
