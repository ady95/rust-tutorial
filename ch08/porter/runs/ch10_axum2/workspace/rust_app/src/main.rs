//! stockroom: 재고 관리 API (python_src/stockroom/app.py 의 Rust 이식).
//!
//! 사용법: stockroom [--host HOST] [--port PORT]   (기본 127.0.0.1:8000)

mod handlers;
mod http;
mod jsonout;
mod lax;
mod models;
mod pyjson;
mod router;
mod store;
#[cfg(test)]
mod verify_io;

use std::net::TcpListener;
use std::process::ExitCode;
use std::sync::Arc;

const STACK_SIZE: usize = 64 * 1024 * 1024;

const USAGE: &str = "usage: stockroom [-h] [--host HOST] [--port PORT]";

const HELP: &str = "usage: stockroom [-h] [--host HOST] [--port PORT]

options:
  -h, --help   show this help message and exit
  --host HOST
  --port PORT";

struct Args {
    host: String,
    /// Python int 로 받은 값(범위 검사는 바인드할 때 uvicorn 처럼)
    port: i128,
}

/// argparse 의 `type=int`: Python `int(text)` (ASCII 숫자만 지원, 밑줄은 숫자 사이 하나씩)
fn python_int(text: &str) -> Option<i128> {
    let t = text.trim_matches(|c: char| c.is_whitespace() || ('\u{1c}'..='\u{1f}').contains(&c));
    let (neg, digits) = match t.as_bytes().first() {
        Some(b'-') => (true, &t[1..]),
        Some(b'+') => (false, &t[1..]),
        _ => (false, t),
    };
    if digits.is_empty()
        || digits.starts_with('_')
        || digits.ends_with('_')
        || digits.contains("__")
        || !digits.bytes().all(|b| b.is_ascii_digit() || b == b'_')
    {
        return None;
    }
    let value: i128 = digits.replace('_', "").parse().unwrap_or(i128::MAX);
    Some(if neg { -value } else { value })
}

fn usage_error(message: &str) -> ExitCode {
    eprintln!("{USAGE}\nstockroom: error: {message}");
    ExitCode::from(2)
}

/// argparse 처럼 `--host H`, `--host=H`, 모호하지 않은 접두 약어(`--po`)를 받는다
fn parse_args(raw: &[String]) -> Result<Option<Args>, String> {
    let mut args = Args {
        host: "127.0.0.1".into(),
        port: 8000,
    };
    let mut unrecognized: Vec<&str> = Vec::new();
    let mut i = 0;
    while i < raw.len() {
        let arg = &raw[i];
        if arg == "-h" {
            return Ok(None);
        }
        if arg == "--" {
            unrecognized.extend(raw[i..].iter().map(String::as_str));
            break;
        }
        let Some(long) = arg.strip_prefix("--") else {
            unrecognized.push(arg);
            i += 1;
            continue;
        };
        let (name, inline) = match long.split_once('=') {
            Some((n, v)) => (n, Some(v.to_string())),
            None => (long, None),
        };
        let options = ["help", "host", "port"];
        let chosen = match options.iter().find(|o| **o == name) {
            Some(exact) => *exact,
            None => {
                let found: Vec<&str> = options
                    .iter()
                    .copied()
                    .filter(|o| o.starts_with(name))
                    .collect();
                match found[..] {
                    [one] => one,
                    [] => {
                        unrecognized.push(arg);
                        i += 1;
                        continue;
                    }
                    _ => {
                        let names: Vec<String> = found.iter().map(|o| format!("--{o}")).collect();
                        return Err(format!(
                            "ambiguous option: --{name} could match {}",
                            names.join(", ")
                        ));
                    }
                }
            }
        };
        if chosen == "help" {
            return Ok(None);
        }
        let value = match inline {
            Some(v) => v,
            None => {
                i += 1;
                raw.get(i)
                    .cloned()
                    .ok_or_else(|| format!("argument --{chosen}: expected one argument"))?
            }
        };
        if chosen == "host" {
            args.host = value;
        } else {
            args.port = python_int(&value)
                .ok_or_else(|| format!("argument --port: invalid int value: '{value}'"))?;
        }
        i += 1;
    }
    if !unrecognized.is_empty() {
        return Err(format!(
            "unrecognized arguments: {}",
            unrecognized.join(" ")
        ));
    }
    Ok(Some(args))
}

fn main() -> ExitCode {
    let raw: Vec<String> = std::env::args().skip(1).collect();
    let args = match parse_args(&raw) {
        Ok(Some(args)) => args,
        Ok(None) => {
            println!("{HELP}");
            return ExitCode::SUCCESS;
        }
        Err(message) => return usage_error(&message),
    };
    let test_mode = std::env::var("STOCKROOM_TEST").as_deref() == Ok("1");
    // 범위 밖 포트는 uvicorn 에서 OverflowError(종료 코드 1), 바인드 실패는 종료 코드 3
    let Ok(port) = u16::try_from(args.port) else {
        eprintln!("ERROR:    port must be 0-65535: {}", args.port);
        return ExitCode::from(1);
    };
    let listener = match TcpListener::bind((args.host.as_str(), port)) {
        Ok(listener) => listener,
        Err(err) => {
            let text = err.to_string();
            let reason = text
                .split(" (os error")
                .next()
                .unwrap_or(&text)
                .to_lowercase();
            eprintln!(
                "ERROR:    [Errno {}] error while attempting to bind on address ('{}', {port}): {reason}",
                err.raw_os_error().unwrap_or(0),
                args.host
            );
            return ExitCode::from(3);
        }
    };
    // JSON 해석이 재귀라 깊은 중첩(pyjson::MAX_DEPTH)을 견딜 스택을 작업자 스레드에 준다
    let runtime = match tokio::runtime::Builder::new_multi_thread()
        .thread_stack_size(STACK_SIZE)
        .enable_io()
        .build()
    {
        Ok(runtime) => runtime,
        Err(err) => {
            eprintln!("ERROR:    {err}");
            return ExitCode::from(1);
        }
    };
    let app = Arc::new(handlers::App::new(test_mode));
    runtime.block_on(async move {
        let converted = listener
            .set_nonblocking(true)
            .and_then(|()| tokio::net::TcpListener::from_std(listener));
        let Ok(listener) = converted else {
            return ExitCode::from(1);
        };
        match http::serve(listener, app).await {
            Ok(()) => ExitCode::SUCCESS,
            Err(_) => ExitCode::from(1),
        }
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn parse(args: &[&str]) -> Result<Option<Args>, String> {
        parse_args(&args.iter().map(|s| s.to_string()).collect::<Vec<_>>())
    }

    #[test]
    fn arguments_like_argparse() {
        let args = parse(&["--port", "9000", "--host=0.0.0.0"])
            .unwrap()
            .unwrap();
        assert_eq!((args.host.as_str(), args.port), ("0.0.0.0", 9000));
        assert_eq!(parse(&["--po=81"]).unwrap().unwrap().port, 81);
        assert!(parse(&["--h", "x"]).is_err());
        assert!(parse(&["--port", "x"]).is_err());
        assert!(parse(&["--help"]).unwrap().is_none());
    }
}
