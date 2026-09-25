//! HTTP for the AI services, with the request deadline and streaming rules.
//!
//! Ports `RequestDeadline` and `stream_chat_completion` from `ai_provider.py`.
//! Everything is blocking for the caller (the UI calls from worker threads);
//! internally one small tokio runtime drives `reqwest`, so a request that
//! outlives its limits, or is cancelled, is dropped and its connection closed
//! at once — the equivalent of Python closing the OpenAI client.

use std::future::Future;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, OnceLock};
use std::time::{Duration, Instant};

use serde_json::Value;
use tokio::runtime::Runtime;

use crate::errors::TransportError;
use crate::pyfmt::truthy;

/// `REQUEST_DEADLINE_SECONDS`: the ceiling for a non-streamed completion.
pub const REQUEST_DEADLINE: Duration = Duration::from_secs(30);

const CONNECT_TIMEOUT: Duration = Duration::from_secs(20);
/// How often limits and cancellation are checked (Python's watchdog period).
const TICK: Duration = Duration::from_millis(100);

/// Cancels a running request from another thread.
#[derive(Debug, Clone, Default)]
pub struct CancelToken(Arc<AtomicBool>);

impl CancelToken {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn cancel(&self) {
        self.0.store(true, Ordering::SeqCst);
    }

    pub fn is_cancelled(&self) -> bool {
        self.0.load(Ordering::SeqCst)
    }
}

/// When to give up on a request. A queued model sends only keep-alive
/// comments, so one with no token after `first_token` is dropped for the
/// retry; a model that is writing is kept until it goes `stall` without a
/// token or hits `total`.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct StreamLimits {
    pub first_token: Option<Duration>,
    pub stall: Option<Duration>,
    pub total: Duration,
}

impl StreamLimits {
    /// `FIRST_TOKEN_SECONDS`, `STALL_SECONDS`, `STREAM_DEADLINE_SECONDS`.
    pub const STREAMING: Self = Self {
        first_token: Some(Duration::from_secs(10)),
        stall: Some(Duration::from_secs(15)),
        total: Duration::from_secs(90),
    };

    /// A single ceiling, as the Weather Assistant's tool-calling requests use.
    pub const fn deadline(total: Duration) -> Self {
        Self {
            first_token: None,
            stall: None,
            total,
        }
    }
}

fn runtime() -> &'static Runtime {
    static RUNTIME: OnceLock<Runtime> = OnceLock::new();
    RUNTIME.get_or_init(|| {
        tokio::runtime::Builder::new_multi_thread()
            .worker_threads(1)
            .thread_name("aw-ai-http")
            .enable_all()
            .build()
            .expect("create the AI HTTP runtime")
    })
}

fn client() -> &'static reqwest::Client {
    static CLIENT: OnceLock<reqwest::Client> = OnceLock::new();
    CLIENT.get_or_init(|| {
        reqwest::Client::builder()
            .user_agent(concat!("AccessiWeather/", env!("CARGO_PKG_VERSION")))
            .connect_timeout(CONNECT_TIMEOUT)
            .build()
            .expect("create the AI HTTP client")
    })
}

fn transport_error(error: reqwest::Error) -> TransportError {
    if error.is_timeout() {
        TransportError::Timeout
    } else {
        TransportError::Connect
    }
}

/// Tracks the limits of one request, like Python's `RequestDeadline`.
struct Watch<'a> {
    limits: StreamLimits,
    cancel: Option<&'a CancelToken>,
    started: Instant,
    last_progress: Option<Instant>,
}

impl<'a> Watch<'a> {
    fn new(limits: StreamLimits, cancel: Option<&'a CancelToken>) -> Self {
        Self {
            limits,
            cancel,
            started: Instant::now(),
            last_progress: None,
        }
    }

    /// Record that the model produced a token.
    fn progress(&mut self) {
        self.last_progress = Some(Instant::now());
    }

    fn check(&self) -> Result<(), TransportError> {
        if self.cancel.is_some_and(CancelToken::is_cancelled) {
            return Err(TransportError::Cancelled);
        }
        let now = Instant::now();
        let secs = |d: Duration| format!("{:.0}", d.as_secs_f64());
        if now - self.started >= self.limits.total {
            return Err(TransportError::Deadline(format!(
                "The AI service did not answer within {} seconds.",
                secs(self.limits.total)
            )));
        }
        match (
            self.last_progress,
            self.limits.first_token,
            self.limits.stall,
        ) {
            (None, Some(first), _) if now - self.started >= first => {
                Err(TransportError::Deadline(format!(
                    "The AI model did not start answering within {} seconds.",
                    secs(first)
                )))
            }
            (Some(last), _, Some(stall)) if now - last >= stall => {
                Err(TransportError::Deadline(format!(
                    "The AI model stopped answering for {} seconds.",
                    secs(stall)
                )))
            }
            _ => Ok(()),
        }
    }

    /// Drive `future`, abandoning it (and its connection) once a limit expires.
    async fn run<F: Future>(&self, future: F) -> Result<F::Output, TransportError> {
        let mut future = std::pin::pin!(future);
        loop {
            self.check()?;
            if let Ok(output) = tokio::time::timeout(TICK, &mut future).await {
                return Ok(output);
            }
        }
    }
}

pub(crate) struct HttpResponse {
    pub status: u16,
    pub body: String,
}

/// An authenticated (when `bearer` is given) GET; statuses are not errors here.
pub(crate) fn get(
    url: &str,
    bearer: Option<&str>,
    timeout: Duration,
) -> Result<HttpResponse, TransportError> {
    runtime().block_on(async {
        let mut request = client().get(url).timeout(timeout);
        if let Some(key) = bearer {
            request = request.bearer_auth(key);
        }
        let response = request.send().await.map_err(transport_error)?;
        let status = response.status().as_u16();
        let body = response.text().await.map_err(transport_error)?;
        Ok(HttpResponse { status, body })
    })
}

fn post(
    url: &str,
    api_key: &str,
    headers: &[(&str, &str)],
    body: &Value,
) -> reqwest::RequestBuilder {
    let mut request = client().post(url).bearer_auth(api_key).json(body);
    for (name, value) in headers {
        request = request.header(*name, *value);
    }
    request
}

/// A non-streamed chat completion; returns the response JSON.
pub(crate) fn chat_completion(
    url: &str,
    api_key: &str,
    headers: &[(&str, &str)],
    body: &Value,
    limits: StreamLimits,
    cancel: Option<&CancelToken>,
) -> Result<Value, TransportError> {
    runtime().block_on(async {
        let watch = Watch::new(limits, cancel);
        let response = watch
            .run(post(url, api_key, headers, body).send())
            .await?
            .map_err(transport_error)?;
        let status = response.status().as_u16();
        let text = watch.run(response.text()).await?.map_err(transport_error)?;
        if status >= 400 {
            return Err(TransportError::Status { status, body: text });
        }
        serde_json::from_str(&text).map_err(|_| TransportError::Other)
    })
}

/// The text, model, finish reason and token counts of a streamed completion.
#[derive(Debug, Clone, Default, PartialEq)]
pub(crate) struct ChatStream {
    pub content: String,
    pub model: Option<String>,
    pub finish_reason: Option<String>,
    pub total_tokens: u64,
    pub prompt_tokens: u64,
    pub completion_tokens: u64,
}

impl ChatStream {
    /// Fold one `chat.completion.chunk`; true when it carried a token.
    fn add(&mut self, chunk: &Value, usage: &mut Option<Value>) -> bool {
        if let Some(model) = chunk.get("model").and_then(Value::as_str) {
            if !model.is_empty() {
                self.model = Some(model.to_string());
            }
        }
        if let Some(u) = chunk.get("usage").filter(|u| !u.is_null()) {
            *usage = Some(u.clone());
        }
        let Some(choice) = chunk
            .get("choices")
            .and_then(Value::as_array)
            .and_then(|c| c.first())
        else {
            return false;
        };
        if let Some(reason) = choice.get("finish_reason").and_then(Value::as_str) {
            if !reason.is_empty() {
                self.finish_reason = Some(reason.to_string());
            }
        }
        let Some(delta) = choice.get("delta").filter(|d| !d.is_null()) else {
            return false;
        };
        let field = |name: &str| delta.get(name).filter(|v| truthy(v));
        // Reasoning models stream their thinking before any answer text.
        let progressed = ["content", "reasoning", "reasoning_content"]
            .iter()
            .any(|name| field(name).is_some());
        if let Some(text) = field("content").and_then(Value::as_str) {
            self.content.push_str(text);
        }
        progressed
    }
}

/// Stream one completion and return its text, model, finish reason and token
/// counts, enforcing `limits`.
pub(crate) fn stream_chat_completion(
    url: &str,
    api_key: &str,
    headers: &[(&str, &str)],
    body: &Value,
    limits: StreamLimits,
    cancel: Option<&CancelToken>,
) -> Result<ChatStream, TransportError> {
    let mut body = body.clone();
    body["stream"] = Value::Bool(true);
    body["stream_options"] = serde_json::json!({"include_usage": true});
    let mut result = ChatStream::default();
    let mut usage = None;
    runtime().block_on(async {
        let mut watch = Watch::new(limits, cancel);
        let mut response = watch
            .run(post(url, api_key, headers, &body).send())
            .await?
            .map_err(transport_error)?;
        let status = response.status().as_u16();
        if status >= 400 {
            let text = watch.run(response.text()).await?.unwrap_or_default();
            return Err(TransportError::Status { status, body: text });
        }
        let mut events = SseParser::default();
        'read: loop {
            let chunk = watch
                .run(response.chunk())
                .await?
                .map_err(transport_error)?;
            let data = match &chunk {
                Some(bytes) => events.push(bytes),
                None => events.finish(),
            };
            for event in data {
                if event.starts_with("[DONE]") {
                    break 'read;
                }
                let chunk: Value =
                    serde_json::from_str(&event).map_err(|_| TransportError::Other)?;
                if let Some(error) = chunk.get("error").filter(|e| truthy(e)) {
                    return Err(stream_api_error(error));
                }
                if result.add(&chunk, &mut usage) {
                    watch.progress();
                }
            }
            if chunk.is_none() {
                break;
            }
        }
        Ok(())
    })?;
    if let Some(usage) = usage {
        let count = |name: &str| usage.get(name).and_then(Value::as_u64).unwrap_or(0);
        result.total_tokens = count("total_tokens");
        result.prompt_tokens = count("prompt_tokens");
        result.completion_tokens = count("completion_tokens");
    }
    Ok(result)
}

/// The OpenAI SDK raises `APIError` for an `error` object inside a stream.
fn stream_api_error(error: &Value) -> TransportError {
    let message = error
        .get("message")
        .and_then(Value::as_str)
        .filter(|m| !m.is_empty())
        .unwrap_or("An error occurred during streaming");
    let code = error
        .get("code")
        .filter(|c| !c.is_null())
        .map(crate::pyfmt::str);
    TransportError::Api {
        code,
        message: message.to_string(),
    }
}

/// Server-sent events: yields the `data` of each complete event; comments
/// (keep-alive pings) are ignored.
#[derive(Default)]
struct SseParser {
    buffer: Vec<u8>,
    data: Vec<String>,
}

impl SseParser {
    fn push(&mut self, bytes: &[u8]) -> Vec<String> {
        self.buffer.extend_from_slice(bytes);
        let mut events = Vec::new();
        while let Some(end) = self.buffer.iter().position(|&b| b == b'\n') {
            let line: Vec<u8> = self.buffer.drain(..=end).collect();
            let line = String::from_utf8_lossy(&line);
            self.line(line.trim_end_matches(['\n', '\r']), &mut events);
        }
        events
    }

    fn finish(&mut self) -> Vec<String> {
        let mut events = Vec::new();
        if !self.buffer.is_empty() {
            let rest = std::mem::take(&mut self.buffer);
            let line = String::from_utf8_lossy(&rest);
            self.line(line.trim_end_matches('\r'), &mut events);
        }
        self.line("", &mut events);
        events
    }

    fn line(&mut self, line: &str, events: &mut Vec<String>) {
        if line.is_empty() {
            if !self.data.is_empty() {
                events.push(self.data.join("\n"));
                self.data.clear();
            }
            return;
        }
        if line.starts_with(':') {
            return;
        }
        let (field, value) = line.split_once(':').unwrap_or((line, ""));
        if field == "data" {
            self.data
                .push(value.strip_prefix(' ').unwrap_or(value).to_string());
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::test_server::{sse_chunk, Reply, Step, TestServer};
    use serde_json::json;

    fn limits(first: f64, stall: f64, total: f64) -> StreamLimits {
        StreamLimits {
            first_token: Some(Duration::from_secs_f64(first)),
            stall: Some(Duration::from_secs_f64(stall)),
            total: Duration::from_secs_f64(total),
        }
    }

    fn pings(count: usize) -> Vec<Step> {
        (0..count)
            .flat_map(|_| {
                [
                    Step::Send(b": OPENROUTER PROCESSING\n\n".to_vec()),
                    Step::Sleep(Duration::from_millis(100)),
                ]
            })
            .collect()
    }

    fn stream(server: &TestServer, limits: StreamLimits) -> Result<ChatStream, TransportError> {
        stream_chat_completion(
            &format!("{}/chat/completions", server.url()),
            "test",
            &[],
            &json!({"model": "m", "messages": []}),
            limits,
            None,
        )
    }

    #[test]
    fn drops_a_model_that_never_starts_answering() {
        let server = TestServer::start(vec![Reply::sse(pings(200))]);
        let started = Instant::now();
        let error = stream(&server, limits(0.5, 5.0, 10.0)).unwrap_err();
        assert_eq!(
            error,
            TransportError::Deadline(
                "The AI model did not start answering within 0 seconds.".into()
            )
        );
        assert!(started.elapsed() < Duration::from_secs(3));
        let sent: Value = serde_json::from_str(&server.requests()[0].body).unwrap();
        assert_eq!(sent["stream"], true);
        assert_eq!(sent["stream_options"], json!({"include_usage": true}));
    }

    #[test]
    fn drops_a_model_that_stops_answering_midway() {
        let mut steps = vec![Step::Send(sse_chunk(Some("Clear "), None, None))];
        steps.extend(pings(200));
        let server = TestServer::start(vec![Reply::sse(steps)]);
        let started = Instant::now();
        let error = stream(&server, limits(5.0, 0.5, 10.0)).unwrap_err();
        assert!(matches!(error, TransportError::Deadline(m) if m.contains("stopped answering")));
        assert!(started.elapsed() < Duration::from_secs(3));
    }

    #[test]
    fn keeps_a_model_that_writes_longer_than_the_stall_limit() {
        let mut steps = Vec::new();
        for word in ["Clear ", "skies ", "tonight."] {
            steps.push(Step::Send(sse_chunk(Some(word), None, None)));
            steps.push(Step::Sleep(Duration::from_millis(400)));
        }
        steps.push(Step::Send(sse_chunk(None, Some("stop"), None)));
        let usage = json!({"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7});
        steps.push(Step::Send(sse_chunk(None, None, Some(usage))));
        steps.push(Step::Send(b"data: [DONE]\n\n".to_vec()));
        let server = TestServer::start(vec![Reply::sse(steps)]);
        let result = stream(&server, limits(0.5, 0.5, 10.0)).unwrap();
        assert_eq!(
            result,
            ChatStream {
                content: "Clear skies tonight.".into(),
                model: Some("picked/model".into()),
                finish_reason: Some("stop".into()),
                total_tokens: 7,
                prompt_tokens: 3,
                completion_tokens: 4,
            }
        );
    }

    #[test]
    fn reasoning_counts_as_progress_but_is_not_answer_text() {
        let reasoning =
            b"data: {\"model\":\"r\",\"choices\":[{\"delta\":{\"reasoning\":\"hmm\"}}]}\n\n";
        let mut steps = vec![
            Step::Send(reasoning.to_vec()),
            Step::Sleep(Duration::from_millis(700)),
        ];
        steps.push(Step::Send(sse_chunk(
            Some("Answer text."),
            Some("stop"),
            None,
        )));
        let server = TestServer::start(vec![Reply::sse(steps)]);
        let result = stream(&server, limits(0.5, 5.0, 10.0)).unwrap();
        assert_eq!(result.content, "Answer text.");
        assert_eq!(result.total_tokens, 0);
    }

    #[test]
    fn total_deadline_cuts_off_a_keep_alive_stall() {
        let steps = (0..200)
            .flat_map(|_| {
                [
                    Step::Send(b" ".to_vec()),
                    Step::Sleep(Duration::from_millis(100)),
                ]
            })
            .collect();
        let server = TestServer::start(vec![Reply::raw(200, "application/json", steps)]);
        let started = Instant::now();
        let error = chat_completion(
            &format!("{}/chat/completions", server.url()),
            "k",
            &[],
            &json!({}),
            StreamLimits::deadline(Duration::from_millis(500)),
            None,
        )
        .unwrap_err();
        assert!(
            matches!(error, TransportError::Deadline(m) if m.contains("did not answer within"))
        );
        assert!(started.elapsed() < Duration::from_secs(3));
    }

    #[test]
    fn cancellation_stops_a_stream_promptly() {
        let server = TestServer::start(vec![Reply::sse(pings(200))]);
        let cancel = CancelToken::new();
        let trigger = cancel.clone();
        std::thread::spawn(move || {
            std::thread::sleep(Duration::from_millis(300));
            trigger.cancel();
        });
        let started = Instant::now();
        let error = stream_chat_completion(
            &format!("{}/chat/completions", server.url()),
            "k",
            &[],
            &json!({}),
            StreamLimits::STREAMING,
            Some(&cancel),
        )
        .unwrap_err();
        assert_eq!(error, TransportError::Cancelled);
        assert!(started.elapsed() < Duration::from_secs(2));
    }

    #[test]
    fn stream_errors_and_statuses_are_reported() {
        let server = TestServer::start(vec![
            Reply::sse(vec![Step::Send(
                b"data: {\"error\": {\"code\": 502, \"message\": \"Provider returned error\"}}\n\n"
                    .to_vec(),
            )]),
            Reply::text(429, "busy"),
        ]);
        assert_eq!(
            stream(&server, StreamLimits::STREAMING).unwrap_err(),
            TransportError::Api {
                code: Some("502".into()),
                message: "Provider returned error".into()
            }
        );
        assert_eq!(
            stream(&server, StreamLimits::STREAMING).unwrap_err(),
            TransportError::Status {
                status: 429,
                body: "busy".into()
            }
        );
    }

    #[test]
    fn sse_parser_handles_split_lines_and_comments() {
        let mut parser = SseParser::default();
        assert!(parser.push(b": ping\n\nda").is_empty());
        assert!(parser.push(b"ta: {\"a\":").is_empty());
        assert_eq!(
            parser.push(b"1}\r\n\r\ndata: x"),
            vec!["{\"a\":1}".to_string()]
        );
        assert_eq!(parser.finish(), vec!["x".to_string()]);
    }
}
