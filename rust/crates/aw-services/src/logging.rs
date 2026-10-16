//! Console and rotating file logging for `tracing` (`logging_config.py` and
//! the fallback in `main.setup_logging`): `{config_root}/logs/accessiweather.log`,
//! 5 MB per file, 3 backups, Python's record formats.

use std::fs::{File, OpenOptions};
use std::io::{self, Write};
use std::path::{Path, PathBuf};
use std::sync::Mutex;

use tracing::{Event, Level, Subscriber};
use tracing_subscriber::filter::LevelFilter;
use tracing_subscriber::fmt::format::Writer;
use tracing_subscriber::fmt::{FmtContext, FormatEvent, FormatFields};
use tracing_subscriber::layer::SubscriberExt;
use tracing_subscriber::registry::LookupSpan;

pub const LOG_FILE_NAME: &str = "accessiweather.log";
pub const MAX_BYTES: u64 = 5 * 1024 * 1024;
pub const BACKUP_COUNT: u32 = 3;

/// `logging.handlers.RotatingFileHandler`: before a record would push the
/// file to `max_bytes`, `.log` becomes `.log.1`, `.log.1` becomes `.log.2`, ...
pub struct RotatingFile {
    path: PathBuf,
    max_bytes: u64,
    backups: u32,
    file: Option<File>,
    size: u64,
}

impl RotatingFile {
    pub fn open(path: PathBuf, max_bytes: u64, backups: u32) -> io::Result<Self> {
        let file = OpenOptions::new().create(true).append(true).open(&path)?;
        let size = file.metadata()?.len();
        Ok(Self {
            path,
            max_bytes,
            backups,
            file: Some(file),
            size,
        })
    }

    fn numbered(&self, n: u32) -> PathBuf {
        let mut name = self.path.clone().into_os_string();
        name.push(format!(".{n}"));
        PathBuf::from(name)
    }

    fn rollover(&mut self) -> io::Result<()> {
        // Windows cannot rename an open file.
        self.file = None;
        if self.backups > 0 {
            for i in (1..self.backups).rev() {
                let (src, dst) = (self.numbered(i), self.numbered(i + 1));
                if src.exists() {
                    let _ = std::fs::remove_file(&dst);
                    std::fs::rename(&src, &dst)?;
                }
            }
            let first = self.numbered(1);
            let _ = std::fs::remove_file(&first);
            std::fs::rename(&self.path, &first)?;
        }
        let file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&self.path)?;
        self.size = file.metadata()?.len();
        self.file = Some(file);
        Ok(())
    }
}

impl Write for RotatingFile {
    /// The fmt layer hands over each formatted record in one write.
    fn write(&mut self, buf: &[u8]) -> io::Result<usize> {
        if self.max_bytes > 0 && self.size + buf.len() as u64 >= self.max_bytes {
            self.rollover()?;
        }
        let file = match self.file.as_mut() {
            Some(f) => f,
            None => return Err(io::Error::other("log file is closed")),
        };
        let n = file.write(buf)?;
        self.size += n as u64;
        Ok(n)
    }

    fn flush(&mut self) -> io::Result<()> {
        self.file.as_mut().map_or(Ok(()), Write::flush)
    }
}

#[derive(Clone, Copy)]
enum Style {
    /// `%(asctime)s - %(levelname)s - %(name)s - %(message)s`, time as `%H:%M:%S`.
    Console,
    /// `%(asctime)s - %(levelname)s - %(name)s - %(filename)s:%(lineno)d - %(message)s`.
    File,
    /// `basicConfig` fallback: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`.
    Basic,
}

struct PyFormat(Style);

fn level_name(level: &Level) -> &'static str {
    match *level {
        Level::ERROR => "ERROR",
        Level::WARN => "WARNING",
        Level::INFO => "INFO",
        _ => "DEBUG",
    }
}

impl<S, N> FormatEvent<S, N> for PyFormat
where
    S: Subscriber + for<'a> LookupSpan<'a>,
    N: for<'a> FormatFields<'a> + 'static,
{
    fn format_event(
        &self,
        ctx: &FmtContext<'_, S, N>,
        mut writer: Writer<'_>,
        event: &Event<'_>,
    ) -> std::fmt::Result {
        let meta = event.metadata();
        let now = chrono::Local::now();
        let asctime = format!(
            "{},{:03}",
            now.format("%Y-%m-%d %H:%M:%S"),
            now.timestamp_subsec_millis().min(999)
        );
        let level = level_name(meta.level());
        let name = meta.target();
        match self.0 {
            Style::Console => write!(writer, "{} - {level} - {name} - ", now.format("%H:%M:%S"))?,
            Style::File => {
                let file = meta
                    .file()
                    .and_then(|f| Path::new(f).file_name())
                    .map_or("?".into(), |f| f.to_string_lossy());
                let line = meta.line().unwrap_or(0);
                write!(writer, "{asctime} - {level} - {name} - {file}:{line} - ")?
            }
            Style::Basic => write!(writer, "{asctime} - {name} - {level} - ")?,
        }
        ctx.field_format().format_fields(writer.by_ref(), event)?;
        writeln!(writer)
    }
}

/// The subscriber `setup_logging` installs, and the log directory when file
/// logging is available. A log folder that cannot be created or opened
/// falls back to console-only logging instead of failing startup.
pub fn build_subscriber(
    debug: bool,
    config_root: &Path,
) -> (impl Subscriber + Send + Sync, Option<PathBuf>) {
    let level = if debug {
        LevelFilter::DEBUG
    } else {
        LevelFilter::INFO
    };
    let log_dir = config_root.join("logs");
    let file = std::fs::create_dir_all(&log_dir)
        .and_then(|()| {
            #[cfg(unix)]
            {
                use std::os::unix::fs::PermissionsExt;
                let _ = std::fs::set_permissions(&log_dir, std::fs::Permissions::from_mode(0o700));
            }
            RotatingFile::open(log_dir.join(LOG_FILE_NAME), MAX_BYTES, BACKUP_COUNT)
        })
        .ok();
    let console_style = if file.is_some() {
        Style::Console
    } else {
        Style::Basic
    };
    let has_file = file.is_some();
    let subscriber = tracing_subscriber::registry()
        .with(level)
        .with(
            tracing_subscriber::fmt::layer()
                .with_ansi(false)
                .event_format(PyFormat(console_style))
                .with_writer(io::stdout),
        )
        .with(file.map(|f| {
            tracing_subscriber::fmt::layer()
                .with_ansi(false)
                .event_format(PyFormat(Style::File))
                .with_writer(Mutex::new(f))
        }));
    (subscriber, has_file.then_some(log_dir))
}

/// Install the global subscriber; returns the log directory, if any.
pub fn setup_logging(debug: bool, config_root: &Path) -> Option<PathBuf> {
    let (subscriber, log_dir) = build_subscriber(debug, config_root);
    if tracing::subscriber::set_global_default(subscriber).is_err() {
        return log_dir;
    }
    let level = if debug { "DEBUG" } else { "INFO" };
    match &log_dir {
        Some(dir) => {
            tracing::info!("Logging initialized at level {level}");
            tracing::info!("Log file: {}", dir.join(LOG_FILE_NAME).display());
        }
        None => tracing::warn!("File logging unavailable; console only"),
    }
    log_dir
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn records_reach_the_file_in_python_format() {
        let dir = tempfile::tempdir().unwrap();
        let (subscriber, log_dir) = build_subscriber(false, dir.path());
        assert_eq!(log_dir.as_deref(), Some(dir.path().join("logs").as_path()));
        tracing::subscriber::with_default(subscriber, || {
            tracing::info!(target: "accessiweather.test", "radio auto-tune skipped");
            tracing::debug!(target: "accessiweather.test", "hidden at INFO");
        });
        let text = std::fs::read_to_string(dir.path().join("logs").join(LOG_FILE_NAME)).unwrap();
        let line = text.lines().next().unwrap();
        let re = regex::Regex::new(
            r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d{3} - INFO - accessiweather\.test - logging\.rs:\d+ - radio auto-tune skipped$",
        )
        .unwrap();
        assert!(re.is_match(line), "{line}");
        assert!(!text.contains("hidden at INFO"));
    }

    #[test]
    fn unwritable_log_directory_falls_back_to_console() {
        let dir = tempfile::tempdir().unwrap();
        let blocker = dir.path().join("root");
        std::fs::write(&blocker, b"a file, not a folder").unwrap();
        let (_subscriber, log_dir) = build_subscriber(true, &blocker);
        assert!(log_dir.is_none());
    }

    #[test]
    fn rotation_keeps_three_backups() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join(LOG_FILE_NAME);
        let mut log = RotatingFile::open(path.clone(), 100, 3).unwrap();
        for i in 0..20 {
            log.write_all(format!("record {i:02} {}\n", "x".repeat(30)).as_bytes())
                .unwrap();
        }
        drop(log);
        let name = |n: u32| dir.path().join(format!("{LOG_FILE_NAME}.{n}"));
        assert!(name(1).exists() && name(2).exists() && name(3).exists());
        assert!(!name(4).exists());
        assert!(std::fs::metadata(&path).unwrap().len() < 100);
        let newest = std::fs::read_to_string(&path).unwrap();
        assert!(newest.contains("record 19"));
        assert!(std::fs::read_to_string(name(1))
            .unwrap()
            .contains("record 17"));
    }
}
