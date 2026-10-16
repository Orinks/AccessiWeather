//! AccessiWeather native desktop application.

// Release builds are GUI programs, so Windows doesn't open a console window
// beside the app. Debug builds keep theirs for `cargo run`.
#![cfg_attr(all(windows, not(debug_assertions)), windows_subsystem = "windows")]

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
    #[cfg(all(windows, not(debug_assertions)))]
    release_console::attach();
    let args = cli::Args::parse_args();
    #[cfg(all(windows, not(debug_assertions)))]
    if !(args.check || args.smoke || args.print_paths) {
        release_console::detach();
    }
    match app::run(args) {
        Ok(()) => ExitCode::SUCCESS,
        Err(e) => {
            eprintln!("accessiweather: {e}");
            ExitCode::FAILURE
        }
    }
}

/// A GUI-subsystem program started from a terminal has nowhere to print, so
/// borrow that terminal for `--version`, `--help` and the tool modes.
#[cfg(all(windows, not(debug_assertions)))]
mod release_console {
    use windows_sys::Win32::System::Console::{
        AttachConsole, FreeConsole, GetStdHandle, ATTACH_PARENT_PROCESS, STD_OUTPUT_HANDLE,
    };

    /// Output that is already redirected (CI, a pipe) is left alone.
    pub fn attach() {
        unsafe {
            if GetStdHandle(STD_OUTPUT_HANDLE).is_null() {
                AttachConsole(ATTACH_PARENT_PROCESS);
            }
        }
    }

    /// The windowed app lets go of the terminal, so closing it or pressing
    /// Ctrl+C there doesn't take the app down.
    pub fn detach() {
        unsafe {
            FreeConsole();
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
