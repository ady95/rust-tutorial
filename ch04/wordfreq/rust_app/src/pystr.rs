//! 계약이 기대는 Python `str` 동작을 옮긴 것.
//!
//! 기준은 CPython 3.12 (.python-version) 이고, 그 Unicode 데이터 버전은 15.0 이다.
//! Rust 표준 라이브러리의 Unicode 버전이 더 새로우면 생기는 차이를 여기서 맞춘다.

/// Python `str.isspace()` / `str.split()` 의 공백.
/// Rust `char::is_whitespace` 에 없는 U+001C..U+001F (정보 구분 문자) 를 더한다.
pub fn is_space(c: char) -> bool {
    c.is_whitespace() || ('\u{1c}'..='\u{1f}').contains(&c)
}

/// Unicode 16.0 이후에 소문자 대응이 생긴 대문자.
/// Python 3.12 에서는 미배정 글자이므로 `str.lower()` 가 바꾸지 않는다.
fn cased_after_unicode_15(c: char) -> bool {
    matches!(
        c,
        '\u{1C89}'                    // CYRILLIC CAPITAL LETTER TJE (16.0)
            | '\u{A7CB}'              // LATIN CAPITAL LETTER RAMS HORN (16.0)
            | '\u{A7CC}'              // LATIN CAPITAL LETTER S WITH DIAGONAL STROKE (16.0)
            | '\u{A7CE}'              // LATIN CAPITAL LETTER PHARYNGEAL VOICED FRICATIVE (17.0)
            | '\u{A7D2}'              // LATIN CAPITAL LETTER DOUBLE THORN (17.0)
            | '\u{A7D4}'              // LATIN CAPITAL LETTER DOUBLE WYNN (17.0)
            | '\u{A7DA}'              // LATIN CAPITAL LETTER LAMBDA (16.0)
            | '\u{A7DC}'              // LATIN CAPITAL LETTER LAMBDA WITH STROKE (16.0)
            | '\u{10D50}'..='\u{10D65}' // GARAY CAPITAL LETTERS (16.0)
    )
}

/// Python `str.lower()`. 전체 소문자 대응(İ → i̇)과 끝 시그마(Σ → ς) 규칙은 Rust 와 같다.
pub fn lower(s: &str) -> String {
    // 위 글자들은 Python 3.12 에서 cased 도 case-ignorable 도 아니라서 끝 시그마 문맥을 끊는다.
    // 그 자리에서 잘라 조각마다 바꾸면 Python 과 같은 결과가 된다.
    let mut out = String::with_capacity(s.len());
    let mut rest = s;
    while let Some(pos) = rest.find(cased_after_unicode_15) {
        let c = rest[pos..].chars().next().unwrap();
        out.push_str(&rest[..pos].to_lowercase());
        out.push(c);
        rest = &rest[pos + c.len_utf8()..];
    }
    out.push_str(&rest.to_lowercase());
    out
}

/// Unicode 15.0 의 Nd(십진 숫자) 묶음마다 0 에 해당하는 코드 포인트. 각 묶음은 0..9 열 글자가 이어진다.
const DECIMAL_ZEROS: [u32; 68] = [
    0x0030, 0x0660, 0x06F0, 0x07C0, 0x0966, 0x09E6, 0x0A66, 0x0AE6, 0x0B66, 0x0BE6, 0x0C66, 0x0CE6,
    0x0D66, 0x0DE6, 0x0E50, 0x0ED0, 0x0F20, 0x1040, 0x1090, 0x17E0, 0x1810, 0x1946, 0x19D0, 0x1A80,
    0x1A90, 0x1B50, 0x1BB0, 0x1C40, 0x1C50, 0xA620, 0xA8D0, 0xA900, 0xA9D0, 0xA9F0, 0xAA50, 0xABF0,
    0xFF10, 0x104A0, 0x10D30, 0x11066, 0x110F0, 0x11136, 0x111D0, 0x112F0, 0x11450, 0x114D0,
    0x11650, 0x116C0, 0x11730, 0x118E0, 0x11950, 0x11C50, 0x11D50, 0x11DA0, 0x11F50, 0x16A60,
    0x16AC0, 0x16B50, 0x1D7CE, 0x1D7D8, 0x1D7E2, 0x1D7EC, 0x1D7F6, 0x1E140, 0x1E2F0, 0x1E4F0,
    0x1E950, 0x1FBF0,
];

/// Python `unicodedata.decimal(c)`. `int()` 와 정규식 `\d` 가 숫자로 보는 글자.
pub fn decimal_value(c: char) -> Option<u32> {
    let cp = c as u32;
    DECIMAL_ZEROS.iter().find(|&&zero| (zero..zero + 10).contains(&cp)).map(|zero| cp - zero)
}

/// CPython 이 문자열을 정수로 바꿀 때 허용하는 최대 자릿수 (sys.int_info.default_max_str_digits).
const MAX_STR_DIGITS: usize = 4300;

/// Python `int(s)` (밑 10). 앞뒤 공백, 부호, 숫자 사이 밑줄(1_000), 비 ASCII 십진 숫자(５)를 받는다.
/// 값이 i128 범위를 넘으면 그 끝 값으로 자른다.
pub fn int(s: &str) -> Option<i128> {
    // CPython 은 먼저 비 ASCII 공백을 ' ' 로, 비 ASCII 십진 숫자를 ASCII 숫자로 바꾸고,
    // 그 밖의 비 ASCII 글자가 있으면 실패한다. ASCII 글자는 그대로 둔다.
    let mut ascii = Vec::with_capacity(s.len());
    for c in s.chars() {
        if (c as u32) < 0x7f {
            ascii.push(c as u8);
        } else if is_space(c) {
            ascii.push(b' ');
        } else {
            ascii.push(b'0' + decimal_value(c)? as u8);
        }
    }

    // 여기서 공백은 ASCII 6자뿐이다 (U+001C..U+001F 는 들어가지 않는다).
    let is_ws = |b: &u8| matches!(b, b' ' | b'\t' | b'\n' | b'\x0b' | b'\x0c' | b'\r');
    let start = ascii.iter().position(|b| !is_ws(b))?;
    let end = ascii.iter().rposition(|b| !is_ws(b))? + 1;
    let trimmed = &ascii[start..end];
    let (negative, body) = match trimmed.split_first() {
        Some((b'+', rest)) => (false, rest),
        Some((b'-', rest)) => (true, rest),
        _ => (false, trimmed),
    };

    // 밑줄은 숫자 사이에 하나씩만 올 수 있다.
    let well_formed = !body.is_empty()
        && body.iter().all(|b| b.is_ascii_digit() || *b == b'_')
        && body.first() != Some(&b'_')
        && body.last() != Some(&b'_')
        && !body.windows(2).any(|pair| pair == b"__");
    if !well_formed {
        return None;
    }
    let digits: Vec<u8> = body.iter().filter(|b| b.is_ascii_digit()).map(|b| b - b'0').collect();
    if digits.len() > MAX_STR_DIGITS {
        return None;
    }
    let magnitude = digits
        .iter()
        .fold(0i128, |acc, &d| acc.saturating_mul(10).saturating_add(i128::from(d)));
    Some(if negative { -magnitude } else { magnitude })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn info_separators_are_whitespace() {
        assert_eq!("a\u{1c}b\u{1f}c\u{3000}d".split(is_space).collect::<Vec<_>>(), ["a", "b", "c", "d"]);
        assert!(!is_space('\u{200b}'));
    }

    #[test]
    fn lower_uses_full_mapping_and_final_sigma() {
        assert_eq!(lower("RUST"), "rust");
        assert_eq!(lower("İ"), "i\u{307}");
        assert_eq!(lower("ΟΔΟΣ"), "οδο\u{3c2}");
        assert_eq!(lower("ΣΑΣ"), "\u{3c3}α\u{3c2}");
    }

    #[test]
    fn lower_keeps_letters_newer_than_unicode_15() {
        assert_eq!(lower("A\u{10D50}B"), "a\u{10D50}b");
        // 미배정 글자 앞의 Σ 는 끝 시그마, 뒤의 Σ 는 일반 시그마.
        assert_eq!(lower("ΑΣ\u{A7CB}ΣΑ"), "α\u{3c2}\u{A7CB}\u{3c3}α");
    }

    #[test]
    fn decimal_digits_cover_unicode_15() {
        assert_eq!(DECIMAL_ZEROS.len() * 10, 680);
        assert_eq!(decimal_value('７'), Some(7));
        assert_eq!(decimal_value('٣'), Some(3));
        assert_eq!(decimal_value('²'), None);
        assert_eq!(decimal_value('a'), None);
    }

    #[test]
    fn int_matches_python_rules() {
        assert_eq!(int("10"), Some(10));
        assert_eq!(int(" +7\n"), Some(7));
        assert_eq!(int("-3"), Some(-3));
        assert_eq!(int("007"), Some(7));
        assert_eq!(int("1_000"), Some(1000));
        assert_eq!(int("１２"), Some(12));
        assert_eq!(int("\u{3000}5\u{a0}"), Some(5));
        assert_eq!(int("99999999999999999999999999999999999999999"), Some(i128::MAX));
        for bad in ["", " ", "+", "abc", "1.5", "0x10", "_1", "1_", "1__0", "- 5", "\u{1c}5", "²", "1e3"] {
            assert_eq!(int(bad), None, "{bad:?}");
        }
        assert_eq!(int(&"1".repeat(MAX_STR_DIGITS)), Some(i128::MAX));
        assert_eq!(int(&"1".repeat(MAX_STR_DIGITS + 1)), None);
    }
}
