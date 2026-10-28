//! stats — 숫자 목록 요약. `python_src/stats.py` 의 Rust 이식.
//!
//! 사용법: stats FILE

mod bigint;
mod pyfloat;
mod stats;

use std::io::Write;
use std::process::ExitCode;

fn parse(lines: &[&str]) -> Result<Vec<f64>, String> {
    let mut numbers = Vec::new();
    for (i, line) in lines.iter().enumerate() {
        let text = line.trim_matches(pyfloat::is_py_space);
        if text.is_empty() {
            continue;
        }
        match pyfloat::parse(text) {
            Some(x) => numbers.push(x),
            None => return Err(format!("not a number on line {}: {}", i + 1, text)),
        }
    }
    Ok(numbers)
}

fn summarize(numbers: &[f64]) -> String {
    let mean = stats::mean(numbers);
    let lines = [
        format!("count: {}", numbers.len()),
        format!("sum: {}", pyfloat::repr(stats::py_sum(numbers))),
        format!("mean: {}", pyfloat::repr(mean)),
        format!("mean2: {}", pyfloat::repr(pyfloat::round(mean, 2))),
        format!("stdev: {}", pyfloat::fixed(stats::stdev(numbers), 4)),
        format!("min: {}", pyfloat::repr(stats::py_min(numbers))),
        format!("max: {}", pyfloat::repr(stats::py_max(numbers))),
    ];
    lines.join("\n") + "\n"
}

/// Python 의 UnicodeDecodeError 메시지.
fn decode_error(bytes: &[u8], err: std::str::Utf8Error) -> String {
    let start = err.valid_up_to();
    let (end, reason) = match err.error_len() {
        None => (bytes.len(), "unexpected end of data"),
        Some(len) => {
            let reason = if (0xc2..=0xf4).contains(&bytes[start]) {
                "invalid continuation byte"
            } else {
                "invalid start byte"
            };
            (start + len, reason)
        }
    };
    if end == start + 1 {
        format!(
            "'utf-8' codec can't decode byte 0x{:02x} in position {}: {}",
            bytes[start], start, reason
        )
    } else {
        format!(
            "'utf-8' codec can't decode bytes in position {}-{}: {}",
            start,
            end - 1,
            reason
        )
    }
}

fn run(args: &[String]) -> Result<String, (u8, String)> {
    if args.len() != 1 {
        return Err((2, "usage: stats FILE".to_string()));
    }
    let path = &args[0];
    let bytes =
        std::fs::read(path).map_err(|_| (1, format!("stats: error: cannot read file: {path}")))?;
    let text = std::str::from_utf8(&bytes)
        .map_err(|e| (1, format!("stats: error: {}", decode_error(&bytes, e))))?;
    let numbers =
        parse(&pyfloat::splitlines(text)).map_err(|e| (1, format!("stats: error: {e}")))?;
    if numbers.len() < 2 {
        return Err((1, "stats: error: need at least 2 numbers".to_string()));
    }
    if numbers.iter().any(|x| !x.is_finite()) {
        // statistics.stdev 는 inf/nan 이 섞이면 float 에 .numerator 를 찾다가 AttributeError 로 죽는다.
        // 추적 정보(traceback)까지 똑같이 재현하지는 못하므로 마지막 줄만 낸다.
        return Err((
            1,
            "AttributeError: 'float' object has no attribute 'numerator'".to_string(),
        ));
    }
    Ok(summarize(&numbers))
}

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args_os()
        .skip(1)
        .map(|a| a.to_string_lossy().into_owned())
        .collect();
    match run(&args) {
        Ok(out) => {
            let _ = std::io::stdout().write_all(out.as_bytes());
            ExitCode::SUCCESS
        }
        Err((code, msg)) => {
            eprintln!("{msg}");
            ExitCode::from(code)
        }
    }
}
