//! 집계(기준 구현의 summarize)와 --strict 처리(port/rust_reference/src/lib.rs 에서 가져옴).
//! 출력 문자열 만들기는 하지 않는다. 그건 Python(format_text, json.dumps)이 한다.

use std::collections::HashMap;

use crate::output::error_rate;
use crate::record::{self, Record};
use crate::ts;

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
    let k = (p * sorted_values.len()).div_ceil(100);
    sorted_values[k.max(1) - 1]
}

pub fn summarize(records: &[Record], skipped: usize, top_n: u64) -> Summary {
    let mut status = [0usize; 4];
    let mut methods: HashMap<&'static str, usize> = HashMap::new();
    let mut minutes: HashMap<i64, usize> = HashMap::new();
    let mut by_path: HashMap<&[u8], Vec<&Record>> = HashMap::new();
    for r in records {
        // 1xx 는 어디에도 세지 않는다
        if let Some(slot) = usize::try_from(r.status / 100 - 2)
            .ok()
            .and_then(|i| status.get_mut(i))
        {
            *slot += 1;
        }
        *methods.entry(r.method).or_default() += 1;
        *minutes.entry(ts::minute_index(r.ts)).or_default() += 1;
        by_path.entry(&r.path).or_default().push(r);
    }
    let mut methods: Vec<(&'static str, usize)> = methods.into_iter().collect();
    methods.sort_by(|a, b| b.1.cmp(&a.1).then(a.0.cmp(b.0)));

    let mut paths: Vec<(&[u8], Vec<&Record>)> = by_path.into_iter().collect();
    paths.sort_by(|a, b| b.1.len().cmp(&a.1.len()).then(a.0.cmp(b.0)));
    let take = usize::try_from(top_n).unwrap_or(usize::MAX);
    let top = paths
        .into_iter()
        .take(take)
        .map(|(path, rows)| {
            let values = sorted(rows.iter().map(|r| r.latency_ms).collect());
            let errors = rows.iter().filter(|r| r.status >= 500).count();
            TopPath {
                path: path.to_vec(),
                count: rows.len(),
                error_rate: error_rate(errors, rows.len()),
                p50: nearest_rank(&values, 50),
                p95: nearest_rank(&values, 95),
            }
        })
        .collect();

    // 개수가 가장 많은 분, 같으면 이른 분
    let peak = minutes
        .into_iter()
        .min_by(|a, b| b.1.cmp(&a.1).then(a.0.cmp(&b.0)))
        .map(|(minute, count)| (ts::minute_key(minute * 60_000_000), count));
    let latencies = sorted(records.iter().map(|r| r.latency_ms).collect());
    Summary {
        records: records.len(),
        skipped,
        first: records.iter().map(|r| r.ts).min(),
        last: records.iter().map(|r| r.ts).max(),
        bytes: records.iter().map(|r| r.bytes as u128).sum(),
        status,
        methods,
        latency: if records.is_empty() {
            None
        } else {
            Some([50, 95, 99].map(|p| nearest_rank(&latencies, p)))
        },
        peak,
        top,
    }
}

/// 입력 오류(파일 전체 오류, --strict 의 첫 잘못된 레코드) 메시지 또는 요약.
/// 기준 구현 run() 과 같은 순서: 헤더·긴 필드 오류가 --strict 보다 먼저다.
pub fn run(text: &str, csv: bool, top_n: u64, strict: bool) -> Result<Summary, String> {
    let rows = if csv {
        let (rows, header_error) = record::read_csv(text);
        if let Some(err) = header_error {
            return Err(err);
        }
        rows
    } else {
        record::read_jsonl(text)
    };
    let mut records = Vec::new();
    let mut skipped = 0;
    for (number, item) in rows {
        match item {
            Ok(r) => records.push(r),
            Err(reason) => {
                if strict {
                    return Err(format!("record {number}: {reason}"));
                }
                skipped += 1;
            }
        }
    }
    Ok(summarize(&records, skipped, top_n))
}

#[cfg(test)]
mod tests {
    use super::*;

    const HEADER: &str = "ts,method,path,status,bytes,latency_ms\n";

    #[test]
    fn peak_and_top() {
        let text = format!(
            "{HEADER}2026-10-29T09:00:30+09:00,GET,/a?x=1,200,1,1\n2026-10-29T00:00:10Z,GET,/a,500,1,3\n\
             2026-10-29T00:01:00Z,POST,/b,200,1,1\n"
        );
        let s = run(&text, true, 10, false).unwrap();
        assert_eq!(s.peak, Some(("2026-10-29T00:00Z".to_string(), 2)));
        assert_eq!(s.top[0].count, 2);
        assert_eq!(s.top[0].error_rate, "50.0%");
        assert_eq!(s.methods, [("GET", 2), ("POST", 1)]);
    }

    #[test]
    fn huge_field_beats_strict() {
        let text = format!(
            "{HEADER}x\n2026-10-29T00:00:00Z,GET,/{},200,1,1\n",
            "x".repeat(131_072)
        );
        assert_eq!(
            run(&text, true, 10, true).err().as_deref(),
            Some("record 2: csv field too large")
        );
    }

    #[test]
    fn bytes_sum_does_not_overflow() {
        let total: u128 = std::iter::repeat(1_000_000_000_000_u64)
            .take(20_000_000)
            .map(u128::from)
            .sum();
        assert_eq!(total, 20_000_000_000_000_000_000);
    }
}
