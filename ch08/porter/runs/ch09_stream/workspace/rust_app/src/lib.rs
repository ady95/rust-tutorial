//! logstat: CSV·JSON Lines 접근 로그를 요약한다(python_src/logstat.py 의 Rust 이식).
//!
//! `run` 은 입출력 없이 (종료 코드, stdout, stderr)를 돌려주는 순수 함수이고, main.rs 가 파일과 표준 출력을 다룬다.
//! stdout 은 WTF-8 바이트다. JSON 의 짝 없는 서로게이트(`"\ud800"`)가 경로로 출력되면 UTF-8 이 아니게 되고,
//! 그 처리는 main.rs 가 한다(Python 은 그 경우 stdout 에 쓰다가 UnicodeEncodeError 로 끝난다).

pub mod cli;
pub mod csv;
pub mod help;
pub mod json;
pub mod output;
pub mod record;
pub mod ts;

use std::collections::HashMap;

use output::{error_rate, json_string, py_repr};
use record::Record;

pub const EXIT_OK: i32 = 0;
pub const EXIT_INPUT_ERROR: i32 = 1;
pub const EXIT_USAGE_ERROR: i32 = 2;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Format {
    Csv,
    Jsonl,
}

pub struct TopPath {
    pub path: Vec<u8>,
    pub count: usize,
    pub error_rate: String,
    pub p50: f64,
    pub p95: f64,
}

pub struct Summary {
    pub records: usize,
    pub skipped: usize,
    pub first: Option<i64>,
    pub last: Option<i64>,
    /// 넘침 없는 합(레코드당 최대 10^12)
    pub bytes: u128,
    /// 2xx, 3xx, 4xx, 5xx
    pub status: [usize; 4],
    pub methods: Vec<(&'static str, usize)>,
    pub latency: Option<[f64; 3]>,
    pub peak: Option<(String, usize)>,
    pub top: Vec<TopPath>,
}

/// 안정 정렬. -0.0 과 0.0 은 같은 값으로 보아 입력 순서를 지킨다(Python sorted 와 같음).
fn sorted(mut values: Vec<f64>) -> Vec<f64> {
    values.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
    values
}

/// nearest-rank: k = ceil(p * n / 100), 정수로만 계산
fn nearest_rank(sorted_values: &[f64], p: usize) -> f64 {
    let k = (p * sorted_values.len() + 99) / 100;
    sorted_values[k.max(1) - 1]
}

/// 경로 하나의 누적값. latency 는 입력 순서대로 모은다(안정 정렬의 기준)
#[derive(Default)]
struct PathStats {
    count: usize,
    errors: usize,
    latencies: Vec<f64>,
}

/// 레코드를 하나씩 받아 요약에 필요한 값만 누적한다. Record 는 보관하지 않는다.
#[derive(Default)]
struct Aggregator {
    records: usize,
    skipped: usize,
    first: Option<i64>,
    last: Option<i64>,
    bytes: u128,
    status: [usize; 4],
    methods: HashMap<&'static str, usize>,
    minutes: HashMap<i64, usize>,
    latencies: Vec<f64>,
    by_path: HashMap<Vec<u8>, PathStats>,
}

impl Aggregator {
    fn add(&mut self, r: Record) {
        self.records += 1;
        self.first = Some(self.first.map_or(r.ts, |v| v.min(r.ts)));
        self.last = Some(self.last.map_or(r.ts, |v| v.max(r.ts)));
        self.bytes += r.bytes as u128;
        // 1xx 는 어디에도 세지 않는다
        if let Some(slot) = usize::try_from(r.status / 100 - 2)
            .ok()
            .and_then(|i| self.status.get_mut(i))
        {
            *slot += 1;
        }
        *self.methods.entry(r.method).or_default() += 1;
        *self.minutes.entry(ts::minute_index(r.ts)).or_default() += 1;
        self.latencies.push(r.latency_ms);
        let stats = self.by_path.entry(r.path).or_default();
        stats.count += 1;
        stats.errors += usize::from(r.status >= 500);
        stats.latencies.push(r.latency_ms);
    }

    fn finish(self, top_n: u64) -> Summary {
        let mut methods: Vec<(&'static str, usize)> = self.methods.into_iter().collect();
        methods.sort_by(|a, b| b.1.cmp(&a.1).then(a.0.cmp(b.0)));

        let mut paths: Vec<(Vec<u8>, PathStats)> = self.by_path.into_iter().collect();
        paths.sort_by(|a, b| b.1.count.cmp(&a.1.count).then(a.0.cmp(&b.0)));
        let take = usize::try_from(top_n).unwrap_or(usize::MAX);
        let top = paths
            .into_iter()
            .take(take)
            .map(|(path, stats)| {
                let values = sorted(stats.latencies);
                TopPath {
                    path,
                    count: stats.count,
                    error_rate: error_rate(stats.errors, stats.count),
                    p50: nearest_rank(&values, 50),
                    p95: nearest_rank(&values, 95),
                }
            })
            .collect();

        // 개수가 가장 많은 분, 같으면 이른 분
        let peak = self
            .minutes
            .into_iter()
            .min_by(|a, b| b.1.cmp(&a.1).then(a.0.cmp(&b.0)))
            .map(|(minute, count)| (ts::minute_key(minute * 60_000_000), count));
        let latencies = sorted(self.latencies);
        Summary {
            records: self.records,
            skipped: self.skipped,
            first: self.first,
            last: self.last,
            bytes: self.bytes,
            status: self.status,
            methods,
            latency: if self.records == 0 {
                None
            } else {
                Some([50, 95, 99].map(|p| nearest_rank(&latencies, p)))
            },
            peak,
            top,
        }
    }
}

const STATUS_KEYS: [&str; 4] = ["2xx", "3xx", "4xx", "5xx"];

pub fn format_text(s: &Summary) -> Vec<u8> {
    let range = match (s.first, s.last) {
        (Some(first), Some(last)) => {
            format!("{} .. {}", ts::isoformat(first), ts::isoformat(last))
        }
        _ => "-".to_string(),
    };
    let status: Vec<String> = STATUS_KEYS
        .iter()
        .zip(s.status)
        .map(|(k, v)| format!("{k}={v}"))
        .collect();
    let methods: Vec<String> = s.methods.iter().map(|(k, v)| format!("{k}={v}")).collect();
    let methods = if methods.is_empty() {
        "-".to_string()
    } else {
        methods.join(" ")
    };
    let latency = match s.latency {
        Some([p50, p95, p99]) => format!(
            "p50={} p95={} p99={}",
            py_repr(p50),
            py_repr(p95),
            py_repr(p99)
        ),
        None => "-".to_string(),
    };
    let peak = match &s.peak {
        Some((minute, count)) => format!("{minute} {count}"),
        None => "-".to_string(),
    };
    let mut out = format!(
        "records: {}\nskipped: {}\nrange: {range}\nbytes: {}\nstatus: {}\nmethods: {methods}\n\
         latency_ms: {latency}\npeak_minute: {peak}\ntop_paths:\n",
        s.records,
        s.skipped,
        s.bytes,
        status.join(" ")
    )
    .into_bytes();
    for t in &s.top {
        out.extend_from_slice(
            format!(
                "{}\t{}\t{}\t{}\t",
                t.count,
                t.error_rate,
                py_repr(t.p50),
                py_repr(t.p95)
            )
            .as_bytes(),
        );
        out.extend_from_slice(&t.path);
        out.push(b'\n');
    }
    out
}

fn json_opt_string(out: &mut Vec<u8>, s: Option<String>) {
    match s {
        Some(s) => json_string(out, s.as_bytes()),
        None => out.extend_from_slice(b"null"),
    }
}

/// `json.dumps(summary, ensure_ascii=False, separators=(",", ":")) + "\n"`
pub fn format_json(s: &Summary) -> Vec<u8> {
    let mut out = Vec::new();
    out.extend_from_slice(
        format!(
            "{{\"records\":{},\"skipped\":{},\"first\":",
            s.records, s.skipped
        )
        .as_bytes(),
    );
    json_opt_string(&mut out, s.first.map(ts::isoformat));
    out.extend_from_slice(b",\"last\":");
    json_opt_string(&mut out, s.last.map(ts::isoformat));
    out.extend_from_slice(format!(",\"bytes\":{},\"status\":{{", s.bytes).as_bytes());
    let status: Vec<String> = STATUS_KEYS
        .iter()
        .zip(s.status)
        .map(|(k, v)| format!("\"{k}\":{v}"))
        .collect();
    out.extend_from_slice(status.join(",").as_bytes());
    out.extend_from_slice(b"},\"methods\":{");
    let methods: Vec<String> = s
        .methods
        .iter()
        .map(|(k, v)| format!("\"{k}\":{v}"))
        .collect();
    out.extend_from_slice(methods.join(",").as_bytes());
    out.extend_from_slice(b"},\"latency_ms\":");
    match s.latency {
        Some([p50, p95, p99]) => out.extend_from_slice(
            format!(
                "{{\"p50\":{},\"p95\":{},\"p99\":{}}}",
                py_repr(p50),
                py_repr(p95),
                py_repr(p99)
            )
            .as_bytes(),
        ),
        None => out.extend_from_slice(b"null"),
    }
    out.extend_from_slice(b",\"peak_minute\":");
    match &s.peak {
        Some((minute, count)) => {
            out.extend_from_slice(b"{\"minute\":");
            json_string(&mut out, minute.as_bytes());
            out.extend_from_slice(format!(",\"count\":{count}}}").as_bytes());
        }
        None => out.extend_from_slice(b"null"),
    }
    out.extend_from_slice(b",\"top_paths\":[");
    for (i, t) in s.top.iter().enumerate() {
        if i > 0 {
            out.push(b',');
        }
        out.extend_from_slice(b"{\"path\":");
        json_string(&mut out, &t.path);
        out.extend_from_slice(
            format!(
                ",\"count\":{},\"error_rate\":\"{}\",\"p50\":{},\"p95\":{}}}",
                t.count,
                t.error_rate,
                py_repr(t.p50),
                py_repr(t.p95)
            )
            .as_bytes(),
        );
    }
    out.extend_from_slice(b"]}\n");
    out
}

/// 입출력 없는 본체. (종료 코드, stdout, stderr)
pub fn run(
    text: &str,
    fmt: Format,
    top_n: u64,
    as_json: bool,
    strict: bool,
) -> (i32, Vec<u8>, Vec<u8>) {
    let mut agg = Aggregator::default();
    // --strict 의 첫 오류. 파일 끝까지 읽은 뒤에야 확정한다(뒤의 헤더·긴 필드 오류가 우선)
    let mut strict_error: Option<String> = None;
    let sink = |number: usize, item: Result<Record, String>| match item {
        Ok(r) => {
            if strict_error.is_none() {
                agg.add(r);
            }
        }
        Err(reason) if strict => {
            strict_error
                .get_or_insert_with(|| format!("logstat: error: record {number}: {reason}\n"));
        }
        Err(_) => agg.skipped += 1,
    };
    if fmt == Format::Csv {
        if let Some(err) = record::read_csv(text, sink) {
            return (
                EXIT_INPUT_ERROR,
                Vec::new(),
                format!("logstat: error: {err}\n").into_bytes(),
            );
        }
    } else {
        record::read_jsonl(text, sink);
    }
    if let Some(err) = strict_error {
        return (EXIT_INPUT_ERROR, Vec::new(), err.into_bytes());
    }
    let summary = agg.finish(top_n);
    let out = if as_json {
        format_json(&summary)
    } else {
        format_text(&summary)
    };
    (EXIT_OK, out, Vec::new())
}

#[cfg(test)]
mod tests {
    use super::*;

    const HEADER: &str = "ts,method,path,status,bytes,latency_ms\n";

    #[test]
    fn query_string_is_dropped() {
        let text = format!("{HEADER}2026-10-29T00:00:00Z,GET,/a?x=1,200,1,1\n2026-10-29T00:00:00Z,GET,/a?y=2,200,1,1\n");
        let (_, out, _) = run(&text, Format::Csv, 10, false, false);
        assert!(String::from_utf8(out)
            .unwrap()
            .ends_with("2\t0.0%\t1.0\t1.0\t/a\n"));
    }

    #[test]
    fn timezone_and_peak_minute() {
        let text = format!(
            "{HEADER}2026-10-29T09:00:30+09:00,GET,/a,200,1,1\n2026-10-29T00:00:10Z,GET,/a,200,1,1\n\
             2026-10-29T00:01:00Z,GET,/a,200,1,1\n"
        );
        let out = String::from_utf8(run(&text, Format::Csv, 10, false, false).1).unwrap();
        assert!(out.contains("range: 2026-10-29T00:00:10+00:00 .. 2026-10-29T00:01:00+00:00\n"));
        assert!(out.contains("peak_minute: 2026-10-29T00:00Z 2\n"));
    }

    #[test]
    fn empty_input_json() {
        let (_, out, _) = run("", Format::Csv, 10, true, false);
        assert_eq!(
            String::from_utf8(out).unwrap(),
            "{\"records\":0,\"skipped\":0,\"first\":null,\"last\":null,\"bytes\":0,\
             \"status\":{\"2xx\":0,\"3xx\":0,\"4xx\":0,\"5xx\":0},\"methods\":{},\"latency_ms\":null,\
             \"peak_minute\":null,\"top_paths\":[]}\n"
        );
    }

    #[test]
    fn strict_reasons() {
        let cases = [
            ("{\"ts\":\"2026-10-29T00:00:00Z\",\"method\":\"GET\",\"path\":\"/\",\"status\":true,\"bytes\":1,\"latency_ms\":1}", "bad status"),
            ("{\"ts\":\"2026-10-29T00:00:00Z\",\"method\":\"GET\",\"path\":\"/\",\"status\":200,\"bytes\":1,\"latency_ms\":NaN}", "bad latency_ms"),
            ("{\"ts\":\"2026-02-30T00:00:00Z\",\"method\":\"GET\",\"path\":\"/\",\"status\":200,\"bytes\":1,\"latency_ms\":1}", "bad ts"),
            ("{\"ts\":\"2026-10-29T00:00:00Z\",\"method\":\"GET\",\"path\":\"/\",\"status\":200,\"bytes\":1}", "missing field: latency_ms"),
            ("[1]", "not an object"),
            ("{", "invalid json"),
        ];
        for (line, reason) in cases {
            let got = run(&format!("{line}\n"), Format::Jsonl, 10, false, true);
            assert_eq!(
                got,
                (
                    1,
                    Vec::new(),
                    format!("logstat: error: record 1: {reason}\n").into_bytes()
                )
            );
        }
    }

    #[test]
    fn huge_field_beats_strict() {
        let text = format!(
            "{HEADER}x\n2026-10-29T00:00:00Z,GET,/{},200,1,1\n",
            "x".repeat(131_072)
        );
        assert_eq!(
            run(&text, Format::Csv, 10, false, true),
            (
                1,
                Vec::new(),
                b"logstat: error: record 2: csv field too large\n".to_vec()
            )
        );
    }

    #[test]
    fn negative_zero_keeps_input_order() {
        let line = |lat: &str| {
            format!("{{\"ts\":\"2026-10-29T00:00:00Z\",\"method\":\"GET\",\"path\":\"/\",\"status\":200,\"bytes\":1,\"latency_ms\":{lat}}}\n")
        };
        let a = run(
            &(line("-0.0") + &line("0.0")),
            Format::Jsonl,
            10,
            false,
            false,
        )
        .1;
        assert!(String::from_utf8(a).unwrap().contains("p50=-0.0 p95=0.0"));
        let b = run(
            &(line("0.0") + &line("-0.0")),
            Format::Jsonl,
            10,
            false,
            false,
        )
        .1;
        assert!(String::from_utf8(b).unwrap().contains("p50=0.0 p95=-0.0"));
    }

    #[test]
    fn bytes_sum_does_not_overflow() {
        // u64 는 약 1,850만 × 10^12 에서 넘친다
        let mut agg = Aggregator {
            bytes: u128::from(u64::MAX),
            ..Aggregator::default()
        };
        agg.add(Record {
            ts: 0,
            method: "GET",
            path: b"/".to_vec(),
            status: 200,
            bytes: 1_000_000_000_000,
            latency_ms: 1.0,
        });
        assert_eq!(agg.bytes, u128::from(u64::MAX) + 1_000_000_000_000);
    }
}
