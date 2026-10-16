//! A scripted HTTP/1.1 server on 127.0.0.1 for transport tests: each
//! connection gets the next [`Reply`], whose body can arrive in timed pieces
//! (SSE streams with slow starts, stalls and keep-alive pings).

use std::collections::VecDeque;
use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream};
use std::sync::{Arc, Mutex};
use std::time::Duration;

use serde_json::{json, Value};

pub(crate) enum Step {
    Send(Vec<u8>),
    Sleep(Duration),
}

pub(crate) struct Reply {
    status: u16,
    content_type: &'static str,
    steps: Vec<Step>,
}

impl Reply {
    pub fn raw(status: u16, content_type: &'static str, steps: Vec<Step>) -> Self {
        Self {
            status,
            content_type,
            steps,
        }
    }

    pub fn json(status: u16, body: Value) -> Self {
        Self::raw(
            status,
            "application/json",
            vec![Step::Send(body.to_string().into_bytes())],
        )
    }

    pub fn text(status: u16, body: &str) -> Self {
        Self::raw(
            status,
            "text/plain",
            vec![Step::Send(body.as_bytes().to_vec())],
        )
    }

    pub fn sse(steps: Vec<Step>) -> Self {
        Self::raw(200, "text/event-stream", steps)
    }
}

/// One `data:` event of a `chat.completion.chunk` from "picked/model".
pub(crate) fn sse_chunk(
    content: Option<&str>,
    finish: Option<&str>,
    usage: Option<Value>,
) -> Vec<u8> {
    let choices = if content.is_none() && finish.is_none() {
        json!([])
    } else {
        let delta = content.map_or(json!({}), |c| json!({"content": c}));
        json!([{"index": 0, "delta": delta, "finish_reason": finish}])
    };
    let mut body = json!({"id": "c", "object": "chat.completion.chunk", "created": 0,
                          "model": "picked/model", "choices": choices});
    if let Some(usage) = usage {
        body["usage"] = usage;
    }
    format!("data: {body}\n\n").into_bytes()
}

#[derive(Debug, Clone)]
pub(crate) struct Request {
    pub method: String,
    pub path: String,
    pub headers: Vec<(String, String)>,
    pub body: String,
}

impl Request {
    pub fn header(&self, name: &str) -> Option<&str> {
        self.headers
            .iter()
            .find(|(k, _)| k.eq_ignore_ascii_case(name))
            .map(|(_, v)| v.as_str())
    }

    pub fn json(&self) -> Value {
        serde_json::from_str(&self.body).unwrap_or(Value::Null)
    }
}

pub(crate) struct TestServer {
    port: u16,
    requests: Arc<Mutex<Vec<Request>>>,
}

impl TestServer {
    pub fn start(replies: Vec<Reply>) -> Self {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let port = listener.local_addr().unwrap().port();
        let requests = Arc::new(Mutex::new(Vec::new()));
        let replies = Arc::new(Mutex::new(VecDeque::from(replies)));
        let log = requests.clone();
        std::thread::spawn(move || {
            for stream in listener.incoming().flatten() {
                let Some(reply) = replies.lock().unwrap().pop_front() else {
                    break;
                };
                let log = log.clone();
                std::thread::spawn(move || serve(stream, reply, &log));
            }
        });
        Self { port, requests }
    }

    pub fn url(&self) -> String {
        format!("http://127.0.0.1:{}", self.port)
    }

    pub fn requests(&self) -> Vec<Request> {
        self.requests.lock().unwrap().clone()
    }
}

fn serve(mut stream: TcpStream, reply: Reply, log: &Mutex<Vec<Request>>) {
    let Some(request) = read_request(&mut stream) else {
        return;
    };
    log.lock().unwrap().push(request);
    let head = format!(
        "HTTP/1.1 {} Test\r\nContent-Type: {}\r\nConnection: close\r\n\r\n",
        reply.status, reply.content_type
    );
    if stream.write_all(head.as_bytes()).is_err() {
        return;
    }
    for step in reply.steps {
        match step {
            Step::Send(bytes) => {
                if stream
                    .write_all(&bytes)
                    .and_then(|_| stream.flush())
                    .is_err()
                {
                    return;
                }
            }
            Step::Sleep(duration) => std::thread::sleep(duration),
        }
    }
}

fn read_request(stream: &mut TcpStream) -> Option<Request> {
    let mut data = Vec::new();
    let mut buf = [0u8; 4096];
    let header_end = loop {
        let n = stream.read(&mut buf).ok()?;
        if n == 0 {
            return None;
        }
        data.extend_from_slice(&buf[..n]);
        if let Some(pos) = data.windows(4).position(|w| w == b"\r\n\r\n") {
            break pos + 4;
        }
    };
    let head = String::from_utf8_lossy(&data[..header_end]).to_string();
    let mut lines = head.split("\r\n");
    let mut first = lines.next()?.split(' ');
    let method = first.next()?.to_string();
    let path = first.next()?.to_string();
    let headers: Vec<(String, String)> = lines
        .filter_map(|l| l.split_once(':'))
        .map(|(k, v)| (k.trim().to_string(), v.trim().to_string()))
        .collect();
    let length: usize = headers
        .iter()
        .find(|(k, _)| k.eq_ignore_ascii_case("content-length"))
        .and_then(|(_, v)| v.parse().ok())
        .unwrap_or(0);
    while data.len() < header_end + length {
        let n = stream.read(&mut buf).ok()?;
        if n == 0 {
            break;
        }
        data.extend_from_slice(&buf[..n]);
    }
    let body = String::from_utf8_lossy(&data[header_end..]).to_string();
    Some(Request {
        method,
        path,
        headers,
        body,
    })
}
