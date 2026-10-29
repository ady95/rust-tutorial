//! HTTP/1.1 서버(연결마다 스레드 하나, keep-alive). 요청 줄·헤더 검사는 h11 규칙을 따른다.

use std::io::{self, BufRead, BufReader, Read, Write};
use std::net::{SocketAddr, TcpListener, TcpStream};
use std::sync::Arc;
use std::thread;

use crate::handlers::{App, Request, Response};

/// 요청 머리(요청 줄부터 빈 줄까지, CRLF 포함) 한도. 기준 서버(uvicorn + h11)에서 실측한 경계
/// (verify/probe_head_limit.py: 127973 바이트는 받고 127974 바이트는 400)
const MAX_HEAD: usize = 127_973;
const STACK_SIZE: usize = 64 * 1024 * 1024;

struct Parsed {
    method: String,
    target: Vec<u8>,
    headers: Vec<(String, Vec<u8>)>,
    body: Vec<u8>,
    keep_alive: bool,
    expect_continue: bool,
}

enum ReadError {
    /// 연결이 닫혔거나 읽기 실패
    Closed,
    /// 잘못된 요청 줄·헤더 → 400 후 닫기
    Invalid,
    /// 잘못된 chunked 본문 → 400(chunked) 후 닫기
    InvalidBody,
}

impl From<io::Error> for ReadError {
    fn from(_: io::Error) -> Self {
        ReadError::Closed
    }
}

pub fn serve(listener: TcpListener, app: Arc<App>) {
    for stream in listener.incoming() {
        let Ok(stream) = stream else { continue };
        let app = Arc::clone(&app);
        // JSON 해석이 재귀라 깊은 중첩(pyjson::MAX_DEPTH)을 견딜 스택을 준다
        let spawned = thread::Builder::new()
            .stack_size(STACK_SIZE)
            .spawn(move || {
                let _ = connection(stream, &app);
            });
        drop(spawned);
    }
}

fn connection(stream: TcpStream, app: &App) -> io::Result<()> {
    let local = stream.local_addr()?;
    let _ = stream.set_nodelay(true);
    let mut reader = BufReader::new(stream.try_clone()?);
    let mut writer = stream;
    loop {
        let read = read_head(&mut reader).and_then(|(mut request, framing)| {
            // uvicorn 은 본문을 읽는 라우트에서만 100 Continue 를 보낸다
            if request.expect_continue && app.reads_body(&request.method, &request.target) {
                writer.write_all(b"HTTP/1.1 100 Continue\r\n\r\n")?;
            }
            request.body = read_body(&mut reader, framing)?;
            Ok(request)
        });
        match read {
            Ok(request) => {
                let response = handle(app, &request, local);
                let head_only = request.method == "HEAD";
                write_response(&mut writer, &response, head_only, request.keep_alive)?;
                if !request.keep_alive {
                    return Ok(());
                }
            }
            Err(ReadError::Closed) => return Ok(()),
            Err(ReadError::Invalid) => {
                // 헤더 단계 오류: uvicorn 은 content-length 없이 보내고 연결을 닫는다
                writer.write_all(&invalid_request(false))?;
                return writer.flush();
            }
            Err(ReadError::InvalidBody) => {
                // 본문 단계 오류: h11 이 chunked 로 보낸다
                writer.write_all(&invalid_request(true))?;
                return writer.flush();
            }
        }
    }
}

fn handle(app: &App, request: &Parsed, local: SocketAddr) -> Response {
    let req = Request {
        method: &request.method,
        target: &request.target,
        headers: &request.headers,
        body: &request.body,
        local,
    };
    // 처리 중 패닉은 Python 의 처리되지 않은 예외처럼 500 으로 바꾼다
    std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| app.handle(&req)))
        .unwrap_or_else(|_| Response::internal_error())
}

fn read_line(reader: &mut impl BufRead, budget: &mut usize) -> Result<Vec<u8>, ReadError> {
    let mut line = Vec::new();
    let read = reader
        .by_ref()
        .take(*budget as u64 + 1)
        .read_until(b'\n', &mut line)?;
    if read == 0 {
        return Err(ReadError::Closed);
    }
    if read > *budget {
        return Err(ReadError::Invalid);
    }
    *budget -= read;
    if line.pop() != Some(b'\n') {
        return Err(ReadError::Closed);
    }
    if line.last() == Some(&b'\r') {
        line.pop();
    }
    Ok(line)
}

fn is_token(s: &[u8]) -> bool {
    !s.is_empty()
        && s.iter()
            .all(|&c| c.is_ascii_alphanumeric() || b"!#$%&'*+-.^_`|~".contains(&c))
}

fn invalid_request(chunked: bool) -> Vec<u8> {
    const BODY: &str = "Invalid HTTP request received.";
    let head = "HTTP/1.1 400 Bad Request\r\ncontent-type: text/plain; charset=utf-8\r\nconnection: close\r\n";
    if chunked {
        format!(
            "{head}transfer-encoding: chunked\r\n\r\n{:x}\r\n{BODY}\r\n0\r\n\r\n",
            BODY.len()
        )
    } else {
        format!("{head}\r\n{BODY}")
    }
    .into_bytes()
}

enum Framing {
    None,
    Length(usize),
    Chunked,
}

fn read_body(reader: &mut impl BufRead, framing: Framing) -> Result<Vec<u8>, ReadError> {
    match framing {
        Framing::None => Ok(Vec::new()),
        Framing::Length(length) => {
            let mut body = vec![0; length];
            reader.read_exact(&mut body)?;
            Ok(body)
        }
        Framing::Chunked => read_chunked(reader),
    }
}

/// `Content-Length` 값(쉼표 목록이면 모두 같아야 한다, h11)
fn content_length(values: &[&[u8]]) -> Result<usize, ReadError> {
    let mut found = None;
    for value in values {
        for part in value.split(|&c| c == b',') {
            let part = part.trim_ascii();
            if part.is_empty() || !part.iter().all(u8::is_ascii_digit) {
                return Err(ReadError::Invalid);
            }
            let n: usize = std::str::from_utf8(part)
                .ok()
                .and_then(|s| s.parse().ok())
                .ok_or(ReadError::Invalid)?;
            if found.is_some_and(|f| f != n) {
                return Err(ReadError::Invalid);
            }
            found = Some(n);
        }
    }
    found.ok_or(ReadError::Invalid)
}

fn read_head(reader: &mut impl BufRead) -> Result<(Parsed, Framing), ReadError> {
    let mut budget = MAX_HEAD;
    let line = read_line(reader, &mut budget)?;
    let parts: Vec<&[u8]> = line.split(|&c| c == b' ').collect();
    let [method, target, version] = parts[..] else {
        return Err(ReadError::Invalid);
    };
    if !is_token(method)
        || target.is_empty()
        || !target.iter().all(|&c| (0x21..=0x7E).contains(&c))
        || version.len() != 8
        || !version.starts_with(b"HTTP/")
        || !version[5].is_ascii_digit()
        || version[6] != b'.'
        || !version[7].is_ascii_digit()
    {
        return Err(ReadError::Invalid);
    }
    // HTTP/1.1 이상이면 keep-alive, Host 필수(h11)
    let http11 = (version[5], version[7]) >= (b'1', b'1');
    let mut headers: Vec<(String, Vec<u8>)> = Vec::new();
    loop {
        let line = read_line(reader, &mut budget).map_err(|e| match e {
            ReadError::Closed => ReadError::Invalid,
            other => other,
        })?;
        if line.is_empty() {
            break;
        }
        // obs-fold: 앞 헤더 값에 공백 하나로 이어 붙인다
        if line[0] == b' ' || line[0] == b'\t' {
            let (_, value) = headers.last_mut().ok_or(ReadError::Invalid)?;
            if line.iter().any(|&c| matches!(c, 0 | 0x0B | 0x0C)) {
                return Err(ReadError::Invalid);
            }
            value.push(b' ');
            value.extend_from_slice(line.trim_ascii());
            continue;
        }
        let colon = line
            .iter()
            .position(|&c| c == b':')
            .ok_or(ReadError::Invalid)?;
        let name = &line[..colon];
        if !is_token(name) {
            return Err(ReadError::Invalid);
        }
        let value = line[colon + 1..].trim_ascii();
        if value
            .iter()
            .any(|&c| matches!(c, 0 | b'\n' | b'\r' | 0x0B | 0x0C))
        {
            return Err(ReadError::Invalid);
        }
        headers.push((
            String::from_utf8_lossy(name).to_ascii_lowercase(),
            value.to_vec(),
        ));
    }
    let values = |name: &str| -> Vec<&[u8]> {
        headers
            .iter()
            .filter(|(n, _)| n == name)
            .map(|(_, v)| v.as_slice())
            .collect()
    };
    let close = values("connection").iter().any(|v| {
        v.split(|&c| c == b',')
            .any(|t| t.trim_ascii().eq_ignore_ascii_case(b"close"))
    });
    let hosts = values("host").len();
    if hosts > 1 || (http11 && hosts == 0) {
        return Err(ReadError::Invalid);
    }
    let expect_continue = http11
        && values("expect")
            .iter()
            .any(|v| v.eq_ignore_ascii_case(b"100-continue"));
    let transfer = values("transfer-encoding");
    let lengths = values("content-length");
    // Transfer-Encoding 이 있으면 Content-Length 는 무시한다(h11)
    let framing = if !transfer.is_empty() {
        if transfer.len() != 1 || !transfer[0].eq_ignore_ascii_case(b"chunked") {
            return Err(ReadError::Invalid);
        }
        Framing::Chunked
    } else if !lengths.is_empty() {
        Framing::Length(content_length(&lengths)?)
    } else {
        Framing::None
    };
    let parsed = Parsed {
        method: String::from_utf8_lossy(method).into_owned(),
        target: target.to_vec(),
        headers,
        body: Vec::new(),
        keep_alive: http11 && !close,
        expect_continue,
    };
    Ok((parsed, framing))
}

fn read_chunked(reader: &mut impl BufRead) -> Result<Vec<u8>, ReadError> {
    let mut body = Vec::new();
    loop {
        let mut budget = MAX_HEAD;
        let line = read_line(reader, &mut budget)?;
        let size_text = line
            .split(|&c| c == b';')
            .next()
            .unwrap_or(&[])
            .trim_ascii();
        let size = std::str::from_utf8(size_text)
            .ok()
            .filter(|s| !s.is_empty() && s.len() <= 20)
            .and_then(|s| usize::from_str_radix(s, 16).ok())
            .ok_or(ReadError::InvalidBody)?;
        if size == 0 {
            // 트레일러를 빈 줄까지 버린다
            loop {
                if read_line(reader, &mut budget)?.is_empty() {
                    return Ok(body);
                }
            }
        }
        let start = body.len();
        body.resize(start + size, 0);
        reader.read_exact(&mut body[start..])?;
        // 조각 뒤에는 정확히 CRLF(h11 0.16)
        let mut footer = [0; 2];
        reader.read_exact(&mut footer)?;
        if &footer != b"\r\n" {
            return Err(ReadError::InvalidBody);
        }
    }
}

fn reason(status: u16) -> &'static str {
    match status {
        200 => "OK",
        201 => "Created",
        204 => "No Content",
        307 => "Temporary Redirect",
        400 => "Bad Request",
        404 => "Not Found",
        405 => "Method Not Allowed",
        409 => "Conflict",
        422 => "Unprocessable Entity",
        _ => "Internal Server Error",
    }
}

fn write_response(
    writer: &mut TcpStream,
    response: &Response,
    head_only: bool,
    keep_alive: bool,
) -> io::Result<()> {
    let mut head = format!(
        "HTTP/1.1 {} {}\r\n",
        response.status,
        reason(response.status)
    );
    if response.status != 204 {
        head.push_str(&format!("content-length: {}\r\n", response.body.len()));
    }
    if let Some(content_type) = response.content_type {
        head.push_str(&format!("content-type: {content_type}\r\n"));
    }
    if let Some(location) = &response.location {
        head.push_str(&format!("location: {location}\r\n"));
    }
    if let Some(allow) = response.allow {
        head.push_str(&format!("allow: {allow}\r\n"));
    }
    if !keep_alive {
        head.push_str("connection: close\r\n");
    }
    head.push_str("\r\n");
    let mut out = head.into_bytes();
    if !head_only {
        out.extend_from_slice(&response.body);
    }
    writer.write_all(&out)?;
    writer.flush()
}
