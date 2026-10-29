//! 단어 규칙 (계약 2절): 공백 분리 → 앞뒤 문장 부호 제거 → 소문자 → 빈 문자열 버림.

use std::collections::HashMap;

/// 단어 앞뒤에서 떼어 낼 문장 부호 (ASCII 32자 + “ ” ‘ ’ … ·)
pub const PUNCTUATION: &str =
    "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~\u{201C}\u{201D}\u{2018}\u{2019}\u{2026}\u{B7}";

/// Python 3.12 `str.split()`(인자 없음)의 공백 집합 (Py_UNICODE_ISSPACE, Unicode 15.0).
/// verify/gen_props.py 로 Python 에서 뽑은 표와 단위 테스트로 대조한다.
/// `char::is_whitespace` 와 달리 U+001C–U+001F 를 포함한다.
pub fn is_py_space(c: char) -> bool {
    matches!(
        c,
        '\u{9}'..='\u{D}'
            | '\u{1C}'..='\u{20}'
            | '\u{85}'
            | '\u{A0}'
            | '\u{1680}'
            | '\u{2000}'..='\u{200A}'
            | '\u{2028}'
            | '\u{2029}'
            | '\u{202F}'
            | '\u{205F}'
            | '\u{3000}'
    )
}

fn is_punct(c: char) -> bool {
    PUNCTUATION.contains(c)
}

// 아래 두 표는 Python 3.12.3(Unicode 15.0.0)과 이 프로젝트를 빌드한 Rust 툴체인
// (char::UNICODE_VERSION = 17.0.0)의 전 코드 포인트 비교 결과다 (추측으로 넣은 항목 없음).
// 표 원본: tests/data/py_lower_table.txt (verify/gen_lower_table.py 가 생성).
// 차이 목록 생성: cargo test -- --ignored dump_unicode_diffs → target/unicode_diffs.txt.
// 툴체인의 Unicode 버전이 바뀌면 lower_table_matches_python / sigma_class_matches_python
// 테스트가 실패하므로 그때 다시 만든다.

/// Python 3.12 에서는 `lower()` 로 바뀌지 않지만 Rust 17.0 표의 `char::to_lowercase` 는 바꾸는 글자 구간.
/// (반대로 Python 이 바꾸는 글자는 모두 Rust 와 결과가 같았다)
const PY_LOWER_UNCHANGED: &[(char, char)] = &[
    ('\u{1C89}', '\u{1C89}'),
    ('\u{A7CB}', '\u{A7CC}'),
    ('\u{A7CE}', '\u{A7CE}'),
    ('\u{A7D2}', '\u{A7D2}'),
    ('\u{A7D4}', '\u{A7D4}'),
    ('\u{A7DA}', '\u{A7DA}'),
    ('\u{A7DC}', '\u{A7DC}'),
    ('\u{10D50}', '\u{10D65}'),
    ('\u{16EA0}', '\u{16EB8}'),
];

/// Final_Sigma 판단에서 Python 3.12 와 Rust 17.0 의 글자 분류가 다른 구간과 Python 쪽 분류
const PY_SIGMA_CLASS_OVERRIDES: &[(char, char, SigmaClass)] = &[
    ('\u{295}', '\u{295}', SigmaClass::Cased),
    ('\u{897}', '\u{897}', SigmaClass::Other),
    ('\u{1ACF}', '\u{1ADD}', SigmaClass::Other),
    ('\u{1AE0}', '\u{1AEB}', SigmaClass::Other),
    ('\u{1C89}', '\u{1C8A}', SigmaClass::Other),
    ('\u{A7CB}', '\u{A7CF}', SigmaClass::Other),
    ('\u{A7D2}', '\u{A7D2}', SigmaClass::Other),
    ('\u{A7D4}', '\u{A7D4}', SigmaClass::Other),
    ('\u{A7DA}', '\u{A7DC}', SigmaClass::Other),
    ('\u{A7F1}', '\u{A7F1}', SigmaClass::Other),
    ('\u{10D4E}', '\u{10D4E}', SigmaClass::Other),
    ('\u{10D50}', '\u{10D65}', SigmaClass::Other),
    ('\u{10D69}', '\u{10D6D}', SigmaClass::Other),
    ('\u{10D6F}', '\u{10D85}', SigmaClass::Other),
    ('\u{10EC5}', '\u{10EC5}', SigmaClass::Other),
    ('\u{10EFA}', '\u{10EFC}', SigmaClass::Other),
    ('\u{113BB}', '\u{113C0}', SigmaClass::Other),
    ('\u{113CE}', '\u{113CE}', SigmaClass::Other),
    ('\u{113D0}', '\u{113D0}', SigmaClass::Other),
    ('\u{113D2}', '\u{113D2}', SigmaClass::Other),
    ('\u{113E1}', '\u{113E2}', SigmaClass::Other),
    ('\u{1171E}', '\u{1171E}', SigmaClass::Ignorable),
    ('\u{11B60}', '\u{11B60}', SigmaClass::Other),
    ('\u{11B62}', '\u{11B64}', SigmaClass::Other),
    ('\u{11B66}', '\u{11B66}', SigmaClass::Other),
    ('\u{11DD9}', '\u{11DD9}', SigmaClass::Other),
    ('\u{11F5A}', '\u{11F5A}', SigmaClass::Other),
    ('\u{1611E}', '\u{16129}', SigmaClass::Other),
    ('\u{1612D}', '\u{1612F}', SigmaClass::Other),
    ('\u{16D40}', '\u{16D42}', SigmaClass::Other),
    ('\u{16D6B}', '\u{16D6C}', SigmaClass::Other),
    ('\u{16EA0}', '\u{16EB8}', SigmaClass::Other),
    ('\u{16EBB}', '\u{16ED3}', SigmaClass::Other),
    ('\u{16FF2}', '\u{16FF3}', SigmaClass::Other),
    ('\u{1E5EE}', '\u{1E5EF}', SigmaClass::Other),
    ('\u{1E6E3}', '\u{1E6E3}', SigmaClass::Other),
    ('\u{1E6E6}', '\u{1E6E6}', SigmaClass::Other),
    ('\u{1E6EE}', '\u{1E6EF}', SigmaClass::Other),
    ('\u{1E6F5}', '\u{1E6F5}', SigmaClass::Other),
    ('\u{1E6FF}', '\u{1E6FF}', SigmaClass::Other),
];

/// Final_Sigma 문맥에서의 글자 분류
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SigmaClass {
    /// Case_Ignorable: 건너뛴다
    Ignorable,
    /// Cased 이고 Case_Ignorable 이 아님
    Cased,
    /// 그 밖
    Other,
}

const CAPITAL_SIGMA: char = '\u{3A3}';
const SMALL_SIGMA: char = '\u{3C3}';
const FINAL_SIGMA: char = '\u{3C2}';

/// Rust 표준 라이브러리의 Final_Sigma 처리 결과를 관찰해 분류를 얻는다
/// (core 의 Cased/Case_Ignorable 표는 공개 API 가 아니다).
///   "cΣ" 가 ς 로 끝남   <=> Cased(c) && !Case_Ignorable(c)
///   "AcΣ" 가 ς 로 끝남  <=> Case_Ignorable(c) || Cased(c)
fn rust_sigma_class(c: char) -> SigmaClass {
    let mut probe = String::with_capacity(8);
    probe.push(c);
    probe.push(CAPITAL_SIGMA);
    if probe.to_lowercase().ends_with(FINAL_SIGMA) {
        return SigmaClass::Cased;
    }
    probe.clear();
    probe.push('A');
    probe.push(c);
    probe.push(CAPITAL_SIGMA);
    if probe.to_lowercase().ends_with(FINAL_SIGMA) {
        SigmaClass::Ignorable
    } else {
        SigmaClass::Other
    }
}

/// Python 3.12 기준의 Final_Sigma 분류
pub fn sigma_class(c: char) -> SigmaClass {
    match PY_SIGMA_CLASS_OVERRIDES
        .iter()
        .find(|(lo, hi, _)| *lo <= c && c <= *hi)
    {
        Some(&(_, _, class)) => class,
        None => rust_sigma_class(c),
    }
}

/// CPython `handle_capital_sigma` 와 같은 판단
fn is_final_sigma(chars: &[char], i: usize) -> bool {
    let mut j = i;
    let mut before = None;
    while j > 0 {
        j -= 1;
        let class = sigma_class(chars[j]);
        if class != SigmaClass::Ignorable {
            before = Some(class);
            break;
        }
    }
    if before != Some(SigmaClass::Cased) {
        return false;
    }
    for &c in &chars[i + 1..] {
        let class = sigma_class(c);
        if class != SigmaClass::Ignorable {
            return class != SigmaClass::Cased;
        }
    }
    true
}

/// 글자 하나의 Python `lower()` 결과 (Σ 제외)
fn push_lower_char(out: &mut String, c: char) {
    if PY_LOWER_UNCHANGED
        .iter()
        .any(|&(lo, hi)| lo <= c && c <= hi)
    {
        out.push(c);
    } else {
        out.extend(c.to_lowercase());
    }
}

/// Python 3.12 `str.lower()` 와 같은 결과
pub fn py_lower(word: &str) -> String {
    let mut out = String::with_capacity(word.len());
    if !word.contains(CAPITAL_SIGMA) {
        for c in word.chars() {
            push_lower_char(&mut out, c);
        }
        return out;
    }
    let chars: Vec<char> = word.chars().collect();
    for (i, &c) in chars.iter().enumerate() {
        if c == CAPITAL_SIGMA {
            out.push(if is_final_sigma(&chars, i) {
                FINAL_SIGMA
            } else {
                SMALL_SIGMA
            });
        } else {
            push_lower_char(&mut out, c);
        }
    }
    out
}

/// 기준 구현 tokenize
pub fn tokenize(text: &str) -> Vec<String> {
    text.split(is_py_space)
        .filter(|raw| !raw.is_empty())
        .map(|raw| py_lower(raw.trim_matches(is_punct)))
        .filter(|word| !word.is_empty())
        .collect()
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Report {
    pub total_words: usize,
    pub unique_words: usize,
    pub top: Vec<(String, u64)>,
}

/// 빈도 내림차순, 같은 빈도는 코드 포인트 오름차순(= UTF-8 바이트 순)으로 상위 top_n 개
pub fn count_words(words: &[String], top_n: usize) -> Report {
    let mut counter: HashMap<&str, u64> = HashMap::new();
    for word in words {
        *counter.entry(word.as_str()).or_insert(0) += 1;
    }
    let unique_words = counter.len();
    let mut ranked: Vec<(String, u64)> = counter
        .into_iter()
        .map(|(w, n)| (w.to_string(), n))
        .collect();
    ranked.sort_unstable_by(|a, b| b.1.cmp(&a.1).then_with(|| a.0.cmp(&b.0)));
    ranked.truncate(top_n);
    Report {
        total_words: words.len(),
        unique_words,
        top: ranked,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn toks(text: &str) -> Vec<String> {
        tokenize(text)
    }

    #[test]
    fn reference_examples() {
        assert_eq!(
            toks("\"Hello,\" Don't e-mail... RUST!"),
            ["hello", "don't", "e-mail", "rust"]
        );
        assert!(toks("!!! --- ...").is_empty());
        let words: Vec<String> = ["b", "a", "c", "b", "a", "c", "d"]
            .iter()
            .map(|s| s.to_string())
            .collect();
        let report = count_words(&words, 10);
        let top: Vec<(&str, u64)> = report.top.iter().map(|(w, n)| (w.as_str(), *n)).collect();
        assert_eq!(top, [("a", 2), ("b", 2), ("c", 2), ("d", 1)]);
    }

    #[test]
    fn r1_whitespace() {
        // 기대값: verify/probe_text.py 의 Python tokenize 결과
        assert_eq!(toks("a\u{1c}b a\u{1f}b"), ["a", "b", "a", "b"]);
        assert_eq!(toks("a\u{b}b"), ["a", "b"]);
        assert_eq!(toks("a\u{3000}b"), ["a", "b"]);
        assert_eq!(toks("a\u{85}b"), ["a", "b"]);
        assert_eq!(toks("a\u{200b}b"), ["a\u{200b}b"]);
        assert_eq!(toks("a\u{180e}b"), ["a\u{180e}b"]);
        assert_eq!(toks("a\u{feff}b"), ["a\u{feff}b"]);
        assert_eq!(
            toks("a\u{2028}b\u{2029}c\u{a0}d\u{202f}e"),
            ["a", "b", "c", "d", "e"]
        );
    }

    #[test]
    fn r2_lowercase_and_sigma() {
        // 기대값: verify/probe_text.py 의 Python 3.12.3 lower() 결과
        assert_eq!(py_lower("\u{130}"), "i\u{307}");
        assert_eq!(py_lower("ΑΣ"), "ας");
        assert_eq!(py_lower("Σ"), "σ");
        assert_eq!(py_lower("ΑΣΑ"), "ασα");
        // plan.json 은 ας'β 로 적었지만 Python 실행 결과는 ασ'β ('는 Case_Ignorable 이라 건너뜀)
        assert_eq!(py_lower("ΑΣ'Β"), "ασ'β");
        assert_eq!(py_lower("ΆΣ"), "άς");
        assert_eq!(py_lower("ΑΣ\u{301}"), "ας\u{301}");
        assert_eq!(py_lower("ΑΣΣ"), "ασς");
        assert_eq!(py_lower("'Σ"), "'σ");
        // Rust 17.0 과 Python 15.0 의 분류가 다른 글자가 문맥에 있는 경우
        assert_eq!(py_lower("\u{295}Σ"), "\u{295}ς");
        assert_eq!(py_lower("Α\u{1171e}Σ"), "α\u{1171e}ς");
        assert_eq!(py_lower("ΑΣ\u{1c89}"), "ας\u{1c89}");
        assert_eq!(py_lower("ΑΣ\u{10d50}"), "ας\u{10d50}");
        assert_eq!(py_lower("Α\u{897}Σ"), "α\u{897}σ");
        // Rust 17.0 에만 대소문자 쌍이 있는 글자는 그대로
        let new_pairs = "\u{1c89}\u{a7cb}\u{a7cc}\u{a7dc}\u{10d50}\u{16ea0}";
        assert_eq!(py_lower(new_pairs), new_pairs);
        // 문장 부호를 뗀 뒤의 단어 안에서만 문맥을 본다
        assert_eq!(toks("ΑΣ."), ["ας"]);
        assert_eq!(toks("ΑΣ.Β"), ["ασ.β"]);
        assert_eq!(toks("(ΑΣ)"), ["ας"]);
        assert_eq!(toks("ΑΣ'"), ["ας"]);
    }

    #[test]
    fn r10_bom_cr_nul() {
        assert_eq!(toks("\u{feff}hello hello"), ["\u{feff}hello", "hello"]);
        assert_eq!(toks("a\rb"), ["a", "b"]);
        assert_eq!(toks("a\0b"), ["a\0b"]);
    }

    #[test]
    fn r11_order_and_truncate() {
        let words = toks("é e z \u{fffd} \u{1f600} z");
        let report = count_words(&words, usize::MAX);
        let top: Vec<&str> = report.top.iter().map(|(w, _)| w.as_str()).collect();
        assert_eq!(top, ["z", "e", "é", "\u{fffd}", "\u{1f600}"]);
        assert_eq!(report.total_words, 6);
        assert_eq!(report.unique_words, 5);
    }

    struct Tables {
        lower: HashMap<u32, String>,
        classes: Vec<SigmaClass>,
        spaces: Vec<bool>,
    }

    fn hex(s: &str) -> u32 {
        u32::from_str_radix(s, 16).unwrap_or(u32::MAX)
    }

    fn load_tables() -> Tables {
        let lower_data = include_str!("../tests/data/py_lower_table.txt");
        let props_data = include_str!("../tests/data/py_props.txt");
        let mut lower = HashMap::new();
        let mut classes = vec![SigmaClass::Other; 0x110000];
        for line in lower_data.lines() {
            let parts: Vec<&str> = line.split(' ').collect();
            match parts.as_slice() {
                ["L", cp, seq] => {
                    let s: String = seq
                        .split(',')
                        .filter_map(|h| char::from_u32(hex(h)))
                        .collect();
                    lower.insert(hex(cp), s);
                }
                ["S", class, lo, hi] => {
                    let class = if *class == "C" {
                        SigmaClass::Cased
                    } else {
                        SigmaClass::Ignorable
                    };
                    for cp in hex(lo)..=hex(hi) {
                        classes[cp as usize] = class;
                    }
                }
                _ => {}
            }
        }
        let mut spaces = vec![false; 0x110000];
        for line in props_data.lines() {
            let parts: Vec<&str> = line.split(' ').collect();
            if let ["SPACE", lo, hi] = parts.as_slice() {
                for cp in hex(lo)..=hex(hi) {
                    spaces[cp as usize] = true;
                }
            }
        }
        Tables {
            lower,
            classes,
            spaces,
        }
    }

    #[test]
    fn rust_unicode_version_is_reported() {
        let (a, b, c) = char::UNICODE_VERSION;
        eprintln!("rust char::UNICODE_VERSION = {a}.{b}.{c}");
    }

    /// 위험 R2: 전 코드 포인트(서로게이트 제외)의 lower() 를 Python 3.12 표와 비교
    #[test]
    fn lower_table_matches_python() {
        let tables = load_tables();
        assert!(tables.lower.len() > 1000, "table not loaded");
        let mut diffs = Vec::new();
        for cp in 0..0x110000u32 {
            let Some(c) = char::from_u32(cp) else {
                continue;
            };
            if c == CAPITAL_SIGMA {
                continue;
            }
            let expected = tables
                .lower
                .get(&cp)
                .cloned()
                .unwrap_or_else(|| c.to_string());
            let mut got = String::new();
            push_lower_char(&mut got, c);
            if got != expected {
                let rust_raw: String = c.to_lowercase().collect();
                diffs.push(format!(
                    "U+{cp:04X} python={:X?} ours={:X?} rust_raw={:X?}",
                    expected.chars().map(u32::from).collect::<Vec<_>>(),
                    got.chars().map(u32::from).collect::<Vec<_>>(),
                    rust_raw.chars().map(u32::from).collect::<Vec<_>>()
                ));
            }
        }
        assert!(
            diffs.is_empty(),
            "{} lower differences:\n{}",
            diffs.len(),
            diffs.join("\n")
        );
    }

    /// 위험 R2: Final_Sigma 판단에 쓰는 글자 분류를 Python 3.12 와 비교
    #[test]
    fn sigma_class_matches_python() {
        let tables = load_tables();
        let mut diffs = Vec::new();
        for cp in 0..0x110000u32 {
            let Some(c) = char::from_u32(cp) else {
                continue;
            };
            let expected = tables.classes[cp as usize];
            let got = sigma_class(c);
            if got != expected {
                diffs.push(format!(
                    "U+{cp:04X} python={expected:?} ours={got:?} rust_raw={:?}",
                    rust_sigma_class(c)
                ));
            }
        }
        assert!(
            diffs.is_empty(),
            "{} sigma class differences:\n{}",
            diffs.len(),
            diffs.join("\n")
        );
    }

    /// 예외 목록을 만들 때 쓰는 도구: Rust 원래 동작과 Python 표의 차이를 구간으로 묶어
    /// target/unicode_diffs.txt 에 쓴다. `cargo test -- --ignored dump_unicode_diffs` 로 실행
    #[test]
    #[ignore]
    fn dump_unicode_diffs() {
        let tables = load_tables();
        let mut lower_ranges: Vec<(u32, u32)> = Vec::new();
        let mut sigma_ranges: Vec<(u32, u32, SigmaClass)> = Vec::new();
        for cp in 0..0x110000u32 {
            let Some(c) = char::from_u32(cp) else {
                continue;
            };
            if c != CAPITAL_SIGMA {
                let raw: String = c.to_lowercase().collect();
                if let Some(expected) = tables.lower.get(&cp) {
                    assert_eq!(&raw, expected, "U+{cp:04X}: python maps differently");
                } else if raw != c.to_string() {
                    match lower_ranges.last_mut() {
                        Some(last) if last.1 + 1 == cp => last.1 = cp,
                        _ => lower_ranges.push((cp, cp)),
                    }
                }
            }
            let expected = tables.classes[cp as usize];
            if rust_sigma_class(c) != expected {
                match sigma_ranges.last_mut() {
                    Some(last) if last.1 + 1 == cp && last.2 == expected => last.1 = cp,
                    _ => sigma_ranges.push((cp, cp, expected)),
                }
            }
        }
        let (a, b, c) = char::UNICODE_VERSION;
        let mut text = format!("// rust char::UNICODE_VERSION = {a}.{b}.{c}\n// lower unchanged\n");
        for (lo, hi) in &lower_ranges {
            text.push_str(&format!("    ('\\u{{{lo:X}}}', '\\u{{{hi:X}}}'),\n"));
        }
        text.push_str("// sigma overrides\n");
        for (lo, hi, class) in &sigma_ranges {
            text.push_str(&format!(
                "    ('\\u{{{lo:X}}}', '\\u{{{hi:X}}}', SigmaClass::{class:?}),\n"
            ));
        }
        let path = concat!(env!("CARGO_MANIFEST_DIR"), "/target/unicode_diffs.txt");
        std::fs::write(path, text).expect("write diffs");
    }

    /// 위험 R1: 공백 집합을 Python 3.12 와 비교
    #[test]
    fn space_table_matches_python() {
        let tables = load_tables();
        let mut diffs = Vec::new();
        for cp in 0..0x110000u32 {
            let Some(c) = char::from_u32(cp) else {
                continue;
            };
            if is_py_space(c) != tables.spaces[cp as usize] {
                diffs.push(format!("U+{cp:04X}"));
            }
        }
        assert!(diffs.is_empty(), "space differences: {}", diffs.join(" "));
    }
}
