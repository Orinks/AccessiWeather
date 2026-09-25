//! AccessiWeather native desktop application.

mod app;
mod cli;
mod fixtures;
mod portable_keys;
mod screen_reader;
mod ui;

use std::process::ExitCode;

fn main() -> ExitCode {
    let args = cli::Args::parse_args();
    init_logging(args.verbose || args.debug);
    match app::run(args) {
        Ok(()) => ExitCode::SUCCESS,
        Err(e) => {
            eprintln!("accessiweather: {e}");
            ExitCode::FAILURE
        }
    }
}

fn init_logging(verbose: bool) {
    let default = if verbose { "debug" } else { "info" };
    let filter = tracing_subscriber::EnvFilter::try_from_env("ACCESSIWEATHER_LOG")
        .unwrap_or_else(|_| tracing_subscriber::EnvFilter::new(default));
    let _ = tracing_subscriber::fmt()
        .with_env_filter(filter)
        .with_writer(std::io::stderr)
        .try_init();
}
