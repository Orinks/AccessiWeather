use std::path::PathBuf;

use clap::Parser;

#[derive(Parser, Debug, Clone)]
#[command(
    name = "accessiweather",
    version,
    about = "AccessiWeather: accessible desktop weather"
)]
pub struct Args {
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

    /// Force portable mode (config folder next to the executable).
    #[arg(long)]
    pub portable: bool,

    /// Override the configuration directory.
    #[arg(long, value_name = "DIR")]
    pub config_dir: Option<PathBuf>,

    /// Verbose logging.
    #[arg(short, long)]
    pub verbose: bool,

    /// Enable debug logging
    #[arg(long)]
    pub debug: bool,
}

impl Args {
    pub fn parse_args() -> Self {
        Self::parse()
    }
}
