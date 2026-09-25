//! Network audio playback: an HTTP stream is decoded by symphonia on its own
//! thread and handed to the default output device through a rodio mixer.
//!
//! Replaces the BASS `URLStream` the Python app uses. NOAA Weather Radio
//! feeds (wxradio.org, GWES, weatherUSA, Broadcastify and the volunteer
//! Icecast/Shoutcast servers) are MP3; AAC (ADTS) and Ogg Vorbis are
//! decoded too. None of the known feeds use HLS.

use std::num::{NonZeroU16, NonZeroU32};
use std::sync::atomic::{AtomicBool, AtomicU32, Ordering};
use std::sync::mpsc::{self, Receiver, SyncSender, TryRecvError};
use std::sync::Arc;
use std::time::Duration;

use rodio::Source;
use symphonia::core::audio::SampleBuffer;
use symphonia::core::codecs::{Decoder, DecoderOptions, CODEC_TYPE_NULL};
use symphonia::core::errors::Error as SymphoniaError;
use symphonia::core::formats::{FormatOptions, FormatReader};
use symphonia::core::io::{MediaSourceStream, ReadOnlySource};
use symphonia::core::meta::MetadataOptions;
use symphonia::core::probe::Hint;

use crate::player::{AudioBackend, AudioStream};

/// Connect and per-read timeout for the HTTP stream.
const NETWORK_TIMEOUT: Duration = Duration::from_secs(10);
/// Give up on a stream that has not produced audio by now.
const STARTUP_TIMEOUT: Duration = Duration::from_secs(20);
/// Audio decoded before output starts, to ride out network jitter.
const PREBUFFER: Duration = Duration::from_secs(1);
/// Decoded packets queued between the decoder and the device (~5 s, the
/// size of BASS's default network buffer).
const QUEUE_PACKETS: usize = 200;
/// Starved this long, the stream reports itself stalled.
const STALL_AFTER: Duration = Duration::from_secs(1);
/// Window for the level meter (BASS measures 20 ms).
const LEVEL_WINDOW: Duration = Duration::from_millis(20);

/// Plays HTTP audio streams on the default output device.
pub struct RodioBackend {
    http: reqwest::blocking::Client,
}

impl RodioBackend {
    pub fn new() -> Result<Self, String> {
        let http = reqwest::blocking::Client::builder()
            .user_agent(aw_providers::http::USER_AGENT)
            .connect_timeout(NETWORK_TIMEOUT)
            // Blocking reqwest applies this to the headers and to each body
            // read, i.e. it is a read timeout, not a cap on the stream.
            .timeout(NETWORK_TIMEOUT)
            .build()
            .map_err(|e| e.to_string())?;
        Ok(Self { http })
    }
}

#[derive(Default)]
struct Shared {
    stop: AtomicBool,
    finished: AtomicBool,
    stalled: AtomicBool,
    volume: AtomicU32,
    level: AtomicU32,
}

impl Shared {
    fn volume(&self) -> f32 {
        f32::from_bits(self.volume.load(Ordering::Relaxed))
    }
}

struct RodioStream(Arc<Shared>);

impl AudioStream for RodioStream {
    fn set_volume(&self, volume: f32) {
        self.0.volume.store(volume.to_bits(), Ordering::Relaxed);
    }
    fn is_playing(&self) -> bool {
        let s = &self.0;
        !s.stop.load(Ordering::Relaxed)
            && !s.finished.load(Ordering::Relaxed)
            && !s.stalled.load(Ordering::Relaxed)
    }
    fn is_stalled(&self) -> bool {
        self.0.stalled.load(Ordering::Relaxed)
    }
    fn level(&self) -> u32 {
        self.0.level.load(Ordering::Relaxed)
    }
    fn stop(&self) {
        self.0.stop.store(true, Ordering::Relaxed);
    }
}

impl Drop for RodioStream {
    fn drop(&mut self) {
        self.stop();
    }
}

impl AudioBackend for RodioBackend {
    fn open(&self, url: &str, volume: f32) -> Result<Box<dyn AudioStream>, String> {
        let shared = Arc::new(Shared::default());
        shared.volume.store(volume.to_bits(), Ordering::Relaxed);
        let (ready_tx, ready_rx) = mpsc::channel();
        let (http, url_owned, thread_shared) = (self.http.clone(), url.to_string(), shared.clone());
        std::thread::Builder::new()
            .name("NoaaRadioStream".into())
            .spawn(move || {
                if let Err(e) = run_stream(&http, &url_owned, &thread_shared, &ready_tx) {
                    tracing::debug!("radio stream {url_owned} ended: {e}");
                    // Only the first send matters; after start-up nobody listens.
                    let _ = ready_tx.send(Err(e));
                }
                thread_shared.finished.store(true, Ordering::Relaxed);
            })
            .map_err(|e| e.to_string())?;
        match ready_rx.recv_timeout(STARTUP_TIMEOUT) {
            Ok(Ok(())) => Ok(Box::new(RodioStream(shared))),
            Ok(Err(e)) => Err(e),
            Err(_) => {
                shared.stop.store(true, Ordering::Relaxed);
                Err("timed out waiting for audio".into())
            }
        }
    }
}

/// Connect, decode, prebuffer, start output, then keep decoding until the
/// stream ends or is stopped. Errors before start-up go back to `open`.
fn run_stream(
    http: &reqwest::blocking::Client,
    url: &str,
    shared: &Arc<Shared>,
    ready: &mpsc::Sender<Result<(), String>>,
) -> Result<(), String> {
    let response = http.get(url).send().map_err(|e| e.to_string())?;
    if !response.status().is_success() {
        return Err(format!("HTTP {}", response.status().as_u16()));
    }
    let source =
        MediaSourceStream::new(Box::new(ReadOnlySource::new(response)), Default::default());
    let probed = symphonia::default::get_probe()
        .format(
            &Hint::new(),
            source,
            &FormatOptions::default(),
            &MetadataOptions::default(),
        )
        .map_err(|e| format!("unsupported stream: {e}"))?;
    let mut format = probed.format;
    let track = format
        .tracks()
        .iter()
        .find(|t| t.codec_params.codec != CODEC_TYPE_NULL)
        .ok_or("no audio track in stream")?;
    let track_id = track.id;
    let mut decoder = symphonia::default::get_codecs()
        .make(&track.codec_params, &DecoderOptions::default())
        .map_err(|e| format!("unsupported codec: {e}"))?;

    // Prebuffer, which also tells us the output format.
    let mut spec = None;
    let mut buffered = Vec::new();
    let mut buffered_samples = 0usize;
    loop {
        if shared.stop.load(Ordering::Relaxed) {
            return Ok(());
        }
        let Some((samples, rate, channels)) = next_chunk(&mut *format, &mut *decoder, track_id)?
        else {
            return Err("stream ended before audio arrived".into());
        };
        let spec = *spec.get_or_insert((rate, channels));
        if spec != (rate, channels) {
            return Err("stream changed format while starting".into());
        }
        buffered_samples += samples.len();
        buffered.push(samples);
        let prebuffer = (rate as f64 * channels as f64 * PREBUFFER.as_secs_f64()) as usize;
        if buffered_samples >= prebuffer {
            break;
        }
    }
    let (rate, channels) = spec.expect("prebuffer decoded at least one chunk");

    let (tx, rx) = mpsc::sync_channel(QUEUE_PACKETS.max(buffered.len()));
    for chunk in buffered {
        let _ = tx.send(chunk);
    }
    let mut device = rodio::DeviceSinkBuilder::open_default_sink()
        .map_err(|e| format!("no audio output device: {e}"))?;
    device.log_on_drop(false);
    let frame = |d: Duration| (rate as f64 * d.as_secs_f64()) as usize * channels as usize;
    device.mixer().add(StreamSource {
        rx,
        chunk: Vec::new(),
        pos: 0,
        pad_silence: 0,
        channels: NonZeroU16::new(channels).ok_or("stream has no channels")?,
        rate: NonZeroU32::new(rate).ok_or("stream has no sample rate")?,
        starved: 0,
        stall_after: frame(STALL_AFTER).max(1),
        peak: 0.0,
        window: 0,
        window_len: frame(LEVEL_WINDOW).max(1),
        shared: shared.clone(),
    });
    let _ = ready.send(Ok(()));

    let result = pump(
        &mut *format,
        &mut *decoder,
        track_id,
        (rate, channels),
        shared,
        &tx,
    );
    drop(tx);
    // Keep the device open until the queued audio has played out.
    while !shared.stop.load(Ordering::Relaxed) && !shared.finished.load(Ordering::Relaxed) {
        std::thread::sleep(Duration::from_millis(50));
    }
    result
}

fn pump(
    format: &mut dyn FormatReader,
    decoder: &mut dyn Decoder,
    track_id: u32,
    spec: (u32, u16),
    shared: &Shared,
    tx: &SyncSender<Vec<f32>>,
) -> Result<(), String> {
    while !shared.stop.load(Ordering::Relaxed) {
        let Some((samples, rate, channels)) = next_chunk(format, decoder, track_id)? else {
            return Ok(());
        };
        if (rate, channels) != spec {
            // ponytail: mid-stream format changes end the stream; NWR feeds
            // keep one format. Rebuild the output if a feed ever needs it.
            return Err("stream changed audio format".into());
        }
        if tx.send(samples).is_err() {
            return Ok(()); // output ended (stopped)
        }
    }
    Ok(())
}

/// Next decoded chunk as interleaved f32 with its rate and channel count;
/// `None` at end of stream.
fn next_chunk(
    format: &mut dyn FormatReader,
    decoder: &mut dyn Decoder,
    track_id: u32,
) -> Result<Option<(Vec<f32>, u32, u16)>, String> {
    loop {
        let packet = match format.next_packet() {
            Ok(packet) => packet,
            Err(SymphoniaError::IoError(e)) if e.kind() == std::io::ErrorKind::UnexpectedEof => {
                return Ok(None)
            }
            Err(e) => return Err(e.to_string()),
        };
        if packet.track_id() != track_id {
            continue;
        }
        match decoder.decode(&packet) {
            Ok(decoded) => {
                let spec = *decoded.spec();
                if decoded.frames() == 0 {
                    continue;
                }
                let mut buffer = SampleBuffer::<f32>::new(decoded.capacity() as u64, spec);
                buffer.copy_interleaved_ref(decoded);
                return Ok(Some((
                    buffer.samples().to_vec(),
                    spec.rate,
                    spec.channels.count() as u16,
                )));
            }
            // Corrupt frames happen on live streams; skip them.
            Err(SymphoniaError::DecodeError(e)) => tracing::trace!("skipping bad frame: {e}"),
            Err(e) => return Err(e.to_string()),
        }
    }
}

/// The rodio side: pulls decoded chunks without blocking the audio thread,
/// plays silence while starved, applies volume and meters the level.
struct StreamSource {
    rx: Receiver<Vec<f32>>,
    chunk: Vec<f32>,
    pos: usize,
    /// Silence still owed to finish a frame, so channels stay aligned.
    pad_silence: usize,
    channels: NonZeroU16,
    rate: NonZeroU32,
    starved: usize,
    stall_after: usize,
    peak: f32,
    window: usize,
    window_len: usize,
    shared: Arc<Shared>,
}

impl StreamSource {
    fn meter(&mut self, sample: f32) {
        self.peak = self.peak.max(sample.abs());
        self.window += 1;
        if self.window >= self.window_len {
            let level = (self.peak.min(1.0) * 32768.0) as u32;
            self.shared.level.store(level, Ordering::Relaxed);
            self.peak = 0.0;
            self.window = 0;
        }
    }

    fn silence(&mut self) -> f32 {
        self.starved += 1;
        if self.starved >= self.stall_after {
            self.shared.stalled.store(true, Ordering::Relaxed);
        }
        self.meter(0.0);
        0.0
    }
}

impl Iterator for StreamSource {
    type Item = f32;

    fn next(&mut self) -> Option<f32> {
        if self.shared.stop.load(Ordering::Relaxed) {
            return None;
        }
        if self.pad_silence > 0 {
            self.pad_silence -= 1;
            return Some(self.silence());
        }
        while self.pos >= self.chunk.len() {
            match self.rx.try_recv() {
                Ok(chunk) => {
                    self.chunk = chunk;
                    self.pos = 0;
                }
                Err(TryRecvError::Empty) => {
                    self.pad_silence = self.channels.get() as usize - 1;
                    return Some(self.silence());
                }
                Err(TryRecvError::Disconnected) => {
                    self.shared.finished.store(true, Ordering::Relaxed);
                    return None;
                }
            }
        }
        self.starved = 0;
        self.shared.stalled.store(false, Ordering::Relaxed);
        let sample = self.chunk[self.pos];
        self.pos += 1;
        self.meter(sample);
        Some(sample * self.shared.volume())
    }
}

impl Source for StreamSource {
    fn current_span_len(&self) -> Option<usize> {
        None
    }
    fn channels(&self) -> rodio::ChannelCount {
        self.channels
    }
    fn sample_rate(&self) -> rodio::SampleRate {
        self.rate
    }
    fn total_duration(&self) -> Option<Duration> {
        None
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn source(rx: Receiver<Vec<f32>>, shared: Arc<Shared>) -> StreamSource {
        StreamSource {
            rx,
            chunk: Vec::new(),
            pos: 0,
            pad_silence: 0,
            channels: NonZeroU16::new(2).unwrap(),
            rate: NonZeroU32::new(8000).unwrap(),
            starved: 0,
            stall_after: 4,
            peak: 0.0,
            window: 0,
            window_len: 2,
            shared,
        }
    }

    #[test]
    fn source_applies_volume_pads_whole_frames_and_detects_stalls() {
        let shared = Arc::new(Shared::default());
        shared.volume.store(0.5f32.to_bits(), Ordering::Relaxed);
        let (tx, rx) = mpsc::sync_channel(4);
        let mut src = source(rx, shared.clone());
        tx.send(vec![0.4, -0.8]).unwrap();
        assert_eq!(src.next(), Some(0.2));
        assert_eq!(src.next(), Some(-0.4));
        assert_eq!(
            shared.level.load(Ordering::Relaxed),
            (0.8f32 * 32768.0) as u32
        );
        // Starved: silence comes in whole stereo frames.
        tx.send(vec![0.1, 0.1]).unwrap();
        assert_eq!(src.next(), Some(0.05));
        assert_eq!(src.next(), Some(0.05));
        assert_eq!(src.next(), Some(0.0));
        tx.send(vec![0.2, 0.2]).unwrap();
        assert_eq!(src.next(), Some(0.0), "pads the rest of the frame first");
        assert_eq!(src.next(), Some(0.1));
        assert_eq!(src.next(), Some(0.1));
        for _ in 0..4 {
            src.next();
        }
        assert!(shared.stalled.load(Ordering::Relaxed));
        assert_eq!(shared.level.load(Ordering::Relaxed), 0);
        tx.send(vec![0.3, 0.3]).unwrap();
        src.next();
        assert!(!shared.stalled.load(Ordering::Relaxed));
        src.next();
        drop(tx);
        assert_eq!(src.next(), None);
        assert!(shared.finished.load(Ordering::Relaxed));
    }

    #[test]
    fn stopped_source_ends() {
        let shared = Arc::new(Shared::default());
        let (_tx, rx) = mpsc::sync_channel(1);
        let mut src = source(rx, shared.clone());
        let stream = RodioStream(shared);
        assert!(stream.is_playing());
        stream.stop();
        assert!(!stream.is_playing());
        assert_eq!(src.next(), None);
    }

    /// Manual check: plays a live NOAA Weather Radio stream for a few
    /// seconds on the default output device.
    /// `cargo test -p aw-radio live_stream -- --ignored --nocapture`
    #[test]
    #[ignore = "needs the network and an audio device"]
    fn live_stream_plays_for_a_few_seconds() {
        let backend = RodioBackend::new().unwrap();
        let url = std::env::var("AW_RADIO_TEST_URL")
            .unwrap_or_else(|_| "https://wxradio.org/FL-Tallahassee-KIH24".into());
        // AW_RADIO_TEST_VOLUME=0 checks decoding silently (the level meter
        // reads before volume).
        let volume = std::env::var("AW_RADIO_TEST_VOLUME")
            .ok()
            .and_then(|v| v.parse().ok())
            .unwrap_or(0.8);
        let stream = backend.open(&url, volume).expect("stream should start");
        let mut heard = false;
        for _ in 0..16 {
            std::thread::sleep(Duration::from_millis(500));
            heard |= stream.level() > 0;
            println!(
                "playing={} stalled={} level={}",
                stream.is_playing(),
                stream.is_stalled(),
                stream.level()
            );
        }
        stream.stop();
        assert!(heard, "expected some audio from {url}");
    }
}
