//! order.py(03-1 주문 합계 계산)를 같은 동작으로 옮긴 Rust 구현.

use std::env;
use std::fs;
use std::io::{self, Write};
use std::path::PathBuf;
use std::process::ExitCode;

use serde_json::{Number, Value};

/// Python의 print는 Windows에서 "\n"을 "\r\n"으로 바꿔 쓴다.
#[cfg(windows)]
const NEWLINE: &str = "\r\n";
#[cfg(not(windows))]
const NEWLINE: &str = "\n";

#[derive(Debug, Clone, Copy)]
struct Item {
    price: i128, // 원 단위 정수
    qty: i128,
}

#[derive(Debug, Clone, Copy)]
enum Coupon {
    Fixed(i128),   // 원
    Percent(i128), // 0~100
}

#[derive(Debug)]
struct Order {
    items: Vec<Item>,
    coupon: Option<Coupon>,
}

/// 실패를 order.py에서 어떻게 끝나는지에 따라 나눈다. 종료 코드는 모두 1.
enum Failure {
    /// main의 except가 잡아 `order: error: ...`로 보고하는 경우
    Caught(String),
    /// order.py에서는 잡히지 않고 트레이스백으로 끝나는 경우
    Uncaught(String),
    /// Python의 무제한 정수와 달리 i128 범위를 넘은 경우
    Unsupported(String),
}

impl Failure {
    fn message(&self) -> String {
        match self {
            Failure::Caught(msg) | Failure::Unsupported(msg) => format!("order: error: {msg}"),
            Failure::Uncaught(msg) => msg.clone(),
        }
    }
}

fn out_of_range() -> Failure {
    Failure::Unsupported("integer out of supported range (i128)".to_string())
}

/// Python json은 '.', 'e', 'E'가 있는 수를 float로, 나머지를 int로 읽는다.
fn is_float_literal(n: &Number) -> bool {
    n.to_string().contains(|c| matches!(c, '.' | 'e' | 'E'))
}

/// float 리터럴의 값. Python처럼 범위를 넘으면 inf가 된다.
fn float_value(n: &Number) -> f64 {
    n.to_string().parse().expect("serde_json이 검사한 수 리터럴")
}

fn py_type_name(value: &Value) -> &'static str {
    match value {
        Value::Null => "NoneType",
        Value::Bool(_) => "bool",
        Value::Number(n) if is_float_literal(n) => "float",
        Value::Number(_) => "int",
        Value::String(_) => "str",
        Value::Array(_) => "list",
        Value::Object(_) => "dict",
    }
}

/// Python `container[key]` (key는 str).
fn subscript<'a>(container: &'a Value, key: &str) -> Result<&'a Value, Failure> {
    match container {
        Value::Object(map) => map.get(key).ok_or_else(|| Failure::Caught(py_repr_str(key))),
        Value::Array(_) => Err(Failure::Caught(
            "list indices must be integers or slices, not str".to_string(),
        )),
        Value::String(_) => Err(Failure::Caught(
            "string indices must be integers, not 'str'".to_string(),
        )),
        other => Err(Failure::Caught(format!(
            "'{}' object is not subscriptable",
            py_type_name(other)
        ))),
    }
}

/// Python `for x in value`. dict는 키를, str은 글자를 하나씩 돈다.
fn iterate(value: &Value) -> Result<Vec<Value>, Failure> {
    match value {
        Value::Array(items) => Ok(items.clone()),
        Value::Object(map) => Ok(map.keys().map(|k| Value::String(k.clone())).collect()),
        Value::String(s) => Ok(s.chars().map(|c| Value::String(c.to_string())).collect()),
        other => Err(Failure::Caught(format!(
            "'{}' object is not iterable",
            py_type_name(other)
        ))),
    }
}

/// Python `int(value)`. JSON에서 나올 수 있는 값만 다룬다.
fn py_int(value: &Value) -> Result<i128, Failure> {
    match value {
        Value::Bool(b) => Ok(i128::from(*b)),
        Value::Number(n) if is_float_literal(n) => float_to_int(float_value(n)),
        Value::Number(n) => n.to_string().parse().map_err(|_| out_of_range()),
        Value::String(s) => str_to_int(s),
        other => Err(Failure::Caught(format!(
            "int() argument must be a string, a bytes-like object or a real number, not '{}'",
            py_type_name(other)
        ))),
    }
}

/// int(float): 0 쪽으로 버린다. serde_json은 NaN을 만들지 않으므로 inf만 따로 본다.
fn float_to_int(f: f64) -> Result<i128, Failure> {
    if f.is_infinite() {
        return Err(Failure::Uncaught(
            "OverflowError: cannot convert float infinity to integer".to_string(),
        ));
    }
    let t = f.trunc();
    if t >= i128::MAX as f64 || t < i128::MIN as f64 {
        return Err(out_of_range());
    }
    Ok(t as i128)
}

/// Python 공백(str.isspace). Rust의 is_whitespace에 \x1c~\x1f가 더해진다.
fn is_py_space(c: char) -> bool {
    c.is_whitespace() || ('\x1c'..='\x1f').contains(&c)
}

/// int(str): 앞뒤 공백, 부호, 숫자 사이의 밑줄 하나("1_000")를 허용한다.
fn str_to_int(s: &str) -> Result<i128, Failure> {
    let body = s.trim_matches(is_py_space);
    let (negative, digits) = match body.as_bytes().first() {
        Some(b'-') => (true, &body[1..]),
        Some(b'+') => (false, &body[1..]),
        _ => (false, body),
    };
    let well_formed = digits
        .split('_')
        .all(|group| !group.is_empty() && group.bytes().all(|b| b.is_ascii_digit()));
    if !well_formed {
        return Err(Failure::Caught(format!(
            "invalid literal for int() with base 10: {}",
            py_repr_str(s)
        )));
    }
    let mut n: i128 = 0;
    for b in digits.bytes().filter(|b| *b != b'_') {
        let d = i128::from(b - b'0');
        n = n
            .checked_mul(10)
            .and_then(|n| if negative { n.checked_sub(d) } else { n.checked_add(d) })
            .ok_or_else(out_of_range)?;
    }
    Ok(n)
}

fn parse_coupon(raw: Option<&Value>) -> Result<Option<Coupon>, Failure> {
    match raw {
        None | Some(Value::Null) => return Ok(None),
        Some(Value::Number(n)) if !is_float_literal(n) => {
            let literal = n.to_string();
            if !literal.starts_with('-') || literal == "-0" {
                // i128을 넘는 쿠폰은 어떤 소계든 0 아래로 내리므로 MAX로 대신해도 합계가 같다
                return Ok(Some(Coupon::Fixed(literal.parse().unwrap_or(i128::MAX))));
            }
        }
        Some(Value::String(s)) => {
            if let Some(digits) = s.strip_suffix('%') {
                if !digits.is_empty() && digits.bytes().all(|b| b.is_ascii_digit()) {
                    let significant = digits.trim_start_matches('0');
                    if significant.len() <= 3 {
                        let percent: i128 = significant.parse().unwrap_or(0);
                        if percent <= 100 {
                            return Ok(Some(Coupon::Percent(percent)));
                        }
                    }
                }
            }
        }
        _ => {}
    }
    let repr = raw.map_or_else(|| "None".to_string(), py_repr);
    Err(Failure::Caught(format!("invalid coupon: {repr}")))
}

/// JSON 문자열 → Order. 파일을 읽지 않는 순수 함수.
fn parse_order(text: &str) -> Result<Order, Failure> {
    let data: Value =
        serde_json::from_str(text).map_err(|err| Failure::Caught(err.to_string()))?;
    let mut items = Vec::new();
    for it in iterate(subscript(&data, "items")?)? {
        let price = py_int(subscript(&it, "price")?)?;
        // it["price"]가 통과했으니 it은 dict다
        let qty = match it.get("qty") {
            Some(raw) => py_int(raw)?,
            None => 1,
        };
        items.push(Item { price, qty });
    }
    let coupon = parse_coupon(data.get("coupon"))?;
    Ok(Order { items, coupon })
}

/// 할인 적용 합계(원). 퍼센트 할인은 원 단위 미만을 버린다. 0 아래로 내려가지 않는다.
fn total(order: &Order) -> Result<i128, Failure> {
    let mut subtotal: i128 = 0;
    for item in &order.items {
        subtotal = item
            .price
            .checked_mul(item.qty)
            .and_then(|line| subtotal.checked_add(line))
            .ok_or_else(out_of_range)?;
    }
    let discounted = match order.coupon {
        None => subtotal,
        // 넘침은 음수 쪽에서만 일어나고, 그 값은 어차피 0으로 잘린다
        Some(Coupon::Fixed(amount)) => subtotal.saturating_sub(amount),
        Some(Coupon::Percent(percent)) => percent_off(subtotal, percent),
    };
    Ok(discounted.max(0))
}

/// subtotal * (100 - percent) // 100을 곱셈 넘침 없이 계산한다.
/// 결과가 0 이하인 경우는 0을 돌려준다(어차피 0으로 잘린다).
fn percent_off(subtotal: i128, percent: i128) -> i128 {
    if subtotal <= 0 {
        return 0;
    }
    let keep = 100 - percent;
    subtotal / 100 * keep + subtotal % 100 * keep / 100
}

/// Python repr(). 쿠폰 오류 메시지에 쓴다.
fn py_repr(value: &Value) -> String {
    match value {
        Value::Null => "None".to_string(),
        Value::Bool(true) => "True".to_string(),
        Value::Bool(false) => "False".to_string(),
        Value::Number(n) if is_float_literal(n) => py_float_repr(float_value(n)),
        Value::Number(n) => {
            let literal = n.to_string();
            if literal == "-0" {
                "0".to_string()
            } else {
                literal
            }
        }
        Value::String(s) => py_repr_str(s),
        Value::Array(items) => {
            let parts: Vec<String> = items.iter().map(py_repr).collect();
            format!("[{}]", parts.join(", "))
        }
        Value::Object(map) => {
            let parts: Vec<String> = map
                .iter()
                .map(|(k, v)| format!("{}: {}", py_repr_str(k), py_repr(v)))
                .collect();
            format!("{{{}}}", parts.join(", "))
        }
    }
}

/// Python repr(float): 가장 짧은 왕복 자릿수. 10진 지수가 -4 미만이거나 16 이상이면 지수 표기.
fn py_float_repr(f: f64) -> String {
    if f.is_infinite() {
        return if f > 0.0 { "inf" } else { "-inf" }.to_string();
    }
    let sci = format!("{f:e}"); // 예: "-1.5e-7"
    let (mantissa, exp) = sci.split_once('e').expect("{:e} 출력에는 e가 있다");
    let exp: i32 = exp.parse().expect("{:e} 출력의 지수");
    let (sign, mantissa) = match mantissa.strip_prefix('-') {
        Some(m) => ("-", m),
        None => ("", mantissa),
    };
    let digits: String = mantissa.chars().filter(|c| *c != '.').collect();
    let body = if exp < -4 || exp >= 16 {
        let (first, rest) = digits.split_at(1);
        let rest = if rest.is_empty() { String::new() } else { format!(".{rest}") };
        let exp_sign = if exp < 0 { '-' } else { '+' };
        format!("{first}{rest}e{exp_sign}{:02}", exp.abs())
    } else if exp < 0 {
        format!("0.{}{digits}", "0".repeat((-exp - 1) as usize))
    } else {
        let point = exp as usize + 1;
        if digits.len() <= point {
            format!("{digits}{}.0", "0".repeat(point - digits.len()))
        } else {
            format!("{}.{}", &digits[..point], &digits[point..])
        }
    };
    format!("{sign}{body}")
}

/// Python repr(str): 작은따옴표를 쓰되, '만 있고 "가 없으면 큰따옴표를 쓴다.
fn py_repr_str(s: &str) -> String {
    let quote = if s.contains('\'') && !s.contains('"') { '"' } else { '\'' };
    let mut out = String::with_capacity(s.len() + 2);
    out.push(quote);
    for c in s.chars() {
        match c {
            '\\' => out.push_str("\\\\"),
            '\t' => out.push_str("\\t"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            c if c == quote => {
                out.push('\\');
                out.push(c);
            }
            c if is_py_printable(c) => out.push(c),
            c if (c as u32) <= 0xff => out.push_str(&format!("\\x{:02x}", c as u32)),
            c if (c as u32) <= 0xffff => out.push_str(&format!("\\u{:04x}", c as u32)),
            c => out.push_str(&format!("\\U{:08x}", c as u32)),
        }
    }
    out.push(quote);
    out
}

/// str.isprintable의 근사. 유니코드 미할당 문자(Cn)는 구분하지 못한다.
fn is_py_printable(c: char) -> bool {
    if c == ' ' {
        return true;
    }
    if c.is_control() || c.is_whitespace() {
        return false;
    }
    // 서식 문자(Cf)와 사용자 정의 영역(Co)
    !matches!(
        c as u32,
        0x00AD
            | 0x0600..=0x0605
            | 0x061C
            | 0x06DD
            | 0x070F
            | 0x180E
            | 0x200B..=0x200F
            | 0x202A..=0x202E
            | 0x2060..=0x2064
            | 0x2066..=0x206F
            | 0xFEFF
            | 0xFFF9..=0xFFFB
            | 0xE0001
            | 0xE0020..=0xE007F
            | 0xE000..=0xF8FF
            | 0xF0000..=0xFFFFD
            | 0x100000..=0x10FFFD
    )
}

fn report(line: &str) {
    let _ = write!(io::stderr(), "{line}{NEWLINE}");
}

/// 입출력은 여기서만 한다.
fn main() -> ExitCode {
    // order.py는 첫 인자만 쓰고 나머지는 무시한다
    let Some(path) = env::args_os().nth(1).map(PathBuf::from) else {
        report("IndexError: list index out of range");
        return ExitCode::from(1);
    };
    let text = match fs::read_to_string(&path) {
        Ok(text) => text,
        Err(err) => {
            report(&Failure::Uncaught(format!("{}: {err}", path.display())).message());
            return ExitCode::from(1);
        }
    };
    match parse_order(&text).and_then(|order| total(&order)) {
        Ok(sum) => {
            let _ = write!(io::stdout(), "{sum}{NEWLINE}");
            ExitCode::SUCCESS
        }
        Err(failure) => {
            report(&failure.message());
            ExitCode::from(1)
        }
    }
}
