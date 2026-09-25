//! Speech output.
//!
//! The UI never touches a synthesizer directly: it hands strings to a
//! [`Speaker`], which forwards them over a bounded channel to a worker thread
//! owning a [`SpeechSink`]. Sinks are pluggable so tests can capture
//! transcripts and headless runs can use the null sink.

use std::sync::mpsc::{self, Receiver, SyncSender, TrySendError};
use std::sync::{Arc, Mutex};
use std::thread::JoinHandle;
use std::time::Duration;

const QUEUE_CAPACITY: usize = 64;
const SHUTDOWN_TIMEOUT: Duration = Duration::from_millis(500);

/// A destination for spoken text.
pub trait SpeechSink: Send {
    fn speak(&mut self, text: &str, interrupt: bool);
    fn stop(&mut self);
}

/// Discards everything; used for `--smoke` and when no engine is available.
#[derive(Default)]
pub struct NullSink;

impl SpeechSink for NullSink {
    fn speak(&mut self, _text: &str, _interrupt: bool) {}
    fn stop(&mut self) {}
}

/// Records utterances so tests can assert on what would have been spoken.
#[derive(Default, Clone)]
pub struct RecordingSink {
    transcript: Arc<Mutex<Vec<String>>>,
}

impl RecordingSink {
    pub fn transcript(&self) -> Vec<String> {
        self.transcript.lock().unwrap().clone()
    }
}

impl SpeechSink for RecordingSink {
    fn speak(&mut self, text: &str, interrupt: bool) {
        let mut t = self.transcript.lock().unwrap();
        if interrupt {
            t.push(format!("[interrupt] {text}"));
        } else {
            t.push(text.to_string());
        }
    }
    fn stop(&mut self) {
        self.transcript.lock().unwrap().push("[stop]".into());
    }
}

#[cfg(feature = "native")]
pub struct NativeSink(tts::Tts);

#[cfg(feature = "native")]
impl NativeSink {
    pub fn new() -> Option<Self> {
        match tts::Tts::default() {
            Ok(t) => Some(Self(t)),
            Err(e) => {
                tracing::warn!("no native speech engine available: {e}");
                None
            }
        }
    }
}

#[cfg(feature = "native")]
impl SpeechSink for NativeSink {
    fn speak(&mut self, text: &str, interrupt: bool) {
        if let Err(e) = self.0.speak(text, interrupt) {
            tracing::warn!("speech failed: {e}");
        }
    }
    fn stop(&mut self) {
        let _ = self.0.stop();
    }
}

enum Command {
    Speak { text: String, interrupt: bool },
    Stop,
    Shutdown,
}

/// Thread-safe handle used by the UI. Cheap to clone.
#[derive(Clone)]
pub struct Speaker {
    tx: SyncSender<Command>,
    worker: Arc<Mutex<Option<JoinHandle<()>>>>,
}

impl Speaker {
    /// Start a worker owning `sink`.
    pub fn spawn(mut sink: Box<dyn SpeechSink>) -> Self {
        let (tx, rx): (SyncSender<Command>, Receiver<Command>) = mpsc::sync_channel(QUEUE_CAPACITY);
        let worker = std::thread::Builder::new()
            .name("aw-speech".into())
            .spawn(move || {
                while let Ok(cmd) = rx.recv() {
                    match cmd {
                        Command::Speak { text, interrupt } => sink.speak(&text, interrupt),
                        Command::Stop => sink.stop(),
                        Command::Shutdown => {
                            sink.stop();
                            break;
                        }
                    }
                }
            })
            .expect("spawn speech worker");
        Self {
            tx,
            worker: Arc::new(Mutex::new(Some(worker))),
        }
    }

    /// Best available engine, falling back to silence.
    pub fn native_or_null() -> Self {
        #[cfg(feature = "native")]
        {
            if let Some(sink) = NativeSink::new() {
                return Self::spawn(Box::new(sink));
            }
        }
        Self::spawn(Box::new(NullSink))
    }

    pub fn null() -> Self {
        Self::spawn(Box::new(NullSink))
    }

    /// Queue an utterance; drops it (with a log line) if the queue is full so
    /// the UI thread never blocks.
    pub fn speak(&self, text: impl Into<String>, interrupt: bool) {
        let text = text.into();
        if text.trim().is_empty() {
            return;
        }
        match self.tx.try_send(Command::Speak { text, interrupt }) {
            Ok(()) => {}
            Err(TrySendError::Full(_)) => tracing::warn!("speech queue full; utterance dropped"),
            Err(TrySendError::Disconnected(_)) => {}
        }
    }

    pub fn stop(&self) {
        let _ = self.tx.try_send(Command::Stop);
    }

    /// Idempotent, bounded shutdown.
    pub fn shutdown(&self) {
        let _ = self.tx.try_send(Command::Shutdown);
        if let Some(handle) = self.worker.lock().unwrap().take() {
            let deadline = std::time::Instant::now() + SHUTDOWN_TIMEOUT;
            while !handle.is_finished() && std::time::Instant::now() < deadline {
                std::thread::sleep(Duration::from_millis(10));
            }
            if handle.is_finished() {
                let _ = handle.join();
            } else {
                tracing::warn!("speech worker did not stop within {SHUTDOWN_TIMEOUT:?}");
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn worker_forwards_in_order_and_shuts_down() {
        let sink = RecordingSink::default();
        let speaker = Speaker::spawn(Box::new(sink.clone()));
        speaker.speak("first", false);
        speaker.speak("   ", false);
        speaker.speak("second", true);
        speaker.shutdown();
        speaker.shutdown();
        assert_eq!(
            sink.transcript(),
            vec!["first", "[interrupt] second", "[stop]"]
        );
    }
}
