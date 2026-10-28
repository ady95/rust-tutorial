//! Python float 의 문자열 변환·파싱·round 동작을 흉내 낸다.

/// `str.isspace()` 가 참인 문자. Rust 의 `char::is_whitespace` 와 달리 U+001C..U+001F 를 포함한다.
pub fn is_py_space(c: char) -> bool {
    matches!(
        c,
        '\t' | '\n'
            | '\u{0b}'
            | '\u{0c}'
            | '\r'
            | '\u{1c}'..='\u{1f}'
            | ' '
            | '\u{85}'
            | '\u{a0}'
            | '\u{1680}'
            | '\u{2000}'..='\u{200a}'
            | '\u{2028}'
            | '\u{2029}'
            | '\u{202f}'
            | '\u{205f}'
            | '\u{3000}'
    )
}

/// `str.splitlines()` 와 같은 줄 나누기(줄 끝 문자는 버린다).
pub fn splitlines(s: &str) -> Vec<&str> {
    let mut lines = Vec::new();
    let mut start = 0;
    let mut iter = s.char_indices().peekable();
    while let Some((i, c)) = iter.next() {
        let is_break = matches!(
            c,
            '\n' | '\r'
                | '\u{0b}'
                | '\u{0c}'
                | '\u{1c}'
                | '\u{1d}'
                | '\u{1e}'
                | '\u{85}'
                | '\u{2028}'
                | '\u{2029}'
        );
        if !is_break {
            continue;
        }
        lines.push(&s[start..i]);
        let mut end = i + c.len_utf8();
        if c == '\r' && iter.next_if(|&(_, n)| n == '\n').is_some() {
            end += 1;
        }
        start = end;
    }
    if start < s.len() {
        lines.push(&s[start..]);
    }
    lines
}

/// `float(text)` 와 같은 문법을 받아들인다(text 는 이미 strip 된 상태).
/// 밑줄은 숫자와 숫자 사이에만 허용된다.
pub fn parse(text: &str) -> Option<f64> {
    let bytes = text.as_bytes();
    if !text.is_ascii() {
        return None;
    }
    let mut cleaned = String::with_capacity(text.len());
    for (i, &b) in bytes.iter().enumerate() {
        if b == b'_' {
            let prev_digit = i > 0 && bytes[i - 1].is_ascii_digit();
            let next_digit = bytes.get(i + 1).is_some_and(|c| c.is_ascii_digit());
            if !(prev_digit && next_digit) {
                return None;
            }
        } else {
            cleaned.push(b as char);
        }
    }
    let body = cleaned.strip_prefix(['+', '-']).unwrap_or(&cleaned);
    let lower = body.to_ascii_lowercase();
    if !(matches!(lower.as_str(), "inf" | "infinity" | "nan") || is_decimal(body)) {
        return None;
    }
    cleaned.parse().ok()
}

/// digits ["." [digits]] [exp] | "." digits [exp]
fn is_decimal(s: &str) -> bool {
    let b = s.as_bytes();
    let mut i = 0;
    let digits = |i: &mut usize| {
        let st = *i;
        while *i < b.len() && b[*i].is_ascii_digit() {
            *i += 1;
        }
        *i - st
    };
    let mut n = digits(&mut i);
    if i < b.len() && b[i] == b'.' {
        i += 1;
        n += digits(&mut i);
    }
    if n == 0 {
        return false;
    }
    if i < b.len() && (b[i] == b'e' || b[i] == b'E') {
        i += 1;
        if i < b.len() && (b[i] == b'+' || b[i] == b'-') {
            i += 1;
        }
        if digits(&mut i) == 0 {
            return false;
        }
    }
    i == b.len()
}

/// `repr(float)`: 가장 짧은 왕복 자릿수, 10진 지수가 -4 미만이거나 16 이상이면 지수 표기.
pub fn repr(x: f64) -> String {
    if x.is_nan() {
        return "nan".to_string();
    }
    if x.is_infinite() {
        return if x > 0.0 { "inf" } else { "-inf" }.to_string();
    }
    let sign = if x.is_sign_negative() { "-" } else { "" };
    if x == 0.0 {
        return format!("{sign}0.0");
    }
    // Rust 의 `{:e}` 는 가장 짧은 왕복 자릿수를 낸다: "d.ddde-5"
    let sci = format!("{:e}", x.abs());
    let (mant, exp) = sci.split_once('e').expect("LowerExp has exponent");
    let digits: String = mant.chars().filter(|&c| c != '.').collect();
    let exp: i32 = exp.parse().expect("valid exponent");
    let decpt = exp + 1;
    let body = if -4 < decpt && decpt <= 16 {
        let n = digits.len() as i32;
        if decpt <= 0 {
            format!("0.{}{}", "0".repeat((-decpt) as usize), digits)
        } else if decpt >= n {
            format!("{}{}.0", digits, "0".repeat((decpt - n) as usize))
        } else {
            let (a, b) = digits.split_at(decpt as usize);
            format!("{a}.{b}")
        }
    } else {
        let (first, rest) = digits.split_at(1);
        let frac = if rest.is_empty() {
            String::new()
        } else {
            format!(".{rest}")
        };
        let esign = if exp < 0 { '-' } else { '+' };
        format!("{first}{frac}e{esign}{:02}", exp.abs())
    };
    format!("{sign}{body}")
}

/// `round(x, ndigits)`: 정확한 10진 값을 기준으로 반올림(동점은 짝수)한 뒤 다시 float 로 읽는다.
pub fn round(x: f64, ndigits: usize) -> f64 {
    if !x.is_finite() {
        return x;
    }
    format!("{x:.ndigits$}")
        .parse()
        .expect("formatted float parses")
}

/// `format(x, ".Nf")`.
pub fn fixed(x: f64, ndigits: usize) -> String {
    if x.is_nan() {
        return "nan".to_string();
    }
    format!("{x:.ndigits$}")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn repr_matches_python() {
        let cases = [
            (1.0, "1.0"),
            (-0.0, "-0.0"),
            (0.1, "0.1"),
            (1e16, "1e+16"),
            (1e15, "1000000000000000.0"),
            (123456789012345680.0, "1.2345678901234568e+17"),
            (0.0001, "0.0001"),
            (0.00001, "1e-05"),
            (1.5e-7, "1.5e-07"),
            (1e300, "1e+300"),
            (5e-324, "5e-324"),
            (2.5, "2.5"),
        ];
        for (x, want) in cases {
            assert_eq!(repr(x), want);
        }
    }

    #[test]
    fn round_ties_to_even_on_exact_value() {
        assert_eq!(round(0.125, 2), 0.12);
        assert_eq!(round(0.375, 2), 0.38);
        assert_eq!(round(2.675, 2), 2.67);
        assert_eq!(repr(round(-0.001, 2)), "-0.0");
        assert_eq!(fixed(0.00005, 4), "0.0001");
        assert_eq!(fixed(0.25, 1), "0.2");
    }

    #[test]
    fn parse_like_python() {
        assert_eq!(parse("1_000"), Some(1000.0));
        assert_eq!(parse("1__0"), None);
        assert_eq!(parse("_1"), None);
        assert_eq!(parse("1_.5"), None);
        assert_eq!(parse("1."), Some(1.0));
        assert_eq!(parse(".5"), Some(0.5));
        assert_eq!(parse("."), None);
        assert_eq!(parse("-4E2"), Some(-400.0));
        assert_eq!(parse("1e"), None);
        assert_eq!(parse("+Infinity"), Some(f64::INFINITY));
        assert!(parse("-nan").unwrap().is_nan());
        assert_eq!(parse("infinit"), None);
        assert_eq!(parse("0x10"), None);
        assert_eq!(parse("abc"), None);
    }

    #[test]
    fn splitlines_like_python() {
        assert_eq!(splitlines("a\r\nb\rc\x1cd\n"), vec!["a", "b", "c", "d"]);
        assert_eq!(splitlines("a\n\n"), vec!["a", ""]);
        assert_eq!(splitlines(""), Vec::<&str>::new());
    }
}
