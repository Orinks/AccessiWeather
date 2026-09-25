//! AccessiWeather native desktop application.

mod app;
mod cli;
mod fixtures;
mod hotkeys;
mod lifecycle;
mod portable_keys;
mod radio;
mod screen_reader;
mod tray;
mod ui;

use std::process::ExitCode;

fn main() -> ExitCode {
    let args = cli::Args::parse_args();
    match app::run(args) {
        Ok(()) => ExitCode::SUCCESS,
        Err(e) => {
            eprintln!("accessiweather: {e}");
            ExitCode::FAILURE
        }
    }
}

/// Console-only logging for the tool modes (`--check`, `--smoke`,
/// `--print-paths`), which must not write into the user's log file.
fn init_console_logging(verbose: bool) {
    let default = if verbose { "debug" } else { "info" };
    let filter = tracing_subscriber::EnvFilter::try_from_env("ACCESSIWEATHER_LOG")
        .unwrap_or_else(|_| tracing_subscriber::EnvFilter::new(default));
    let _ = tracing_subscriber::fmt()
        .with_env_filter(filter)
        .with_writer(std::io::stderr)
        .try_init();
}
