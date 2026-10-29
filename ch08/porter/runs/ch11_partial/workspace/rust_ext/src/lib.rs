//! logstat_core: logstat 의 해석·검증(v1)과 해석·검증·집계(v2)를 Rust 로 하는 PyO3 확장 모듈.
//!
//! 해석·검증·집계 코드는 port/rust_reference 에서 가져왔고, 이 파일은 Python 객체와의 경계만 다룬다.
//! - v1 `read_csv`, `read_jsonl`: 기준 구현과 같은 `(레코드 번호, Record | BadRecord)` 목록을 만든다
//! - v2 `summarize`: 기준 구현 summarize() 가 돌려주는 것과 같은 구조의 dict 를 만든다

pub mod csv;
pub mod json;
pub mod output;
pub mod record;
pub mod summary;
pub mod ts;

use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDateTime, PyDict, PyList, PyString, PyTzInfo};

use record::Record;
use summary::Summary;

/// WTF-8 바이트를 Python str 로. 짝 없는 서로게이트가 있으면 surrogatepass 로 읽는다.
fn py_str<'py>(py: Python<'py>, b: &[u8]) -> PyResult<Bound<'py, PyAny>> {
    match std::str::from_utf8(b) {
        Ok(s) => Ok(PyString::new(py, s).into_any()),
        Err(_) => PyBytes::new(py, b).call_method1("decode", ("utf-8", "surrogatepass")),
    }
}

fn py_datetime<'py>(
    py: Python<'py>,
    tz: &Bound<'py, PyTzInfo>,
    t: i64,
) -> PyResult<Bound<'py, PyDateTime>> {
    let p = ts::parts(t);
    PyDateTime::new(
        py,
        p.year as i32,
        p.month as u8,
        p.day as u8,
        p.hour as u8,
        p.minute as u8,
        p.second as u8,
        p.micro as u32,
        Some(tz),
    )
}

struct Builder<'py> {
    py: Python<'py>,
    tz: Bound<'py, PyTzInfo>,
    record_cls: Bound<'py, PyAny>,
    bad_cls: Bound<'py, PyAny>,
}

impl<'py> Builder<'py> {
    fn new(
        py: Python<'py>,
        record_cls: &Bound<'py, PyAny>,
        bad_cls: &Bound<'py, PyAny>,
    ) -> PyResult<Self> {
        Ok(Builder {
            py,
            tz: PyTzInfo::utc(py)?.to_owned(),
            record_cls: record_cls.clone(),
            bad_cls: bad_cls.clone(),
        })
    }

    fn rows(&self, rows: Vec<record::Row>) -> PyResult<Bound<'py, PyList>> {
        let out = PyList::empty(self.py);
        for (number, item) in rows {
            let obj = match item {
                Ok(r) => self.record(&r)?,
                Err(reason) => self.bad_cls.call1((reason,))?,
            };
            out.append((number, obj))?;
        }
        Ok(out)
    }

    fn record(&self, r: &Record) -> PyResult<Bound<'py, PyAny>> {
        self.record_cls.call1((
            py_datetime(self.py, &self.tz, r.ts)?,
            r.method,
            py_str(self.py, &r.path)?,
            r.status,
            r.bytes,
            r.latency_ms,
        ))
    }
}

/// 기준 구현 read_csv(text) 와 같은 `(rows, header_error)`.
#[pyfunction]
fn read_csv<'py>(
    py: Python<'py>,
    text: &str,
    record_cls: &Bound<'py, PyAny>,
    bad_cls: &Bound<'py, PyAny>,
) -> PyResult<(Bound<'py, PyList>, Option<String>)> {
    let (rows, error) = record::read_csv(text);
    Ok((Builder::new(py, record_cls, bad_cls)?.rows(rows)?, error))
}

/// 기준 구현 read_jsonl(text) 와 같은 rows.
#[pyfunction]
fn read_jsonl<'py>(
    py: Python<'py>,
    text: &str,
    record_cls: &Bound<'py, PyAny>,
    bad_cls: &Bound<'py, PyAny>,
) -> PyResult<Bound<'py, PyList>> {
    Builder::new(py, record_cls, bad_cls)?.rows(record::read_jsonl(text))
}

fn summary_dict<'py>(py: Python<'py>, s: &Summary) -> PyResult<Bound<'py, PyDict>> {
    let d = PyDict::new(py);
    d.set_item("records", s.records)?;
    d.set_item("skipped", s.skipped)?;
    d.set_item("first", s.first.map(ts::isoformat))?;
    d.set_item("last", s.last.map(ts::isoformat))?;
    d.set_item("bytes", s.bytes)?;
    let status = PyDict::new(py);
    for (key, n) in ["2xx", "3xx", "4xx", "5xx"].iter().zip(s.status) {
        status.set_item(key, n)?;
    }
    d.set_item("status", status)?;
    let methods = PyDict::new(py);
    for (key, n) in &s.methods {
        methods.set_item(key, n)?;
    }
    d.set_item("methods", methods)?;
    match s.latency {
        Some([p50, p95, p99]) => {
            let lat = PyDict::new(py);
            lat.set_item("p50", p50)?;
            lat.set_item("p95", p95)?;
            lat.set_item("p99", p99)?;
            d.set_item("latency_ms", lat)?;
        }
        None => d.set_item("latency_ms", py.None())?,
    }
    match &s.peak {
        Some((minute, count)) => {
            let peak = PyDict::new(py);
            peak.set_item("minute", minute)?;
            peak.set_item("count", count)?;
            d.set_item("peak_minute", peak)?;
        }
        None => d.set_item("peak_minute", py.None())?,
    }
    let top = PyList::empty(py);
    for t in &s.top {
        let item = PyDict::new(py);
        item.set_item("path", py_str(py, &t.path)?)?;
        item.set_item("count", t.count)?;
        item.set_item("error_rate", &t.error_rate)?;
        item.set_item("p50", t.p50)?;
        item.set_item("p95", t.p95)?;
        top.append(item)?;
    }
    d.set_item("top_paths", top)?;
    Ok(d)
}

/// 해석·검증·집계까지 한다. 입력 오류면 `(메시지, None)`, 아니면 `(None, summary dict)`.
/// 메시지는 `logstat: error: ` 뒤에 올 문자열(헤더·긴 필드 오류, 또는 `record N: 이유`).
#[pyfunction]
fn summarize<'py>(
    py: Python<'py>,
    text: &str,
    is_csv: bool,
    top_n: &Bound<'py, PyAny>,
    strict: bool,
) -> PyResult<(Option<String>, Option<Bound<'py, PyDict>>)> {
    // --top 은 자릿수 제한이 없는 Python int 다. u64 를 넘으면 "전부"와 같으므로 최댓값으로 둔다
    let top_n = top_n.extract::<u64>().unwrap_or(u64::MAX);
    match summary::run(text, is_csv, top_n, strict) {
        Err(message) => Ok((Some(message), None)),
        Ok(s) => Ok((None, Some(summary_dict(py, &s)?))),
    }
}

#[pymodule]
fn logstat_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(read_csv, m)?)?;
    m.add_function(wrap_pyfunction!(read_jsonl, m)?)?;
    m.add_function(wrap_pyfunction!(summarize, m)?)?;
    Ok(())
}
