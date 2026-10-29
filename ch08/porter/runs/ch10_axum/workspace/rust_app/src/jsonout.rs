//! 한 줄 JSON 직렬화. 실수는 pydantic-core(serde_json + ryu)와 같은 표기,
//! 문자열은 '"', '\\', 제어문자만 이스케이프하고 비ASCII 는 그대로 둔다.

use std::fmt::Write;

use crate::pyjson::PyStr;

/// 문자열 이스케이프. 고립 서로게이트가 있으면 UTF-8 로 만들 수 없으므로 None
pub fn push_pystr(out: &mut String, s: &PyStr) -> Option<()> {
    out.push('"');
    for &c in s {
        let ch = char::from_u32(c)?;
        push_char(out, ch);
    }
    out.push('"');
    Some(())
}

pub fn push_str(out: &mut String, s: &str) {
    out.push('"');
    for ch in s.chars() {
        push_char(out, ch);
    }
    out.push('"');
}

fn push_char(out: &mut String, ch: char) {
    match ch {
        '"' => out.push_str("\\\""),
        '\\' => out.push_str("\\\\"),
        '\n' => out.push_str("\\n"),
        '\r' => out.push_str("\\r"),
        '\t' => out.push_str("\\t"),
        '\u{8}' => out.push_str("\\b"),
        '\u{c}' => out.push_str("\\f"),
        c if (c as u32) < 0x20 => {
            let _ = write!(out, "\\u{:04x}", c as u32);
        }
        c => out.push(c),
    }
}

/// ryu `format64` 규칙. 자릿수는 Rust 의 최단 왕복 지수 표기(`{:e}`)에서 얻는다
pub fn push_f64(out: &mut String, x: f64) {
    if x.is_sign_negative() {
        out.push('-');
    }
    if x == 0.0 {
        out.push_str("0.0");
        return;
    }
    let shortest = format!("{:e}", x.abs());
    // `{:e}` 는 같은 길이 후보가 정확히 반반일 때 위로 올린다. pydantic-core 는 짝수 쪽을 고르므로
    // 같은 자릿수로 정확 반올림(반올림 짝수)한 표기를 쓰고, 왕복하지 않을 때만 원래 것을 쓴다
    let length = shortest
        .split('e')
        .next()
        .map_or(1, |m| m.chars().filter(char::is_ascii_digit).count());
    let even = format!("{:.*e}", length.saturating_sub(1), x.abs());
    let sci = if even.parse::<f64>() == Ok(x.abs()) {
        even
    } else {
        shortest
    };
    let (mantissa, exp) = sci.split_once('e').unwrap_or((&sci, "0"));
    let exp: i32 = exp.parse().unwrap_or(0);
    let digits: String = mantissa.chars().filter(|c| *c != '.').collect();
    let length = digits.len() as i32;
    // 10^(kk-1) <= x < 10^kk
    let kk = exp + 1;
    let k = kk - length;
    if 0 <= k && kk <= 16 {
        out.push_str(&digits);
        out.push_str(&"0".repeat(k as usize));
        out.push_str(".0");
    } else if 0 < kk && kk <= 16 {
        out.push_str(&digits[..kk as usize]);
        out.push('.');
        out.push_str(&digits[kk as usize..]);
    } else if -5 < kk && kk <= 0 {
        out.push_str("0.");
        out.push_str(&"0".repeat((-kk) as usize));
        out.push_str(&digits);
    } else if length == 1 {
        let _ = write!(out, "{digits}e{}", kk - 1);
    } else {
        let _ = write!(out, "{}.{}e{}", &digits[..1], &digits[1..], kk - 1);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn float(x: f64) -> String {
        let mut out = String::new();
        push_f64(&mut out, x);
        out
    }

    #[test]
    fn floats_follow_ryu() {
        let cases = [
            (10.0, "10.0"),
            (1e-7, "1e-7"),
            (0.1, "0.1"),
            (5e-324, "5e-324"),
            (123456.789, "123456.789"),
            (1e-5, "0.00001"),
            (1e-6, "1e-6"),
            (999999.9999999999, "999999.9999999999"),
            (1e16, "1e16"),
            (1e15, "1000000000000000.0"),
            (1.5e300, "1.5e300"),
            (-0.0, "-0.0"),
            (0.0, "0.0"),
            (1.8, "1.8"),
            (1e12, "1000000000000.0"),
            (0.000123, "0.000123"),
            (1.2345e-7, "1.2345e-7"),
            // 정확히 반반인 경우 짝수 쪽(pydantic-core 실측)
            (654840279078428.2, "654840279078428.2"),
            (75506162623260.12, "75506162623260.12"),
        ];
        for (x, want) in cases {
            assert_eq!(float(x), want, "{x:e}");
        }
    }

    #[test]
    fn strings_escape_like_python() {
        let mut out = String::new();
        push_str(&mut out, "a\"\\\n\u{1}\u{7f}/é😀");
        assert_eq!(out, "\"a\\\"\\\\\\n\\u0001\u{7f}/é😀\"");
    }
}
