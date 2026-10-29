//! 레코드 검사(계약 3절)와 CSV·JSON Lines 읽기(계약 2절)(port/rust_reference/src/record.rs 에서 가져옴).

use crate::csv;
use crate::json::{self, Parsed, Value};
use crate::ts;

pub const FIELDS: [&str; 6] = ["ts", "method", "path", "status", "bytes", "latency_ms"];
const MAX_BYTES: i64 = 1_000_000_000_000;
const MAX_LATENCY_MS: f64 = 1e9;
const METHODS: [&str; 7] = ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"];

#[derive(Debug, Clone, PartialEq)]
pub struct Record {
    /// UTC 마이크로초(ts.rs)
    pub ts: i64,
    pub method: &'static str,
    /// WTF-8 바이트(JSON 의 짝 없는 서로게이트 포함). 바이트 순서 = 코드 포인트 순서
    pub path: Vec<u8>,
    pub status: i64,
    pub bytes: i64,
    pub latency_ms: f64,
}

/// (레코드 번호, 레코드 또는 이유 문자열)
pub type Row = (usize, Result<Record, String>);

fn bad(reason: &str) -> String {
    reason.to_string()
}

fn method(s: &[u8]) -> Result<&'static str, String> {
    METHODS
        .iter()
        .find(|m| m.as_bytes() == s)
        .copied()
        .ok_or_else(|| bad("bad method"))
}

fn timestamp(s: &[u8]) -> Result<i64, String> {
    ts::parse(s).ok_or_else(|| bad("bad ts"))
}

fn path(s: &[u8]) -> Result<Vec<u8>, String> {
    if s.first() != Some(&b'/') {
        return Err(bad("bad path"));
    }
    let end = s.iter().position(|&c| c == b'?').unwrap_or(s.len());
    Ok(s[..end].to_vec())
}

fn all_digits(s: &str) -> bool {
    !s.is_empty() && s.bytes().all(|c| c.is_ascii_digit())
}

/// CSV 한 행. `get` 은 필드 이름으로 값을 준다.
fn record_from_strings<'a>(get: impl Fn(&str) -> &'a str) -> Result<Record, String> {
    let method = method(get("method").as_bytes())?;
    let status = get("status").as_bytes();
    if !(status.len() == 3
        && (b'1'..=b'5').contains(&status[0])
        && status[1..].iter().all(u8::is_ascii_digit))
    {
        return Err(bad("bad status"));
    }
    let raw_bytes = get("bytes");
    let digits = match raw_bytes.trim_start_matches('0') {
        "" => "0",
        d => d,
    };
    if !all_digits(raw_bytes) || digits.len() > 13 {
        return Err(bad("bad bytes"));
    }
    let size: i64 = digits.parse().map_err(|_| bad("bad bytes"))?;
    if size > MAX_BYTES {
        return Err(bad("bad bytes"));
    }
    let raw_latency = get("latency_ms");
    let latency_ok = match raw_latency.split_once('.') {
        None => all_digits(raw_latency),
        Some((int, frac)) => all_digits(int) && all_digits(frac),
    };
    let latency: f64 = if latency_ok {
        raw_latency.parse().map_err(|_| bad("bad latency_ms"))?
    } else {
        return Err(bad("bad latency_ms"));
    };
    if latency > MAX_LATENCY_MS {
        return Err(bad("bad latency_ms"));
    }
    Ok(Record {
        ts: timestamp(get("ts").as_bytes())?,
        method,
        path: path(get("path").as_bytes())?,
        status: i64::from(status[0] - b'0') * 100
            + i64::from(status[1] - b'0') * 10
            + i64::from(status[2] - b'0'),
        bytes: size,
        latency_ms: latency,
    })
}

fn record_from_json(obj: &[(Vec<u8>, Value)]) -> Result<Record, String> {
    for name in FIELDS {
        if json::get(obj, name).is_none() {
            return Err(format!("missing field: {name}"));
        }
    }
    let field = |name: &str| json::get(obj, name).unwrap_or(&Value::Null);
    let method = match field("method") {
        Value::Str(s) => method(s)?,
        _ => return Err(bad("bad method")),
    };
    let status = match field("status") {
        Value::Int(Some(v)) if (100..=599).contains(v) => *v,
        _ => return Err(bad("bad status")),
    };
    let size = match field("bytes") {
        Value::Int(Some(v)) if (0..=MAX_BYTES).contains(v) => *v,
        _ => return Err(bad("bad bytes")),
    };
    let latency = match field("latency_ms") {
        Value::Int(Some(v)) if (0..=1_000_000_000).contains(v) => *v as f64,
        // NaN 은 비교가 모두 거짓이라 여기서 걸린다. -0.0 은 통과하고 부호를 유지한다
        Value::Float(x) if 0.0 <= *x && *x <= MAX_LATENCY_MS => *x,
        _ => return Err(bad("bad latency_ms")),
    };
    let ts = match field("ts") {
        Value::Str(s) => timestamp(s)?,
        _ => return Err(bad("bad ts")),
    };
    let path = match field("path") {
        Value::Str(s) => path(s)?,
        _ => return Err(bad("bad path")),
    };
    Ok(Record {
        ts,
        method,
        path,
        status,
        bytes: size,
        latency_ms: latency,
    })
}

/// (레코드 목록, 파일 전체를 거부하는 오류 메시지). 오류가 나도 그 앞까지 읽은 레코드는 돌려준다.
pub fn read_csv(text: &str) -> (Vec<Row>, Option<String>) {
    let mut reader = csv::Reader::new(text);
    let header = match reader.next() {
        None => return (Vec::new(), None),
        Some(Err(_)) => return (Vec::new(), Some("header: csv field too large".to_string())),
        Some(Ok(h)) => h,
    };
    // 같은 이름이 두 번 나오면 뒤의 열(dict(zip(header, row)))
    let mut index = [0usize; 6];
    for (slot, name) in index.iter_mut().zip(FIELDS) {
        match header.iter().rposition(|h| h == name) {
            Some(i) => *slot = i,
            None => return (Vec::new(), Some(format!("missing column: {name}"))),
        }
    }
    let mut out = Vec::new();
    let mut number = 0;
    for row in reader {
        let row = match row {
            Ok(row) => row,
            Err(_) => {
                return (
                    out,
                    Some(format!("record {}: csv field too large", number + 1)),
                )
            }
        };
        if row.is_empty() {
            continue;
        }
        number += 1;
        if row.len() != header.len() {
            out.push((number, Err(bad("bad field count"))));
            continue;
        }
        let get = |name: &str| {
            let i = FIELDS.iter().position(|f| *f == name).unwrap_or(0);
            row[index[i]].as_str()
        };
        out.push((number, record_from_strings(get)));
    }
    (out, None)
}

pub fn read_jsonl(text: &str) -> Vec<Row> {
    let mut out = Vec::new();
    let mut number = 0;
    // splitlines() 가 아니라 split('\n'): U+2028 등에서 나누지 않는다
    for line in text.split('\n') {
        if line.bytes().all(|b| matches!(b, b' ' | b'\t' | b'\r')) {
            continue;
        }
        number += 1;
        let item = match json::loads(line) {
            Err(_) => Err(bad("invalid json")),
            Ok(Parsed::NotObject) => Err(bad("not an object")),
            Ok(Parsed::Object(obj)) => record_from_json(&obj),
        };
        out.push((number, item));
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    const HEADER: &str = "ts,method,path,status,bytes,latency_ms\n";

    fn reasons(text: &str) -> Vec<String> {
        read_csv(text)
            .0
            .into_iter()
            .map(|(_, r)| r.err().unwrap_or_default())
            .collect()
    }

    #[test]
    fn csv_field_rules() {
        let t = format!(
            "{HEADER}2026-10-29T00:00:00Z,GET,/a,200,{},1\n\
             2026-10-29T00:00:00Z,GET,/a,200,1,1000000000.000001\n\
             2026-10-29T00:00:00Z,GET,/a,200,1,1.\n\
             2026-10-29T00:00:00Z,GET,/a,٢00,1,1\n\
             2026-10-29T00:00:00Z,get,/a,200,1,1\n\
             \"\"\n",
            "0".repeat(200) + "5"
        );
        assert_eq!(
            reasons(&t),
            [
                "",
                "bad latency_ms",
                "bad latency_ms",
                "bad status",
                "bad method",
                "bad field count"
            ]
        );
    }

    #[test]
    fn csv_header_errors() {
        assert_eq!(
            read_csv(&format!("\n{HEADER}")).1.as_deref(),
            Some("missing column: ts")
        );
        let big = format!("{HEADER}x,x,x,x,x,x\n,,/{},,,\n", "x".repeat(131_072));
        assert_eq!(
            read_csv(&big).1.as_deref(),
            Some("record 2: csv field too large")
        );
    }

    #[test]
    fn json_reasons() {
        let line = |status: &str| {
            format!(
                "{{\"ts\":\"2026-10-29T00:00:00Z\",\"method\":\"GET\",\"path\":\"/\",\"status\":{status},\"bytes\":1,\"latency_ms\":1}}"
            )
        };
        let text = [
            line("true"),
            line("200.0"),
            line("99999999999999999999"),
            line("200"),
        ]
        .join("\n");
        let got: Vec<String> = read_jsonl(&text)
            .into_iter()
            .map(|(_, r)| r.err().unwrap_or_default())
            .collect();
        assert_eq!(got, ["bad status", "bad status", "bad status", ""]);
    }
}
