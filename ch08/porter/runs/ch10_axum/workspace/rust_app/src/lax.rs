//! pydantic 2.14(pydantic-core 2.50) lax 변환: 입력값 → int / float / str.
//!
//! 정수 문자열 규칙은 컴파일된 pydantic-core 를 직접 읽지 못해 실측으로 정했다
//! (verify/int_model.py 가 같은 규칙의 Python 모형을 pydantic 과 무작위 비교한다).

use std::fmt;

use crate::pyjson::{self, Value};

/// 정수 자릿수 한도(pydantic-core 의 문자열→정수 크기 제한)
const MAX_INT_LEN: usize = 4300;

/// 임의 크기 정수. digits 는 앞의 0이 없는 10진 문자열("0" 포함), 0이면 neg 는 false
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PyInt {
    neg: bool,
    digits: String,
}

impl PyInt {
    pub fn new(neg: bool, digits: &str) -> PyInt {
        let digits = digits.trim_start_matches('0');
        if digits.is_empty() {
            return PyInt::from_i64(0);
        }
        PyInt {
            neg,
            digits: digits.to_string(),
        }
    }

    pub fn from_i64(value: i64) -> PyInt {
        PyInt {
            neg: value < 0,
            digits: value.unsigned_abs().to_string(),
        }
    }

    /// 범위 검사용 값. 30자리를 넘으면 ±10^30 으로 포화한다(제약은 모두 1e6 이하)
    pub fn saturating(&self) -> i128 {
        let magnitude: i128 = if self.digits.len() > 30 {
            10i128.pow(30)
        } else {
            self.digits.parse().unwrap_or(0)
        };
        if self.neg {
            -magnitude
        } else {
            magnitude
        }
    }
}

impl fmt::Display for PyInt {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        if self.neg {
            f.write_str("-")?;
        }
        f.write_str(&self.digits)
    }
}

pub type LaxResult<T> = Result<T, &'static str>;

enum JsonInt {
    Value(PyInt),
    Size,
    No,
}

/// JSON 정수 문법 `-?(0|[1-9][0-9]*)` 으로 앞에서부터 읽는다. '-' 포함 4300자를 넘으면 크기 오류
fn json_int(s: &str) -> JsonInt {
    let b = s.as_bytes();
    let mut i = usize::from(b.first() == Some(&b'-'));
    match b.get(i) {
        Some(b'0') => i += 1,
        Some(b'1'..=b'9') => {
            i += 1;
            while i < b.len() && b[i].is_ascii_digit() {
                i += 1;
                if i > MAX_INT_LEN {
                    return JsonInt::Size;
                }
            }
        }
        _ => return JsonInt::No,
    }
    if i != b.len() {
        return JsonInt::No;
    }
    match s.strip_prefix('-') {
        Some(digits) => JsonInt::Value(PyInt::new(true, digits)),
        None => JsonInt::Value(PyInt::new(false, s)),
    }
}

/// 부호 하나 → 앞의 0(과 그 사이 밑줄) → 밑줄 제거 → JSON 정수.
/// 앞의 0을 떼지 않았으면 부호 뒤에 다시 '-'가 올 수 없다
fn signed_zeros(u: &str) -> Option<PyInt> {
    let (neg, mut rest) = match u.as_bytes().first() {
        Some(b'-') => (true, &u[1..]),
        Some(b'+') => (false, &u[1..]),
        _ => (false, u),
    };
    if rest.starts_with('0') {
        if rest.ends_with('_') {
            return None;
        }
        rest = rest.trim_start_matches(['0', '_']);
        if rest.is_empty() {
            return Some(PyInt::from_i64(0));
        }
    } else if rest.starts_with('-') {
        return None;
    }
    let owned;
    if rest.contains('_') {
        if rest.starts_with('_') || rest.ends_with('_') || rest.contains("__") {
            return None;
        }
        owned = rest.replace('_', "");
        rest = &owned;
    }
    let text = if neg {
        format!("-{rest}")
    } else {
        rest.to_string()
    };
    match json_int(&text) {
        JsonInt::Value(value) => Some(value),
        _ => None,
    }
}

/// `5.000` 처럼 '.' 뒤가 모두 '0'(하나 이상)이면 앞부분
fn strip_decimal_zeros(s: &str) -> Option<&str> {
    let dot = s.rfind('.')?;
    let tail = &s[dot + 1..];
    (!tail.is_empty() && tail.bytes().all(|c| c == b'0')).then_some(&s[..dot])
}

pub fn str_as_int(s: &str) -> LaxResult<PyInt> {
    match json_int(s) {
        JsonInt::Value(value) => return Ok(value),
        JsonInt::Size => return Err("int_parsing_size"),
        JsonInt::No => {}
    }
    let t = s.trim();
    if let Some(value) = signed_zeros(t) {
        return Ok(value);
    }
    strip_decimal_zeros(t)
        .and_then(signed_zeros)
        .ok_or("int_parsing")
}

pub fn str_as_float(s: &str) -> LaxResult<f64> {
    if let Ok(value) = s.trim().parse::<f64>() {
        return Ok(value);
    }
    if s.starts_with('_') || s.ends_with('_') || s.contains("__") {
        return Err("float_parsing");
    }
    s.replace('_', "").parse().map_err(|_| "float_parsing")
}

fn float_as_int(value: f64) -> LaxResult<PyInt> {
    if !value.is_finite() {
        Err("finite_number")
    } else if value.fract() != 0.0 {
        Err("int_from_float")
    } else if (i64::MIN as f64) < value && value < (i64::MAX as f64) {
        Ok(PyInt::from_i64(value as i64))
    } else {
        Err("int_parsing_size")
    }
}

pub fn int_from_value(value: &Value) -> LaxResult<PyInt> {
    match value {
        Value::Int(text) => Ok(match text.strip_prefix('-') {
            Some(digits) => PyInt::new(true, digits),
            None => PyInt::new(false, text),
        }),
        Value::Bool(b) => Ok(PyInt::from_i64(i64::from(*b))),
        Value::Float(f) => float_as_int(*f),
        Value::Str(s) => str_as_int(&pyjson::to_string(s).ok_or("string_unicode")?),
        _ => Err("int_type"),
    }
}

pub fn float_from_value(value: &Value) -> LaxResult<f64> {
    match value {
        // Python float(int): 올바르게 반올림하고, 넘치면 OverflowError → float_type
        Value::Int(text) => match text.parse::<f64>() {
            Ok(f) if f.is_finite() => Ok(f),
            _ => Err("float_type"),
        },
        Value::Float(f) => Ok(*f),
        Value::Bool(b) => Ok(f64::from(u8::from(*b))),
        Value::Str(s) => str_as_float(&pyjson::to_string(s).ok_or("string_unicode")?),
        _ => Err("float_type"),
    }
}

pub fn str_from_value(value: &Value) -> LaxResult<String> {
    match value {
        Value::Str(s) => pyjson::to_string(s).ok_or("string_unicode"),
        _ => Err("string_type"),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn int(s: &str) -> String {
        match str_as_int(s) {
            Ok(v) => v.to_string(),
            Err(e) => e.to_string(),
        }
    }

    #[test]
    fn int_strings_match_pydantic() {
        let cases = [
            ("5", "5"),
            ("05", "5"),
            ("+1", "1"),
            ("-0", "0"),
            (" 5 ", "5"),
            ("5_0", "50"),
            ("5.0", "5"),
            ("5.", "int_parsing"),
            (".0", "int_parsing"),
            ("5__0", "int_parsing"),
            ("\u{a0}5", "5"),
            ("\u{1c}5", "int_parsing"),
            ("+-1", "int_parsing"),
            ("0-1", "-1"),
            ("+00-9", "-9"),
            ("-0-1", "int_parsing"),
            ("0__00", "0"),
            ("00_", "int_parsing"),
            ("1e1", "int_parsing"),
            ("\u{665}", "int_parsing"),
            ("", "int_parsing"),
            ("99999999999999999999", "99999999999999999999"),
            ("5.0_0", "int_parsing"),
            ("1_0.0", "10"),
        ];
        for (input, want) in cases {
            assert_eq!(int(input), want, "input {input:?}");
        }
        assert_eq!(int(&"1".repeat(4301)), "int_parsing_size");
        assert_eq!(int(&format!("+{}", "1".repeat(4301))), "int_parsing");
        assert_eq!(int(&"0".repeat(5000)), "0");
    }

    #[test]
    fn float_strings_match_pydantic() {
        assert_eq!(str_as_float(" 2 "), Ok(2.0));
        assert_eq!(str_as_float("1_0.5"), Ok(10.5));
        assert_eq!(str_as_float(" 1_0.5"), Err("float_parsing"));
        assert_eq!(str_as_float("1__0"), Err("float_parsing"));
        assert_eq!(str_as_float("0x1p3"), Err("float_parsing"));
        assert!(str_as_float("NAN").unwrap().is_nan());
        assert_eq!(str_as_float("-_1"), Ok(-1.0));
    }

    #[test]
    fn floats_to_int() {
        assert_eq!(float_as_int(3.0), Ok(PyInt::from_i64(3)));
        assert_eq!(float_as_int(3.5), Err("int_from_float"));
        assert_eq!(float_as_int(f64::NAN), Err("finite_number"));
        assert_eq!(float_as_int(2f64.powi(63)), Err("int_parsing_size"));
        assert_eq!(float_as_int(-2f64.powi(63)), Err("int_parsing_size"));
    }
}
