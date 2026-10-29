//! verify/exhaustive.py 와 함께 쓰는 실측 비교용 덤프. 평소 `cargo test` 에서는 건너뛴다.
//!
//! 사용법: python 쪽 `gen` → `cargo test -- --ignored dump_for_verify` → python 쪽 `check`
//! `../verify/data/<kind>.in`(한 줄에 16진 입력 하나)을 읽어 `<kind>.rust` 에 결과를 한 줄씩 쓴다.
//! 코드 포인트 전수 시험(`*sweep`)은 입력 파일 없이 같은 순서로 직접 만들고, 기본 오류가 아닌 줄만 쓴다.

use std::fs;

use crate::handlers::{is_json_content_type, latin1};
use crate::jsonout::push_f64;
use crate::lax::{str_as_float, str_as_int};
use crate::pyjson::{self, LoadError};
use crate::router::{parse_host, unquote};

const DIR: &str = "../verify/data";
const INT_TEMPLATES: [&str; 6] = ["X", "X5", "5X", "5X0", "+X1", " X5"];
const FLOAT_TEMPLATES: [&str; 6] = ["X", "X1", "1X", "1X5", "1eX5", " X1"];

fn unhex(s: &str) -> Vec<u8> {
    (0..s.len())
        .step_by(2)
        .map(|i| u8::from_str_radix(&s[i..i + 2], 16).unwrap())
        .collect()
}

fn cps(values: impl IntoIterator<Item = u32>) -> String {
    let parts: Vec<String> = values.into_iter().map(|c| format!("{c:x}")).collect();
    parts.join(" ")
}

fn run(kind: &str, f: impl Fn(&[u8]) -> String) {
    let Ok(input) = fs::read_to_string(format!("{DIR}/{kind}.in")) else {
        return;
    };
    let mut out = String::new();
    for line in input.lines() {
        out.push_str(&f(&unhex(line)));
        out.push('\n');
    }
    fs::write(format!("{DIR}/{kind}.rust"), out).unwrap();
}

fn int_result(s: &str) -> String {
    match str_as_int(s) {
        Ok(v) => format!("ok {v}"),
        Err(e) => format!("err {e}"),
    }
}

fn float_result(s: &str) -> String {
    match str_as_float(s) {
        Ok(v) if v.is_nan() => "ok nan".into(),
        Ok(v) => format!("ok {:016x}", v.to_bits()),
        Err(e) => format!("err {e}"),
    }
}

fn sweep(kind: &str, templates: &[&str], default: &str, f: impl Fn(&str) -> String) {
    let mut out = String::new();
    for (ti, template) in templates.iter().enumerate() {
        for ch in (0..=0x10FFFFu32).filter_map(char::from_u32) {
            let result = f(&template.replace('X', &ch.to_string()));
            if result != default {
                out.push_str(&format!("{ti} {:x} {result}\n", ch as u32));
            }
        }
    }
    fs::write(format!("{DIR}/{kind}.rust"), out).unwrap();
}

#[test]
#[ignore]
fn dump_for_verify() {
    if fs::metadata(DIR).is_err() {
        return;
    }
    let text = |b: &[u8]| String::from_utf8(b.to_vec()).unwrap();
    run("intstr", |b| int_result(&text(b)));
    run("floatstr", |b| float_result(&text(b)));
    run("unquote", |b| cps(unquote(b).chars().map(u32::from)));
    run("jsondecode", |b| match pyjson::decode_bytes(b) {
        Some(v) => format!("ok {}", cps(v)),
        None => "err".into(),
    });
    run("jsonload", |b| match pyjson::loads(b) {
        Ok(_) => "ok".into(),
        Err(LoadError::Invalid(pos)) => format!("pos {pos}"),
        Err(LoadError::Other) => "other".into(),
    });
    run("ctype", |b| {
        u8::from(is_json_content_type(&latin1(b))).to_string()
    });
    run("host", |b| {
        parse_host(&latin1(b)).unwrap_or("<none>").to_string()
    });
    run("floatfmt", |b| {
        let mut out = String::new();
        push_f64(
            &mut out,
            f64::from_bits(u64::from_be_bytes(b.try_into().unwrap())),
        );
        out
    });
    sweep("intsweep", &INT_TEMPLATES, "err int_parsing", int_result);
    sweep(
        "floatsweep",
        &FLOAT_TEMPLATES,
        "err float_parsing",
        float_result,
    );
}
