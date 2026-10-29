//! Python 표기 규칙: `repr(float)`, `f"{x:.1f}"`, `json.dumps(ensure_ascii=False)` 문자열.

/// Python `repr(float)` (유한값). 최단 왕복 자릿수는 Rust `{:e}` 에서 얻고 배치만 Python 규칙으로 바꾼다.
pub fn py_repr(x: f64) -> String {
    if x == 0.0 {
        return if x.is_sign_negative() { "-0.0" } else { "0.0" }.to_string();
    }
    let shortest = format!("{:e}", x.abs());
    // 최단 자릿수의 두 후보가 정확히 같은 거리(동률)면 Rust {:e} 는 올림, Python(dtoa mode 0)은 짝수를 고른다.
    // 같은 자릿수로 정확한 half-even 반올림({:.Ne})을 다시 만들어 왕복하면 그것을 쓴다(verify/bulk_check.py repr)
    let digits_len = shortest
        .split('e')
        .next()
        .unwrap_or("")
        .replace('.', "")
        .len();
    let even = format!("{:.*e}", digits_len.saturating_sub(1), x.abs());
    let sci = if even.parse::<f64>() == Ok(x.abs()) {
        even
    } else {
        shortest
    };
    let (mantissa, exp) = sci.split_once('e').unwrap_or((&sci, "0"));
    let exp: i32 = exp.parse().unwrap_or(0);
    let digits: String = mantissa.chars().filter(|c| *c != '.').collect();
    let n = digits.len() as i32;
    let decpt = exp + 1;
    let body = if decpt <= -4 || decpt > 16 {
        let (first, rest) = digits.split_at(1);
        let frac = if rest.is_empty() {
            String::new()
        } else {
            format!(".{rest}")
        };
        let sign = if exp < 0 { '-' } else { '+' };
        format!("{first}{frac}e{sign}{:02}", exp.abs())
    } else if decpt <= 0 {
        format!("0.{}{digits}", "0".repeat((-decpt) as usize))
    } else if decpt >= n {
        format!("{digits}{}.0", "0".repeat((decpt - n) as usize))
    } else {
        let (int, frac) = digits.split_at(decpt as usize);
        format!("{int}.{frac}")
    };
    if x < 0.0 {
        format!("-{body}")
    } else {
        body
    }
}

/// `f"{errors / n * 100:.1f}%"`. 계산 순서(나눗셈 후 곱셈)를 바꾸지 않는다.
pub fn error_rate(errors: usize, n: usize) -> String {
    format!("{:.1}%", errors as f64 / n as f64 * 100.0)
}

/// `json.dumps(s, ensure_ascii=False)`. 입력은 WTF-8 바이트이고 그대로 이어 붙인다.
pub fn json_string(out: &mut Vec<u8>, s: &[u8]) {
    out.push(b'"');
    for &c in s {
        match c {
            b'"' => out.extend_from_slice(b"\\\""),
            b'\\' => out.extend_from_slice(b"\\\\"),
            b'\n' => out.extend_from_slice(b"\\n"),
            b'\r' => out.extend_from_slice(b"\\r"),
            b'\t' => out.extend_from_slice(b"\\t"),
            0x08 => out.extend_from_slice(b"\\b"),
            0x0C => out.extend_from_slice(b"\\f"),
            0x00..=0x1F => out.extend_from_slice(format!("\\u{c:04x}").as_bytes()),
            _ => out.push(c),
        }
    }
    out.push(b'"');
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn repr_matches_python() {
        let cases = [
            (0.0001, "0.0001"),
            (0.00012, "0.00012"),
            (1e-05, "1e-05"),
            (1.5e-07, "1.5e-07"),
            (5e-324, "5e-324"),
            (1e9, "1000000000.0"),
            (123456789.125, "123456789.125"),
            (0.1 + 0.2, "0.30000000000000004"),
            (-0.0, "-0.0"),
            (0.0, "0.0"),
            (12.0, "12.0"),
            (1.5, "1.5"),
            (1e16, "1e+16"),
            (1e15, "1000000000000000.0"),
            (1234567890123456.7, "1234567890123456.8"),
            (-2.5e-5, "-2.5e-05"),
            // 최단 자릿수 동률: Python 은 짝수 쪽(verify/bulk_check.py 에서 찾은 값)
            (f64::from_bits(0x3e60000000000000), "2.9802322387695312e-08"),
            (f64::from_bits(0x42384a7241869400), "104328216966.57812"),
            (f64::from_bits(0x42a013c1ff9d7e20), "8838522588863.062"),
            (1.7976931348623157e308, "1.7976931348623157e+308"),
        ];
        for (x, want) in cases {
            assert_eq!(py_repr(x), want);
        }
    }

    #[test]
    fn rate_rounds_half_even() {
        // Python: 0.125->0.1, 0.25->0.2, 12.25->12.2, 0.05->0.1 (verify/probe.py)
        assert_eq!(format!("{:.1}", 0.125), "0.1");
        assert_eq!(format!("{:.1}", 0.25), "0.2");
        assert_eq!(format!("{:.1}", 12.25), "12.2");
        assert_eq!(format!("{:.1}", 0.05), "0.1");
        assert_eq!(error_rate(1, 3), "33.3%");
        assert_eq!(error_rate(0, 3), "0.0%");
    }

    #[test]
    fn json_escapes() {
        let mut out = Vec::new();
        json_string(
            &mut out,
            "a\"\\\n\r\t\u{8}\u{c}\u{1}\u{7f}\u{2028}/é".as_bytes(),
        );
        assert_eq!(
            String::from_utf8(out).unwrap(),
            "\"a\\\"\\\\\\n\\r\\t\\b\\f\\u0001\u{7f}\u{2028}/é\""
        );
    }
}
