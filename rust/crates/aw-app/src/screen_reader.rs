//! Screen reader announcements through prism, like the Python app's
//! `ScreenReaderAnnouncer`: the best backend is acquired once, used only when
//! it reports `IS_SUPPORTED_AT_RUNTIME`, and text is spoken without
//! interrupting. Everything runs on the UI thread.

use std::cell::RefCell;

use prismer::{Backend, Features, Prism};

thread_local! {
    static BACKEND: RefCell<Option<Backend<'static>>> = const { RefCell::new(None) };
}

/// Acquire the best screen reader backend for this (UI) thread.
pub fn init() {
    // The context lives for the whole process, as it does in the Python app.
    let prism: &'static Prism = match Prism::new() {
        Ok(p) => Box::leak(Box::new(p)),
        Err(e) => {
            tracing::debug!("prism not available; announcer will be a no-op: {e}");
            return;
        }
    };
    let backend = match prism.acquire_best() {
        Ok(b) => b,
        Err(e) => {
            tracing::warn!("Failed to acquire screen reader backend: {e}");
            return;
        }
    };
    if !backend
        .features()
        .contains(Features::IS_SUPPORTED_AT_RUNTIME)
    {
        tracing::debug!(
            "Screen reader backend found ({}) but not running at runtime",
            backend.name()
        );
        return;
    }
    tracing::info!("Screen reader backend active: {}", backend.name());
    BACKEND.with(|b| *b.borrow_mut() = Some(backend));
}

/// Speak `text` through the screen reader. No-op when none is available.
pub fn announce(text: &str) {
    if text.trim().is_empty() {
        return;
    }
    BACKEND.with(|b| {
        if let Some(backend) = b.borrow().as_ref() {
            if let Err(e) = backend.speak(text, false) {
                tracing::warn!("Failed to announce text: {e}");
            }
        }
    });
}

/// Release the backend before the UI thread winds down.
pub fn shutdown() {
    BACKEND.with(|b| b.borrow_mut().take());
}

// prism's macOS backends (AVSpeech, VoiceOver) marshal onto the main thread
// unless they are already on it. The app calls them from the main thread;
// cargo runs tests on worker threads while the main thread just waits, so
// on macOS these would deadlock.
#[cfg(all(test, not(target_os = "macos")))]
mod tests {
    /// Every backend must initialise or fail cleanly, including those whose
    /// DLLs are absent (prism's delay-load hook substitutes stubs).
    #[test]
    fn every_backend_initialises_or_fails_cleanly() {
        let prism = prismer::Prism::new().unwrap();
        for id in prism.backend_ids() {
            if let Ok(backend) = prism.create(id) {
                let _ = backend.initialize();
            }
        }
    }

    #[test]
    fn init_and_shutdown_never_panic() {
        super::init();
        super::shutdown();
    }
}
