//! Python `json.loads(bytes)` 호환 해석기.
//!
//! - `json.detect_encoding` 과 `surrogatepass` 디코딩을 그대로 옮긴다(실패하면 400).
//! - CPython `_json.c` 스캐너와 같은 문법: NaN/Infinity, 문자열 안 제어문자 거부, 중복 키는 첫 위치에 뒤 값.
//! - 오류 위치는 코드 포인트 단위(`JSONDecodeError.pos`).

/// 문자열은 코드 포인트 배열로 든다(고립 서로게이트를 담기 위해).
pub type PyStr = Vec<u32>;

#[derive(Debug, Clone, PartialEq)]
pub enum Value {
    Null,
    Bool(bool),
    /// JSON 정수 토큰 텍스트(`-?(0|[1-9][0-9]*)`)
    Int(String),
    Float(f64),
    Str(PyStr),
    Array(Vec<Value>),
    Object(Vec<(PyStr, Value)>),
}

#[derive(Debug, PartialEq)]
pub enum LoadError {
    /// `JSONDecodeError` → 422 json_invalid, loc ["body", pos]
    Invalid(usize),
    /// 그 밖의 예외(UnicodeDecodeError, RecursionError, 정수 자릿수 초과) → 400
    Other,
}

/// CPython 3.12 의 정수 문자열 변환 한도(sys.int_info.default_max_str_digits)
const MAX_INT_DIGITS: usize = 4300;
/// 기준 서버에서 실측한 중첩 한도(verify/probe_depth.py). 더 깊으면 RecursionError → 400
pub const MAX_DEPTH: usize = 9993;

pub fn to_string(s: &[u32]) -> Option<String> {
    s.iter().map(|&c| char::from_u32(c)).collect()
}

pub fn loads(bytes: &[u8]) -> Result<Value, LoadError> {
    let text = decode_bytes(bytes).ok_or(LoadError::Other)?;
    let mut parser = Parser { s: &text, depth: 0 };
    let start = parser.skip_ws(0);
    let (value, end) = match parser.scan_once(start) {
        Ok(found) => found,
        Err(Fail::Stop(pos)) | Err(Fail::Msg(pos)) => return Err(LoadError::Invalid(pos)),
        Err(Fail::Fatal) => return Err(LoadError::Other),
    };
    let end = parser.skip_ws(end);
    if end != text.len() {
        return Err(LoadError::Invalid(end));
    }
    Ok(value)
}

// ---- json.detect_encoding + bytes.decode(encoding, "surrogatepass") ----

pub(crate) fn decode_bytes(b: &[u8]) -> Option<Vec<u32>> {
    if b.starts_with(&[0, 0, 0xFE, 0xFF]) {
        return decode_utf32(&b[4..], true);
    }
    if b.starts_with(&[0xFF, 0xFE, 0, 0]) {
        return decode_utf32(&b[4..], false);
    }
    if b.starts_with(&[0xFE, 0xFF]) {
        return decode_utf16(&b[2..], true);
    }
    if b.starts_with(&[0xFF, 0xFE]) {
        return decode_utf16(&b[2..], false);
    }
    if b.starts_with(&[0xEF, 0xBB, 0xBF]) {
        return decode_utf8(&b[3..]);
    }
    if b.len() >= 4 {
        if b[0] == 0 {
            return if b[1] != 0 {
                decode_utf16(b, true)
            } else {
                decode_utf32(b, true)
            };
        }
        if b[1] == 0 {
            return if b[2] != 0 || b[3] != 0 {
                decode_utf16(b, false)
            } else {
                decode_utf32(b, false)
            };
        }
    } else if b.len() == 2 {
        if b[0] == 0 {
            return decode_utf16(b, true);
        }
        if b[1] == 0 {
            return decode_utf16(b, false);
        }
    }
    decode_utf8(b)
}

/// UTF-8 strict + surrogatepass(ED A0..BF 80..BF 를 서로게이트로 받는다)
fn decode_utf8(b: &[u8]) -> Option<Vec<u32>> {
    let mut out = Vec::with_capacity(b.len());
    let mut i = 0;
    let cont = |i: usize| b.get(i).copied().filter(|c| (0x80..=0xBF).contains(c));
    while i < b.len() {
        let c = b[i];
        if c < 0x80 {
            out.push(c as u32);
            i += 1;
        } else if (0xC2..=0xDF).contains(&c) {
            let c1 = cont(i + 1)?;
            out.push(((c as u32 & 0x1F) << 6) | (c1 as u32 & 0x3F));
            i += 2;
        } else if (0xE0..=0xEF).contains(&c) {
            let c1 = cont(i + 1)?;
            let c2 = cont(i + 2)?;
            if c == 0xE0 && c1 < 0xA0 {
                return None;
            }
            out.push(((c as u32 & 0x0F) << 12) | ((c1 as u32 & 0x3F) << 6) | (c2 as u32 & 0x3F));
            i += 3;
        } else if (0xF0..=0xF4).contains(&c) {
            let c1 = cont(i + 1)?;
            if (c == 0xF0 && c1 < 0x90) || (c == 0xF4 && c1 > 0x8F) {
                return None;
            }
            let c2 = cont(i + 2)?;
            let c3 = cont(i + 3)?;
            out.push(
                ((c as u32 & 0x07) << 18)
                    | ((c1 as u32 & 0x3F) << 12)
                    | ((c2 as u32 & 0x3F) << 6)
                    | (c3 as u32 & 0x3F),
            );
            i += 4;
        } else {
            return None;
        }
    }
    Some(out)
}

fn decode_utf16(b: &[u8], big_endian: bool) -> Option<Vec<u32>> {
    let (pairs, rest) = b.as_chunks::<2>();
    if !rest.is_empty() {
        return None;
    }
    let units: Vec<u32> = pairs
        .iter()
        .map(|&p| {
            if big_endian {
                u16::from_be_bytes(p) as u32
            } else {
                u16::from_le_bytes(p) as u32
            }
        })
        .collect();
    let mut out = Vec::with_capacity(units.len());
    let mut i = 0;
    while i < units.len() {
        let u = units[i];
        if (0xD800..0xDC00).contains(&u) {
            if let Some(&low) = units.get(i + 1) {
                if (0xDC00..0xE000).contains(&low) {
                    out.push(0x10000 + ((u - 0xD800) << 10) + (low - 0xDC00));
                    i += 2;
                    continue;
                }
            }
        }
        out.push(u);
        i += 1;
    }
    Some(out)
}

fn decode_utf32(b: &[u8], big_endian: bool) -> Option<Vec<u32>> {
    let (quads, rest) = b.as_chunks::<4>();
    if !rest.is_empty() {
        return None;
    }
    quads
        .iter()
        .map(|&p| {
            let c = if big_endian {
                u32::from_be_bytes(p)
            } else {
                u32::from_le_bytes(p)
            };
            (c < 0x110000).then_some(c)
        })
        .collect()
}

// ---- _json.c scan_once_unicode ----

enum Fail {
    /// StopIteration(idx) → "Expecting value" at idx
    Stop(usize),
    /// raise_errmsg(..., idx)
    Msg(usize),
    Fatal,
}

struct Parser<'a> {
    s: &'a [u32],
    depth: usize,
}

fn is_ws(c: u32) -> bool {
    c == 0x20 || c == 0x09 || c == 0x0A || c == 0x0D
}

fn is_digit(c: u32) -> bool {
    (0x30..=0x39).contains(&c)
}

impl Parser<'_> {
    fn at(&self, i: usize) -> Option<u32> {
        self.s.get(i).copied()
    }

    fn skip_ws(&self, mut i: usize) -> usize {
        while self.at(i).is_some_and(is_ws) {
            i += 1;
        }
        i
    }

    fn matches(&self, i: usize, word: &str) -> bool {
        word.chars()
            .enumerate()
            .all(|(k, ch)| self.at(i + k) == Some(ch as u32))
    }

    fn scan_once(&mut self, idx: usize) -> Result<(Value, usize), Fail> {
        let Some(c) = self.at(idx) else {
            return Err(Fail::Stop(idx));
        };
        match char::from_u32(c) {
            Some('"') => {
                let (s, end) = self.scan_string(idx + 1)?;
                return Ok((Value::Str(s), end));
            }
            Some('{') => return self.nested(idx, true),
            Some('[') => return self.nested(idx, false),
            Some('n') if self.matches(idx, "null") => return Ok((Value::Null, idx + 4)),
            Some('t') if self.matches(idx, "true") => return Ok((Value::Bool(true), idx + 4)),
            Some('f') if self.matches(idx, "false") => return Ok((Value::Bool(false), idx + 5)),
            Some('N') if self.matches(idx, "NaN") => return Ok((Value::Float(f64::NAN), idx + 3)),
            Some('I') if self.matches(idx, "Infinity") => {
                return Ok((Value::Float(f64::INFINITY), idx + 8))
            }
            Some('-') if self.matches(idx, "-Infinity") => {
                return Ok((Value::Float(f64::NEG_INFINITY), idx + 9))
            }
            _ => {}
        }
        self.match_number(idx)
    }

    fn nested(&mut self, idx: usize, object: bool) -> Result<(Value, usize), Fail> {
        if self.depth >= MAX_DEPTH {
            return Err(Fail::Fatal);
        }
        self.depth += 1;
        let result = if object {
            self.parse_object(idx + 1)
        } else {
            self.parse_array(idx + 1)
        };
        self.depth -= 1;
        result
    }

    fn match_number(&self, start: usize) -> Result<(Value, usize), Fail> {
        let mut idx = start;
        let len = self.s.len();
        if self.at(idx) == Some('-' as u32) {
            idx += 1;
            if idx >= len {
                return Err(Fail::Stop(start));
            }
        }
        match self.at(idx) {
            Some(c) if (0x31..=0x39).contains(&c) => {
                idx += 1;
                while self.at(idx).is_some_and(is_digit) {
                    idx += 1;
                }
            }
            Some(0x30) => idx += 1,
            _ => return Err(Fail::Stop(start)),
        }
        let mut is_float = false;
        if idx + 1 < len && self.s[idx] == '.' as u32 && is_digit(self.s[idx + 1]) {
            is_float = true;
            idx += 2;
            while self.at(idx).is_some_and(is_digit) {
                idx += 1;
            }
        }
        if idx + 1 < len && (self.s[idx] == 'e' as u32 || self.s[idx] == 'E' as u32) {
            let e_start = idx;
            idx += 1;
            if idx + 1 < len && (self.s[idx] == '-' as u32 || self.s[idx] == '+' as u32) {
                idx += 1;
            }
            while self.at(idx).is_some_and(is_digit) {
                idx += 1;
            }
            if is_digit(self.s[idx - 1]) {
                is_float = true;
            } else {
                idx = e_start;
            }
        }
        let text: String = self.s[start..idx]
            .iter()
            .map(|&c| char::from_u32(c).unwrap_or('?'))
            .collect();
        if is_float {
            let value: f64 = text.parse().map_err(|_| Fail::Fatal)?;
            Ok((Value::Float(value), idx))
        } else {
            if text.trim_start_matches('-').len() > MAX_INT_DIGITS {
                return Err(Fail::Fatal);
            }
            Ok((Value::Int(text), idx))
        }
    }

    /// `end` 는 여는 따옴표 다음 위치
    fn scan_string(&self, mut end: usize) -> Result<(PyStr, usize), Fail> {
        let begin = end - 1;
        let len = self.s.len();
        let mut out = Vec::new();
        loop {
            let mut next = end;
            let mut c = 0;
            while next < len {
                c = self.s[next];
                if c == '"' as u32 || c == '\\' as u32 {
                    break;
                }
                if c <= 0x1F {
                    return Err(Fail::Msg(next));
                }
                next += 1;
            }
            if next >= len {
                return Err(Fail::Msg(begin));
            }
            out.extend_from_slice(&self.s[end..next]);
            next += 1;
            if c == '"' as u32 {
                return Ok((out, next));
            }
            if next == len {
                return Err(Fail::Msg(begin));
            }
            let esc = self.s[next];
            if esc != 'u' as u32 {
                end = next + 1;
                let ch = match char::from_u32(esc) {
                    Some('"') => '"',
                    Some('\\') => '\\',
                    Some('/') => '/',
                    Some('b') => '\u{8}',
                    Some('f') => '\u{c}',
                    Some('n') => '\n',
                    Some('r') => '\r',
                    Some('t') => '\t',
                    _ => return Err(Fail::Msg(end - 2)),
                };
                out.push(ch as u32);
                continue;
            }
            next += 1;
            end = next + 4;
            if end >= len {
                return Err(Fail::Msg(next - 1));
            }
            let mut cp = self.hex4(next).ok_or(Fail::Msg(end - 5))?;
            if (0xD800..0xDC00).contains(&cp)
                && end + 6 < len
                && self.s[end] == '\\' as u32
                && self.s[end + 1] == 'u' as u32
            {
                let low = self.hex4(end + 2).ok_or(Fail::Msg(end + 1))?;
                if (0xDC00..0xE000).contains(&low) {
                    cp = 0x10000 + ((cp - 0xD800) << 10) + (low - 0xDC00);
                    end += 6;
                }
            }
            out.push(cp);
        }
    }

    fn hex4(&self, at: usize) -> Option<u32> {
        let mut value = 0;
        for k in 0..4 {
            let d = char::from_u32(self.s[at + k])?.to_digit(16)?;
            value = (value << 4) | d;
        }
        Some(value)
    }

    fn parse_array(&mut self, idx: usize) -> Result<(Value, usize), Fail> {
        let mut items = Vec::new();
        let mut idx = self.skip_ws(idx);
        if self.at(idx) == Some(']' as u32) {
            return Ok((Value::Array(items), idx + 1));
        }
        loop {
            let (value, next) = self.scan_once(idx)?;
            items.push(value);
            idx = self.skip_ws(next);
            match self.at(idx) {
                Some(c) if c == ']' as u32 => return Ok((Value::Array(items), idx + 1)),
                Some(c) if c == ',' as u32 => idx = self.skip_ws(idx + 1),
                _ => return Err(Fail::Msg(idx)),
            }
        }
    }

    fn parse_object(&mut self, idx: usize) -> Result<(Value, usize), Fail> {
        let mut pairs: Vec<(PyStr, Value)> = Vec::new();
        let mut idx = self.skip_ws(idx);
        if self.at(idx) == Some('}' as u32) {
            return Ok((Value::Object(pairs), idx + 1));
        }
        loop {
            if self.at(idx) != Some('"' as u32) {
                return Err(Fail::Msg(idx));
            }
            let (key, next) = self.scan_string(idx + 1)?;
            idx = self.skip_ws(next);
            if self.at(idx) != Some(':' as u32) {
                return Err(Fail::Msg(idx));
            }
            idx = self.skip_ws(idx + 1);
            let (value, next) = self.scan_once(idx)?;
            match pairs.iter_mut().find(|(k, _)| *k == key) {
                Some(slot) => slot.1 = value,
                None => pairs.push((key, value)),
            }
            idx = self.skip_ws(next);
            match self.at(idx) {
                Some(c) if c == '}' as u32 => return Ok((Value::Object(pairs), idx + 1)),
                Some(c) if c == ',' as u32 => idx = self.skip_ws(idx + 1),
                _ => return Err(Fail::Msg(idx)),
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn pos(text: &str) -> Result<Value, LoadError> {
        loads(text.as_bytes())
    }

    #[test]
    fn error_positions_follow_cpython() {
        assert_eq!(pos("{bad"), Err(LoadError::Invalid(1)));
        assert_eq!(
            pos(r#"{"name":"t","price":1,"quantity":1} x"#),
            Err(LoadError::Invalid(36))
        );
        assert_eq!(
            pos(r#"{"name":"é", "price": 1,"#),
            Err(LoadError::Invalid(24))
        );
        assert_eq!(pos(""), Err(LoadError::Invalid(0)));
        assert_eq!(pos("[1,]"), Err(LoadError::Invalid(3)));
        assert_eq!(pos("\"abc"), Err(LoadError::Invalid(0)));
        assert_eq!(pos("-"), Err(LoadError::Invalid(0)));
        assert_eq!(pos("1."), Err(LoadError::Invalid(1)));
    }

    #[test]
    fn values_and_duplicates() {
        let value = pos(r#"{"a":1,"b":2.5,"a":NaN}"#).unwrap();
        let Value::Object(pairs) = value else {
            panic!("not an object")
        };
        assert_eq!(pairs.len(), 2);
        assert!(matches!(pairs[0].1, Value::Float(f) if f.is_nan()));
        assert_eq!(pairs[1].1, Value::Float(2.5));
        assert_eq!(pos("-0"), Ok(Value::Int("-0".into())));
        assert_eq!(pos("1e400"), Ok(Value::Float(f64::INFINITY)));
        assert_eq!(pos(r#""\ud800""#), Ok(Value::Str(vec![0xD800])));
        assert_eq!(pos(r#""😀""#), Ok(Value::Str(vec![0x1F600])));
    }

    #[test]
    fn encodings() {
        assert_eq!(loads(b"\xEF\xBB\xBF1"), Ok(Value::Int("1".into())));
        assert_eq!(loads(b"1\x002\x00"), Ok(Value::Int("12".into())));
        assert_eq!(loads(b"\xFF\xFE1\x00"), Ok(Value::Int("1".into())));
        assert_eq!(loads(b"\"\xED\xA0\x80\""), Ok(Value::Str(vec![0xD800])));
        assert_eq!(loads(b"\"\xE9\""), Err(LoadError::Other));
        assert_eq!(loads(&[b'1'; 4301]), Err(LoadError::Other));
    }
}
