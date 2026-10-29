//! Python 문자열 동작 모음: splitlines, strip, lower, `\w`, 십진 숫자.
//! Unicode 표는 verify/gen_unicode_tables.py 가 Python 에서 뽑은 것이다.

use std::cmp::Ordering;

use crate::unicode_tables::{DECIMAL_ZEROS, LOWER, SIGMA_CASED, SIGMA_SKIP, SPACE};

fn in_ranges(table: &[(u32, u32)], c: u32) -> bool {
    table
        .binary_search_by(|&(lo, hi)| {
            if hi < c {
                Ordering::Less
            } else if lo > c {
                Ordering::Greater
            } else {
                Ordering::Equal
            }
        })
        .is_ok()
}

/// Python `str.isspace()`.
pub fn is_space(c: char) -> bool {
    in_ranges(SPACE, c as u32)
}

/// Python `re` 의 `\w` (str 패턴): `isalnum()` 이거나 `_`.
pub fn is_word_char(c: char) -> bool {
    if c.is_ascii() {
        return c.is_ascii_alphanumeric() || c == '_';
    }
    in_ranges(crate::unicode_tables::ALNUM, c as u32)
}

/// 십진 숫자의 값(`unicodedata.decimal`, 정규식 `\d`).
pub fn decimal_value(c: char) -> Option<u32> {
    let c = c as u32;
    let idx = match DECIMAL_ZEROS.binary_search(&c) {
        Ok(i) => i,
        Err(0) => return None,
        Err(i) => i - 1,
    };
    let diff = c - DECIMAL_ZEROS[idx];
    (diff < 10).then_some(diff)
}

/// Python `str.splitlines()`: 줄 경계 10종과 `\r\n`. 끝의 경계는 빈 줄을 만들지 않는다.
pub fn splitlines(text: &str) -> Vec<&str> {
    let mut lines = Vec::new();
    let mut start = 0;
    let mut iter = text.char_indices().peekable();
    while let Some((i, c)) = iter.next() {
        match c {
            '\n' | '\x0b' | '\x0c' | '\x1c'..='\x1e' | '\u{85}' | '\u{2028}' | '\u{2029}' => {
                lines.push(&text[start..i]);
                start = i + c.len_utf8();
            }
            '\r' => {
                lines.push(&text[start..i]);
                start = i + 1;
                if let Some(&(j, '\n')) = iter.peek() {
                    iter.next();
                    start = j + 1;
                }
            }
            _ => {}
        }
    }
    if start < text.len() {
        lines.push(&text[start..]);
    }
    lines
}

/// Python `str.strip()` (인자 없음): 앞뒤의 `isspace()` 글자를 지운다.
pub fn strip(s: &str) -> &str {
    s.trim_matches(is_space)
}

/// Python `str.strip(" \t")`.
pub fn strip_space_tab(s: &str) -> &str {
    s.trim_matches([' ', '\t'])
}

fn is_sigma_skip(c: char) -> bool {
    in_ranges(SIGMA_SKIP, c as u32)
}

fn is_sigma_cased(c: char) -> bool {
    in_ranges(SIGMA_CASED, c as u32)
}

/// Final_Sigma: 앞에 (Case_Ignorable 을 건너뛰고) Cased 글자가 있고 뒤에는 Cased 글자가 오지 않는다.
fn final_sigma(chars: &[char], i: usize) -> bool {
    let before = chars[..i]
        .iter()
        .rev()
        .find(|&&c| !is_sigma_skip(c))
        .is_some_and(|&c| is_sigma_cased(c));
    if !before {
        return false;
    }
    let after = chars[i + 1..]
        .iter()
        .find(|&&c| !is_sigma_skip(c))
        .is_some_and(|&c| is_sigma_cased(c));
    !after
}

/// Python `str.lower()`: 전체 Unicode 소문자 규칙(`İ` → 두 글자)과 Final_Sigma.
pub fn lower(s: &str) -> String {
    if s.is_ascii() {
        return s.to_ascii_lowercase();
    }
    let chars: Vec<char> = s.chars().collect();
    let mut out = String::with_capacity(s.len());
    for (i, &c) in chars.iter().enumerate() {
        if c == '\u{3A3}' {
            out.push(if final_sigma(&chars, i) {
                '\u{3C2}'
            } else {
                '\u{3C3}'
            });
        } else if c.is_ascii() {
            out.push(c.to_ascii_lowercase());
        } else if let Ok(k) = LOWER.binary_search_by_key(&(c as u32), |e| e.0) {
            let (_, first, second) = LOWER[k];
            out.push(char::from_u32(first).unwrap_or(c));
            if second != 0 {
                out.push(char::from_u32(second).unwrap_or(c));
            }
        } else {
            out.push(c);
        }
    }
    out
}

/// Python `int(str)` 중 십진수 해석. 값이 너무 크면 크기만 유지해 돌려준다. 실패하면 `None`.
pub fn py_int(s: &str) -> Option<i64> {
    let mut ascii = String::with_capacity(s.len());
    for c in s.chars() {
        if (c as u32) < 127 {
            ascii.push(c);
        } else if is_space(c) {
            ascii.push(' ');
        } else {
            ascii.push(char::from_digit(decimal_value(c)?, 10)?);
        }
    }
    let body = ascii.trim_matches([' ', '\t', '\n', '\x0b', '\x0c', '\r']);
    let (negative, digits) = match body.as_bytes().first() {
        Some(b'-') => (true, &body[1..]),
        Some(b'+') => (false, &body[1..]),
        _ => (false, body),
    };
    let bytes = digits.as_bytes();
    let mut value: i64 = 0;
    let mut prev_digit = false;
    for &b in bytes {
        if b.is_ascii_digit() {
            value = value
                .saturating_mul(10)
                .saturating_add(i64::from(b - b'0'))
                .min(1 << 40);
            prev_digit = true;
        } else if b == b'_' && prev_digit {
            prev_digit = false;
        } else {
            return None;
        }
    }
    if !prev_digit {
        return None;
    }
    Some(if negative { -value } else { value })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn splitlines_boundaries() {
        let text = "a\nb\r\nc\rd\x0be\x0cf\x1cg\x1dh\x1ei\u{85}j\u{2028}k\u{2029}l";
        assert_eq!(
            splitlines(text),
            ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l"]
        );
        assert_eq!(splitlines("a\n\rb\r\r\n"), ["a", "", "b", ""]);
        assert_eq!(splitlines("a\n"), ["a"]);
        assert_eq!(splitlines("\n"), [""]);
        assert!(splitlines("").is_empty());
    }

    #[test]
    fn strip_is_unicode() {
        assert_eq!(strip("\x1f a\u{3000}\u{2003}"), "a");
        assert_eq!(strip("\u{feff}a"), "\u{feff}a");
        assert_eq!(strip_space_tab(" \t\u{a0}a \t"), "\u{a0}a");
    }

    #[test]
    fn lower_cases() {
        assert_eq!(lower("İstanbul"), "i\u{307}stanbul");
        assert_eq!(lower("ΣΊΣΥΦΟΣ"), "σίσυφος");
        assert_eq!(lower("AΣ"), "aς");
        assert_eq!(lower("Σ"), "σ");
        assert_eq!(lower("AΣB"), "aσb");
        assert_eq!(lower("A.Σ"), "a.ς");
    }

    #[test]
    fn word_chars() {
        assert!(is_word_char('_') && is_word_char('가') && is_word_char('Ⅻ') && is_word_char('½'));
        assert!(!is_word_char('\u{307}') && !is_word_char('🎉') && !is_word_char('-'));
    }

    #[test]
    fn int_parsing() {
        assert_eq!(py_int("3"), Some(3));
        assert_eq!(py_int(" +3\u{3000}"), Some(3));
        assert_eq!(py_int("0_3"), Some(3));
        assert_eq!(py_int("٣"), Some(3));
        assert_eq!(py_int("３"), Some(3));
        assert_eq!(py_int("-0"), Some(0));
        for bad in [
            "", "_3", "3_", "3__0", "3.0", "1e0", "--1", "0x3", "\x1c3", "٣?",
        ] {
            assert_eq!(py_int(bad), None, "{bad:?}");
        }
    }
}
