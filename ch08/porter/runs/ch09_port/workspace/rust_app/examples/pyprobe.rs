//! verify/ 의 Python 스크립트가 라이브러리 함수를 대량으로 대조할 때 쓰는 도구.
//!
//! 표준 입력 한 줄에 요청 하나, 표준 출력 한 줄에 결과 하나:
//! - `repr <f64 비트 16진>` → `py_repr`
//! - `rate <errors> <n>` → `error_rate`
//! - `int <UTF-8 바이트 16진>` → `python_int`(ValueError 면 `ERR`)
//! - `help <columns>` → `help_text` 의 UTF-8 바이트 16진

use std::io::{BufRead, BufWriter, Write};

use logstat::help::{help_text, python_int};
use logstat::output::{error_rate, py_repr};

fn unhex(s: &str) -> Vec<u8> {
    (0..s.len() / 2)
        .map(|i| u8::from_str_radix(&s[2 * i..2 * i + 2], 16).unwrap_or(0))
        .collect()
}

fn hex(b: &[u8]) -> String {
    b.iter().map(|x| format!("{x:02x}")).collect()
}

fn main() {
    let stdin = std::io::stdin();
    let mut out = BufWriter::new(std::io::stdout().lock());
    for line in stdin.lock().lines() {
        let line = line.unwrap_or_default();
        let mut words = line.split(' ');
        let result = match (words.next(), words.next(), words.next()) {
            (Some("repr"), Some(bits), _) => {
                py_repr(f64::from_bits(u64::from_str_radix(bits, 16).unwrap_or(0)))
            }
            (Some("rate"), Some(e), Some(n)) => {
                error_rate(e.parse().unwrap_or(0), n.parse().unwrap_or(1))
            }
            (Some("int"), arg, _) => {
                let text = String::from_utf8_lossy(&unhex(arg.unwrap_or(""))).into_owned();
                python_int(&text).map_or("ERR".to_string(), |v| v.to_string())
            }
            (Some("help"), Some(cols), _) => hex(help_text(cols.parse().unwrap_or(80)).as_bytes()),
            _ => "BAD REQUEST".to_string(),
        };
        let _ = writeln!(out, "{result}");
    }
}
