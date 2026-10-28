//! order.py의 Rust 이식: 주문 JSON 파일을 읽어 합계를 Python과 같은 형식으로 출력한다.

use serde_json::Value;
use std::process::ExitCode;

// Python의 print는 Windows에서 "\n"을 "\r\n"으로 바꿔 쓴다.
const LINE_END: &str = if cfg!(windows) { "\r\n" } else { "\n" };

/// Python의 int/float 구분을 흉내 낸 숫자. 정수끼리의 연산은 정수로 남는다.
#[derive(Clone, Copy)]
enum Num {
    Int(i128),
    Float(f64),
}

impl Num {
    fn to_f64(self) -> f64 {
        match self {
            Num::Int(i) => i as f64,
            Num::Float(f) => f,
        }
    }
}

fn overflow() -> String {
    "정수 연산이 i128 범위를 넘었습니다".to_string()
}

fn arith(
    a: Num,
    b: Num,
    int_op: fn(i128, i128) -> Option<i128>,
    float_op: fn(f64, f64) -> f64,
) -> Result<Num, String> {
    match (a, b) {
        (Num::Int(x), Num::Int(y)) => int_op(x, y).map(Num::Int).ok_or_else(overflow),
        _ => Ok(Num::Float(float_op(a.to_f64(), b.to_f64()))),
    }
}

/// Python에서 bool은 int이므로 true/false도 1/0으로 계산에 쓰인다.
fn as_num(v: &Value) -> Option<Num> {
    match v {
        Value::Bool(b) => Some(Num::Int(*b as i128)),
        Value::Number(n) => Some(if let Some(i) = n.as_i64() {
            Num::Int(i as i128)
        } else if let Some(u) = n.as_u64() {
            Num::Int(u as i128)
        } else {
            Num::Float(n.as_f64()?)
        }),
        _ => None,
    }
}

/// Python의 truthiness: None, False, 0, 0.0, "", [], {}만 거짓이다.
fn truthy(v: &Value) -> bool {
    match v {
        Value::Null => false,
        Value::Bool(b) => *b,
        Value::Number(_) => match as_num(v) {
            Some(Num::Int(i)) => i != 0,
            Some(Num::Float(f)) => f != 0.0,
            None => true,
        },
        Value::String(s) => !s.is_empty(),
        Value::Array(a) => !a.is_empty(),
        Value::Object(o) => !o.is_empty(),
    }
}

/// Python int(str)의 10진 규칙: 앞뒤 공백, 부호, 숫자 사이의 밑줄 하나를 허용한다.
fn parse_py_int(text: &str) -> Option<i128> {
    let t = text.trim();
    let (neg, digits) = match t.as_bytes().first() {
        Some(b'-') => (true, &t[1..]),
        Some(b'+') => (false, &t[1..]),
        _ => (false, t),
    };
    if digits.is_empty() || digits.starts_with('_') || digits.ends_with('_') || digits.contains("__")
    {
        return None;
    }
    let mut n: i128 = 0;
    for ch in digits.chars().filter(|&c| c != '_') {
        let d = ch.to_digit(10)?;
        n = n.checked_mul(10)?.checked_add(d as i128)?;
    }
    Some(if neg { -n } else { n })
}

fn total(order: &Value) -> Result<Option<Num>, String> {
    let order = order.as_object().ok_or("주문이 JSON 객체가 아닙니다")?;
    let items = order.get("items").ok_or("주문에 'items' 키가 없습니다")?;
    if !truthy(items) {
        return Ok(None);
    }
    let items = items.as_array().ok_or("'items'가 배열이 아닙니다")?;
    let mut s = Num::Int(0);
    for it in items {
        let it = it.as_object().ok_or("항목이 JSON 객체가 아닙니다")?;
        let price = it.get("price").ok_or("항목에 'price' 키가 없습니다")?;
        let price = as_num(price).ok_or("'price'가 숫자가 아닙니다")?;
        let qty = match it.get("qty") {
            None => Num::Int(1),
            Some(q) => as_num(q).ok_or("'qty'가 숫자가 아닙니다")?,
        };
        let line = arith(price, qty, i128::checked_mul, |x, y| x * y)?;
        s = arith(s, line, i128::checked_add, |x, y| x + y)?;
    }
    let c = order.get("coupon").unwrap_or(&Value::Null);
    match c {
        Value::String(text) if text.ends_with('%') => {
            let pct = parse_py_int(&text[..text.len() - 1])
                .ok_or_else(|| format!("쿠폰 할인율을 정수로 읽을 수 없습니다: {text:?}"))?;
            let factor = 100i128.checked_sub(pct).ok_or_else(overflow)?;
            // Python의 `/`는 항상 float를 만든다.
            s = Num::Float(match s {
                Num::Int(x) => x.checked_mul(factor).ok_or_else(overflow)? as f64 / 100.0,
                Num::Float(x) => x * factor as f64 / 100.0,
            });
        }
        _ if truthy(c) => {
            let amount = as_num(c).ok_or("쿠폰 금액이 숫자가 아닙니다")?;
            s = arith(s, amount, i128::checked_sub, |x, y| x - y)?;
        }
        _ => {}
    }
    Ok(Some(s))
}

/// Python repr(float)와 같은 문자열: 최단 왕복 자릿수, 지수가 -4 이상 16 미만이면 고정소수점.
fn py_float_repr(x: f64) -> String {
    if x.is_nan() {
        return "nan".to_string();
    }
    if x.is_infinite() {
        return if x > 0.0 { "inf" } else { "-inf" }.to_string();
    }
    let sci = format!("{:e}", x.abs());
    let (mantissa, exp) = sci.split_once('e').expect("LowerExp 출력에는 'e'가 있다");
    let exp: i32 = exp.parse().expect("LowerExp 지수는 정수다");
    let digits: String = mantissa.chars().filter(|&c| c != '.').collect();
    let sign = if x.is_sign_negative() { "-" } else { "" };
    let body = if (-4..16).contains(&exp) {
        if exp < 0 {
            format!("0.{}{}", "0".repeat((-exp - 1) as usize), digits)
        } else {
            let point = exp as usize + 1;
            if digits.len() <= point {
                format!("{}{}.0", digits, "0".repeat(point - digits.len()))
            } else {
                format!("{}.{}", &digits[..point], &digits[point..])
            }
        }
    } else {
        let mant = if digits.len() > 1 {
            format!("{}.{}", &digits[..1], &digits[1..])
        } else {
            digits
        };
        format!("{}e{}{:02}", mant, if exp < 0 { '-' } else { '+' }, exp.abs())
    };
    format!("{sign}{body}")
}

fn run() -> Result<String, String> {
    let path = std::env::args_os().nth(1).ok_or("사용법: order <주문.json>")?;
    let text = std::fs::read_to_string(&path)
        .map_err(|e| format!("{}: {e}", path.to_string_lossy()))?;
    let order: Value = serde_json::from_str(&text).map_err(|e| format!("JSON 파싱 실패: {e}"))?;
    Ok(match total(&order)? {
        None => "None".to_string(),
        Some(Num::Int(i)) => i.to_string(),
        Some(Num::Float(f)) => py_float_repr(f),
    })
}

fn main() -> ExitCode {
    match run() {
        Ok(out) => {
            print!("{out}{LINE_END}");
            ExitCode::SUCCESS
        }
        Err(msg) => {
            eprintln!("error: {msg}");
            ExitCode::FAILURE
        }
    }
}
