//! Python `json.loads`(C 스캐너)와 같은 것을 받고 거부하는 파서(port/rust_reference/src/json.rs 에서 가져옴).
//!
//! - 앞뒤 공백은 ` \t\n\r` 만, BOM 으로 시작하면 오류, 뒤에 남은 데이터가 있으면 오류
//! - `NaN`, `Infinity`, `-Infinity` 리터럴, 1e400 같은 넘침은 inf
//! - 문자열 안의 제어문자(< 0x20) 거부, 짝 없는 서로게이트 `\ud800` 은 그대로 남긴다(WTF-8 바이트로 보관)
//! - 4,300자리가 넘는 정수 리터럴과 9,997단계보다 깊은 중첩은 오류
//!
//! 최상위 객체의 멤버만 값으로 만들고, 그 안쪽 배열·객체는 명시적 스택으로 문법만 검사한다(재귀 없음).

/// Python 3.12.3 에서 측정한 중첩 한도(바깥 객체 포함). 계약 2.2절.
pub const MAX_DEPTH: usize = 9997;
/// `sys.get_int_max_str_digits()` 기본값.
pub const MAX_INT_DIGITS: usize = 4300;

#[derive(Debug, PartialEq, Eq)]
pub struct Invalid;

#[derive(Debug, Clone, PartialEq)]
pub enum Value {
    Null,
    Bool(bool),
    /// 정수. i64 범위를 넘으면 None(이 프로그램의 모든 범위 검사에서 범위 밖)
    Int(Option<i64>),
    Float(f64),
    /// WTF-8 바이트(짝 없는 서로게이트도 3바이트로 담는다)
    Str(Vec<u8>),
    /// 배열 또는 객체(내용은 쓰지 않는다)
    Container,
}

#[derive(Debug, PartialEq)]
pub enum Parsed {
    /// 멤버를 나온 순서대로 담는다. 같은 키는 뒤의 것이 이기므로 찾을 때 뒤에서부터 본다.
    Object(Vec<(Vec<u8>, Value)>),
    NotObject,
}

pub fn get<'a>(members: &'a [(Vec<u8>, Value)], key: &str) -> Option<&'a Value> {
    members
        .iter()
        .rev()
        .find(|(k, _)| k == key.as_bytes())
        .map(|(_, v)| v)
}

pub fn loads(text: &str) -> Result<Parsed, Invalid> {
    if text.starts_with('\u{feff}') {
        return Err(Invalid);
    }
    let mut p = Parser {
        b: text.as_bytes(),
        i: 0,
    };
    p.ws();
    let parsed = match p.peek() {
        Some(b'{') => Parsed::Object(p.top_object()?),
        Some(b'[') => {
            p.skip_container(0)?;
            Parsed::NotObject
        }
        _ => {
            p.scalar()?;
            Parsed::NotObject
        }
    };
    p.ws();
    if p.i != p.b.len() {
        return Err(Invalid);
    }
    Ok(parsed)
}

struct Parser<'a> {
    b: &'a [u8],
    i: usize,
}

fn push_wtf8(out: &mut Vec<u8>, cp: u32) {
    if cp < 0x80 {
        out.push(cp as u8);
    } else if cp < 0x800 {
        out.push(0xC0 | (cp >> 6) as u8);
        out.push(0x80 | (cp & 0x3F) as u8);
    } else if cp < 0x10000 {
        out.push(0xE0 | (cp >> 12) as u8);
        out.push(0x80 | ((cp >> 6) & 0x3F) as u8);
        out.push(0x80 | (cp & 0x3F) as u8);
    } else {
        out.push(0xF0 | (cp >> 18) as u8);
        out.push(0x80 | ((cp >> 12) & 0x3F) as u8);
        out.push(0x80 | ((cp >> 6) & 0x3F) as u8);
        out.push(0x80 | (cp & 0x3F) as u8);
    }
}

impl Parser<'_> {
    fn peek(&self) -> Option<u8> {
        self.b.get(self.i).copied()
    }

    fn ws(&mut self) {
        while matches!(self.peek(), Some(b' ' | b'\t' | b'\n' | b'\r')) {
            self.i += 1;
        }
    }

    fn expect(&mut self, c: u8) -> Result<(), Invalid> {
        if self.peek() != Some(c) {
            return Err(Invalid);
        }
        self.i += 1;
        Ok(())
    }

    fn digit_at(&self, i: usize) -> bool {
        matches!(self.b.get(i), Some(c) if c.is_ascii_digit())
    }

    fn top_object(&mut self) -> Result<Vec<(Vec<u8>, Value)>, Invalid> {
        let mut members = Vec::new();
        self.i += 1;
        self.ws();
        if self.peek() == Some(b'}') {
            self.i += 1;
            return Ok(members);
        }
        loop {
            let key = self.key()?;
            let value = match self.peek() {
                Some(b'{' | b'[') => {
                    self.skip_container(1)?;
                    Value::Container
                }
                _ => self.scalar()?,
            };
            members.push((key, value));
            self.ws();
            match self.peek() {
                Some(b'}') => {
                    self.i += 1;
                    return Ok(members);
                }
                Some(b',') => {
                    self.i += 1;
                    self.ws();
                }
                _ => return Err(Invalid),
            }
        }
    }

    /// `"키"` 공백 `:` 공백 까지 읽는다.
    fn key(&mut self) -> Result<Vec<u8>, Invalid> {
        if self.peek() != Some(b'"') {
            return Err(Invalid);
        }
        let key = self.string()?;
        self.ws();
        self.expect(b':')?;
        self.ws();
        Ok(key)
    }

    /// `{` 또는 `[` 에서 시작하는 값 하나를 끝까지 검사한다. `outer` 는 바깥 중첩 깊이.
    fn skip_container(&mut self, outer: usize) -> Result<(), Invalid> {
        let mut stack: Vec<u8> = Vec::new();
        loop {
            // 값 하나를 읽을 차례
            match self.peek() {
                Some(open @ (b'{' | b'[')) => {
                    if outer + stack.len() + 1 > MAX_DEPTH {
                        return Err(Invalid);
                    }
                    self.i += 1;
                    self.ws();
                    let close = if open == b'{' { b'}' } else { b']' };
                    if self.peek() == Some(close) {
                        self.i += 1;
                    } else {
                        stack.push(open);
                        if open == b'{' {
                            self.key()?;
                        }
                        continue;
                    }
                }
                _ => {
                    self.scalar()?;
                }
            }
            // 값 하나를 다 읽었다: 닫는 괄호 또는 쉼표
            loop {
                let Some(&top) = stack.last() else {
                    return Ok(());
                };
                self.ws();
                let close = if top == b'{' { b'}' } else { b']' };
                match self.peek() {
                    Some(c) if c == close => {
                        self.i += 1;
                        stack.pop();
                    }
                    Some(b',') => {
                        self.i += 1;
                        self.ws();
                        if top == b'{' {
                            self.key()?;
                        }
                        break;
                    }
                    _ => return Err(Invalid),
                }
            }
        }
    }

    fn literal(&mut self, word: &str, value: Value) -> Result<Value, Invalid> {
        if self.b[self.i..].starts_with(word.as_bytes()) {
            self.i += word.len();
            Ok(value)
        } else {
            Err(Invalid)
        }
    }

    fn scalar(&mut self) -> Result<Value, Invalid> {
        match self.peek() {
            Some(b'"') => Ok(Value::Str(self.string()?)),
            Some(b'n') => self.literal("null", Value::Null),
            Some(b't') => self.literal("true", Value::Bool(true)),
            Some(b'f') => self.literal("false", Value::Bool(false)),
            Some(b'N') => self.literal("NaN", Value::Float(f64::NAN)),
            Some(b'I') => self.literal("Infinity", Value::Float(f64::INFINITY)),
            Some(b'-') if self.b[self.i..].starts_with(b"-Infinity") => {
                self.literal("-Infinity", Value::Float(f64::NEG_INFINITY))
            }
            _ => self.number(),
        }
    }

    /// `-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][-+]?[0-9]+)?`
    fn number(&mut self) -> Result<Value, Invalid> {
        let start = self.i;
        let mut i = self.i;
        let negative = self.b.get(i) == Some(&b'-');
        if negative {
            i += 1;
        }
        match self.b.get(i) {
            Some(b'1'..=b'9') => {
                i += 1;
                while self.digit_at(i) {
                    i += 1;
                }
            }
            Some(b'0') => i += 1,
            _ => return Err(Invalid),
        }
        let int_end = i;
        let mut is_float = false;
        if self.b.get(i) == Some(&b'.') && self.digit_at(i + 1) {
            is_float = true;
            i += 2;
            while self.digit_at(i) {
                i += 1;
            }
        }
        if matches!(self.b.get(i), Some(b'e' | b'E')) {
            let e_start = i;
            i += 1;
            if matches!(self.b.get(i), Some(b'-' | b'+')) {
                i += 1;
            }
            let digits_start = i;
            while self.digit_at(i) {
                i += 1;
            }
            if i > digits_start {
                is_float = true;
            } else {
                // 지수가 아니다: 되돌린다(뒤에 남은 'e' 때문에 결국 오류가 된다)
                i = e_start;
            }
        }
        self.i = i;
        // 숫자 부분은 ASCII 라 문자열 경계가 맞다
        let s = std::str::from_utf8(&self.b[start..i]).map_err(|_| Invalid)?;
        if is_float {
            // Rust 의 parse 는 정확한 반올림이고 넘치면 inf 다(Python PyFloat_FromString 과 같음)
            return s.parse::<f64>().map(Value::Float).map_err(|_| Invalid);
        }
        let digits = int_end - start - usize::from(negative);
        if digits > MAX_INT_DIGITS {
            return Err(Invalid);
        }
        Ok(Value::Int(s.parse::<i64>().ok()))
    }

    fn hex4(&self, at: usize) -> Result<u32, Invalid> {
        let h = self.b.get(at..at + 4).ok_or(Invalid)?;
        let mut v = 0u32;
        for &c in h {
            let d = (c as char).to_digit(16).ok_or(Invalid)?;
            v = v * 16 + d;
        }
        Ok(v)
    }

    /// 여는 `"` 에서 시작해 닫는 `"` 뒤까지 읽는다.
    fn string(&mut self) -> Result<Vec<u8>, Invalid> {
        let mut out = Vec::new();
        self.i += 1;
        loop {
            let c = self.peek().ok_or(Invalid)?;
            match c {
                b'"' => {
                    self.i += 1;
                    return Ok(out);
                }
                b'\\' => {
                    self.i += 1;
                    let e = self.peek().ok_or(Invalid)?;
                    self.i += 1;
                    match e {
                        b'"' | b'\\' | b'/' => out.push(e),
                        b'b' => out.push(0x08),
                        b'f' => out.push(0x0C),
                        b'n' => out.push(b'\n'),
                        b'r' => out.push(b'\r'),
                        b't' => out.push(b'\t'),
                        b'u' => {
                            let mut cp = self.hex4(self.i)?;
                            self.i += 4;
                            if (0xD800..=0xDBFF).contains(&cp)
                                && self.b[self.i..].starts_with(b"\\u")
                            {
                                let low = self.hex4(self.i + 2)?;
                                if (0xDC00..=0xDFFF).contains(&low) {
                                    cp = 0x10000 + ((cp - 0xD800) << 10) + (low - 0xDC00);
                                    self.i += 6;
                                }
                            }
                            push_wtf8(&mut out, cp);
                        }
                        _ => return Err(Invalid),
                    }
                }
                0x00..=0x1F => return Err(Invalid),
                _ => {
                    out.push(c);
                    self.i += 1;
                }
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn value(s: &str) -> Value {
        match loads(&format!("{{\"k\":{s}}}")) {
            Ok(Parsed::Object(m)) => m[0].1.clone(),
            other => panic!("{s}: {other:?}"),
        }
    }

    #[test]
    fn numbers() {
        assert_eq!(value("-0"), Value::Int(Some(0)));
        assert_eq!(value("1e400"), Value::Float(f64::INFINITY));
        assert_eq!(value("99999999999999999999"), Value::Int(None));
        assert!(loads(&format!("{{\"k\":{}}}", "1".repeat(4301))).is_err());
        for bad in ["01", "1.", ".5", "-", "+1", "-NaN", "1e", "1.e5", "nul"] {
            assert!(loads(&format!("{{\"k\":{bad}}}")).is_err(), "{bad}");
        }
    }

    #[test]
    fn strings_and_structure() {
        assert_eq!(value(r#""\ud800""#), Value::Str(vec![0xED, 0xA0, 0x80]));
        assert!(loads("{\"k\":\"a\u{1}\"}").is_err());
        assert_eq!(loads(" [1, {\"a\": []}] \r"), Ok(Parsed::NotObject));
        assert!(loads("\u{feff}{}").is_err());
        assert!(loads("{} x").is_err());
        let Ok(Parsed::Object(m)) = loads(r#"{"a":1,"a":2}"#) else {
            panic!()
        };
        assert_eq!(get(&m, "a"), Some(&Value::Int(Some(2))));
    }

    #[test]
    fn depth_limit() {
        for (depth, ok) in [(9997, true), (9998, false)] {
            let obj = format!("{}1{}", "{\"a\":".repeat(depth), "}".repeat(depth));
            assert_eq!(loads(&obj).is_ok(), ok);
        }
    }
}
