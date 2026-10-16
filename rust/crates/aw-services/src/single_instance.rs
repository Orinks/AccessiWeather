//! One running AccessiWeather per Windows session (`single_instance.py`,
//! `activation_ipc.py`).
//!
//! The mutex name is Python's, so the two editions exclude each other: they
//! share one settings file and would overwrite each other's changes if both
//! ran. The activation pipe is not shared: Python's pipe speaks
//! `multiprocessing.connection`'s authenticated protocol, so the Rust edition
//! listens on its own pipe. A second launch of either edition still reaches a
//! running instance of the other through the fallbacks both implement:
//! restoring the window titled "AccessiWeather" and the shared handoff file.
//!
//! Off Windows there is no enforcement, as in Python.

use std::path::PathBuf;

use aw_notify::activation::{self, ActivationKind, ActivationRequest};

pub const SINGLE_INSTANCE_MUTEX_NAME: &str = "Local\\AccessiWeather.SingleInstance";
pub const ACTIVATION_PIPE_NAME: &str = r"\\.\pipe\AccessiWeather.SingleInstance.Activation.Rust";

/// Whether a launch that lost the lock should wake the running instance:
/// an automatic `--startup` launch without a toast request stays silent.
pub fn should_request_existing_instance(
    activation_request: Option<&ActivationRequest>,
    startup_launch: bool,
) -> bool {
    activation_request.is_some() || !startup_launch
}

/// AccessiWeather's main window titles, but not browser pages about it.
pub fn is_accessiweather_window_title(title: &str) -> bool {
    title == "AccessiWeather" || title.starts_with("AccessiWeather \u{2014} ")
}

/// `SingleInstanceManager`.
pub struct SingleInstance {
    config_dir: PathBuf,
    mutex: Option<isize>,
    ipc: Option<ipc::Server>,
}

impl SingleInstance {
    /// `config_dir` locates the handoff file (`<config>/state/activation_request.json`).
    pub fn new(config_dir: PathBuf) -> Self {
        Self {
            config_dir,
            mutex: None,
            ipc: None,
        }
    }

    /// True when this process is the primary instance. Any unexpected
    /// failure allows startup: a guard that occasionally lets a second copy
    /// run beats one that can keep the app from starting.
    pub fn try_acquire_lock(&mut self) -> bool {
        match win::acquire_mutex(SINGLE_INSTANCE_MUTEX_NAME) {
            win::Mutex::Acquired(handle) => {
                if win::find_accessiweather_window().is_some() {
                    tracing::info!(
                        "Found an existing AccessiWeather window without the mutex; \
                         treating it as the running instance"
                    );
                    win::close(handle);
                    return false;
                }
                self.mutex = Some(handle);
                tracing::info!("Acquired AccessiWeather single-instance mutex");
                true
            }
            win::Mutex::AlreadyExists => {
                tracing::info!("Another AccessiWeather instance already owns the mutex");
                false
            }
            win::Mutex::Unavailable => true,
        }
    }

    /// Ask the running instance to show itself and route `request`: over the
    /// pipe, else by restoring its window plus the handoff file.
    pub fn request_existing_instance_show(&self, request: Option<ActivationRequest>) -> bool {
        let request = request.unwrap_or_else(ActivationRequest::generic_fallback);
        if !cfg!(windows) {
            self.write_activation_handoff(&request);
            return false;
        }
        if ipc::send(&request) {
            return true;
        }
        let shown = win::show_existing_window();
        // A restored window already satisfies a plain generic request.
        if !shown || request.kind != ActivationKind::GenericFallback {
            self.write_activation_handoff(&request);
        }
        shown
    }

    pub fn write_activation_handoff(&self, request: &ActivationRequest) -> bool {
        activation::write_handoff(&activation::handoff_file(&self.config_dir), request)
    }

    pub fn consume_activation_handoff(&self) -> Option<ActivationRequest> {
        activation::consume_handoff(&activation::handoff_file(&self.config_dir))
    }

    /// Listen for duplicate-launch requests; `on_request` runs on the
    /// listener thread (post it to the UI thread).
    pub fn start_activation_ipc_server(
        &mut self,
        on_request: impl Fn(ActivationRequest) + Send + 'static,
    ) -> bool {
        if self.ipc.is_some() {
            return true;
        }
        self.ipc = ipc::Server::start(ACTIVATION_PIPE_NAME, Box::new(on_request));
        self.ipc.is_some()
    }

    pub fn stop_activation_ipc_server(&mut self) {
        if let Some(server) = self.ipc.take() {
            server.stop();
        }
    }

    pub fn release_lock(&mut self) {
        self.stop_activation_ipc_server();
        if let Some(handle) = self.mutex.take() {
            win::close(handle);
            tracing::info!("Released AccessiWeather single-instance mutex");
        }
    }
}

impl Drop for SingleInstance {
    fn drop(&mut self) {
        self.release_lock();
    }
}

#[cfg(windows)]
mod win {
    use std::ptr::null;

    use windows_sys::Win32::Foundation::{
        CloseHandle, GetLastError, ERROR_ALREADY_EXISTS, HANDLE, HWND, LPARAM,
    };
    use windows_sys::Win32::System::Threading::CreateMutexW;
    use windows_sys::Win32::UI::WindowsAndMessaging::{
        EnumWindows, FindWindowW, GetWindowTextLengthW, GetWindowTextW, SetForegroundWindow,
        ShowWindow, SW_RESTORE, SW_SHOWNORMAL,
    };

    pub enum Mutex {
        Acquired(isize),
        AlreadyExists,
        Unavailable,
    }

    fn wide(s: &str) -> Vec<u16> {
        s.encode_utf16().chain(Some(0)).collect()
    }

    pub fn acquire_mutex(name: &str) -> Mutex {
        let name = wide(name);
        // SAFETY: NUL-terminated name, default security, not initially owned.
        let (handle, err) = unsafe {
            let h = CreateMutexW(null(), 0, name.as_ptr());
            (h, GetLastError())
        };
        if handle.is_null() {
            tracing::warn!("CreateMutexW failed; allowing startup to continue");
            return Mutex::Unavailable;
        }
        if err == ERROR_ALREADY_EXISTS {
            close(handle as isize);
            return Mutex::AlreadyExists;
        }
        Mutex::Acquired(handle as isize)
    }

    pub fn close(handle: isize) {
        // SAFETY: a handle this module created and still owns.
        unsafe { CloseHandle(handle as HANDLE) };
    }

    fn window_title(hwnd: HWND) -> String {
        // SAFETY: plain Win32 queries on a window handle from the system.
        unsafe {
            let len = GetWindowTextLengthW(hwnd);
            if len <= 0 {
                return String::new();
            }
            let mut buf = vec![0u16; len as usize + 1];
            let n = GetWindowTextW(hwnd, buf.as_mut_ptr(), len + 1);
            String::from_utf16_lossy(&buf[..n.max(0) as usize])
        }
    }

    unsafe extern "system" fn enum_callback(hwnd: HWND, lparam: LPARAM) -> i32 {
        if super::is_accessiweather_window_title(window_title(hwnd).trim()) {
            // SAFETY: `lparam` is the `Option<HWND>` slot passed below.
            unsafe { *(lparam as *mut Option<HWND>) = Some(hwnd) };
            return 0;
        }
        1
    }

    pub fn find_accessiweather_window() -> Option<HWND> {
        let title = wide("AccessiWeather");
        // SAFETY: NUL-terminated title; the callback only writes our slot.
        unsafe {
            let hwnd = FindWindowW(null(), title.as_ptr());
            if !hwnd.is_null() {
                return Some(hwnd);
            }
            let mut found: Option<HWND> = None;
            EnumWindows(Some(enum_callback), &mut found as *mut _ as LPARAM);
            found
        }
    }

    pub fn show_existing_window() -> bool {
        let Some(hwnd) = find_accessiweather_window() else {
            tracing::info!("No existing AccessiWeather window found to restore");
            return false;
        };
        // SAFETY: a live top-level window handle.
        unsafe {
            ShowWindow(hwnd, SW_RESTORE);
            ShowWindow(hwnd, SW_SHOWNORMAL);
            SetForegroundWindow(hwnd);
        }
        true
    }
}

#[cfg(not(windows))]
mod win {
    pub enum Mutex {
        #[allow(dead_code)]
        Acquired(isize),
        #[allow(dead_code)]
        AlreadyExists,
        Unavailable,
    }

    pub fn acquire_mutex(_name: &str) -> Mutex {
        Mutex::Unavailable
    }

    pub fn close(_handle: isize) {}

    pub fn find_accessiweather_window() -> Option<()> {
        None
    }

    pub fn show_existing_window() -> bool {
        false
    }
}

#[cfg(windows)]
mod ipc {
    //! A byte-mode named pipe: the client writes one JSON request and closes.

    use std::fs::File;
    use std::io::{Read, Write};
    use std::os::windows::io::FromRawHandle;
    use std::ptr::{null, null_mut};
    use std::sync::atomic::{AtomicBool, Ordering};
    use std::sync::Arc;

    use windows_sys::Win32::Foundation::{
        GetLastError, ERROR_NO_DATA, ERROR_PIPE_CONNECTED, INVALID_HANDLE_VALUE,
    };
    use windows_sys::Win32::Storage::FileSystem::PIPE_ACCESS_INBOUND;
    use windows_sys::Win32::System::Pipes::{
        ConnectNamedPipe, CreateNamedPipeW, PIPE_READMODE_BYTE, PIPE_REJECT_REMOTE_CLIENTS,
        PIPE_TYPE_BYTE, PIPE_UNLIMITED_INSTANCES, PIPE_WAIT,
    };

    use aw_notify::ActivationRequest;

    type Callback = Box<dyn Fn(ActivationRequest) + Send>;

    pub struct Server {
        name: &'static str,
        stop: Arc<AtomicBool>,
    }

    impl Server {
        pub fn start(name: &'static str, on_request: Callback) -> Option<Self> {
            let stop = Arc::new(AtomicBool::new(false));
            let flag = stop.clone();
            let first = create(name)?;
            std::thread::Builder::new()
                .name("AccessiWeatherActivationIPC".into())
                .spawn(move || serve(name, first, &flag, &on_request))
                .ok()?;
            tracing::info!("Started AccessiWeather activation IPC listener");
            Some(Self { name, stop })
        }

        pub fn stop(self) {
            self.stop.store(true, Ordering::SeqCst);
            // Wake the listener blocked in ConnectNamedPipe.
            let _ = std::fs::OpenOptions::new().write(true).open(self.name);
        }
    }

    fn create(name: &str) -> Option<File> {
        let wide: Vec<u16> = name.encode_utf16().chain(Some(0)).collect();
        // SAFETY: NUL-terminated name; default security (only this user may write).
        let handle = unsafe {
            CreateNamedPipeW(
                wide.as_ptr(),
                PIPE_ACCESS_INBOUND,
                PIPE_TYPE_BYTE | PIPE_READMODE_BYTE | PIPE_WAIT | PIPE_REJECT_REMOTE_CLIENTS,
                PIPE_UNLIMITED_INSTANCES,
                0,
                4096,
                0,
                null(),
            )
        };
        if handle == INVALID_HANDLE_VALUE {
            tracing::warn!("Failed to start activation IPC listener");
            return None;
        }
        // SAFETY: we own the new pipe handle; File closes it.
        Some(unsafe { File::from_raw_handle(handle) })
    }

    fn serve(name: &str, first: File, stop: &AtomicBool, on_request: &Callback) {
        let mut pipe = Some(first);
        while let Some(mut file) = pipe.take().or_else(|| create(name)) {
            // A client that already wrote and closed gives ERROR_NO_DATA; its
            // bytes are still buffered.
            // SAFETY: a pipe handle owned by `file`.
            let connected = unsafe {
                ConnectNamedPipe(
                    std::os::windows::io::AsRawHandle::as_raw_handle(&file),
                    null_mut(),
                ) != 0
                    || matches!(GetLastError(), ERROR_PIPE_CONNECTED | ERROR_NO_DATA)
            };
            if stop.load(Ordering::SeqCst) {
                return;
            }
            if !connected {
                continue;
            }
            let mut payload = Vec::new();
            if (&mut file)
                .take(64 * 1024)
                .read_to_end(&mut payload)
                .is_err()
            {
                continue;
            }
            match ActivationRequest::from_json(&String::from_utf8_lossy(&payload)) {
                Some(request) => on_request(request),
                None => tracing::warn!("Ignoring invalid activation IPC request"),
            }
        }
    }

    pub fn send(request: &ActivationRequest) -> bool {
        let result = std::fs::OpenOptions::new()
            .write(true)
            .open(super::ACTIVATION_PIPE_NAME)
            .and_then(|mut pipe| pipe.write_all(request.to_json().as_bytes()));
        if let Err(e) = &result {
            tracing::info!("Activation IPC send failed; falling back to window lookup: {e}");
        }
        result.is_ok()
    }
}

#[cfg(not(windows))]
mod ipc {
    use aw_notify::ActivationRequest;

    pub struct Server;

    impl Server {
        pub fn start(
            _name: &'static str,
            _on_request: Box<dyn Fn(ActivationRequest) + Send>,
        ) -> Option<Self> {
            None
        }

        pub fn stop(self) {}
    }

    pub fn send(_request: &ActivationRequest) -> bool {
        false
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn startup_launches_only_wake_the_primary_for_toast_requests() {
        let req = ActivationRequest::discussion();
        assert!(should_request_existing_instance(None, false));
        assert!(!should_request_existing_instance(None, true));
        assert!(should_request_existing_instance(Some(&req), true));
    }

    #[test]
    fn window_titles_exclude_browser_pages() {
        assert!(is_accessiweather_window_title("AccessiWeather"));
        assert!(is_accessiweather_window_title(
            "AccessiWeather \u{2014} Philadelphia, PA"
        ));
        assert!(!is_accessiweather_window_title(
            "Orinks/AccessiWeather: Accessible weather - Google Chrome"
        ));
        assert!(!is_accessiweather_window_title("AccessiWeather - GitHub"));
    }

    #[cfg(not(windows))]
    #[test]
    fn non_windows_never_blocks_and_writes_the_handoff() {
        let dir = tempfile::tempdir().unwrap();
        let mut si = SingleInstance::new(dir.path().to_path_buf());
        assert!(si.try_acquire_lock());
        assert!(!si.request_existing_instance_show(None));
        assert_eq!(
            si.consume_activation_handoff(),
            Some(ActivationRequest::generic_fallback())
        );
    }

    /// Exercises the real mutex and pipe under throwaway names.
    #[cfg(windows)]
    #[test]
    fn mutex_excludes_a_second_instance_and_the_pipe_delivers_requests() {
        use std::sync::mpsc;
        use std::time::Duration;

        let name = format!("Local\\AccessiWeather.Test.{}", std::process::id());
        let first = win::acquire_mutex(&name);
        let win::Mutex::Acquired(handle) = first else {
            panic!("first acquire should own the mutex");
        };
        assert!(matches!(
            win::acquire_mutex(&name),
            win::Mutex::AlreadyExists
        ));
        win::close(handle);
        let win::Mutex::Acquired(again) = win::acquire_mutex(&name) else {
            panic!("released mutex should be free again");
        };
        win::close(again);

        let pipe: &'static str = Box::leak(
            format!(r"\\.\pipe\AccessiWeather.Test.{}", std::process::id()).into_boxed_str(),
        );
        let (tx, rx) = mpsc::channel();
        let server = ipc::Server::start(
            pipe,
            Box::new(move |req| {
                let _ = tx.send(req);
            }),
        )
        .unwrap();
        let req = ActivationRequest::alert_details("urn:1");
        std::fs::OpenOptions::new()
            .write(true)
            .open(pipe)
            .and_then(|mut p| std::io::Write::write_all(&mut p, req.to_json().as_bytes()))
            .unwrap();
        assert_eq!(rx.recv_timeout(Duration::from_secs(5)).unwrap(), req);
        server.stop();
    }
}
